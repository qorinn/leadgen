#!/usr/bin/env python3
"""A kuldes ketlepcsos kapuja (13. szakasz, F7).

KET DOLOG VAN EBBEN A FAJLBAN:

  terv()          -- MI menne ki ma, teljes szoveggel (a kuldot kerdezzuk meg)
  token_*()       -- a ketlepcsos kapu: elonezet nelkul nem indul eles kuldes

─────────────────────────────────────────────────────────────────────────────
MIERT SUBPROCESS (es miert nem importaljuk a kuldot):

Ugyanaz az indok, mint a `report._sender_state()`-nel: a kuldo a rendszer
`python3`-jan fut (3.9.6), lapos importokkal, a sajat konyvtarabol. A venv
Pythonjabol nem importalhato. De a fontosabb ok nem technikai: a TERV a
kuldo tulajdona. A `sender.build_plan()` tudja a follow-up sorrendet, a
DNC-t, a `verify.looks_unsendable()` szurest es a kampany szerinti
sablonvalasztast. Ha ezt itt ujraimplementalnank, a felulet MAST mutatna,
mint ami kimegy -- pont azt a hibat, ami ellen ez az egesz kepernyo van.

─────────────────────────────────────────────────────────────────────────────
A KETLEPCSOS KAPU -- ES MIERT A SZERVEREN VAN:

Egy letiltott gomb frontend-allapot. Egy elgepelt `fetch`, egy vissza-gomb
vagy egy oldal-ujratoltes megkeruli. A kikuldes visszafordithatatlan, tehat a
vedelemnek a SZERVEREN kell lennie (WEBUI-TERV.md Invariansok #2).

A token a terv TARTALMI hash-e. Az eles kuldes elott a szerver UJRA
lekerdezi a tervet, ujra hasheli, es osszehasonlitja. Ha kozben barmi
valtozott -- lefutott egy export, valaki elutasitott egy leadet, atirtak egy
sablont --, a hash nem egyezik, es a kuldes elutasitva. Nem azert, mert a
tokent "lejartnak" jeloltuk, hanem mert a terv MAR NEM AZ, amit az ember
jovahagyott.

A token ezen felul rovid eletu (10 perc) es EGYSZER hasznalatos: a
ket kattintas kozott eltelt fel ora alatt is valtozhat a vilag, es egy
dupla kattintas nem inditkat ket kuldest.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from . import config

# Ennyi ideig ervenyes egy kiadott elonezet-token.
TOKEN_ELETTARTAM_PERC = 10

# A kuldo lekerdezesenek felso ideje. A terv felepitese fajlolvasas es
# sablon-renderelés, halozati hivas nincs benne -- ha ez 60 masodperc alatt
# nem all ossze, akkor valami mas a baj.
_TIMEOUT_MP = 60

# A mintalevel VALODI SMTP-kuldes, tehat lassabb (kapcsolat + kuldesi
# szunetek). Ezert kap tobb idot.
_MINTA_TIMEOUT_MP = 180


class TokenErvenytelen(Exception):
    """A ketlepcsos kapu elutasitasa. Az uzenet a felhasznalonak szol."""


@dataclass
class Level:
    cimzett: str
    ceg: str
    fok: str
    targy: str
    torzs: str


@dataclass
class Terv:
    """A mai kuldesi terv. `ok=False` -> nem tudtuk megkerdezni a kuldot.

    A `False` NEM ures tervet jelent: az azt jelentene, hogy ma nincs kit
    megkeresni. Ugyanaz a kulonbsegtetel, mint a `report.SenderState`-ben --
    a "nem tudom" soha nem lehet egyenlo a "nulla"-val.
    """
    ok: bool = False
    levelek: list[Level] = field(default_factory=list)
    mai_keret: int = 0
    sent_today: int = 0
    # A kuldesi idoablak (`limits.in_send_window()`). AZ ABLAKON KIVUL a
    # `sender.py --live` exit 0-val kilep, es NEM KULD SEMMIT -- e nelkul a
    # ket mezo nelkul a felhasznalo csak az elo naploban szembesulne ezzel.
    ablak_nyitva: bool = False
    ablak_ok: str = ""
    error: str = ""

    @property
    def terv_meret(self) -> int:
        return len(self.levelek)


# A TERV FELEPITESE A KULDO OLDALAN. Pontosan azt a sorrendet koveti, amit a
# `sender.main()`: keret -> `build_plan(keret)` -> renderelés. A `--dry`
# ugyanezt csinalja, csak az elso 400 karaktert irja ki; itt a TELJES torzs
# kell (WEBUI-TERV.md F7).
#
# GUARDS NELKUL. A `sender.py --dry` alapbol lefuttatja a guardsot, ami IMAP-ot
# nyit ES IR (DNC, bounce-naplo). Egy elonezet nem irhat -- es nem is
# varakoztathatja a felhasznalot egy postafiok-olvasasra. A guards a KULDESKOR
# fut le, es csak SZUKITENI tudja a tervet; ezt a felulet ki is irja.
_TERV_KOD = (
    "import json, limits, sender, store; "
    "store.init_all(); "
    "nyitva, miert = limits.in_send_window(); "
    "keret = limits.remaining_today(); "
    "terv = sender.build_plan(keret) if keret > 0 else []; "
    "print(json.dumps({"
    "'levelek': [{"
    "'cimzett': (lead.get('email') or '').strip().lower(), "
    "'ceg': lead.get('company') or '', "
    "'fok': fok, "
    "'targy': render(lead)['subject'], "
    "'torzs': render(lead)['body']} for lead, fok, render in terv], "
    "'mai_keret': limits.daily_cap(), "
    "'sent_today': store.sent_today_count(), "
    "'ablak_nyitva': nyitva, "
    "'ablak_ok': miert}))"
)


def terv() -> Terv:
    """A mai kuldesi terv, teljes levelekkel. CSAK OLVAS."""
    nyers = _kuldo_kerdez(_TERV_KOD)
    if isinstance(nyers, str):
        return Terv(error=nyers)
    return Terv(
        ok=True,
        levelek=[Level(**sor) for sor in nyers["levelek"]],
        mai_keret=int(nyers["mai_keret"]),
        sent_today=int(nyers["sent_today"]),
        ablak_nyitva=bool(nyers["ablak_nyitva"]),
        ablak_ok=str(nyers["ablak_ok"]),
    )


# ─── Cim-valasztas a kuldes elott (F7 bovites, 2026-09-02) ─────────────────
#
# MIERT ITT ES NEM A ROUTERBEN: melyik sorhoz szabad egyaltalan mas cimet
# valasztani, az UZLETI dontes -- a webui csak megjeleniti. (CLAUDE.md: "az
# uzleti logika soha nem masolodik TypeScriptbe".)
#
# ⚠️ CSAK A `cold` FOKON SZABAD CIMET CSERELNI. A kuldo a szekvencia-fokot a
# `sent.csv`-bol vezeti le, EMAIL-CIM SZERINT (`sender._stage_of`). Ha egy
# follow-upra varo lead cimet kicserelnenk, az uj cimnek NEM lenne elozmenye,
# tehat a rendszer ujra COLD levelet kuldene neki -- ugyanannak a cegnek,
# masodszor, bemutatkozo levellel. A tiltas tehat nem ovatossag, hanem a
# `_stage_of` mukodesebol kovetkezik.
CSEREHETO_FOK = "cold"


def kontakt_valasztek(cimzettek: list[str]) -> dict[str, list[dict]]:
    """cimzett email -> a ceg OSSZES hasznalhato cime (magat is beleertve).

    Csak azok a cegek kerulnek bele, ahol tenylegesen VAN mibol valasztani
    (egynel tobb hasznalhato cim) -- egyetlen cim mellett a select csak zajt
    adna a felulethez.
    """
    from . import db, enrich

    cimek = [(e or "").strip().lower() for e in cimzettek if e]
    if not cimek:
        return {}

    # UGYANAZ a rangsor, amit az export hasznal (`enrich.EMAIL_TYPE_SORREND`):
    # a legordulo elso eleme az legyen, amit a rendszer amugy is valasztana.
    rows = db.query(
        f"""
        select alap.email                as cimzett,
               tars.email                as email,
               tars.email_type           as email_type,
               tars.source_kind          as source_kind,
               tars.verify_result        as verify_result,
               (c.preferred_contact_id = tars.id) as preferred
          from contacts alap
          join companies c on c.id = alap.company_id
          join contacts tars on tars.company_id = c.id
         where alap.email = any(%s)
           and tars.local_check is distinct from 'fail'
           and coalesce(tars.verify_result, '') <> 'invalid'
           and coalesce(tars.bounce_state, '') <> 'hard_bounce'
         order by alap.email,
                  {enrich.email_type_rang_sql('tars.email_type')},
                  {enrich.generic_rang_sql('tars.email')},
                  case tars.source_kind when 'mailto' then 0 else 1 end,
                  tars.created_at
        """,
        (cimek,),
    )

    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["cimzett"], []).append({
            "email": r["email"],
            "email_type": r["email_type"] or "",
            "source_kind": r["source_kind"] or "",
            "verify_result": r["verify_result"] or "unknown",
            "preferred": bool(r["preferred"]),
        })
    return {cim: lista for cim, lista in out.items() if len(lista) > 1}


@dataclass
class CsereEredmeny:
    ok: bool
    hiba: str = ""


def kontakt_csere(regi_email: str, uj_email: str) -> CsereEredmeny:
    """A cimzett cseréje EGY cegnel, a kuldes elott.

    HAROM DOLGOT KELL EGYUTT INTEZNI, es egyik sem hagyhato el:

    1. `companies.preferred_contact_id` -- a TARTOS dontes. Enelkul a
       kovetkezo export ujra a rangsor szerinti cimet valasztana.
    2. `outreach.contact_id` a MAR SORBAN ALLO (`queued`) sornal -- az export
       `SQL_INFLIGHT`-ja innen veszi a cimet, nem a preferenciabol (ott a
       kampany es a cim a sorba allitas pillanataban van BEFAGYASZTVA). E
       nelkul a valasztas a felulen megtortenne, de a levél a regi cimre
       menne.
    3. `leads.csv` ujrairasa -- a kuldo ebbol a fajlbol dolgozik, nem a
       DB-bol. Ezt a hivo (`webui`) inditja kulon, mert az export hosszabb
       muvelet (feedback + validacio), es a felulet allapotjelzot mutat ra.

    A `sent` allapotu sorokat NEM nyulja: lasd `CSEREHETO_FOK`.
    """
    from . import db

    regi = (regi_email or "").strip().lower()
    uj = (uj_email or "").strip().lower()
    if not regi or not uj:
        return CsereEredmeny(ok=False, hiba="hianyzo cim")
    if regi == uj:
        return CsereEredmeny(ok=True)

    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select alap.company_id, uj.id as uj_id
              from contacts alap
              join contacts uj on uj.company_id = alap.company_id and uj.email = %s
             where alap.email = %s
               and uj.local_check is distinct from 'fail'
               and coalesce(uj.verify_result, '') <> 'invalid'
               and coalesce(uj.bounce_state, '') <> 'hard_bounce'
            """,
            (uj, regi),
        )
        hit = cur.fetchone()
        if not hit:
            return CsereEredmeny(
                ok=False,
                hiba="a ket cim nem ugyanahhoz a ceghez tartozik, "
                     "vagy az uj cim nem hasznalhato")

        cur.execute("update companies set preferred_contact_id = %s where id = %s",
                    (hit["uj_id"], hit["company_id"]))
        # CSAK `queued`: a `sent` sor cimet nem irjuk at (lasd CSEREHETO_FOK).
        cur.execute(
            "update outreach set contact_id = %s "
            " where company_id = %s and status = 'queued'",
            (hit["uj_id"], hit["company_id"]))
    return CsereEredmeny(ok=True)


