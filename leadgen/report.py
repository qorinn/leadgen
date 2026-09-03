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

MIERT VAN MINDEN RIPORTNAK EGY `*_adat()` IKERFUGGVENYE (13. szakasz, F1):
A webes felulet API-ja adatot ad vissza, nem szoveget. Ha az API kulon
lekerdezeseket irna, ket igazsag lenne ugyanarra a szamra -- ezert minden
riport-fuggveny ketfele: a `*_adat()` dict-et ad vissza, a nyers (nem
`_adat` vegzodesu) fuggveny EZT hivja es irja ki -- a CLI kimenete emiatt
nem valtozik. A modul-szintu `_STATUSES` gyorsitotar emiatt is tunt el: egy
hosszan futo API-folyamatban beragadt volna, es ket parhuzamos keres kozott
csendben regi szamot adott volna vissza. A `company_statuses()` mostantol
mindig friss lekerdezes; ha egy hivason belul (pl. `report.run()`) ket riport
ugyanazt a szamot kell mutassa, a hivo adja at parameterkent.
"""
from __future__ import annotations

import csv
import json
import subprocess
from dataclasses import dataclass

from . import config, db, enrich, validate

# A `companies.status` eletciklus sorrendben. A riport ebben a sorrendben ir,
# nem darabszam szerint: igy latszik, hol AKAD EL a tolcser.
STATUS_ORDER = [
    "new", "enriching", "enriched", "scored", "ready", "queued", "sent",
    "replied", "done", "review", "hold", "rejected", "suppressed", "error",
]

STATUS_LABEL = {
    "new": "uj (enrichmentre var)",
    "enriching": "enrichment folyamatban",
    "enriched": "feldolgozva (minositesre var)",
    "scored": "ertekelve (most nem exportalhato)",
    "ready": "kesz (exportalhato)",
    "queued": "sorban all (leads.csv-ben)",
    "sent": "level kiment",
    "replied": "VALASZOLT -- ember kezelje",
    "done": "szekvencia lezarult",
    "review": "emberi dontesre var",
    "hold": "kampanybol ideiglenesen visszatartva",
    "rejected": "regi elutasitott allapot",
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

# Kontaktus email_type ertekek megjelenitesi sorrendje. Az `enrich`-bol jon,
# hogy a megjelenites UGYANAZT a rangsort mutassa, amit az export hasznal
# (korabban ket kulon lista volt, es szet is csusztak). Az utolso ertek a
# DB-ben NULL -- az adat oldalon 'unknown', a CLI-n (regi szoveg, ne
# valtozzon) 'ismeretlen'.
_CONTACT_TYPE_ORDER = enrich.EMAIL_TYPE_SORREND + ("unknown",)
_CONTACT_TYPE_CLI_LABEL = {
    "generic": "generic", "personal": "personal", "sales": "sales",
    "role": "role", "unknown": "ismeretlen",
}


@dataclass
class SenderState:
    """Amit a kuldorol tudunk. `ok=False` -> nem tudtuk megkerdezni."""
    ok: bool = False
    cap: int = 0
    sent_today: int = 0
    remaining: int = 0
    leads_rows: int = 0
    # 12. szakasz: a napi kezbesitesi kep is ide tartozik. A `report --daily`
    # celja, hogy EGY KEPERNYON lasd, mi tortenik ma -- ha a bounce-arany
    # miatt kulon parancsot kell futtatni, azt a napi rutinban kihagyod.
    bounces_today: int = 0
    rejects_today: int = 0
    error: str = ""


def _sender_state() -> SenderState:
    """A kuldo sajat szamai, a kuldo sajat interpreteren. Csak olvas.

    A `python3` a gepen 3.9.6 -- a kuldo ott fut. Szandekosan NEM a venv
    Pythonjaval importaljuk a kuldo moduljait: a ket interpretert nem
    keverjuk (CLAUDE.md), meg akkor sem, ha stdlib-only kod mindkettovel menne.
    """
    # A `deliverability.daily_report()`-ot hivjuk, nem szamoljuk ujra a
    # bounce-aranyt: az a fuggveny tudja azt a ket szabalyt, amit ket valodi
    # hamis riasztas tanitott meg (a bounce csak a mai cimzettekre szamit, es
    # a soft bounce nem reputacio-jelzes). Egy masodik implementacio itt
    # csendben mas szamot adna.
    code = (
        "import json, deliverability, limits, store; "
        "rep = deliverability.daily_report(); "
        "print(json.dumps({"
        "'cap': limits.daily_cap(), "
        "'sent_today': store.sent_today_count(), "
        "'remaining': limits.remaining_today(), "
        "'leads_rows': len(store.leads()), "
        "'bounces_today': rep['bounces_reputation'], "
        "'rejects_today': rep['rejects']}))"
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


def sender_thresholds() -> dict:
    """A kuldo riasztasi kuszobei (`cold-email-starter/config.py`). Csak olvas.

    Ugyanaz a mintazat, mint a `_sender_state()`: ezek a kuszobok a kuldo
    sajat .env-jebol jonnek, a sajat interpreteren -- itt nem talalunk ki
    masolatot. Hiba eseten ures dict: az `/api/meta` ettol meg valid marad,
    csak ez a ket kulcs hianyzik belole.
    """
    code = (
        "import json, config; "
        "print(json.dumps({"
        "'bounce_rate_alert': config.BOUNCE_RATE_ALERT, "
        "'reject_rate_alert': config.REJECT_RATE_ALERT}))"
    )
    try:
        proc = subprocess.run(
            ["python3", "-c", code],
            cwd=config.SENDER_DIR, capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0:
            return {}
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        return {}


def _counts(sql: str, params: tuple | None = None) -> dict[str, int]:
    return {str(r["k"]): int(r["n"]) for r in db.query(sql, params)}


def company_statuses() -> dict[str, int]:
    """A `companies.status` szamlalok, mindig friss lekerdezessel.

    NINCS tobbe modul-szintu gyorsitotar (lasd a modul docstringjet): ha egy
    hivason belul tobb riportnak ugyanazt a szamot kell latnia, a hivo egyszer
    kerdezi le, es adja tovabb parameterkent (lasd `run()`).
    """
    return _counts("select status as k, count(*) as n from companies group by 1")


def _split_statuses(statuses: dict[str, int]) -> tuple[dict[str, int], dict[str, int]]:
    """Ismert (STATUS_ORDER sorrendben) es ismeretlen allapotokra bontva."""
    remaining = dict(statuses)
    known: dict[str, int] = {}
    for status in STATUS_ORDER:
        n = remaining.pop(status, 0)
        if n:
            known[status] = n
    return known, remaining


# ─── A teljes tolcser ──────────────────────────────────────────────────────

def funnel_adat(statuses: dict[str, int] | None = None) -> dict:
    """A teljes tolcser adata (`report`). Lasd meg: `funnel()`."""
    if statuses is None:
        statuses = company_statuses()
    total = sum(statuses.values())
    by_status, unknown_status = _split_statuses(statuses)

    if not total:
        return {
            "companies_total": 0, "by_status": {}, "unknown_status": {},
            "contacts": {}, "email_validation": None, "suppression": {},
            "labels": {}, "unlinked_sources": 0, "outreach": {},
            "next_steps": [],
        }

    kapcsolat = _counts("""
        select coalesce(email_type, 'unknown') as k, count(*) as n
          from contacts group by 1
    """)

    email_validacio = None
    if config.EMAIL_VALIDATION != "off":
        email_validacio = {
            "mode": config.EMAIL_VALIDATION,
            "summary": validate.report_sor(),
        }

    suppression = _counts("select reason as k, count(*) as n from suppression group by 1")
    labels = _counts("select label as k, count(*) as n from company_labels group by 1")
    unlinked = db.query("select count(*) as n from sources where company_id is null")
    outreach = _counts("select status as k, count(*) as n from outreach group by 1")

    next_steps = [
        {"status": s, "count": statuses[s], "action": ACTIONABLE[s]}
        for s in STATUS_ORDER if s in ACTIONABLE and statuses.get(s)
    ]

    return {
        "companies_total": total,
        "by_status": by_status,
        "unknown_status": unknown_status,
        "contacts": kapcsolat,
        "email_validation": email_validacio,
        "suppression": suppression,
        "labels": labels,
        "unlinked_sources": unlinked[0]["n"] if unlinked else 0,
        "outreach": outreach,
        "next_steps": next_steps,
    }


def funnel(statuses: dict[str, int] | None = None) -> int:
    adat = funnel_adat(statuses)
    total = adat["companies_total"]

    print(f"CEGEK ({total})")
    if not total:
        print("  Meg egy ceg sincs a DB-ben. Kezdd itt:")
        print("    ./leadgen.sh ingest maps --engine agency_partner --max-results 50")
        return 0

    all_keys = list(adat["by_status"]) + list(adat["unknown_status"])
    width = max(len(STATUS_LABEL.get(s, s)) for s in all_keys) if all_keys else 20
    for status in STATUS_ORDER:
        n = adat["by_status"].get(status, 0)
        if not n:
            continue
        label = STATUS_LABEL.get(status, status)
        print(f"  {label:<{width}}  {n:>4}")
    for status, n in sorted(adat["unknown_status"].items()):
        print(f"  {status:<{width}}  {n:>4}   (ismeretlen allapot)")

    kapcsolat = adat["contacts"]
    if kapcsolat:
        print(f"\nKAPCSOLATOK ({sum(kapcsolat.values())})")
        for k in _CONTACT_TYPE_ORDER:
            if kapcsolat.get(k):
                print(f"  {_CONTACT_TYPE_CLI_LABEL[k]:<10} {kapcsolat[k]:>4}")

    # Email-validacio. Csak akkor irjuk ki, ha van mit: `off` modban zaj lenne.
    if adat["email_validation"]:
        print(f"\nEMAIL-VALIDACIO ({adat['email_validation']['mode']})")
        print(f"  {adat['email_validation']['summary']}")
        if adat["email_validation"]["mode"] == "full":
            print("  A pontos kredit-egyenleg a Reoon vezerlopultjan latszik.")

    supp = adat["suppression"]
    if supp:
        print(f"\nTILTOLISTA ({sum(supp.values())})")
        for reason, n in sorted(supp.items(), key=lambda x: -x[1]):
            print(f"  {reason:<16} {n:>4}")

    cimkek = adat["labels"]
    if cimkek:
        print(f"\nCIMKEK ({sum(cimkek.values())})")
        for label, n in sorted(cimkek.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {label:<24} {n:>4}")

    if adat["unlinked_sources"]:
        print(f"\nNYERS FORRASELEMEK")
        print(f"  ceghez meg nem kapcsolt          {adat['unlinked_sources']:>4}")

    out = adat["outreach"]
    if out:
        print(f"\nMEGKERESESEK ({sum(out.values())})")
        for status in ("queued", "sent", "replied", "done", "stopped"):
            if out.get(status):
                print(f"  {status:<10} {out[status]:>4}")

    if adat["next_steps"]:
        print("\nKOVETKEZO LEPES")
        for lepes in adat["next_steps"]:
            label = STATUS_LABEL.get(lepes["status"], lepes["status"])
            print(f"  {lepes['count']:>4} {label:<32} -> {lepes['action']}")
    return 0


# ─── A mai kep ─────────────────────────────────────────────────────────────

def riasztasok_adat() -> dict:
    """A fennallo riasztasok (`report --daily` a tetejen mutatja).

    A riasztasokat a `leadgen alert` allitja elo; itt csak OLVASSUK oket.
    """
    from . import alerts

    try:
        aktiv = alerts.aktiv_riasztasok()
        return {"ok": True, "aktiv": aktiv, "error": None}
    except Exception as exc:  # noqa: BLE001
        # Ha a riasztas-tabla meg nem letezik (migracio nem futott), az nem
        # allithatja meg a napi riportot -- de hallgatni sem szabad rola.
        return {"ok": False, "aktiv": [], "error": f"{type(exc).__name__}: {exc}"}


def _riasztas_blokk(adat: dict) -> None:
    """A fennallo riasztasok, A RIPORT TETEJEN.

    MIERT ELOL: a 12. szakasz utan a lanc magatol fut, es ez a riport az
    egyetlen kepernyo, amit a napi rutin biztosan megnyit. Ha a riasztas a
    riport aljara kerulne, pont az veszne el, amiert az egesz monitoring van.
    """
    if not adat["ok"]:
        print(f"RIASZTASOK: nem olvashatok ({adat['error'].split(':')[0]}). "
              f"Futott mar a `db migrate`?\n")
        return
    aktiv = adat["aktiv"]
    if not aktiv:
        return

    print("=" * 68)
    print(f">>> {len(aktiv)} RIASZTAS ALL FENN")
    print("=" * 68)
    for a in aktiv:
        elso = a["first_seen"]
        kor = ""
        if elso:
            import datetime as _dt
            napok = (_dt.datetime.now(_dt.timezone.utc) - elso).days
            kor = f"  ({napok} napja)" if napok else "  (ma)"
        print(f"\n  [{a['tipus']}]{kor}")
        print("  " + (a["uzenet"] or "").replace("\n", "\n  "))
    print(f"\n  Teljes naplo: {config.ALERTS_LOG}")
    print("=" * 68 + "\n")


def daily_adat(statuses: dict[str, int] | None = None) -> dict:
    """A mai kep adata (`report --daily`). Lasd meg: `daily()`."""
    if statuses is None:
        statuses = company_statuses()
    st = _sender_state()

    sorban = statuses.get("queued", 0)
    keszen = statuses.get("ready", 0)
    valaszolt = statuses.get("replied", 0)
    atnezendo = statuses.get("review", 0)

    napok_keszlet = None
    if st.ok and st.cap:
        napok_keszlet = (sorban + keszen) / st.cap

    return {
        "riasztasok": riasztasok_adat(),
        "sender": {
            "ok": st.ok, "cap": st.cap, "sent_today": st.sent_today,
            "remaining": st.remaining, "leads_rows": st.leads_rows,
            "bounces_today": st.bounces_today, "rejects_today": st.rejects_today,
            "error": st.error or None,
        },
        "queued": sorban,
        "ready": keszen,
        "replied": valaszolt,
        "review": atnezendo,
        "days_of_backlog": napok_keszlet,
    }


def daily(statuses: dict[str, int] | None = None) -> int:
    adat = daily_adat(statuses)
    _riasztas_blokk(adat["riasztasok"])

    st = adat["sender"]
    print("MA")
    if st["ok"]:
        print(f"  napi keret          {st['cap']}")
        print(f"  ma mar kikuldve     {st['sent_today']}")
        print(f"  ma meg kikuldheto   {st['remaining']}")
        print(f"  leads.csv sorai     {st['leads_rows']}")
        # A kezbesitesi jelek csak akkor jelennek meg, ha van mit mutatni:
        # egy allando "bounce: 0" sor harom nap alatt lathatatlanna valik,
        # es akkor a nem-nulla erteket sem venned eszre.
        if st["bounces_today"]:
            print(f"  bounce ma           {st['bounces_today']}  (reputacio-relevans)")
        if st["rejects_today"]:
            print(f"  SMTP-elutasitas ma  {st['rejects_today']}  "
                  f"-> cold-email-starter/data/rejects.csv")
    else:
        print(f"  A kuldo allapota NEM OLVASHATO: {st['error']}")
        print(f"  (varom itt: {config.SENDER_DIR})")

    print("\nSORBANALLAS")
    print(f"  sorban all (kiment mar a leads.csv-be)   {adat['queued']}")
    print(f"  kesz, meg nincs exportalva               {adat['ready']}")

    # A LENYEG: hany NAPRA eleg a jelenlegi sor. A keret nem a leadek szamatol
    # fugg (limits.daily_cap a kezbesitesi jelekbol emel), tehat tobb lead
    # betoltese NEM gyorsit -- csak varakozo sort epit.
    if adat["days_of_backlog"] is not None:
        napok = adat["days_of_backlog"]
        print(f"\n  a jelenlegi sor ~{napok:.1f} napra eleg (napi {st['cap']} keret mellett)")
        if napok > 5:
            print("  Adagolj: ./leadgen.sh export --limit 20")
            print("  (a follow-up MINDIG veri a friss cold-ot ugyanabban a keretben,")
            print("   tehat egy nagy export nem gyorsit, csak varakozo sort epit)")
        elif napok < 1:
            print("  Fogy a sor. Uj cegek: ./leadgen.sh ingest maps --max-results 100")

    if adat["replied"] or adat["review"]:
        print("\nRAD VAR")
        if adat["replied"]:
            print(f"  {adat['replied']:>4} ceg VALASZOLT -- szemelyes valasz kell, 24 oran belul")
        if adat["review"]:
            print(f"  {adat['review']:>4} ceg emberi dontesre var -> ./leadgen.sh review")
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

# A webui F8 fazisa ket besorolast emel ki kulon (24 oras ora / emberi
# atnezes) -- a `/api/meta`-n keresztul adjuk at oket, nem a besorolas-kulcsot
# magat drotozzuk a TypeScriptbe (WEBUI-TERV.md Invariansok #1, ezt orzi a
# `test_a_frontend_nem_drotoz_be_uzleti_listat`).
_REPLY_SURGOS = {"interested"}
_REPLY_ATTEKINTENDO = {"other"}


def replies_adat() -> dict:
    """A valaszok besorolas szerinti bontasa (`report --replies`)."""
    osszes = _counts("""
        select coalesce(classification, 'unclassified') as k, count(*) as n
          from reply_events group by 1
    """)
    if not osszes:
        return {"total": 0, "by_classification": {}, "error_count": 0,
                "interested": [], "other": []}

    hibas = db.query("select count(*) as n from reply_events where error is not null")

    def _lista(cimke: str) -> list[dict]:
        return db.query("""
            select r.email, r.subject, r.confidence, r.rationale, c.company_name
              from reply_events r
         left join contacts ct on ct.email = r.email
         left join companies c on c.id = ct.company_id
             where r.classification = %s
          order by r.received_at desc nulls last limit 20
        """, (cimke,))

    return {
        "total": sum(osszes.values()),
        "by_classification": osszes,
        "error_count": hibas[0]["n"] if hibas else 0,
        "interested": _lista("interested"),
        "other": _lista("other"),
    }


def replies() -> int:
    """A valaszok besorolas szerinti bontasa (`report --replies`)."""
    adat = replies_adat()
    if not adat["total"]:
        print("Meg nem erkezett valasz.")
        print("  A guards.py irja a replies.csv-t, a `feedback` olvassa be ide.")
        return 0

    osszes = dict(adat["by_classification"])
    print(f"VALASZOK ({adat['total']})")
    width = max(len(_REPLY_LABEL.get(k, k)) for k in osszes) + 2
    for k in _REPLY_ORDER:
        if osszes.pop(k, 0):
            print(f"  {_REPLY_LABEL.get(k, k):<{width}} {adat['by_classification'][k]:>4}")
    for k, n in sorted(osszes.items()):
        print(f"  {k:<{width}} {n:>4}")

    if adat["error_count"]:
        print(f"\n  {adat['error_count']} valasz osztalyozasa HIBARA futott.")
        print("  Ezek ujrafuttathatok: a classified_at nullazasa utan a")
        print("  `classify-replies` ujra nekimegy.")

    # A bizonytalanok es az erdeklodok KIIRVA, nem csak megszamolva: ezekre
    # ember kell, es egy szam onmagaban nem cselekvesre hivo.
    for cimke, cim, rows in (
        ("interested", ">>> ERDEKLODOK -- 24 oran belul valaszolj", adat["interested"]),
        ("other", "BIZONYTALAN -- ezeket nezd at kezzel", adat["other"]),
    ):
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


# ─── Evidence grounding ────────────────────────────────────────────────────

def grounding_adat() -> dict:
    """Az AI allitasai es a hozzajuk tartozo idezetek (`report --grounding`)."""
    rows = db.query("""
        select id, company_name, normalized_domain, webapp_fit, website_fit, mobile_fit,
               best_offer, status, personalization, evidence, grounding_dropped,
               score_model
          from companies
         where scored_at is not null
         order by scored_at desc limit 30
    """)
    if not rows:
        return {"total": 0, "ready": 0, "dropped_directions": 0, "companies": []}

    ossz = db.query("""
        select count(*) as n,
               sum(grounding_dropped) as eldobott,
               count(*) filter (where status = 'ready') as ready
          from companies where scored_at is not null
    """)[0]

    # Az uj schema az opportunity_angles tablan tarolja az egyes iranyok
    # tenyleges pontszamat, paint es idezetet. Ez a kanonikus adat; a
    # companies.evidence csak a kompatibilis, osszefoglalo masolat.
    # Egyetlen lekerdezesben olvassuk ki a 30 megjelenitett ceghez, nem
    # cegenkent nyitunk uj kapcsolatot.
    ids = [r["id"] for r in rows]
    angle_rows = db.query("""
        select company_id, rank, angle_type, score, pain, claim, quote, selected
          from opportunity_angles
         where company_id = any(%s)
         order by company_id, rank
    """, (ids,))
    angles_by_company: dict[object, list[dict]] = {}
    for angle in angle_rows:
        angles_by_company.setdefault(angle["company_id"], []).append(angle)

    companies = []
    for r in rows:
        ev = (r["evidence"] or {})
        uj_angles = angles_by_company.get(r["id"], [])
        megtartott = uj_angles or ev.get("angles") or ev.get("evidence") or []
        eldobott = ev.get("dropped") or []
        scores = {
            tipus: max((float(a.get("score") or 0) for a in uj_angles
                        if a.get("angle_type") == tipus), default=0.0)
            for tipus in ("webapp", "website", "mobile", "landing_page")
        }
        # A korabbi, egyiranyu schema meg csak a harom oszlopot tarolta.
        legacy = not uj_angles and bool(megtartott)
        if legacy:
            scores.update({
                "webapp": float(r["webapp_fit"] or 0),
                "website": float(r["website_fit"] or 0),
                "mobile": float(r["mobile_fit"] or 0),
            })
        companies.append({
            "id": r["id"],
            "company_name": r["company_name"],
            "normalized_domain": r["normalized_domain"],
            "status": r["status"],
            "best_offer": r["best_offer"],
            "scores": scores,
            "personalization": r["personalization"],
            "legacy": legacy,
            "kept": megtartott[:5],
            "dropped": eldobott[:2],
        })

    return {
        "total": ossz["n"],
        "ready": ossz["ready"],
        "dropped_directions": ossz["eldobott"] or 0,
        "companies": companies,
    }


def grounding() -> int:
    """Az AI allitasai es a hozzajuk tartozo idezetek (`report --grounding`).

    EZ AZ EMBERI ATNEZES FELULETE. A terv szerint a szemelyre szabott mondat
    a legkockazatosabb kimenet: egy magabiztosan TEVES mondat hiteltelenne
    tesz. Ezert itt egyutt latszik a mondat ES az idezet, amibol keszult.
    """
    adat = grounding_adat()
    if not adat["total"]:
        print("Meg nem futott AI-minosites.")
        print("  Inditsd: ./leadgen.sh score --dry")
        return 0

    print(f"MINOSITETT CEGEK ({adat['total']})   ready: {adat['ready']}   "
          f"eldobott irany: {adat['dropped_directions']}")

    for c in adat["companies"]:
        scores = c["scores"]
        print(f"\n  {c['company_name']}   "
              f"(status={c['status']} kiemelt={c['best_offer'] or '-'}; "
              f"webapp={scores['webapp']:.0f} "
              f"website={scores['website']:.0f} "
              f"mobile={scores['mobile']:.0f} "
              f"landing_page={scores['landing_page']:.0f})")
        if c["personalization"]:
            print(f"    ➜ A LEVELBE MENO MONDAT:")
            print(f"      \"{c['personalization']}\"")
        if c["legacy"]:
            print("    ℹ régi futás: az egyes szögek típusa és pontszáma "
                  "nem lett eltárolva")
        for e in c["kept"]:
            tipus = e.get("angle_type") or e.get("type")
            score = e.get("score")
            if not c["legacy"]:
                jel = "★" if e.get("selected") else "✓"
                print(f"    {jel} [{tipus} {float(score or 0):.0f}] "
                      f"{str(e.get('claim'))[:70]}")
                if e.get("pain"):
                    print(f"      pain: {str(e['pain'])[:100]}")
            else:
                print(f"    ✓ [régi adat] {str(e.get('claim'))[:70]}")
            print(f"      idezet: \"{str(e.get('quote'))[:70]}\"")
        for e in c["dropped"]:
            print(f"    ✗ ELDOBVA ({e.get('indok')}): \"{str(e.get('quote'))[:60]}\"")

    print("\n  Amelyik mondatot NEM kuldened ki a sajat neveddel, az bukott.")
    print("  Olyankor nem a modell a hibas, hanem a prompt (leadgen/prompts.py).")
    return 0


# ─── 8.2 halott fejleszto ──────────────────────────────────────────────────

_DEAD_DEV_LABEL = {
    "DEAD": "DEAD -- nincs, aki karbantartsa  (+35 pont)",
    "DORMANT": "DORMANT -- a fejleszto evek ota inaktiv  (+20 pont)",
    "ALIVE": "ALIVE -- elo fejleszto (versenytars, nem lead)",
}


def dead_dev_adat() -> dict:
    """A footer-kredit talalatok bontasa (`report --signal dead_dev`)."""
    osszes = _counts("""
        select coalesce(dev_state, 'none') as k, count(*) as n
          from companies where dev_checked_at is not null group by 1
    """)
    if not osszes:
        return {"checked_total": 0, "by_state": {}, "dead": []}

    rows = db.query("""
        select company_name, normalized_domain, dev_domain, dev_name,
               dev_evidence, signal_score
          from companies
         where dev_state = 'DEAD'
         order by signal_score desc nulls last
         limit 30
    """)
    return {
        "checked_total": sum(osszes.values()),
        "by_state": osszes,
        "dead": rows,
    }


def dead_dev() -> int:
    """A footer-kredit talalatok bontasa (`report --signal dead_dev`).

    A DEAD talalatokat RESZLETESEN irjuk ki, a footer szo szerinti
    szovegevel: a terv szabalya szerint ezeket EMBERNEK kell atneznie,
    mielott a fejleszto neve belekerul egy levelbe.
    """
    adat = dead_dev_adat()
    if not adat["checked_total"]:
        print("Meg nem futott a 8.2 enrichment.")
        print("  Inditsd: ./leadgen.sh enrich dead-dev")
        return 0

    osszes = dict(adat["by_state"])
    # A CLI-n a hianyzo kredit meg mindig a regi magyar cimkevel jelenik meg
    # -- ez a kimenet nem valtozhat.
    if "none" in osszes:
        osszes["(nincs kredit a footerben)"] = osszes.pop("none")

    print(f"HALOTT FEJLESZTO ({adat['checked_total']} megvizsgalt ceg)")
    width = max(len(_DEAD_DEV_LABEL.get(k, k)) for k in osszes) + 2
    for k in ("DEAD", "DORMANT", "ALIVE"):
        if osszes.get(k):
            print(f"  {_DEAD_DEV_LABEL[k]:<{width}} {osszes[k]:>4}")
    for k, n in sorted(osszes.items()):
        if k not in _DEAD_DEV_LABEL:
            print(f"  {k:<{width}} {n:>4}")

    rows = adat["dead"]
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


# ─── 7.1 penzugyi ertek + 8.3 webshop ──────────────────────────────────────

def economic_adat() -> dict:
    """A penzugyi kep (`report --economic`).

    A LOW ERTEK NEM KIZARAS. A 2026-08-25-i megorzo leadmodell szerint a
    penzugyi ertek RANGSOROL, nem szur: a LOW ceg is exportalhato, csak
    hatrebb all a sorban. Ezert ez nem "kiesettek" listat ad, hanem azt,
    hogy hany cegrol tudunk egyaltalan valamit.
    """
    ertekek = _counts("""
        select coalesce(economic_value, 'none') as k, count(*) as n
          from companies group by 1
    """)
    megvizsgalt = db.query("""
        select count(*) filter (where financials_checked_at is not null) as nezve,
               count(*) filter (where revenue is not null) as van_szam,
               count(*) as ossz
          from companies
    """)[0]

    if not megvizsgalt["van_szam"]:
        return {
            "total": megvizsgalt["ossz"], "by_value": ertekek,
            "checked": megvizsgalt["nezve"], "with_revenue": 0,
            "thresholds": {
                "revenue_medium_huf": config.REVENUE_MEDIUM_HUF,
                "revenue_high_huf": config.REVENUE_HIGH_HUF,
                "headcount_medium": config.HEADCOUNT_MEDIUM,
                "headcount_high": config.HEADCOUNT_HIGH,
            },
            "rows": [], "missing_labels": {},
        }

    rows = db.query("""
        select id, company_name, normalized_domain, revenue, headcount,
               financial_year, economic_value, webshop_platform, signal_score
          from companies
         where revenue is not null
         order by revenue desc nulls last limit 25
    """)
    hianyzo = _counts("""
        select label as k, count(*) as n from company_labels
         where label in ('financials_missing', 'low_economic_value',
                         'webshop_platform', 'webshop_growth')
         group by 1
    """)

    return {
        "total": megvizsgalt["ossz"], "by_value": ertekek,
        "checked": megvizsgalt["nezve"], "with_revenue": megvizsgalt["van_szam"],
        "thresholds": {
            "revenue_medium_huf": config.REVENUE_MEDIUM_HUF,
            "revenue_high_huf": config.REVENUE_HIGH_HUF,
            "headcount_medium": config.HEADCOUNT_MEDIUM,
            "headcount_high": config.HEADCOUNT_HIGH,
        },
        "rows": rows, "missing_labels": hianyzo,
    }


def economic() -> int:
    adat = economic_adat()
    ertekek = dict(adat["by_value"])
    if "none" in ertekek:
        ertekek["(nincs adat)"] = ertekek.pop("none")

    print(f"PENZUGYI ERTEK ({adat['total']} ceg)")
    for k in ("HIGH", "MEDIUM", "LOW", "(nincs adat)"):
        if ertekek.get(k):
            print(f"  {k:<14} {ertekek[k]:>4}")
    print(f"\n  megvizsgalva : {adat['checked']:>4}")
    print(f"  van arbevetel: {adat['with_revenue']:>4}")
    th = adat["thresholds"]
    print(f"\n  kuszobok (.env): MEDIUM >= {th['revenue_medium_huf'] / 1e6:.0f} M Ft "
          f"vagy {th['headcount_medium']} fo   |   "
          f"HIGH >= {th['revenue_high_huf'] / 1e6:.0f} M Ft vagy "
          f"{th['headcount_high']} fo")

    if not adat["with_revenue"]:
        print("\n  Meg egy cegrol sincs penzugyi adat.")
        print("  Kezdd itt: ./leadgen.sh enrich financials")
        return 0

    print(f"\n{'ceg':<38} {'arbevetel':>12} {'fo':>4}  {'ev':>4} {'ertek':<7} platform")
    print("-" * 88)
    for r in adat["rows"]:
        arb = f"{float(r['revenue']) / 1e6:,.0f} M Ft" if r["revenue"] else "-"
        print(f"{(r['company_name'] or '')[:36]:<38} {arb:>12} "
              f"{r['headcount'] or '-':>4}  {r['financial_year'] or '-':>4} "
              f"{r['economic_value'] or '-':<7} {r['webshop_platform'] or ''}")

    if adat["missing_labels"]:
        print()
        for k, n in sorted(adat["missing_labels"].items()):
            print(f"  {k:<22} {n:>4}")
    return 0


def campaign_adat(nev: str) -> dict:
    """Egy kampany cegei (`report --campaign <nev>`)."""
    from .contract import APPROVED_CAMPAIGNS

    rows = db.query("""
        select id, company_name, normalized_domain, status, economic_value,
               revenue, webshop_platform, signal_score, personalization
          from companies where campaign = %s
         order by signal_score desc nulls last, company_name
    """, (nev,))

    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    return {
        "name": nev,
        "approved": nev in APPROVED_CAMPAIGNS,
        "total": len(rows),
        "by_status": by_status,
        "rows": rows[:40],
    }


def campaign(nev: str) -> int:
    """Egy kampany cegei (`report --campaign webshop_growth`).

    A JOVAHAGYASI ALLAPOT AZ ELSO SOR, mert az donti el, hogy ezek a leadek
    egyaltalan kimehetnek-e. Egy vazlat sablonu kampany barmennyi `ready`
    ceget gyujthet, exportalni akkor sem fog (contract.APPROVED_CAMPAIGNS).
    """
    adat = campaign_adat(nev)

    print(f"KAMPANY: {adat['name']}   ({adat['total']} ceg)")
    print(f"  sablon: {'JOVAHAGYVA -- exportalhato' if adat['approved'] else 'VAZLAT -- NEM exportalhato'}")
    if not adat["approved"]:
        print("  A szoveget at kell irni (cold-email-starter/templates.py), majd")
        print("  felvenni a leadgen/contract.py APPROVED_CAMPAIGNS listajaba.")
    if not adat["rows"] and not adat["total"]:
        print("\n  Meg egy ceg sincs ebben a kampanyban.")
        return 0

    print("\n  " + "   ".join(f"{k}: {n}" for k, n in sorted(adat["by_status"].items())))

    print(f"\n{'ceg':<36} {'allapot':<10} {'ertek':<7} {'platform':<12} pont")
    print("-" * 82)
    for r in adat["rows"]:
        print(f"{(r['company_name'] or '')[:34]:<36} {r['status']:<10} "
              f"{r['economic_value'] or '-':<7} {r['webshop_platform'] or '-':<12} "
              f"{r['signal_score']:>5.1f}")
    return 0


# ─── Kuldo nyers CSV-k (webui F9, "Nyers naplok") ──────────────────────────

# A kuldo (cold-email-starter/) ezeket a CSV-ket irja a sajat interpreteren.
# EZ NEM sérti a "kuldo moduljait csak subprocess-en at hivd" szabalyt: nem
# a kuldo Python-kodjat futtatjuk, csak sima fajlt olvasunk -- ugyanigy
# olvassa oket kozvetlenul a `feedback.py` is (`_FILES`).
SENDER_CSV_NEVEK = ("sent", "do-not-contact", "bounces", "rejects", "replies")


def sender_csv_adat(nev: str, limit: int = 200) -> dict:
    """Egy kuldo-oldali nyers CSV utolso sorai (webui F9).

    Csak olvas, nem ertelmez -- az ertelmezett adat mar a DB-ben van
    (feedback.py importalja be). Ez a nyers ellenorzeshez kell.
    """
    if nev not in SENDER_CSV_NEVEK:
        raise ValueError(f"ismeretlen kuldo-csv: {nev!r}")
    path = config.SENDER_DATA / f"{nev}.csv"
    if not path.exists():
        return {"name": nev, "exists": False, "columns": [], "total": 0, "rows": []}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        rows = list(reader)
    return {
        "name": nev,
        "exists": True,
        "columns": list(columns),
        "total": len(rows),
        "rows": rows[-limit:],
    }


def run(daily_view: bool = False) -> int:
    if daily_view:
        return daily()
    statuses = company_statuses()
    rc = funnel(statuses)
    print()
    daily(statuses)
    return rc
