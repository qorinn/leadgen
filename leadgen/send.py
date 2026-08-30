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