def guards_futtat() -> tuple[int, str]:
    """A kuldo vedelmi kore (`guards.py`) a SAJAT interpreteren. (kod, kimenet)

    MIERT KELL EZ A SCRAPER-OLDALON: a `guards.py` irja a `bounces.csv`-t es a
    `do-not-contact.csv`-t, a `feedback` pedig EZEKET olvassa. Csakhogy a
    guards eddig kizarolag a `sender.py` reszekent futott (annak az elso
    lepese), tehat aki egy nap nem kuldott, annal a valaszok, leiratkozasok es
    visszapattanasok FELDOLGOZATLANUL maradtak -- a `feedback` hiaba futott le
    a napi lancban, nem volt mit beolvasnia.

    Eles eset (2026-08-31): a `padavan@thepitch.hu` cimre kikuldott level
    percekkel a kuldes UTAN pattant vissza. A guards a futas ELEJEN futott le,
    tehat ezt mar nem lathatta -- es mivel azota nem volt kuldes, a bounce ket
    napig feldolgozatlanul allt a postafiokban.

    EZ NEM KULD SEMMIT. Csak IMAP-ot olvas, es a ket vedelmi CSV-t irja. Ezert
    kerulhet be a napi lancba anelkul, hogy a "`--live`-ot ember inditja"
    szabaly serulne.
    """
    try:
        proc = subprocess.run(
            ["python3", "guards.py"],
            cwd=config.SENDER_DIR, capture_output=True, text=True,
            timeout=_TIMEOUT_MP,
        )
    except Exception as exc:  # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def _kuldo_kerdez(kod: str) -> dict[str, Any] | str:
    """Egy kerdes a kuldohoz, a SAJAT interpreteren. Hiba eseten szoveget ad
    vissza, nem dob -- a hivo ezt tovabbadja a felhasznalonak."""
    try:
        proc = subprocess.run(
            ["python3", "-c", kod],
            cwd=config.SENDER_DIR, capture_output=True, text=True,
            timeout=_TIMEOUT_MP,
        )
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        hiba = (proc.stderr or "").strip()
        return hiba.splitlines()[-1] if hiba else f"exit {proc.returncode}"
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as exc:  # noqa: BLE001
        return f"olvashatatlan valasz a kuldotol: {exc}"


