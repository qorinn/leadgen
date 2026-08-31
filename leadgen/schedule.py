#!/usr/bin/env python3
"""A napi lanc es az utemezese (12. szakasz).

KET DOLOG VAN EBBEN A FAJLBAN:

  napi_lanc()  -- a napi lepesek egymas utan, egy paranccsal (`leadgen daily`)
  telepit()    -- launchd bejegyzes, hogy a lanc magatol induljon

─────────────────────────────────────────────────────────────────────────────
MI FUT ES MI NEM -- FELHASZNALOI DONTES (2026-08-27):

A scraper-oldal megy utemezetten, a KULDES NEM. A `sender.py --live` es a
`deliverability.py` kimarad a lancbol: a kikuldes visszafordithatatlan, es a
level a te nevedben megy ki. Ez nem technikai korlat, hanem munkamegosztas
(CLAUDE.md) -- a gep elokeszit, az ember kuld.

Amikor a valaszaranyt es a bounce-okat mar stabilnak latod, a kuldes
felveheto lesz a lancba: egy `Lepes("send", [...])` bejegyzes a `lepesek()`
vegere. A `telepit()` kimenete kiirja azt a ket parancsot, ami most kezi
marad -- hogy egy honap mulva se kelljen kitalalni, mi hianyzik a lancbol.

─────────────────────────────────────────────────────────────────────────────
MIERT launchd ES NEM cron (macOS):

A cron egy alvo gepen KIHAGYJA a futast, es soha nem potolja be. Egy
laptopnal ez azt jelenti, hogy a 07:30-as ingest minden olyan napon
elmarad, amikor a gep 07:30-kor csukva volt -- vagyis a legtobb napon,
csendben. A launchd `StartCalendarInterval` viszont a felebredes utan
BEPOTOLJA a kihagyott futast. Ez pontosan az a kulonbseg, amitol az
"automatikus" szo igaz lesz.

─────────────────────────────────────────────────────────────────────────────
A LANC HIBAKEZELESE -- A LEGFONTOSABB DONTES ITT:

Egy lepes hibaja NEM allitja meg a tobbit, KIVEVE ha a kesobbi lepes a
hibas lepes eredmenyere epul. Ket kulon eset:

  - `ingest` elszall (Apify kimaradas) -> a tobbi lepes ATTOL MEG FUT,
    mert van meg feldolgozatlan ceg a DB-ben tegnaprol. Megallni itt azt
    jelentene, hogy egy kulso szolgaltatas kimaradasa az egesz napot
    kiesteti.

  - `feedback` elszall -> az `export` NEM FUT. Ez a rendszer egyik
    invariansa (CLAUDE.md): feedback nelkul exportalni annyi, mint
    ujra kikuldeni annak, aki tegnap nemet mondott. Ezt az `export.run()`
    maga is kikenyszeriti; a lanc csak nem kerulheti meg.

A vegen MINDIG fut a riasztas-ellenorzes, akkor is, ha kozben minden
elszallt -- pont akkor van a legnagyobb szukseg ra.
"""
from __future__ import annotations

import datetime
import os
import plistlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import config

# A launchd bejegyzes azonositoja es helye. A forditott-domain nev a macOS
# konvencioja; a `leadgen` vegzodes teszi felismerhetove a `launchctl list`
# kimeneteben.
LABEL = "hu.paladi-web.leadgen.daily"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"

# A lanc INDULASI IDEJE. A terv 07:30-tol 09:00-ig szort szet negy lepest;
# itt egyetlen futas van, mert a lepesek sorrendben egymasra epulnek es
# egyutt is percek alatt lefutnak. Negy kulon utemezes csak azt kockaztatna,
# hogy az egyik lepes meg fut, amikor a kovetkezo indul.
INDULAS_ORA = 7
INDULAS_PERC = 30

# A napi kimenet ide megy. A launchd sajat stdout-ja kulonben elveszne.
LOG_PATH = config.SENDER_DATA / "leadgen_daily.log"


def _ki(szoveg: str = "") -> None:
    """Kiiras AZONNALI kiuritessel.

    Ugyanaz az indok, mint a `_futtat()` `-u` kapcsolojanal: a launchd
    naplojaba irva a sima `print` blokkosan pufferel, es a lanc sajat
    fejlecei ("[3/7] score ...") csak a vegen jelennenek meg -- pont a
    tajekozodast lehetetlenitve el egy hosszu futas kozben.
    """
    print(szoveg, flush=True)


