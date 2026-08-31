"""Futtatas-kezelo: a CLI parancsai a feluletrol, elo naploval (F6).

─────────────────────────────────────────────────────────────────────────────
EGYSZERRE EGY FUTAS -- ES MIERT NEM ELEG A `flock`:

A `store._append` mar `flock`-kal ir (12. szakasz), tehat ket parhuzamos
futas nem TORI OSSZE a `sent.csv` egy sorat. De a lock a KETTOS
FELDOLGOZAS ellen nem ved: ket egyszerre inditott `daily` ugyanazt a cegcsokrot
enrichelne, ugyanazt a leadet exportalna, es ketszer koltene AI-tokent. Ezert
a masodik inditas ELUTASITVA (409), a futo job megjelolesevel.

Amit ez NEM lat: a launchd-bol 07:30-kor indulo lanc. Az sajat folyamatban
fut, nem ezen a modulon at. Ez tudatos hatar -- a felulet a SAJAT inditasait
sorositja; az utemezes allapota a `/api/schedule/status`-on latszik.

─────────────────────────────────────────────────────────────────────────────
A KATALOGUS A KONTRAKTUS RESZE:

A frontend NEM tudja, milyen parancsok vannak -- a `/api/jobs/catalog`-bol
kapja meg (WEBUI-TERV.md Invariansok #1). Ez nem formalitas: a `--limit`
alapertelmezesei a CLI sajat argparse-abol jonnek (`_alap_ertekek`), tehat ha
valaki atirja a CLI-t, a felulet magatol koveti.

⚠️ A `sender.py --live` SZANDEKOSAN NINCS EBBEN A KATALOGUSBAN. A kuldes az
F7 kulon utjan megy, ketlepcsos megerositessel. Tesztsor orzi
(`tests/test_webui_jobs.py`).

─────────────────────────────────────────────────────────────────────────────
KOLTSEG: NEM TALALUNK KI SZAMOT.

Ket fajta fizetos parancs van, es a ketto MASHOGY becsulheto:
  - Apify (`ingest`, `resolve-domains`): egysegar x darab, elore tudhato.
    Az egysegar a `pricing.APIFY_TALALAT_USD`, a darab a parancs sajat
    kerete (`--max-results` / `--limit`).
  - AI (`score`, `classify-replies`): TOKENENKENT szamlazodik, tehat elore
    NEM becsulheto. A valasz ilyenkor `ai_tokenenkent=True`, es a felulet
    ezt irja ki -- nem egy kitalalt dollarosszeget.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import signal
import subprocess
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from leadgen import config, pricing, schedule
from leadgen.cli import build_parser

# Ennyi sort tartunk meg egy futasbol a memoriaban. Egy `daily` par szaz
# sort ir; a plafon a beragadt/vegtelen ciklusban levo futas ellen van.
MAX_SOR = 5000

# Ennyi befejezett futas kimenete marad elerheto (`GET /api/jobs/{id}`).
MAX_MEMORIA_JOB = 20

# Az elozmenyek naploja. A `data/` a .gitignore-ban van (nyers munkaadat).
# MIERT FAJL ES NEM CSAK MEMORIA: az API-szervert egy `npm run dev` melletti
# ujraindulas barmikor eldobja, es akkor pont az veszne el, hogy MI FUTOTT MA.
ELOZMENY_PATH = config.BASE / "data" / "webui_jobs.jsonl"


# ─── Katalogus ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Param:
    """Egy allithato keret (`--limit` / `--max-results`).

    Az alapertek NINCS ITT: azt a CLI sajat argparse-a mondja meg
    (`_alap_ertekek`), kulonben ket helyen kellene karbantartani ugyanazt a
    szamot, es csendben elcsusznanak.
    """
    nev: str          # argparse dest, pl. "max_results"
    flag: str         # "--max-results"
    cimke: str
    minimum: int
    maximum: int


@dataclass(frozen=True)
class Parancs:
    kulcs: str
    cimke: str
    magyarazat: str
    argv: tuple[str, ...]
    parameterek: tuple[Param, ...] = ()
    # Apify: egysegar x darab. A darab vagy egy parameter erteke
    # (`apify_darab_parametere`), vagy fix (a napi lanc sajat kerete).
    apify: bool = False
    apify_darab_parametere: str | None = None
    apify_fix_darab: int | None = None
    # AI: tokenenkent szamlazodik, elore nem becsulheto.
    ai: bool = False


_LIMIT = Param("limit", "--limit", "Feldolgozott cegek felso korlatja", 1, 500)
_EXPORT_LIMIT = Param("limit", "--limit", "Exportalt leadek szama (0 = nincs korlat)", 0, 500)
_MAX_RESULTS = Param("max_results", "--max-results", "Talalatok felso korlatja", 1, 500)


def _daily_ingest_keret() -> int:
    """A napi lanc ingest-lepesenek `--max-results` erteke.

    A LANCBOL OLVASSUK KI, nem beirjuk ide: a `schedule.lepesek()` egyetlen
    igazsag arrol, mennyit kolt a `daily`. Ha az a keret valaha valtozik, a
    felulet becslese magatol koveti (WEBUI-TERV.md F6: "ne talalj ki szamot").
    """
    for lepes in schedule.lepesek():
        if lepes.nev != "ingest":
            continue
        if "--max-results" in lepes.argv:
            return int(lepes.argv[lepes.argv.index("--max-results") + 1])
    return 0


KATALOGUS: tuple[Parancs, ...] = (
    Parancs(
        "daily", "Napi lanc (teljes)",
        "Minden lepes egymas utan, az ingesttel egyutt -- ugyanaz, amit az utemezes futtat.",
        ("daily",),
        apify=True, apify_fix_darab=_daily_ingest_keret(), ai=True,
    ),
    Parancs(
        "daily-skip-ingest", "Napi lanc ingest nelkul",
        "A teljes lanc, de uj cegeket nem tolt be -- a tegnapi cegeket dolgozza fel.",
        ("daily", "--skip-ingest"),
        ai=True,
    ),
    Parancs(
        "enrich", "Weboldalak feldolgozasa",
        "A `new` allapotu cegek weboldalanak letoltese es kontakt-kereses.",
        ("enrich",), (_LIMIT,),
    ),
    Parancs(
        "enrich-dead-dev", "Fejleszto-kredit felismerese",
        "8.2: ki keszitette a weboldalt, es el-e meg a fejleszto.",
        ("enrich", "dead-dev"), (_LIMIT,),
    ),
    Parancs(
        "qualify", "Minosites",
        "Kulcsszo-alapu minosites es kizaras, AI-hivas nelkul.",
        ("qualify",), (_LIMIT,),
    ),
    Parancs(
        "score", "AI-minosites",
        "AI-pontozas es evidence grounding a feldolgozott cegekre.",
        ("score",), (_LIMIT,), ai=True,
    ),
    Parancs(
        "webshop-growth", "Dobozos webshop felismerese",
        "8.3: melyik ceg notte ki a dobozos webshop-platformjat.",
        ("webshop-growth",), (_LIMIT,),
    ),
    Parancs(
        "feedback", "Visszajelzes beolvasasa",
        "A kuldo CSV-inek beolvasasa a DB-be. Az export elott kotelezo.",
        ("feedback",),
    ),
    Parancs(
        "export", "Export a kuldonek",
        "A `leads.csv` ujrairasa. Elso lepeskent maga is lefuttatja a feedbacket.",
        ("export",), (_EXPORT_LIMIT,),
    ),
    Parancs(
        "alert", "Riasztas-ellenorzes",
        "A nap allapotanak ellenorzese, es ertesites, ha van mire.",
        ("alert",),
    ),
    Parancs(
        "classify-replies", "AI valasz-osztalyozas",
        "A beerkezett valaszok cimkezese. A visszafordithatatlan cimkeket bizalmi kapu vedi.",
        ("classify-replies",), (_LIMIT,), ai=True,
    ),
    Parancs(
        "ingest-maps", "Uj cegek: Google Maps",
        "Uj cegek betoltese a Google Mapsrol (Apify).",
        ("ingest", "maps"), (_MAX_RESULTS,),
        apify=True, apify_darab_parametere="max_results",
    ),
    Parancs(
        "ingest-ops-pain", "Uj cegek: Profession.hu",
        "Allashirdetesekbol szarmazo cegek betoltese.",
        ("ingest", "ops-pain"), (_MAX_RESULTS,),
        apify=True, apify_darab_parametere="max_results",
    ),
    Parancs(
        "resolve-domains", "Domain-feloldas",
        "A domain nelkul beragadt cegek feloldasa Google Maps-szel (Apify).",
        ("resolve-domains",), (_LIMIT,),
        apify=True, apify_darab_parametere="limit",
    ),
)

_KULCS_SZERINT = {p.kulcs: p for p in KATALOGUS}


def _alap_ertekek(parancs: Parancs) -> dict[str, int]:
    """A parancs `--limit` / `--max-results` alapertelmezesei -- A CLI-BOL.

    A `build_parser().parse_args()` csak feltolti a Namespace-t az
    alapertekekkel; a `func` (a tenyleges muvelet) NEM fut le. Igy a szamokat
    nem kell itt masodszor is leirni.
    """
    ns = build_parser().parse_args(list(parancs.argv))
    return {p.nev: int(getattr(ns, p.nev)) for p in parancs.parameterek}


def _lepes_alap_argv(argv: tuple[str, ...]) -> tuple[str, ...]:
    """Egy napi-lanc-lepes argv-je a `--limit`/`--max-results` szam nelkul --
    igy hasonlithato ossze a katalogus (meg parameter nelkuli) argv-jevel."""
    argv = list(argv)
    if len(argv) >= 2 and argv[-2] in ("--limit", "--max-results"):
        argv = argv[:-2]
    return tuple(argv)


def _naponta_fut_argvk() -> set[tuple[str, ...]]:
    """Melyik parancsok futnak le a napi lancban MAGATOL -- a
    `schedule.lepesek()`-bol szarmaztatva, nem itt masodszor felsorolva
    (WEBUI-TERV.md: "ne talalj ki szamot/listat, ami mar letezik").

    Az `alert` nincs benne a `lepesek()` listajaban (a `schedule.napi_lanc()`
    kulon, a lanc vegen, MINDIG lefuttatja -- lasd annak docstringjet), ezert
    ide kezzel hozza kell venni.
    """
    argvk = {_lepes_alap_argv(l.argv) for l in schedule.lepesek()}
    argvk.add(("alert",))
    return argvk


def katalogus_adat() -> list[dict[str, Any]]:
    naponta_fut_argvk = _naponta_fut_argvk()
    out = []
    for p in KATALOGUS:
        alapok = _alap_ertekek(p)
        out.append({
            "kulcs": p.kulcs,
            "cimke": p.cimke,
            "magyarazat": p.magyarazat,
            "parancs": _parancs_szoveg(list(p.argv)),
            "parameterek": [
                {"nev": par.nev, "flag": par.flag, "cimke": par.cimke,
                 "alap": alapok[par.nev], "minimum": par.minimum,
                 "maximum": par.maximum}
                for par in p.parameterek
            ],
            "koltseg": {
                "fizetos": p.apify or p.ai,
                "apify_egysegar_usd": pricing.APIFY_TALALAT_USD if p.apify else None,
                "apify_fix_darab": p.apify_fix_darab,
                "apify_darab_parametere": p.apify_darab_parametere,
                "ai_tokenenkent": p.ai,
                "magyarazat": _koltseg_magyarazat(p),
            },
            # A "daily"/"daily-skip-ingest" gomb maga a lanc -- ujra
            # inditasa ugyanazt csinalna, amit az utemezes ugyis lefuttat,
            # tehat ez is "automatikusan lefut" (webui F futtatas nezet:
            # elhalvanyitott/kiemelt gombok).
            "naponta_fut": (
                p.kulcs in ("daily", "daily-skip-ingest")
                or tuple(p.argv) in naponta_fut_argvk
            ),
        })
    return out


def _koltseg_magyarazat(p: Parancs) -> str:
    reszek = []
    if p.apify:
        reszek.append(f"Apify: ${pricing.APIFY_TALALAT_USD:.3f} / talalat")
    if p.ai:
        # NEM adunk dollarbecslest: a tokenszam a bemenettol fugg. A tenyleges
        # koltseget a futas utan a `/api/costs` (pricing.py) mutatja meg.
        reszek.append("AI: tokenenkent szamlazodik, elore nem becsulheto")
    return " - ".join(reszek) if reszek else "Nem kerul penzbe."


# ─── Egy futas ─────────────────────────────────────────────────────────────


@dataclass
class Job:
    id: str
    kulcs: str
    cimke: str
    # A folyamat TELJES parancssora (interpreter + argumentumok).
    argv: list[str]
    # Amit a terminalban gepelnel ugyanerre. TAROLT mezo, nem szarmaztatott:
    # a kuldes nem `./leadgen.sh ...`, hanem `cd cold-email-starter && python3
    # sender.py --live` -- ket kulon interpreteren ket kulon alak.
    parancs: str
    started_at: dt.datetime
    finished_at: dt.datetime | None = None
    exit_code: int | None = None
    megszakitva: bool = False
    sorok: deque[str] = field(default_factory=lambda: deque(maxlen=MAX_SOR))
    # Az OSSZES eddig latott sor szama, a memoriabol mar kiesettekkel egyutt.
    # Ez a kurzor alapja: az SSE igy nem ismetel es nem hagy ki sort akkor
    # sem, ha kozben a deque eleje levagodott.
    osszes_sor: int = 0
    _proc: subprocess.Popen | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def fut(self) -> bool:
        return self.finished_at is None

    @property
    def allapot(self) -> str:
        if self.fut:
            return "running"
        if self.megszakitva:
            return "cancelled"
        return "ok" if self.exit_code == 0 else "failed"

    @property
    def allapot_cimke(self) -> str:
        return {
            "running": "Fut",
            "cancelled": "Megszakitva",
            "ok": "Kesz",
            "failed": f"Hibara futott (exit {self.exit_code})",
        }[self.allapot]

    def adat(self) -> dict[str, Any]:
        veg = self.finished_at or dt.datetime.now()
        return {
            "id": self.id,
            "kulcs": self.kulcs,
            "cimke": self.cimke,
            "parancs": self.parancs,
            "fut": self.fut,
            "allapot": self.allapot,
            "allapot_cimke": self.allapot_cimke,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "seconds": round((veg - self.started_at).total_seconds(), 1),
            "exit_code": self.exit_code,
        }

    def sorok_tol(self, cursor: int) -> tuple[list[str], int]:
        """A `cursor` indextol kezdodo sorok, es az uj kurzor."""
        with self._lock:
            sorok = list(self.sorok)
            osszes = self.osszes_sor
        elso = osszes - len(sorok)
        start = max(cursor, elso)
        return sorok[start - elso:], osszes


def _parancs_szoveg(argv: list[str]) -> str:
    """Amit a terminalban gepelnel ugyanerre -- hogy a felulet es a CLI
    ugyanarra a futasra ugyanazt a nevet hasznalja."""
    return "./leadgen.sh " + " ".join(argv)


class MarFut(RuntimeError):
    """Fut mar egy job. A `job` mezo az, ami fut."""

    def __init__(self, job: Job) -> None:
        super().__init__(f"mar fut egy futas: {job.cimke}")
        self.job = job


class IsmeretlenParancs(KeyError):
    pass


class ErvenytelenParameter(ValueError):
    pass


# ─── Kezelo ────────────────────────────────────────────────────────────────

_KEZELO_LOCK = threading.Lock()
_futo: Job | None = None
_memoria: dict[str, Job] = {}
_memoria_sorrend: deque[str] = deque()


def futo() -> Job | None:
    """A MOST futo job, vagy None. A befejezodott job mar nem "futo" --
    a kimenete a `job(id)`-n keresztul marad elerheto."""
    with _KEZELO_LOCK:
        return _futo if (_futo is not None and _futo.fut) else None


def job(job_id: str) -> Job | None:
    with _KEZELO_LOCK:
        return _memoria.get(job_id)


def epit_argv(kulcs: str, params: dict[str, int] | None = None) -> list[str]:
    """A teljes CLI-argv, a keretek ervenyesitesevel.

    Az ERVENYESITES ITT VAN, nem a fronton: a felulet csak felkinalja a
    hatarokat, a betartatas szerver-oldali (WEBUI-TERV.md Invariansok #1).
    """
    parancs = _KULCS_SZERINT.get(kulcs)
    if parancs is None:
        raise IsmeretlenParancs(kulcs)

    ertekek = _alap_ertekek(parancs)
    for nev, ertek in (params or {}).items():
        if nev not in ertekek:
            raise ErvenytelenParameter(
                f"a(z) {kulcs!r} parancsnak nincs {nev!r} parametere")
        ertekek[nev] = int(ertek)

    argv = list(parancs.argv)
    for par in parancs.parameterek:
        ertek = ertekek[par.nev]
        if not (par.minimum <= ertek <= par.maximum):
            raise ErvenytelenParameter(
                f"{par.flag}: {ertek} kivul esik a megengedett "
                f"{par.minimum}..{par.maximum} tartomanyon")
        argv += [par.flag, str(ertek)]
    return argv


def indit(kulcs: str, params: dict[str, int] | None = None) -> Job:
    """Elinditja a KATALOGUSBAN szereplo parancsot. `MarFut`, ha mar fut valami.

    Ez az egyetlen ut, amit a `/api/jobs/start` elerhet. A kuldes
    szandekosan nincs a katalogusban, tehat ezen a fuggvenyen at nem is
    inditkato -- lasd `indit_kuldes()`.
    """
    parancs = _KULCS_SZERINT.get(kulcs)
    if parancs is None:
        raise IsmeretlenParancs(kulcs)
    argv = epit_argv(kulcs, params)
    return _inditas(
        kulcs=kulcs,
        cimke=parancs.cimke,
        argv=schedule.cli_parancs(argv),
        parancs=_parancs_szoveg(argv),
        cwd=config.BASE,
        env=schedule.cli_kornyezet(),
    )


# A kuldes job-kulcsa. SZANDEKOSAN nincs a `KATALOGUS`-ban: a
# `/api/jobs/start` csak katalogus-kulcsot fogad el, tehat ezt a futast
# egyedul a `webui/api/routers/send.py` tudja elinditani -- a ketlepcsos
# token-kapu UTAN (WEBUI-TERV.md Invariansok #2). Tesztsor orzi.
KULDES_KULCS = "send-live"


def indit_kuldes(limit: int = 0) -> Job:
    """`sender.py --live` a kuldo sajat interpreteren, elo kimenettel.

    ⚠️ EZT CSAK A TOKEN-KAPU UTAN SZABAD HIVNI. A fuggveny maga NEM ellenoriz
    tokent -- azt a `leadgen.send.token_beval()` teszi, a hivo oldalon. Itt
    egyetlen vedelmi reteg van: a kulcs nincs a katalogusban, tehat HTTP-n
    ez a fuggveny mas uton nem erheto el.

    A `-u` a kuldo oldalan is kell: enelkul a `sender.py` kimenete fajlba
    (a mi csovunkbe) iranyitva blokkosan pufferelne, es a kikuldes sorai
    csak a futas VEGEN jelennenek meg -- pont a leghosszabb es
    legfeszultebb futasnal (a kuldesi szunetek miatt percekig tart).
    """
    argv = ["python3", "-u", "sender.py", "--live"]
    if limit:
        argv += ["--limit", str(limit)]
    return _inditas(
        kulcs=KULDES_KULCS,
        cimke="Eles kuldes",
        argv=argv,
        parancs="cd cold-email-starter && " + " ".join(a for a in argv if a != "-u"),
        # A kuldo a SAJAT konyvtarabol, a SAJAT interpreteren fut (rendszer
        # python3 3.9.6, lapos importokkal) -- a venv Pythonjabol nem
        # importalhato (CLAUDE.md).
        cwd=config.SENDER_DIR,
        env=dict(os.environ, PYTHONUNBUFFERED="1"),
    )


def _inditas(kulcs: str, cimke: str, argv: list[str], parancs: str,
             cwd, env: dict[str, str]) -> Job:
    """A kozos inditas. EGY sorosito kapu mindket utnak.

    Azert kozos, mert az "egyszerre egy futas" szabaly a KETTO KOZOTT is
    ervenyes: egy export nem futhat kikuldes kozben (a `leads.csv`-t irna at
    a kuldo labai alatt), es forditva sem.
    """
    global _futo
    with _KEZELO_LOCK:
        if _futo is not None and _futo.fut:
            raise MarFut(_futo)
        uj = Job(id=uuid.uuid4().hex, kulcs=kulcs, cimke=cimke,
                 argv=argv, parancs=parancs, started_at=dt.datetime.now())
        _futo = uj
        _memoria[uj.id] = uj
        _memoria_sorrend.append(uj.id)
        while len(_memoria_sorrend) > MAX_MEMORIA_JOB:
            _memoria.pop(_memoria_sorrend.popleft(), None)

    # A `start_new_session=True` SAJAT FOLYAMATCSOPORTOT ad a futasnak. Enelkul
    # a megszakitas csak a kozvetlen gyereket allitana le -- a `daily` viszont
    # tovabbi alfolyamatokat indit (minden lepes kulon `leadgen.cli` futas),
    # es azok arvan tovabb futnanak, tovabb koltve AI- es Apify-kreditet.
    proc = subprocess.Popen(  # noqa: S603
        argv,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    uj._proc = proc
    threading.Thread(target=_olvaso, args=(uj, proc), daemon=True).start()
    return uj


def _olvaso(job_obj: Job, proc: subprocess.Popen) -> None:
    """A kimenet SORONKENT, meg futas kozben.

    Ez a fazis egesz ertelme: a naplonak menet kozben kell frissulnie, nem a
    vegen egyben. A `-u` a gyerek oldalan (schedule.cli_parancs), ez a szal a
    mienken -- a ketto egyutt adja az elo naplot.
    """
    try:
        assert proc.stdout is not None
        for sor in proc.stdout:
            with job_obj._lock:
                job_obj.sorok.append(sor.rstrip("\n"))
                job_obj.osszes_sor += 1
    finally:
        kod = proc.wait()
        job_obj.exit_code = kod
        job_obj.finished_at = dt.datetime.now()
        _elozmeny_ir(job_obj)


def megszakit(job_id: str) -> Job | None:
    """Leallitja a futast. None, ha nincs ilyen job (a hivo dolga 404-elni)."""
    j = job(job_id)
    if j is None:
        return None
    proc = j._proc
    if proc is None or not j.fut:
        return j
    j.megszakitva = True
    try:
        # A TELJES folyamatcsoport, nem csak a kozvetlen gyerek -- lasd az
        # `indit()` `start_new_session` kommentjet.
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        proc.terminate()
    return j


# ─── Elozmenyek ────────────────────────────────────────────────────────────


def _elozmeny_ir(job_obj: Job) -> None:
    adat = job_obj.adat()
    adat["started_at"] = job_obj.started_at.isoformat(timespec="seconds")
    adat["finished_at"] = (
        job_obj.finished_at.isoformat(timespec="seconds") if job_obj.finished_at else None)
    try:
        ELOZMENY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with ELOZMENY_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(adat, ensure_ascii=False) + "\n")
    except OSError:
        # Az elozmeny-naplo KENYELEM, nem igazsagforras: ha nem irhato, a
        # futas eredmenye attol meg megvan a memoriaban es a valaszban.
        pass


def elozmenyek(limit: int = 30) -> list[dict[str, Any]]:
    """A legutobbi befejezett futasok, ujak eloszor."""
    sorok = _elozmeny_sorok()
    out: list[dict[str, Any]] = []
    for sor in reversed(sorok[-limit * 2:]):
        try:
            out.append(json.loads(sor))
        except json.JSONDecodeError:
            continue
        if len(out) >= limit:
            break
    return out


def _elozmeny_sorok() -> list[str]:
    path: Path = ELOZMENY_PATH
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()
