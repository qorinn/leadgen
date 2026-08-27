#!/usr/bin/env python3
"""Riasztasok (12. szakasz): eszreveszi, ha baj van, es szol EGYSZER.

MIERT LETEZIK EZ A MODUL: a 12. szakaszig minden futast ember inditott, es
elolvasta a kimenetet. Cronbol futo lancnal ez megszunik -- a kimenet egy
logfajlba folyik, amit senki nem olvas. Ha a rendszer csendben elromlik
(elfogy a lead, elutasitja a Google a kuldest, valaszol valaki es nem
veszed eszre), a hallgatas megkulonboztethetetlen a jol mukodo rendszertol.

HAROM RIASZTAS, MERT HAROM MODON TUD CSENDBEN ELROMLANI A RENDSZER:

  deliverability          -- a kuldes minosege romlik (bounce vagy SMTP-reject).
                             A `deliverability.py` exit 1-et ad; azt vesszuk at.
  no_ready_leads          -- 3 napja nincs exportalhato lead. A gep tovabb fut,
                             csak nincs kinek levelet kuldeni: a tolcser
                             valahol elakadt (enrich? score? kizarasok?).
  unanswered_interested   -- valaki ERDEKLODIK, es 24 oraja nem valaszoltunk.
                             Ez a legdragabb hiba az egesz rendszerben: a
                             tolcser teljes koltsege egy ilyen valaszert megy
                             el, es egy keso valasz annyit er, mint a semmi.

─────────────────────────────────────────────────────────────────────────────
A KETSZINTU KIMENET, ES MIERT EZ A SORREND:

  1. FAJL (`data/alerts.log`)  -- ez az IGAZSAGFORRAS. Mindig sikerul.
  2. DB (`alerts` tabla)       -- ez fekezi az ismetlest (dedup + `last_notified`).
  3. EMAIL                     -- BEST EFFORT masolat, ami elbukhat.

Az email szandekosan az UTOLSO es szandekosan nem kritikus. Egy SMTP-kimaradas
pontosan az a helyzet, amikor a riasztas a legfontosabb -- es pont akkor nem
mukodne az email ut. Ezert egy sikertelen ertesites SOHA nem allitja meg a
futast es SOHA nem nyeli el a riasztast: a fajlban akkor is ott lesz, es a
`report --daily` akkor is kiirja. Az emailkuldes hibaja maga is bekerul a
naploba.

Az email a kuldo SMTP-fiokjabol megy, de a sajat cimedre, es NEM ir a
sent.csv-be -- tehat nem szamit bele a napi keretbe es nem erinti a rampet.
Ez nem cold email, hanem uzemeltetesi ertesites.

─────────────────────────────────────────────────────────────────────────────
AZ ISMETLES-FEKEZES A LENYEG (`NOTIFY_COOLDOWN_ORA`).

A riasztasi feltetelek NAPOKIG fennallnak: a "3 napja nincs ready lead"
holnap is igaz lesz. Fekezes nelkul ugyanaz a mondat menne ki minden reggel,
valtozatlanul. Harom nap utan a felhasznalo szurot tesz ra a postafiokjaban --
es onnantol a VALODI riasztast sem latja. Egy riasztas, amit megtanulnak
figyelmen kivul hagyni, rosszabb a semmilyen riasztasnal, mert biztonsagerzetet
ad. Ezert egy adott riasztas 24 orankent legfeljebb egyszer ertesit.
"""
from __future__ import annotations

import datetime
import smtplib
import ssl
import subprocess
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate

from . import config, db

# Ennyi ideig nem ertesitunk ujra UGYANARROL a riasztasrol. Lasd a fenti
# indoklast: a ritkasag teszi hihetove a riasztast.
NOTIFY_COOLDOWN_ORA = 24

# Ennyi napja tarto lead-hiany utan riasztunk. A terv szerint 3 nap: egy-ket
# nap szunet normalis (hetvege, kifogyott batch), a harmadik mar elakadas.
READY_HIANY_NAP = 3