@dataclass
class Lepes:
    """A lanc egy lepese.

    `kotelezo`: ha ez elszall, a lanc HATRALEVO resze kimarad. Csak ott
    igaz, ahol a kesobbi lepes helyessege fugg tole (lasd a modul fejlecet).
    """
    nev: str
    argv: list[str]
    magyarazat: str
    kotelezo: bool = False


@dataclass
class LancEredmeny:
    futott: list[str] = field(default_factory=list)
    hibas: list[tuple[str, int]] = field(default_factory=list)
    kihagyott: list[str] = field(default_factory=list)


def lepesek(limit: int = 0, skip_ingest: bool = False) -> list[Lepes]:
    """A napi lanc lepesei, sorrendben.

    A SORREND NEM CSEREHETO FEL: minden lepes a megelozo kimenetebol dolgozik
    (uj ceg -> enrichelt ceg -> minositett ceg -> exportalt lead).
    """
    out: list[Lepes] = []

    if not skip_ingest:
        # FIZETOS LEPES (~$0.005/talalat). A `--max-results` a koltsegfek:
        # egy elszabadult ciklus igy sem tud tobb szazat elkolteni egy nap.
        out.append(Lepes(
            "ingest", ["ingest", "maps", "--max-results", "50"],
            "uj cegek a Google Mapsrol (FIZETOS, keret: 50 talalat)"))

    out += [
        Lepes("enrich", ["enrich", "--limit", "50"],
              "weboldalak feldolgozasa (`new` -> `enriched`)"),
        # A `qualify` a `pipeline.run_qualify`-t hivja: kulcsszo-alapu,
        # AI-hivas nelkuli dontes `enriched` -> `ready`/`review`/`scored`/
        # `suppressed` kozott, az `--engine` sajat kulcsszavai szerint. A
        # `--engine` alapertelmezese (`agency_partner`) egyezik az EGYETLEN
        # ma aktiv engine-nel (`engines.ALL_ENGINES`), ezert nem kell itt
        # kulon megadni -- ha valaha tobb aktiv engine lenne, ezt a lepest
        # boviteni kell.
        #
        # KORABBAN EZ HIANYZOTT A LANCBOL: az `enrich` utan a cegek
        # `enriched` allapotban vartak, es semmi nem vitte oket tovabb
        # `ready`/`review` fele, amig valaki kezzel le nem futtatta a
        # `qualify`-t. Az ops_pain engine-t ez nem erinti: az a `score`
        # lepesen (AI-utvonal) keresztul mar most is automatikusan kapja
        # meg a sajat `ready`/`scored` dontesét.
        Lepes("qualify", ["qualify", "--limit", "50"],
              "minosites (`enriched` -> `ready`/`review`/`scored`)"),
        Lepes("dead-dev", ["enrich", "dead-dev", "--limit", "50"],
              "8.2: ki keszitette a weboldalt, es el-e meg"),
        Lepes("score", ["score", "--limit", "50"],
              "AI-minosites + evidence grounding"),
        Lepes("webshop", ["webshop-growth", "--limit", "50"],
              "8.3: dobozos webshop platform felismerese"),
        # A feedback KOTELEZO: enelkul az export ujra kikuldene annak, aki
        # tegnap nemet mondott. Az `export.run()` maga is kikenyszeriti, de
        # a lanc se kerulhesse meg.
        Lepes("feedback", ["feedback"],
              "a kuldo CSV-inek beolvasasa (KOTELEZO az export elott)",
              kotelezo=True),
        Lepes("classify-replies", ["classify-replies", "--limit", "50"],
              "AI valasz-osztalyozas (a `feedback` altal behozott valaszokra)"),
    ]

    export_argv = ["export"]
    if limit:
        export_argv += ["--limit", str(limit)]
    out.append(Lepes("export", export_argv,
                     "DB -> leads.csv (a kuldo innen dolgozik)"))
    return out