# ─── A terv tartalmi hash-e ────────────────────────────────────────────────


def terv_hash(levelek: list[Level]) -> str:
    """A terv tartalmi ujjlenyomata.

    A TORZS IS BENNE VAN, nem csak a cimzett/fok/targy. A terv szovege
    (WEBUI-TERV.md F7) harom mezot sorol fel, de a `templates.py` a
    felhasznaloe, es kozben barmikor atirhatja: targy-valtozas nelkul is mas
    szoveg menne ki, mint amit az elonezetben jovahagyott. A token igy azt
    fedi le, AMIT AZ EMBER LATOTT -- ez a kapu egesz ertelme. Kifele a token
    ugyanugy egy atlatszatlan string marad.
    """
    kanonikus = json.dumps(
        [[lv.cimzett, lv.fok, lv.targy, lv.torzs] for lv in levelek],
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(kanonikus.encode("utf-8")).hexdigest()


# ─── A ketlepcsos kapu ─────────────────────────────────────────────────────


@dataclass
class _Token:
    ertek: str
    terv_hash: str
    lejar: dt.datetime
    hasznalt: bool = False


_LOCK = threading.Lock()
_TOKENEK: dict[str, _Token] = {}


def token_kiad(levelek: list[Level]) -> tuple[str, dt.datetime]:
    """Uj elonezet-token. Visszateres: (token, mikor jar le)."""
    lejar = dt.datetime.now() + dt.timedelta(minutes=TOKEN_ELETTARTAM_PERC)
    token = uuid.uuid4().hex
    with _LOCK:
        _takarit()
        _TOKENEK[token] = _Token(token, terv_hash(levelek), lejar)
    return token, lejar


def token_beval(token: str, mostani: list[Level]) -> None:
    """Ervenyesiti ES elhasznalja a tokent. Hiba eseten `TokenErvenytelen`.

    A SORREND FONTOS: eloszor jeloljuk hasznaltnak, csak utana indulhat a
    kuldes. Egy dupla kattintas igy nem indit ket futast, meg akkor sem, ha a
    ket keres masodperc-tort resszel ter el.
    """
    with _LOCK:
        _takarit()
        bejegyzes = _TOKENEK.get(token)
        if bejegyzes is None:
            raise TokenErvenytelen(
                "ervenytelen vagy lejart elonezet-token -- kerj uj elonezetet")
        if bejegyzes.hasznalt:
            raise TokenErvenytelen(
                "ezt az elonezetet mar elhasznaltuk -- kerj uj elonezetet")
        if dt.datetime.now() > bejegyzes.lejar:
            raise TokenErvenytelen(
                f"az elonezet lejart ({TOKEN_ELETTARTAM_PERC} perc) "
                "-- kerj uj elonezetet")
        if bejegyzes.terv_hash != terv_hash(mostani):
            # EZ A LENYEGI ELLENORZES. Nem a token "romlott el": a TERV mas,
            # mint amit az ember jovahagyott.
            raise TokenErvenytelen(
                "a terv megvaltozott az elonezet ota (lefutott egy export, "
                "valaki elutasitott egy leadet, vagy modosult egy sablon) "
                "-- kerj uj elonezetet, es nezd at ujra")
        bejegyzes.hasznalt = True


def _takarit() -> None:
    """A lejart tokenek eldobasa. A `_LOCK` mar a hivonal fogva van."""
    most = dt.datetime.now()
    for kulcs in [k for k, v in _TOKENEK.items() if most > v.lejar]:
        _TOKENEK.pop(kulcs, None)


# ─── Mintalevel magadnak ───────────────────────────────────────────────────

# A `preview.py --send-to`-t hivjuk, nem irunk ujra teszt-kuldest. Az a
# script ket dolgot tud, amit egy ujraimplementalas csendben elrontana:
# NEM ir a `sent.csv`-be (tehat a valodi lead szekvenciaja erintetlen marad),
# es kicsereli a valodi leiratkozo tokent egy artalmatlan teszt-linkre (egy
# teszt kozbeni kattintas kulonben veglegesen leiratna egy valodi ceget).
FOKOK = ("cold", "follow_up_1", "follow_up_2")


@dataclass
class MintaEredmeny:
    ok: bool
    sorok: list[str]
    error: str = ""


def mintalevel(cim: str, limit: int = 1, fok: str = "cold") -> MintaEredmeny:
    """Teszt-levelek a SAJAT cimedre. VALODI SMTP-kuldes.

    A valodi cimzettek nem kapnak semmit, es a `sent.csv` sem valtozik --
    de a Google a sajat napi limitjebe beleszamolja.
    """
    if fok not in FOKOK:
        return MintaEredmeny(False, [], f"ismeretlen fok: {fok!r}")
    try:
        proc = subprocess.run(
            ["python3", "preview.py", "--send-to", cim,
             "--limit", str(limit), "--stage", fok],
            cwd=config.SENDER_DIR, capture_output=True, text=True,
            timeout=_MINTA_TIMEOUT_MP,
        )
    except Exception as exc:  # noqa: BLE001
        return MintaEredmeny(False, [], f"{type(exc).__name__}: {exc}")

    sorok = (proc.stdout or "").splitlines()
    if proc.returncode != 0:
        hiba = (proc.stderr or "").strip()
        return MintaEredmeny(
            False, sorok,
            hiba.splitlines()[-1] if hiba else f"exit {proc.returncode}")
    return MintaEredmeny(True, sorok)