# Ennyi ora utan szamit egy erdeklodo valasz megvalaszolatlannak.
VALASZ_HATARIDO_ORA = 24


@dataclass
class Riasztas:
    kulcs: str
    tipus: str
    uzenet: str
    reszletek: dict


# ─── A harom ellenorzes ────────────────────────────────────────────────────

def _ellenoriz_deliverability() -> list[Riasztas]:
    """A kuldo kezbesitesi orjarata (`deliverability.py`).

    A SAJAT INTERPRETEREN futtatjuk, ugyanugy, mint a report._sender_state():
    a kuldo a rendszer python3-jan fut (3.9.6), a scraper a venv 3.12-jen.
    A ketto nem keveredik.

    A `deliverability.py` EXIT 1-ET AD, HA RIASZTAS VAN -- ez nem hiba, ez a
    jelzes (CLAUDE.md). Ezert itt a returncode 1 a riasztas feltetele, es
    minden MAS nem-nulla kod (2, 127, ...) valodi hiba: azt kulon jelezzuk,
    mert a "nem tudtuk megkerdezni" nem egyenlo azzal, hogy "nincs baj".
    """
    try:
        proc = subprocess.run(
            ["python3", "deliverability.py"],
            cwd=config.SENDER_DIR, capture_output=True, text=True, timeout=120,
        )
    except Exception as exc:  # noqa: BLE001
        return [Riasztas(
            kulcs="deliverability_futtathatatlan",
            tipus="deliverability",
            uzenet=f"A napi kezbesitesi jelentes NEM FUTOTT LE: {type(exc).__name__}: {exc}",
            reszletek={"hiba": str(exc)},
        )]

    kimenet = ((proc.stdout or "") + (proc.stderr or "")).strip()
    # Csak a FIGYELEM-sorok kellenek az uzenetbe, nem a teljes napi naplo.
    lenyeg = [s.strip() for s in kimenet.splitlines() if "FIGYELEM" in s]

    if proc.returncode == 1:
        return [Riasztas(
            kulcs="deliverability",
            tipus="deliverability",
            uzenet="A kezbesitesi mutatok atleptek a kuszobot.\n"
                   + ("\n".join(lenyeg) if lenyeg else kimenet[-600:]),
            reszletek={"returncode": 1, "kimenet": kimenet[-2000:]},
        )]
    if proc.returncode != 0:
        return [Riasztas(
            kulcs="deliverability_futtathatatlan",
            tipus="deliverability",
            uzenet=f"A napi kezbesitesi jelentes hibara futott (exit {proc.returncode}).\n"
                   f"{kimenet[-600:]}",
            reszletek={"returncode": proc.returncode, "kimenet": kimenet[-2000:]},
        )]
    return []


def _ellenoriz_ready_leadek() -> list[Riasztas]:
    """Van-e egyaltalan exportalhato lead, es mikor volt utoljara.

    KET FELTETEL EGYUTT, ES MINDKETTO KELL:

      - most nincs `ready` ceg, ES
      - READY_HIANY_NAP napja nem is volt kikuldott level

    A masodik feltetel nelkul minden sikeres export utan azonnal riasztanank:
    az exportalt lead ugyanis `queued`-be megy at, tehat a `ready` szam
    NULLARA esik -- ami teljesen egeszseges allapot. A kerdes nem az, hogy
    van-e most keszlet, hanem az, hogy MEGALLT-E a tolcser.
    """
    sor = db.query("""
        select
          (select count(*) from companies where status = 'ready')  as ready,
          (select count(*) from companies where status = 'queued') as queued,
          (select max(sent_at) from outreach)                      as utolso_kuldes
    """)[0]

    if sor["ready"] or sor["queued"]:
        return []

    utolso = sor["utolso_kuldes"]
    if utolso is not None:
        eltelt = datetime.datetime.now(datetime.timezone.utc) - utolso
        if eltelt.days < READY_HIANY_NAP:
            return []
        napok = eltelt.days
    else:
        # Meg soha nem ment ki level. Ez a rendszer indulasa, nem elakadas --
        # de ha mar van ceg a DB-ben es megsem jut el egy sem a `ready`-ig,
        # az igenis elakadas.
        van_ceg = db.query("select count(*) as n from companies")[0]["n"]
        if not van_ceg:
            return []
        napok = 0

    return [Riasztas(
        kulcs="no_ready_leads",
        tipus="no_ready_leads",
        uzenet=(f"Nincs exportalhato lead, es {napok} napja nem ment ki level.\n"
                if napok else
                "Van ceg a DB-ben, de egy sem jutott el a `ready` allapotig.\n")
               + "  Nezd meg, hol akadt el a tolcser:  ./leadgen.sh report",
        reszletek={"napok": napok},
    )]