def napi_lanc(dry: bool = False, limit: int = 0, skip_ingest: bool = False) -> int:
    """A napi lepesek egymas utan. Visszateres: 0 = rendben, 1 = volt hiba.

    MIERT SUBPROCESS ES NEM KOZVETLEN FUGGVENYHIVAS: minden lepes sajat
    folyamatban fut, tehat egy lepes osszeomlasa (memoria, elszallt kulso
    hivas) nem viszi magaval a lancot. A CLI mar minden lepesre ad
    belepesi pontot -- ugyanazt hivjuk, amit te is kezzel hivnal, tehat
    nincs ket kulon ut, ami szetcsuszhatna.
    """
    from . import alerts

    sorozat = lepesek(limit=limit, skip_ingest=skip_ingest)
    eredmeny = LancEredmeny()

    _ki(f"NAPI LANC -- {datetime.datetime.now().isoformat(timespec='seconds')}")
    _ki(f"{len(sorozat)} lepes\n")

    if dry:
        for i, lepes in enumerate(sorozat, 1):
            jel = "  [KOTELEZO]" if lepes.kotelezo else ""
            _ki(f"  {i}. {lepes.nev:<18} {lepes.magyarazat}{jel}")
            _ki(f"     ./leadgen.sh {' '.join(lepes.argv)}")
        _ki(f"\n  {len(sorozat) + 1}. alert            riasztasok ellenorzese (MINDIG fut)")
        _ki("\n(--dry: semmit nem futtattunk)")
        _ki("\nA KULDES SZANDEKOSAN NEM RESZE A LANCNAK:")
        _ki("  cd cold-email-starter && python3 sender.py --dry   # nezd at")
        _ki("  cd cold-email-starter && python3 sender.py --live  # EMBER inditja")
        return 0

    megallt = False
    for i, lepes in enumerate(sorozat, 1):
        if megallt:
            eredmeny.kihagyott.append(lepes.nev)
            continue

        _ki(f"\n{'=' * 68}\n[{i}/{len(sorozat)}] {lepes.nev} -- {lepes.magyarazat}\n{'=' * 68}")
        kod = _futtat(lepes.argv)

        if kod == 0:
            eredmeny.futott.append(lepes.nev)
            continue

        eredmeny.hibas.append((lepes.nev, kod))
        _ki(f"\n!! A(z) `{lepes.nev}` lepes hibara futott (exit {kod}).")
        if lepes.kotelezo:
            # Nem "csendben tovabb": a kesobbi lepesek helyessege fugg tole.
            _ki("   Ez KOTELEZO lepes -- a lanc hatralevo resze KIMARAD.")
            _ki("   (feedback nelkul exportalni annyi, mint ujra kikuldeni")
            _ki("    annak, aki tegnap nemet mondott)")
            megallt = True
        else:
            _ki("   A lanc tovabb megy: van meg feldolgozatlan ceg tegnaprol,")
            _ki("   es egy kulso szolgaltatas kimaradasa ne essen ki egy egesz napot.")

    # A RIASZTAS MINDIG FUT, akkor is, ha fent minden elszallt -- pont
    # olyankor a legfontosabb. A `skip_deliverability=True` azert kell, mert
    # a `deliverability.py` IMAP-ot nyit es a ramp-ertekelest is elvegzi:
    # az a kuldesi ablak zarasa utan, az esti futasban a helye, nem reggel.
    _ki(f"\n{'=' * 68}\n[riasztas] a nap allapotanak ellenorzese\n{'=' * 68}")
    try:
        alerts.run(skip_deliverability=True)
    except Exception as exc:  # noqa: BLE001
        _ki(f"A riasztas-ellenorzes hibara futott: {type(exc).__name__}: {exc}")
        eredmeny.hibas.append(("alert", 1))

    _osszefoglalo(eredmeny)
    return 1 if eredmeny.hibas else 0


def _futtat(argv: list[str]) -> int:
    """Egy CLI-lepes sajat folyamatban, a venv Pythonjaval.

    A `-u` (unbuffered) NEM ELHAGYHATO. A Python fajlba iranyitva blokkosan
    pufferel, tehat egy launchd-bol futo lanc naploja PERCEKIG URES marad, es
    a mar lefutott lepesek kimenete csak a folyamat vegen jelenik meg. Elesben
    merve: 5 perc futas utan a naplo meg mindig csak az elso lepest mutatta.
    Egy beragadt lancnal pont ez a legrosszabb: nem latszik, HOL akadt el --
    ami az egesz naplozas celja lenne.

    A `PYTHONUNBUFFERED` a gyerekfolyamatoknak is szol; a sajat kimenetunket
    a `flush=True` viszi ki (lasd `_ki()`).
    """
    proc = subprocess.run(
        cli_parancs(argv), cwd=config.BASE, env=cli_kornyezet(),
    )
    return proc.returncode


def cli_parancs(argv: list[str]) -> list[str]:
    """A CLI egy lepesenek teljes parancssora, a venv Pythonjaval.

    KULON FUGGVENY, mert ket hivoja van: a napi lanc (`_futtat`) es a webes
    felulet job-kezeloje (`webui/api/jobs.py`, F6). Ha a ketto kulon epitene
    fel a parancsot, egy nap az egyik `-u` nelkul indulna -- es pont az elo
    naplo (a felulet egesz ertelme) allna le, csendben.
    """
    return [str(config.BASE / ".venv" / "bin" / "python"),
            "-u", "-m", "leadgen.cli", *argv]


