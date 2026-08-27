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

    cimkek = _counts("select label as k, count(*) as n from company_labels group by 1")
    if cimkek:
        print(f"\nCIMKEK ({sum(cimkek.values())})")
        for label, n in sorted(cimkek.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {label:<24} {n:>4}")

    paratlan = db.query("select count(*) as n from sources where company_id is null")
    if paratlan and paratlan[0]["n"]:
        print(f"\nNYERS FORRASELEMEK")
        print(f"  ceghez meg nem kapcsolt          {paratlan[0]['n']:>4}")

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

def _riasztas_blokk() -> None:
    """A fennallo riasztasok, A RIPORT TETEJEN.

    MIERT ELOL: a 12. szakasz utan a lanc magatol fut, es ez a riport az
    egyetlen kepernyo, amit a napi rutin biztosan megnyit. Ha a riasztas a
    riport aljara kerulne, pont az veszne el, amiert az egesz monitoring van.
    A riasztasokat a `leadgen alert` allitja elo; itt csak OLVASSUK oket.
    """
    from . import alerts

    try:
        aktiv = alerts.aktiv_riasztasok()
    except Exception as exc:  # noqa: BLE001
        # Ha a riasztas-tabla meg nem letezik (migracio nem futott), az nem
        # allithatja meg a napi riportot -- de hallgatni sem szabad rola.
        print(f"RIASZTASOK: nem olvashatok ({type(exc).__name__}). "
              f"Futott mar a `db migrate`?\n")
        return
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


def daily() -> int:
    _riasztas_blokk()

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
        # A kezbesitesi jelek csak akkor jelennek meg, ha van mit mutatni:
        # egy allando "bounce: 0" sor harom nap alatt lathatatlanna valik,
        # es akkor a nem-nulla erteket sem venned eszre.
        if st.bounces_today:
            print(f"  bounce ma           {st.bounces_today}  (reputacio-relevans)")
        if st.rejects_today:
            print(f"  SMTP-elutasitas ma  {st.rejects_today}  "
                  f"-> cold-email-starter/data/rejects.csv")
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


# ─── Evidence grounding ────────────────────────────────────────────────────

def grounding() -> int:
    """Az AI allitasai es a hozzajuk tartozo idezetek (`report --grounding`).

    EZ AZ EMBERI ATNEZES FELULETE. A terv szerint a szemelyre szabott mondat
    a legkockazatosabb kimenet: egy magabiztosan TEVES mondat hiteltelenne
    tesz. Ezert itt egyutt latszik a mondat ES az idezet, amibol keszult.
    """
    rows = db.query("""
        select id, company_name, normalized_domain, webapp_fit, website_fit, mobile_fit,
               best_offer, status, personalization, evidence, grounding_dropped,
               score_model
          from companies
         where scored_at is not null
         order by scored_at desc limit 30
    """)
    if not rows:
        print("Meg nem futott AI-minosites.")
        print("  Inditsd: ./leadgen.sh score --dry")
        return 0

    ossz = db.query("""
        select count(*) as n,
               sum(grounding_dropped) as eldobott,
               count(*) filter (where status = 'ready') as ready
          from companies where scored_at is not null
    """)[0]
    print(f"MINOSITETT CEGEK ({ossz['n']})   ready: {ossz['ready']}   "
          f"eldobott irany: {ossz['eldobott'] or 0}")

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
        # Itt nem talalunk ki negyedik pontszamot: a kiiras jelezze, hogy a
        # reszletes angle-adat nem letezik ehhez a regi futashoz.
        legacy = not uj_angles and bool(megtartott)
        if legacy:
            scores.update({
                "webapp": float(r["webapp_fit"] or 0),
                "website": float(r["website_fit"] or 0),
                "mobile": float(r["mobile_fit"] or 0),
            })
        print(f"\n  {r['company_name']}   "
              f"(status={r['status']} kiemelt={r['best_offer'] or '-'}; "
              f"webapp={scores['webapp']:.0f} "
              f"website={scores['website']:.0f} "
              f"mobile={scores['mobile']:.0f} "
              f"landing_page={scores['landing_page']:.0f})")
        if r["personalization"]:
            print(f"    ➜ A LEVELBE MENO MONDAT:")
            print(f"      \"{r['personalization']}\"")
        if legacy:
            print("    ℹ régi futás: az egyes szögek típusa és pontszáma "
                  "nem lett eltárolva")
        for e in megtartott[:5]:
            tipus = e.get("angle_type") or e.get("type")
            score = e.get("score")
            if uj_angles:
                jel = "★" if e.get("selected") else "✓"
                print(f"    {jel} [{tipus} {float(score or 0):.0f}] "
                      f"{str(e.get('claim'))[:70]}")
                if e.get("pain"):
                    print(f"      pain: {str(e['pain'])[:100]}")
            else:
                print(f"    ✓ [régi adat] {str(e.get('claim'))[:70]}")
            print(f"      idezet: \"{str(e.get('quote'))[:70]}\"")
        for e in eldobott[:2]:
            print(f"    ✗ ELDOBVA ({e.get('indok')}): \"{str(e.get('quote'))[:60]}\"")

    print("\n  Amelyik mondatot NEM kuldened ki a sajat neveddel, az bukott.")
    print("  Olyankor nem a modell a hibas, hanem a prompt (leadgen/prompts.py).")
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


# ─── 7.1 penzugyi ertek + 8.3 webshop ──────────────────────────────────────

def economic() -> int:
    """A penzugyi kep (`report --economic`).

    A LOW ERTEK NEM KIZARAS. A 2026-08-25-i megorzo leadmodell szerint a
    penzugyi ertek RANGSOROL, nem szur: a LOW ceg is exportalhato, csak
    hatrebb all a sorban. Ezert ez a riport nem "kiesettek" listat mutat,
    hanem azt, hogy hany cegrol tudunk egyaltalan valamit.
    """
    ertekek = _counts("""
        select coalesce(economic_value, '(nincs adat)') as k, count(*) as n
          from companies group by 1
    """)
    megvizsgalt = db.query("""
        select count(*) filter (where financials_checked_at is not null) as nezve,
               count(*) filter (where revenue is not null) as van_szam,
               count(*) as ossz
          from companies
    """)[0]

    print(f"PENZUGYI ERTEK ({megvizsgalt['ossz']} ceg)")
    for k in ("HIGH", "MEDIUM", "LOW", "(nincs adat)"):
        if ertekek.get(k):
            print(f"  {k:<14} {ertekek[k]:>4}")
    print(f"\n  megvizsgalva : {megvizsgalt['nezve']:>4}")
    print(f"  van arbevetel: {megvizsgalt['van_szam']:>4}")
    print(f"\n  kuszobok (.env): MEDIUM >= {config.REVENUE_MEDIUM_HUF / 1e6:.0f} M Ft "
          f"vagy {config.HEADCOUNT_MEDIUM} fo   |   "
          f"HIGH >= {config.REVENUE_HIGH_HUF / 1e6:.0f} M Ft vagy "
          f"{config.HEADCOUNT_HIGH} fo")

    if not megvizsgalt["van_szam"]:
        print("\n  Meg egy cegrol sincs penzugyi adat.")
        print("  Kezdd itt: ./leadgen.sh enrich financials")
        return 0

    rows = db.query("""
        select company_name, normalized_domain, revenue, headcount,
               financial_year, economic_value, webshop_platform, signal_score
          from companies
         where revenue is not null
         order by revenue desc nulls last limit 25
    """)
    print(f"\n{'ceg':<38} {'arbevetel':>12} {'fo':>4}  {'ev':>4} {'ertek':<7} platform")
    print("-" * 88)
    for r in rows:
        arb = f"{float(r['revenue']) / 1e6:,.0f} M Ft" if r["revenue"] else "-"
        print(f"{(r['company_name'] or '')[:36]:<38} {arb:>12} "
              f"{r['headcount'] or '-':>4}  {r['financial_year'] or '-':>4} "
              f"{r['economic_value'] or '-':<7} {r['webshop_platform'] or ''}")

    hianyzo = _counts("""
        select label as k, count(*) as n from company_labels
         where label in ('financials_missing', 'low_economic_value',
                         'webshop_platform', 'webshop_growth')
         group by 1
    """)
    if hianyzo:
        print()
        for k, n in sorted(hianyzo.items()):
            print(f"  {k:<22} {n:>4}")
    return 0


def campaign(nev: str) -> int:
    """Egy kampany cegei (`report --campaign webshop_growth`).

    A JOVAHAGYASI ALLAPOT AZ ELSO SOR, mert az donti el, hogy ezek a leadek
    egyaltalan kimehetnek-e. Egy vazlat sablonu kampany barmennyi `ready`
    ceget gyujthet, exportalni akkor sem fog (contract.APPROVED_CAMPAIGNS).
    """
    from .contract import APPROVED_CAMPAIGNS

    rows = db.query("""
        select company_name, normalized_domain, status, economic_value,
               revenue, webshop_platform, signal_score, personalization
          from companies where campaign = %s
         order by signal_score desc nulls last, company_name
    """, (nev,))

    jovahagyva = nev in APPROVED_CAMPAIGNS
    print(f"KAMPANY: {nev}   ({len(rows)} ceg)")
    print(f"  sablon: {'JOVAHAGYVA -- exportalhato' if jovahagyva else 'VAZLAT -- NEM exportalhato'}")
    if not jovahagyva:
        print("  A szoveget at kell irni (cold-email-starter/templates.py), majd")
        print("  felvenni a leadgen/contract.py APPROVED_CAMPAIGNS listajaba.")
    if not rows:
        print("\n  Meg egy ceg sincs ebben a kampanyban.")
        return 0

    allapot: dict[str, int] = {}
    for r in rows:
        allapot[r["status"]] = allapot.get(r["status"], 0) + 1
    print("\n  " + "   ".join(f"{k}: {n}" for k, n in sorted(allapot.items())))

    print(f"\n{'ceg':<36} {'allapot':<10} {'ertek':<7} {'platform':<12} pont")
    print("-" * 82)
    for r in rows[:40]:
        print(f"{(r['company_name'] or '')[:34]:<36} {r['status']:<10} "
              f"{r['economic_value'] or '-':<7} {r['webshop_platform'] or '-':<12} "
              f"{r['signal_score']:>5.1f}")
    return 0


def run(daily_view: bool = False) -> int:
    if daily_view:
        return daily()
    rc = funnel()
    print()
    daily()
    return rc