def _ellenoriz_valaszok() -> list[Riasztas]:
    """Megvalaszolatlan `interested` valaszok.

    A "megvalaszolt" jelet a ceg allapota adja: ha mar nem `replied`, akkor
    ember hozzanyult (lezarta, tiltotta, ujraindult a szekvencia). Kulon
    "megvalaszoltam" gomb nincs, es nem is kell: a rendszerben mar van egy
    allapotgep, ami ezt tudja -- ket igazsagforrast csinalni belole hiba lenne.

    CIMZETTENKENT KULON RIASZTAS (a kulcs tartalmazza az email-cimet), mert
    egy kozos riasztas eseten a masodik erdeklodo elnyomva maradna, amig az
    elsot meg nem valaszolod.
    """
    rows = db.query("""
        select r.email, r.subject, r.received_at, c.company_name
          from reply_events r
     left join contacts ct on ct.email = r.email
     left join companies c on c.id = ct.company_id
         where r.classification = 'interested'
           and r.received_at < now() - make_interval(hours => %s)
           and (c.status is null or c.status = 'replied')
      order by r.received_at
    """, (VALASZ_HATARIDO_ORA,))

    out: list[Riasztas] = []
    for r in rows:
        ora = ""
        if r["received_at"]:
            eltelt = datetime.datetime.now(datetime.timezone.utc) - r["received_at"]
            ora = f", {int(eltelt.total_seconds() // 3600)} oraja"
        out.append(Riasztas(
            kulcs=f"unanswered_interested:{r['email']}",
            tipus="unanswered_interested",
            uzenet=(f"ERDEKLODO VALASZ VAR RAD{ora}:\n"
                    f"  {r['company_name'] or '?'}  <{r['email']}>\n"
                    f"  targy: {(r['subject'] or '')[:80]}\n"
                    f"  Ez a legdragabb lead a rendszerben. Valaszolj neki SZEMELYESEN."),
            reszletek={"email": r["email"], "subject": r["subject"] or ""},
        ))
    return out


def osszes_ellenorzes(skip_deliverability: bool = False) -> list[Riasztas]:
    """Mindharom ellenorzes. A sorrend a surgosseg sorrendje."""
    talalatok: list[Riasztas] = []
    talalatok += _ellenoriz_valaszok()          # ember kell hozza, ma
    if not skip_deliverability:
        talalatok += _ellenoriz_deliverability()
    talalatok += _ellenoriz_ready_leadek()
    return talalatok


# ─── Allapot-kezeles (dedup) ───────────────────────────────────────────────