def cli_kornyezet() -> dict[str, str]:
    """A gyerekfolyamat kornyezete. A `PYTHONUNBUFFERED` az EGESZ folyamatfara
    hat -- a lanc sajat fejlecere is, nem csak a lepesekere."""
    return dict(os.environ, PYTHONUNBUFFERED="1")


def _osszefoglalo(e: LancEredmeny) -> None:
    _ki(f"\n{'=' * 68}\nOSSZEFOGLALO\n{'=' * 68}")
    _ki(f"  lefutott : {len(e.futott)}  ({', '.join(e.futott) or '-'})")
    if e.hibas:
        _ki(f"  HIBAS    : {len(e.hibas)}  "
              + ", ".join(f"{nev} (exit {kod})" for nev, kod in e.hibas))
    if e.kihagyott:
        _ki(f"  kihagyva : {len(e.kihagyott)}  ({', '.join(e.kihagyott)})")
    _ki("\n  A mai kep:  ./leadgen.sh report --daily")
    _ki("  A kuldes (EMBER inditja):")
    _ki("    cd cold-email-starter && python3 sender.py --dry")


# ─── launchd ───────────────────────────────────────────────────────────────

def _plist_dict() -> dict:
    """A launchd bejegyzes tartalma.

    HAROM DOLOG, AMI ITT SZANDEKOS:

    1. `RunAtLoad` = False. A telepites pillanataban NE induljon el egy
       fizetos (Apify) futas -- azt te inditsd, amikor keszen allsz ra.

    2. A `PATH` KEZZEL VAN MEGADVA. A launchd nagyon szuk kornyezettel indit,
       amiben nincs benne a Homebrew (`/opt/homebrew/bin`). A lanc a rendszer
       `python3`-jat is hivja (a kuldo allapotahoz), tehat a `/usr/bin` is
       kell. E nelkul a futas "command not found"-dal halna el, es csak a
       logbol derulne ki -- napokkal kesobb.

    3. `StandardOutPath` / `StandardErrorPath`. A launchd kimenete kulonben
       elveszik. Ez a fajl az elso hely, ahova egy nem futo lanc eseten
       nezni kell.
    """
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(config.BASE / "leadgen.sh"), "daily",
        ],
        "WorkingDirectory": str(config.BASE),
        "StartCalendarInterval": {"Hour": INDULAS_ORA, "Minute": INDULAS_PERC},
        "RunAtLoad": False,
        "StandardOutPath": str(LOG_PATH),
        "StandardErrorPath": str(LOG_PATH),
        "EnvironmentVariables": {
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": str(Path.home()),
            # A NAPLO KULONBEN PERCEKIG URES MARAD. A Python fajlba iranyitva
            # blokkosan pufferel, es a `leadgen.sh` a venv Pythont `-u` nelkul
            # inditja (helyesen: azt ember is futtatja terminalbol). Elesben
            # merve: 50 masodperc futas utan a launchd naploja meg mindig
            # teljesen ures volt. Egy beragadt lancnal pont az nem latszana,
            # HOL akadt el. Kornyezeti valtozokent az EGESZ folyamatfara hat,
            # tehat a lanc sajat fejlecere is, nem csak a lepesekere.
            "PYTHONUNBUFFERED": "1",
        },
    }


