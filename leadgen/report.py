#!/usr/bin/env python3
"""Attekinto riport: hol tart a tolcser, es mi tortenik ma.

KET NEZET, MERT KET KERDES VAN:

  report          -- "hol tart a rendszer?"  A teljes tolcser: cegek allapot
                     szerint, kapcsolatok, suppression, outreach. Ez a DB kepe.

  report --daily  -- "mi tortenik MA?"  A DB sorbanallo leadjei ES a kuldo
                     napi kerete egy kepen. Ezt az INTEGRATION-PLAN.md
                     "A 5. szakaszban" kockazata kerte: a follow-up mindig veri
                     a friss cold-ot ugyanabban a keretben, tehat egy nagy
                     export nem gyorsit, csak varakozo sort epit. Ha ez a
                     szam latszik, adagolni lehet (`export --limit N`).

MIERT SUBPROCESS A KULDO ALLAPOTA (`_sender_state`):
A napi keret a kuldo tulajdona: a `data/ramp_state.json`-bol es a
`SMTP_ACCOUNTS` fiokszambol all ossze, es a `limits.daily_cap()` szamolja.
Ha ezt itt ujraimplementalnank, ket igazsag lenne ra -- pont az a hiba, amit
az INTEGRATION-PLAN A) pontja kizar ("koncernenkent egy birtokos"). Ezert
inkabb MEGKERDEZZUK a kuldot a sajat interpreteren, es csak olvasunk. Ha a
kerdes nem megy at (nincs python3, mas a SENDER_DIR), a riport kiirja, hogy
nem tudja -- nem talal ki szamot.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from . import config, db, validate

# A `companies.status` eletciklus sorrendben. A riport ebben a sorrendben ir,
# nem darabszam szerint: igy latszik, hol AKAD EL a tolcser.
STATUS_ORDER = [
    "new", "enriched", "ready", "queued", "sent", "replied", "done",
    "review", "rejected", "suppressed", "error",
]

STATUS_LABEL = {
    "new": "uj (enrichmentre var)",
    "enriched": "feldolgozva (minositesre var)",
    "ready": "kesz (exportalhato)",
    "queued": "sorban all (leads.csv-ben)",
    "sent": "level kiment",
    "replied": "VALASZOLT -- ember kezelje",
    "done": "szekvencia lezarult",
    "review": "emberi dontesre var",
    "rejected": "elutasitva",
    "suppressed": "tiltolistan",
    "error": "hiba (pl. elerhetetlen weboldal)",
}

# Ezekre a felhasznalonak lepnie kell. A riport a vegen kiemeli oket.
ACTIONABLE = {
    "replied": "valaszolj nekik szemelyesen (24 oran belul)",
    "review": "./leadgen.sh review",
    "new": "./leadgen.sh enrich",
    "enriched": "./leadgen.sh qualify",
    "ready": "./leadgen.sh export",
}


@dataclass
class SenderState:
    """Amit a kuldorol tudunk. `ok=False` -> nem tudtuk megkerdezni."""
    ok: bool = False
    cap: int = 0
    sent_today: int = 0
    remaining: int = 0
    leads_rows: int = 0
    error: str = ""


def _sender_state() -> SenderState:
    """A kuldo sajat szamai, a kuldo sajat interpreteren. Csak olvas.

    A `python3` a gepen 3.9.6 -- a kuldo ott fut. Szandekosan NEM a venv
    Pythonjaval importaljuk a kuldo moduljait: a ket interpretert nem
    keverjuk (CLAUDE.md), meg akkor sem, ha stdlib-only kod mindkettovel menne.
    """
    code = (
        "import json, limits, store; "
        "print(json.dumps({"
        "'cap': limits.daily_cap(), "
        "'sent_today': store.sent_today_count(), "
        "'remaining': limits.remaining_today(), "
        "'leads_rows': len(store.leads())}))"
    )
    try:
        proc = subprocess.run(
            ["python3", "-c", code],
            cwd=config.SENDER_DIR, capture_output=True, text=True, timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        return SenderState(error=f"{type(exc).__name__}: {exc}")
    if proc.returncode != 0:
        return SenderState(error=(proc.stderr or "").strip().splitlines()[-1:][0]
                           if proc.stderr.strip() else f"exit {proc.returncode}")
    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as exc:  # noqa: BLE001
        return SenderState(error=f"olvashatatlan valasz: {exc}")
    return SenderState(ok=True, **data)


def _counts(sql: str, params: tuple | None = None) -> dict[str, int]:
    return {str(r["k"]): int(r["n"]) for r in db.query(sql, params)}


_STATUSES: dict[str, int] = {}


def company_statuses(refresh: bool = False) -> dict[str, int]:
    """A `companies.status` szamlalok. Egy futason belul EGYSZER kerdezzuk le:
    a `report` ket nezete ugyanazt a szamot mutassa, ne kettot."""
    if refresh or not _STATUSES:
        _STATUSES.clear()
        _STATUSES.update(
            _counts("select status as k, count(*) as n from companies group by 1"))
    return _STATUSES


# ─── A teljes tolcser ──────────────────────────────────────────────────────

def funnel() -> int:
    statuses = dict(company_statuses())
    total = sum(statuses.values())

    print(f"CEGEK ({total})")
    if not total:
        print("  Meg egy ceg sincs a DB-ben. Kezdd itt:")
        print("    ./leadgen.sh ingest maps --engine agency_partner --max-results 50")
        return 0

    width = max(len(STATUS_LABEL.get(s, s)) for s in statuses) if statuses else 20
    for status in STATUS_ORDER:
        n = statuses.pop(status, 0)
        if not n:
            continue
        label = STATUS_LABEL.get(status, status)
        print(f"  {label:<{width}}  {n:>4}")
    for status, n in sorted(statuses.items()):          # ismeretlen allapot
        print(f"  {status:<{width}}  {n:>4}   (ismeretlen allapot)")

    kapcsolat = _counts("""
        select coalesce(email_type, 'ismeretlen') as k, count(*) as n
          from contacts group by 1
    """)
    if kapcsolat:
        print(f"\nKAPCSOLATOK ({sum(kapcsolat.values())})")
        for k in ("personal", "generic", "role", "ismeretlen"):
            if kapcsolat.get(k):
                print(f"  {k:<10} {kapcsolat[k]:>4}")

    # Email-validacio. Csak akkor irjuk ki, ha van mit: `off` modban zaj lenne.
    if config.EMAIL_VALIDATION != "off":
        print(f"\nEMAIL-VALIDACIO ({config.EMAIL_VALIDATION})")
        print(f"  {validate.report_sor()}")
        if config.EMAIL_VALIDATION == "full":
            print("  A pontos kredit-egyenleg a Reoon vezerlopultjan latszik.")

    supp = _counts("select reason as k, count(*) as n from suppression group by 1")
    if supp:
        print(f"\nTILTOLISTA ({sum(supp.values())})")
        for reason, n in sorted(supp.items(), key=lambda x: -x[1]):
            print(f"  {reason:<16} {n:>4}")

    out = _counts("select status as k, count(*) as n from outreach group by 1")
    if out:
        print(f"\nMEGKERESESEK ({sum(out.values())})")
        for status in ("queued", "sent", "replied", "done", "stopped"):
            if out.get(status):
                print(f"  {status:<10} {out[status]:>4}")

    # ─── Mi a kovetkezo lepes ──────────────────────────────────────────────
    allapot = company_statuses()
    lepesek = [(s, ACTIONABLE[s]) for s in STATUS_ORDER
               if s in ACTIONABLE and allapot.get(s)]
    if lepesek:
        print("\nKOVETKEZO LEPES")
        for status, teendo in lepesek:
            print(f"  {allapot[status]:>4} {STATUS_LABEL.get(status, status):<32} -> {teendo}")
    return 0


# ─── A mai kep ─────────────────────────────────────────────────────────────

def daily() -> int:
    st = _sender_state()
    allapot = company_statuses()

    sorban = allapot.get("queued", 0)
    kuldheto = allapot.get("ready", 0)
    valaszolt = allapot.get("replied", 0)
    atnezendo = allapot.get("review", 0)

    print("MA")
    if st.ok:
        print(f"  napi keret          {st.cap}")
        print(f"  ma mar kikuldve     {st.sent_today}")
        print(f"  ma meg kikuldheto   {st.remaining}")
        print(f"  leads.csv sorai     {st.leads_rows}")
    else:
        print(f"  A kuldo allapota NEM OLVASHATO: {st.error}")
        print(f"  (varom itt: {config.SENDER_DIR})")

    print("\nSORBANALLAS")
    print(f"  sorban all (kiment mar a leads.csv-be)   {sorban}")
    print(f"  kesz, meg nincs exportalva               {kuldheto}")

    # A LENYEG: hany NAPRA eleg a jelenlegi sor. A keret nem a leadek szamatol
    # fugg (limits.daily_cap a kezbesitesi jelekbol emel), tehat tobb lead
    # betoltese NEM gyorsit -- csak varakozo sort epit.
    if st.ok and st.cap:
        napok = (sorban + kuldheto) / st.cap
        print(f"\n  a jelenlegi sor ~{napok:.1f} napra eleg (napi {st.cap} keret mellett)")
        if napok > 5:
            print("  Adagolj: ./leadgen.sh export --limit 20")
            print("  (a follow-up MINDIG veri a friss cold-ot ugyanabban a keretben,")
            print("   tehat egy nagy export nem gyorsit, csak varakozo sort epit)")
        elif napok < 1:
            print("  Fogy a sor. Uj cegek: ./leadgen.sh ingest maps --max-results 100")

    if valaszolt or atnezendo:
        print("\nRAD VAR")
        if valaszolt:
            print(f"  {valaszolt:>4} ceg VALASZOLT -- szemelyes valasz kell, 24 oran belul")
        if atnezendo:
            print(f"  {atnezendo:>4} ceg emberi dontesre var -> ./leadgen.sh review")
    return 0


# ─── Valaszok ──────────────────────────────────────────────────────────────

# A besorolasok sorrendje UZLETI fontossag szerint, nem abc-ben: az elso sor
# az, amire ma lepned kell.
_REPLY_ORDER = ("interested", "other", "not_now", "auto_reply",
                "negative", "unsubscribe")

_REPLY_LABEL = {
    "interested": "ERDEKLODIK -- valaszolj neki",
    "other": "bizonytalan -- nezd at",
    "not_now": "most nem aktualis (90 nap cooldown)",
    "auto_reply": "automatikus valasz (14 nap cooldown)",
    "negative": "elutasitas -> tiltolistan",
    "unsubscribe": "leiratkozas -> tiltolistan (domain szinten)",
}


def replies() -> int:
    """A valaszok besorolas szerinti bontasa (`report --replies`)."""
    osszes = _counts("""
        select coalesce(classification, '(meg nincs osztalyozva)') as k,
               count(*) as n
          from reply_events group by 1
    """)
    if not osszes:
        print("Meg nem erkezett valasz.")
        print("  A guards.py irja a replies.csv-t, a `feedback` olvassa be ide.")
        return 0

    print(f"VALASZOK ({sum(osszes.values())})")
    width = max(len(_REPLY_LABEL.get(k, k)) for k in osszes) + 2
    for k in _REPLY_ORDER:
        if osszes.pop(k, 0):
            n = _counts("select classification as k, count(*) as n from reply_events "
                        "where classification = %s group by 1", (k,)).get(k, 0)
            print(f"  {_REPLY_LABEL.get(k, k):<{width}} {n:>4}")
    for k, n in sorted(osszes.items()):
        print(f"  {k:<{width}} {n:>4}")

    hibas = db.query("select count(*) as n from reply_events where error is not null")
    if hibas and hibas[0]["n"]:
        print(f"\n  {hibas[0]['n']} valasz osztalyozasa HIBARA futott.")
        print("  Ezek ujrafuttathatok: a classified_at nullazasa utan a")
        print("  `classify-replies` ujra nekimegy.")

    # A bizonytalanok es az erdeklodok KIIRVA, nem csak megszamolva: ezekre
    # ember kell, es egy szam onmagaban nem cselekvesre hivo.
    for cimke, cim in (("interested", ">>> ERDEKLODOK -- 24 oran belul valaszolj"),
                       ("other", "BIZONYTALAN -- ezeket nezd at kezzel")):
        rows = db.query("""
            select r.email, r.subject, r.confidence, r.rationale, c.company_name
              from reply_events r
         left join contacts ct on ct.email = r.email
         left join companies c on c.id = ct.company_id
             where r.classification = %s
          order by r.received_at desc nulls last limit 20
        """, (cimke,))
        if not rows:
            continue
        print(f"\n{cim}")
        for r in rows:
            print(f"  {(r['company_name'] or '?')}  <{r['email']}>")
            if r.get("subject"):
                print(f"    targy: {r['subject'][:70]}")
            if r.get("rationale"):
                print(f"    {r['rationale'][:100]}")
    return 0


# ─── 8.2 halott fejleszto ──────────────────────────────────────────────────

def dead_dev() -> int:
    """A footer-kredit talalatok bontasa (`report --signal dead_dev`).

    A DEAD talalatokat RESZLETESEN irjuk ki, a footer szo szerinti
    szovegevel: a terv szabalya szerint ezeket EMBERNEK kell atneznie,
    mielott a fejleszto neve belekerul egy levelbe.
    """
    osszes = _counts("""
        select coalesce(dev_state, '(nincs kredit a footerben)') as k, count(*) as n
          from companies where dev_checked_at is not null group by 1
    """)
    if not osszes:
        print("Meg nem futott a 8.2 enrichment.")
        print("  Inditsd: ./leadgen.sh enrich dead-dev")
        return 0

    cimke = {
        "DEAD": "DEAD -- nincs, aki karbantartsa  (+35 pont)",
        "DORMANT": "DORMANT -- a fejleszto evek ota inaktiv  (+20 pont)",
        "ALIVE": "ALIVE -- elo fejleszto (versenytars, nem lead)",
    }
    print(f"HALOTT FEJLESZTO ({sum(osszes.values())} megvizsgalt ceg)")
    width = max(len(cimke.get(k, k)) for k in osszes) + 2
    for k in ("DEAD", "DORMANT", "ALIVE"):
        if osszes.get(k):
            print(f"  {cimke[k]:<{width}} {osszes[k]:>4}")
    for k, n in sorted(osszes.items()):
        if k not in cimke:
            print(f"  {k:<{width}} {n:>4}")

    rows = db.query("""
        select company_name, normalized_domain, dev_domain, dev_name,
               dev_evidence, signal_score
          from companies
         where dev_state = 'DEAD'
         order by signal_score desc nulls last
         limit 30
    """)
    if rows:
        print(f"\n{'=' * 68}")
        print(">>> EZEKET NEZD AT KEZZEL, mielott levelet kapnanak")
        print("    A fejleszto NEVE szo szerint bekerul a levelbe -- ha teved,")
        print("    az nem apro pontatlansag, hanem kinos.")
        print(f"{'=' * 68}")
        for r in rows:
            print(f"\n  {r['company_name']}")
            print(f"    ceg      : https://{r['normalized_domain']}   ({r['signal_score']} pont)")
            print(f"    fejleszto: {r['dev_name']} -> https://{r['dev_domain']}")
            print(f"    a footerben: \"{(r['dev_evidence'] or '')[:90]}\"")
        print("\n  Ha egy talalat teves: ./leadgen.sh review --reject <ceg-domain>")
    return 0


def run(daily_view: bool = False) -> int:
    if daily_view:
        return daily()
    rc = funnel()
    print()
    daily()
    return rc