def _rogzit(cur, r: Riasztas) -> bool:
    """Felveszi vagy frissiti a riasztast. True, ha MOST ertesiteni kell.

    Az ertesites feltetele: meg soha nem ertesitettunk rola, VAGY az utolso
    ertesites regebbi, mint a cooldown. A `last_notified` frissitese ugyanabban
    a tranzakcioban tortenik, mint a dontes -- igy ket parhuzamos futas nem
    kuldheti ki ketszer ugyanazt.
    """
    cur.execute("""
        insert into alerts (kulcs, tipus, uzenet, reszletek, last_seen)
             values (%s, %s, %s, %s, now())
        on conflict (kulcs) do update
                set last_seen   = now(),
                    uzenet      = excluded.uzenet,
                    reszletek   = excluded.reszletek,
                    -- ujra fennall egy korabban lezart riasztas -> nyissuk ki
                    resolved_at = null
          returning last_notified,
                    (resolved_at is null) as aktiv
    """, (r.kulcs, r.tipus, r.uzenet, db.Json(r.reszletek)))
    sor = cur.fetchone()

    utolso = sor["last_notified"]
    if utolso is not None:
        eltelt = datetime.datetime.now(datetime.timezone.utc) - utolso
        if eltelt.total_seconds() < NOTIFY_COOLDOWN_ORA * 3600:
            return False

    cur.execute("update alerts set last_notified = now() where kulcs = %s", (r.kulcs,))
    return True


def _lezar(cur, aktiv_kulcsok: set[str]) -> int:
    """A mar nem fennallo riasztasok lezarasa.

    NEM TOROL: a megszunt riasztas tortenet marad. Ha egy riasztas hetente
    visszater, azt latni kell -- egy torolt sorbol nem latszana.
    """
    cur.execute("""
        update alerts set resolved_at = now()
         where resolved_at is null and not (kulcs = any(%s))
    """, (list(aktiv_kulcsok),))
    return cur.rowcount


# ─── Kimenetek ─────────────────────────────────────────────────────────────

def _fajlba(r: Riasztas) -> None:
    """A riasztas naplozasa. EZ AZ IGAZSAGFORRAS -- mindig sikerul."""
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    sor = f"[{ts}] {r.tipus}: " + r.uzenet.replace("\n", "\n    ")
    config.ALERTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with config.ALERTS_LOG.open("a", encoding="utf-8") as f:
        f.write(sor + "\n")


def _emailben(riasztasok: list[Riasztas]) -> str:
    """Best-effort ertesites. Hiba eseten a HIBA SZOVEGET adja vissza, nem dob.

    MIERT NEM DOBHAT KIVETELT: a riasztas mar a fajlban van. Ha az emailkuldes
    hibaja megallitana a futast, egy SMTP-kimaradas elnyelne a riasztast --
    pont abban a helyzetben, amikor a legfontosabb lenne. Az ertesites
    kenyelem, nem a mechanizmus.

    EGY LEVEL MEGY, NEM RIASZTASONKENT EGY: harom kulon level harom kulon
    ertesites, es ugyanaz a kifaradas jonne, mint az ismetlesnel.
    """
    cim = config.ALERT_EMAIL
    if not cim:
        return "nincs beallitva ALERT_EMAIL"

    fiokok = _smtp_fiokok()
    if not fiokok:
        return "nincs SMTP_ACCOUNTS a kuldo .env-jeben"
    fiok = fiokok[0]

    torzs = "\n\n".join(r.uzenet for r in riasztasok)
    msg = EmailMessage()
    msg["From"] = fiok["user"]
    msg["To"] = cim
    # A targyban benne van a DARABSZAM es a tipus: igy a postafiokban is
    # latszik, mirol van szo, megnyitas nelkul.
    msg["Subject"] = (f"[leadgen] {len(riasztasok)} riasztas: "
                      + ", ".join(sorted({r.tipus for r in riasztasok})))
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(
        torzs
        + "\n\n---\n"
        + "Ez uzemeltetesi ertesites a lead-rendszertol, nem cold email.\n"
        + "Nem szamit bele a napi kuldesi keretbe.\n"
        + f"A teljes naplo: {config.ALERTS_LOG}\n"
    )

    try:
        ctx = ssl.create_default_context()
        if config.SENDER_SMTP_SSL:
            with smtplib.SMTP_SSL(config.SENDER_SMTP_HOST, config.SENDER_SMTP_PORT,
                                  context=ctx, timeout=30) as s:
                s.login(fiok["user"], fiok["password"])
                s.send_message(msg)
        else:
            with smtplib.SMTP(config.SENDER_SMTP_HOST, config.SENDER_SMTP_PORT,
                              timeout=30) as s:
                s.starttls(context=ctx)
                s.login(fiok["user"], fiok["password"])
                s.send_message(msg)
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"
    return ""