def telepit_adat() -> dict:
    """A tenyleges telepites (launchd plist iras + betoltes), dict-kent
    (webui F10 -- "Utemezes" telepites gomb). A `--dry` elonezet a
    `telepit()`-ben marad: az csak a CLI-nek szol, oldalhatas nelkul, tehat
    nincs ertelme az API-n keresztul elerhetove tenni.
    """
    plist = _plist_dict()
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Ha mar be van toltve, eloszor kivesszuk: a `load` egy mar betoltott
    # labelre hibat ad, es a regi (esetleg mas idopontu) bejegyzes maradna
    # eletben. Az `unload` hibajat elnyeljuk -- ha nem volt betoltve, az nem hiba.
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)],
                   capture_output=True, text=True)
    PLIST_PATH.write_bytes(plistlib.dumps(plist))

    proc = subprocess.run(["launchctl", "load", str(PLIST_PATH)],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        return {"ok": False, "hiba": proc.stderr.strip()}
    return {"ok": True, "hiba": None}


def telepit(dry: bool = False) -> int:
    plist = _plist_dict()
    tartalom = plistlib.dumps(plist).decode("utf-8")

    if dry:
        print(f"Ide kerulne: {PLIST_PATH}\n")
        print(tartalom)
        print(f"Indulas: minden nap {INDULAS_ORA:02d}:{INDULAS_PERC:02d}")
        print("\n(--dry: nem telepitettunk)")
        return 0

    eredmeny = telepit_adat()
    if not eredmeny["ok"]:
        print(f"HIBA: a launchctl load nem sikerult:\n{eredmeny['hiba']}")
        return 1

    print(f"Telepitve: {PLIST_PATH}")
    print(f"A napi lanc minden nap {INDULAS_ORA:02d}:{INDULAS_PERC:02d}-kor indul.")
    print(f"A kimenete ide kerul: {LOG_PATH}")
    print("\nAMI NEM FUT MAGATOL (szandekosan):")
    print("  cd cold-email-starter && python3 sender.py --live   # a KULDES")
    print("  cd cold-email-starter && python3 deliverability.py  # az esti jelentes")
    print("\nEllenorzes:  ./leadgen.sh schedule status")
    print("Eltavolitas: ./leadgen.sh schedule uninstall")
    return 0


def eltavolit_adat() -> dict:
    """A tenyleges eltavolitas, dict-kent (webui F10 -- eltavolitas gomb)."""
    if not PLIST_PATH.exists():
        return {"ok": True, "volt_telepitve": False}
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)],
                   capture_output=True, text=True)
    PLIST_PATH.unlink()
    return {"ok": True, "volt_telepitve": True}


def eltavolit() -> int:
    eredmeny = eltavolit_adat()
    if not eredmeny["volt_telepitve"]:
        print(f"Nincs telepitve (nincs ilyen fajl: {PLIST_PATH})")
        return 0
    print(f"Eltavolitva: {PLIST_PATH}")
    print("A napi lanc tovabbra is futtathato kezzel: ./leadgen.sh daily")
    return 0


def allapot_adat() -> dict:
    """Fut-e az utemezes, es mit mond a legutobbi futas -- dict-kent (F1).

    Ugyanaz a szetvalasztas, mint a `report.py`-ban: az `/api/schedule/status`
    ezt hivja, az `allapot()` ezt irja ki -- egy igazsag, ket megjelenites.
    """
    if not PLIST_PATH.exists():
        return {"installed": False, "loaded": False, "launchctl_lines": [],
                "start_time": f"{INDULAS_ORA:02d}:{INDULAS_PERC:02d}",
                "log_path": str(LOG_PATH), "log_last_written": None,
                "log_last_lines": []}

    proc = subprocess.run(["launchctl", "list", LABEL],
                          capture_output=True, text=True)
    loaded = proc.returncode == 0
    launchctl_lines: list[str] = []
    if loaded:
        for sor in proc.stdout.splitlines():
            if '"LastExitStatus"' in sor or '"PID"' in sor:
                launchctl_lines.append(sor.strip().rstrip(";"))

    log_last_written = None
    log_last_lines: list[str] = []
    if LOG_PATH.exists():
        log_last_written = datetime.datetime.fromtimestamp(
            LOG_PATH.stat().st_mtime).isoformat(timespec="minutes")
        sorok = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        log_last_lines = sorok[-5:]

    return {
        "installed": True, "loaded": loaded,
        "launchctl_lines": launchctl_lines,
        "start_time": f"{INDULAS_ORA:02d}:{INDULAS_PERC:02d}",
        "log_path": str(LOG_PATH),
        "log_last_written": log_last_written,
        "log_last_lines": log_last_lines,
    }


def allapot() -> int:
    """Be van-e toltve, es mit mond a legutobbi futas."""
    adat = allapot_adat()
    print(f"plist : {PLIST_PATH}")
    if not adat["installed"]:
        print("        NINCS TELEPITVE")
        print("\nTelepites: ./leadgen.sh schedule install")
        return 0

    if adat["loaded"]:
        print("        telepitve es BETOLTVE")
        # A launchctl kimenetebol a ket erdekes sor: az utolso kilepesi kod
        # es a PID (ha epp fut).
        for sor in adat["launchctl_lines"]:
            print(f"        {sor}")
    else:
        print("        a fajl megvan, de NINCS BETOLTVE")
        print("        Betoltes: ./leadgen.sh schedule install")

    print(f"\nindulas: minden nap {adat['start_time']}")
    print(f"naplo  : {adat['log_path']}")
    if adat["log_last_written"]:
        print(f"         utoljara irva: {adat['log_last_written']}")
        if adat["log_last_lines"]:
            print("\n  az utolso 5 sor:")
            for sor in adat["log_last_lines"]:
                print(f"    {sor}")
    else:
        print("         (meg nem futott)")
    return 0