def _smtp_fiokok() -> list[dict]:
    """A kuldo SMTP-fiokjai, a KULDO sajat .env-jebol.

    Miert nem a scraper .env-jebol: a kuldo titkai a cold-email-starter/.env-ben
    vannak, es ott is a helyuk (ket rendszer, ket titok-fajl). Itt csak
    OLVASSUK oket, hogy legyen mivel elkuldeni az ertesitest.
    """
    return config.sender_smtp_accounts()


# ─── Fo belepesi pont ──────────────────────────────────────────────────────

def run(dry: bool = False, skip_deliverability: bool = False,
        verbose: bool = True) -> list[Riasztas]:
    """Vegigfuttatja az ellenorzeseket, naplozza es (ha kell) ertesit."""
    talalatok = osszes_ellenorzes(skip_deliverability=skip_deliverability)

    if dry:
        if verbose:
            if not talalatok:
                print("Nincs riasztas.")
            for r in talalatok:
                print(f"\n[{r.tipus}]  kulcs={r.kulcs}")
                print("  " + r.uzenet.replace("\n", "\n  "))
            print("\n(--dry: semmit nem irtunk es nem kuldtunk el)")
        return talalatok

    ertesitendo: list[Riasztas] = []
    with db.connect() as conn, conn.cursor() as cur:
        for r in talalatok:
            if _rogzit(cur, r):
                ertesitendo.append(r)
        lezart = _lezar(cur, {r.kulcs for r in talalatok})

    # A fajl-naplo MINDEN uj ertesitesrol keszul, fuggetlenul attol, hogy az
    # email atment-e. Ez a sorrend a lenyeg: eloszor rogzitunk, aztan kuldunk.
    for r in ertesitendo:
        _fajlba(r)

    email_hiba = ""
    if ertesitendo:
        email_hiba = _emailben(ertesitendo)
        if email_hiba:
            # A sikertelen ertesites maga is naplozando esemeny -- kulonben
            # ugy tunne, hogy szoltunk, pedig nem.
            _fajlba(Riasztas(
                kulcs="alert_email_hiba", tipus="alert_email_hiba",
                uzenet=f"A riasztasi email NEM ment ki: {email_hiba}",
                reszletek={},
            ))

    if verbose:
        if not talalatok:
            print("Nincs riasztas.")
        else:
            print(f"{len(talalatok)} riasztas all fenn, ebbol {len(ertesitendo)} uj "
                  f"(a tobbirol {NOTIFY_COOLDOWN_ORA} oran belul mar szoltunk).")
            for r in talalatok:
                jel = ">>>" if r in ertesitendo else "   "
                print(f"{jel} [{r.tipus}] {r.uzenet.splitlines()[0]}")
        if lezart:
            print(f"{lezart} korabbi riasztas megszunt (lezarva).")
        if email_hiba:
            print(f"\nFIGYELEM: az ertesito email nem ment ki: {email_hiba}")
            print(f"  A riasztas ettol fuggetlenul naplozva van: {config.ALERTS_LOG}")
    return talalatok


def aktiv_riasztasok() -> list[dict]:
    """A meg fennallo riasztasok (a `report --daily` ezt mutatja a tetejen)."""
    return db.query("""
        select kulcs, tipus, uzenet, first_seen, last_seen, last_notified
          from alerts where resolved_at is null
      order by last_seen desc
    """)
