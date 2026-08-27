"""12. szakasz -- utemezes, riasztas, fajl-zarolas: a NEMA hibak elleni tesztek.

MIERT PONT EZEK A TESZTEK: a 12. szakasz minden hibaja nema. A rendszer
attol fut, hogy a cron elindul; ha kozben rosszul dontunk, semmi nem dob
kivetelt -- csak nem tortenik meg valami:

  - a lanc atugorja a `feedback`-et  -> ujra levelet kap, aki nemet mondott
  - a riasztas minden nap ujra kimegy -> megtanulod figyelmen kivul hagyni
  - a `--live` bekerul a lancba       -> a gep kuld a te nevedben
  - a fajl-zarolas kimarad            -> felig kiirt CSV-sor a sent.csv-ben

Ezek egyike sem latszik egy futas kimenetebol. Ezert van ide teszt.
"""
import ast
from pathlib import Path

from leadgen import alerts, schedule

REPO = Path(__file__).resolve().parent.parent
SENDER = REPO / "cold-email-starter"


def _kod(modul_vagy_ut) -> str:
    """A forras KOMMENT es DOCSTRING nelkul.

    Ugyanaz a minta, mint a test_financials.py-ban: az alabbi tesztek tiltott
    szavakat keresnek a kodban ("--live", "rejects=0"), es ezek a MAGYARAZO
    SZOVEGBEN is elofordulnak -- pont azert, mert a fejlec elmagyarazza, miert
    nem szabad oket hasznalni. Nyers szoveges keresessel tehat a sajat
    dokumentacionk buktatna el a tesztet.

    A `.py` ut is elfogadhato, mert a kuldo moduljai (cold-email-starter/)
    nem importalhatok innen: mas interpreteren futnak, lapos importokkal.
    """
    ut = Path(getattr(modul_vagy_ut, "__file__", modul_vagy_ut))
    fa = ast.parse(ut.read_text(encoding="utf-8"))
    for node in ast.walk(fa):
        if not isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        test = node.body[0] if node.body else None
        if (isinstance(test, ast.Expr) and isinstance(test.value, ast.Constant)
                and isinstance(test.value.value, str)):
            node.body.pop(0)
            if not node.body:
                node.body.append(ast.Pass())
    return ast.unparse(ast.fix_missing_locations(fa))


# ─── A napi lanc ───────────────────────────────────────────────────────────

def test_a_lanc_soha_nem_kuld_eles_levelet():
    """A `--live` NEM kerulhet be a napi lancba.

    EZ A LEGFONTOSABB TESZT AZ EGESZ SZAKASZBAN. A felhasznaloi dontes
    (2026-08-27) az, hogy a scraper-oldal fut utemezetten, a kikuldes viszont
    ember kezeben marad: a level a felhasznalo neveben megy ki, es
    visszafordithatatlan. Egy kesobbi "csak beteszem a lancba is" modositas
    ezt csendben megforditana -- a kovetkezmenyt pedig a cimzettek postafiokja
    mutatna meg eloszor, nem egy hibauzenet.
    """
    # A TENYLEGESEN VEGREHAJTOTT parancsokat nezzuk, nem a forras szoveget.
    # A `napi_lanc()` kiirja emlekeztetokent azt a ket parancsot, ami kezi
    # marad ("sender.py --live") -- az egy print, nem futtatas. Ha a forrasban
    # keresnenk a "--live" szot, pont ez a HASZNOS emlekezteto buktatna el a
    # tesztet, es a javitas az lenne, hogy toroljuk. Rossz oszton: a teszt
    # azt vedje, hogy a lanc mit CSINAL, ne azt, hogy mit ir ki.
    argv_szoveg = _lepes_argv_szoveg()
    assert "--live" not in argv_szoveg, "a napi lanc NEM indithat eles kuldest"
    assert "sender" not in argv_szoveg, \
        "a kuldo scriptje nem lehet a lanc lepesei kozott"
    assert "deliverability" not in argv_szoveg, \
        "a kezbesitesi orjarat a kuldesi ablak zarasa utan fut, nem a reggeli lancban"

    # ...es azt is, hogy a lanc egyaltalan a leadgen CLI-t hivja, ne shellt
    for lepes in schedule.lepesek():
        assert lepes.argv and not any("|" in a or ";" in a for a in lepes.argv), \
            f"a(z) {lepes.nev} lepes nem lehet shell-parancs"


def _lepes_argv_szoveg() -> str:
    """A lanc TENYLEGES parancsai (nem a magyarazo szovegek)."""
    return " ".join(" ".join(l.argv) for l in schedule.lepesek())


def test_a_feedback_kotelezo_es_megelozi_az_exportot():
    """A sorrend es a `kotelezo` jelzes egyutt vedi a rendszer invariansat.

    "A feedback-import kotelezo az export elott; ha hibara fut, az export
    exit 1-gyel megall." (CLAUDE.md) Ha a feedback nem `kotelezo`, a lanc
    egy elszallt feedback utan is exportalna -- vagyis ujra kikuldene annak,
    aki tegnap nemet mondott. Ez nem dobna hibat: a lanc "sikeresen" lefutna.
    """
    nevek = [l.nev for l in schedule.lepesek()]
    assert "feedback" in nevek and "export" in nevek
    assert nevek.index("feedback") < nevek.index("export"), \
        "a feedback-nek MEG KELL ELOZNIE az exportot"

    feedback = next(l for l in schedule.lepesek() if l.nev == "feedback")
    assert feedback.kotelezo, \
        "a feedback hibaja utan a lancnak MEG KELL ALLNIA (kotelezo=True)"


def test_az_ingest_nem_kotelezo():
    """Egy kulso szolgaltatas kimaradasa ne essen ki egy egesz napot.

    Az `ingest` az Apify-tol fugg. Ha ez `kotelezo` lenne, egy Apify-kimaradas
    az enrichmentet, a minositest ES az exportot is elvinne -- pedig azoknak
    van mibol dolgozniuk a tegnapi cegekbol.
    """
    ingest = next((l for l in schedule.lepesek() if l.nev == "ingest"), None)
    assert ingest is not None
    assert not ingest.kotelezo


def test_a_skip_ingest_kihagyja_a_fizetos_lepest():
    """A `--skip-ingest` a koltsegfek: legyen igaz, amit iger."""
    nevek = [l.nev for l in schedule.lepesek(skip_ingest=True)]
    assert "ingest" not in nevek
    # ...de a tobbi lepes megmarad, kulonben nem lenne ertelme
    assert "export" in nevek and "enrich" in nevek


# ─── A riasztasok ──────────────────────────────────────────────────────────

def test_a_riasztas_email_hibaja_nem_dob_kivetelt(monkeypatch):
    """Egy SMTP-kimaradas NEM nyelheti el a riasztast.

    Ez a modul legfontosabb hibakezelesi dontese: az emailkuldes pont akkor
    nem mukodik, amikor a legnagyobb szukseg lenne ra. Ha az `_emailben()`
    kivetelt dobna, a hivo oldal elszallna -- es a riasztas, ami mar a
    fajlban es a DB-ben van, ugy tunne el, mintha meg sem tortent volna.
    """
    def robban(*a, **kw):
        raise OSError("szimulalt SMTP-kimaradas")

    monkeypatch.setattr(alerts.config, "ALERT_EMAIL", "teszt@example.invalid")
    monkeypatch.setattr(alerts.config, "sender_smtp_accounts",
                        lambda: [{"user": "a@b.hu", "password": "x"}])
    monkeypatch.setattr(alerts.smtplib, "SMTP_SSL", robban)
    monkeypatch.setattr(alerts.smtplib, "SMTP", robban)

    r = alerts.Riasztas("k", "t", "uzenet", {})
    hiba = alerts._emailben([r])          # nem dobhat
    assert "szimulalt SMTP-kimaradas" in hiba, \
        "a hibat VISSZA kell adni, hogy naplozni lehessen"


def test_nincs_alert_email_eseten_sem_dob():
    """Beallitatlan ALERT_EMAIL mellett a riasztas naplozasa tovabb mukodik."""
    import unittest.mock as mock
    with mock.patch.object(alerts.config, "ALERT_EMAIL", ""):
        assert alerts._emailben([alerts.Riasztas("k", "t", "u", {})])


def test_a_visszafordithatatlan_cimkek_nem_riasztasi_tipusok():
    """A riasztas SOHA nem allit at ceg-allapotot.

    A riasztas megfigyeles, nem beavatkozas. Ha valaha suppressionbe tudna
    tenni egy ceget (pl. "nem valaszolt, zarjuk le"), az egy nema, automatikus
    es visszafordithatatlan dontes lenne -- pont az, amit a rendszer tobbi
    resze harom vedelmi reteggel kerul.
    """
    kod = _kod(alerts)
    for tiltott in ("insert into suppression", "update companies",
                    "delete from companies"):
        assert tiltott not in kod.lower(), \
            f"a riasztas-modul nem irhat cegallapotot ({tiltott})"


def test_a_cooldown_nem_nulla():
    """Fekezes nelkul ugyanaz a riasztas minden nap ujra kimenne.

    A `NOTIFY_COOLDOWN_ORA = 0` szintaktikailag helyes, es semmi nem jelezne
    -- csak harom nap mulva tennel szurot a sajat riasztasaidra.
    """
    assert alerts.NOTIFY_COOLDOWN_ORA >= 1


# ─── A kuldo oldal: fajl-zarolas es a reject-naplo ─────────────────────────

def _sender_modul(nev: str) -> str:
    """A kuldo egy moduljanak forrasa, KOMMENT NELKUL -- lasd `_kod()`."""
    return _kod(SENDER / f"{nev}.py")


def _sender_nyers(nev: str) -> str:
    """A nyers forras, kommentekkel egyutt (az ASCII-teszthez kell)."""
    return (SENDER / f"{nev}.py").read_text(encoding="utf-8")


def test_a_store_minden_irast_zarol():
    """A `_append` es a `_read` flock nelkul felig kiirt sort eredmenyezhet.

    A 12. szakasz ota ket folyamat ir a `data/` ala: a leadgen lanca
    (launchd) es a kuldo (kezi inditas). A `store._append` sima szoveges
    hozzafuzes -- lock nelkul ket egyideju iras egymasba csuszhat. A serult
    sor nem dob hibat: a sent.csv-bol szarmazik a napi volumen ES a
    szekvencia-fok, tehat csendben rossz levelet kuldene ki.
    """
    kod = _sender_modul("store")
    assert "import fcntl" in kod
    for fn in ("def _append", "def _read"):
        assert fn in kod
    # A zarolo segedfuggveny letezik es hasznaljak is
    assert "_locked(" in kod
    assert kod.count("_locked(") >= 3, \
        "az irasnak ES az olvasasnak is zarolnia kell"


def test_a_reject_naplo_letezik_es_a_ramp_hasznalja():
    """A ramp vak foltja (a terv 6. pontja).

    A `deliverability.py` korabban FIXEN nullat adott at az elutasitasoknak,
    ezert a REJECT_RATE_ALERT kuszob soha nem sult el. Ez nem latszott
    semmilyen kimeneten: a rendszer ugy nezett ki, mintha nulla elutasitas
    lenne -- pedig csak nem merte oket.
    """
    store_kod = _sender_modul("store")
    assert "def record_reject" in store_kod
    assert "def rejects_today_count" in store_kod

    sender_kod = _sender_modul("sender")
    assert "store.record_reject(" in sender_kod, \
        "a sender.py hibaagan naplozni kell az elutasitast"

    deliv_kod = _sender_modul("deliverability")
    assert "rejects=0" not in deliv_kod.replace(" ", ""), \
        "a hardcode-olt nulla visszakerult -- a ramp megint vak lenne"
    assert "rejects=rep[" in deliv_kod.replace(" ", "")


def test_a_ket_reject_rate_ugyanazt_a_nevezot_hasznalja():
    """A `limits.evaluate_ramp` es a `deliverability.daily_report` egy szamot
    szamol -- ha szetcsusznak, a riport mast mutat, mint amire a ramp lep.

    Mindketto a MEGKISERELT kuldessel oszt (`sent + rejects`), nem a
    sikeressel: 20 kiserletbol 20 elutasitas eseten a `sent` nulla lenne, es
    pont a legsulyosabb eset adna 0%-ot.
    """
    for nev in ("limits", "deliverability"):
        kod = _sender_modul(nev).replace(" ", "")
        assert "sent+rejects" in kod, \
            f"a {nev}.py nem a megkiserelt kuldessel oszt"


def test_a_store_ascii_marad():
    """A `.py` fajlokban a magyar szoveg ekezet nelkul all (CLAUDE.md).

    Ezt kezzel konnyu elrontani, es semmi nem jelzi -- a fajl attol meg fut.
    """
    for nev in ("store", "sender", "deliverability", "limits"):
        for i, sor in enumerate(_sender_nyers(nev).splitlines(), 1):
            gyanus = [c for c in sor if ord(c) > 127 and c not in "─➜"]
            assert not gyanus, f"{nev}.py:{i} nem-ASCII karakter: {gyanus}"


# ─── A launchd bejegyzes ───────────────────────────────────────────────────

def test_a_plist_nem_indul_el_telepiteskor():
    """`RunAtLoad=False`: a telepites ne inditson azonnal FIZETOS futast."""
    assert schedule._plist_dict()["RunAtLoad"] is False


def test_a_plist_path_ja_tartalmazza_a_homebrew_utat():
    """A launchd nagyon szuk kornyezettel indit.

    A venv Pythonja Homebrew-alapu, es a lanc a rendszer `python3`-jat is
    hivja (a kuldo allapotahoz). PATH nelkul a futas "command not found"-dal
    halna el -- es ez csak a logbol derulne ki, napokkal kesobb.
    """
    path = schedule._plist_dict()["EnvironmentVariables"]["PATH"]
    for kell in ("/opt/homebrew/bin", "/usr/bin"):
        assert kell in path


def test_a_plist_naploz():
    """launchd-kimenet naplo nelkul elveszik -- egy nem futo lancnal ez az
    elso hely, ahova nezni kell."""
    p = schedule._plist_dict()
    assert p["StandardOutPath"] and p["StandardErrorPath"]


# ─── A reject-import (feedback) ────────────────────────────────────────────

def test_a_reject_szamlalo_nem_inkrementalodik():
    """A `send_reject_count` beallitodik, NEM novekszik.

    A `feedback` watermarkja nullazodhat (ha a CSV megrovidul), es olyankor
    ugyanazokat a sorokat megegyszer feldolgozzuk. `oszlop + 1` alakban irva
    a szamlalo felfele torzulna -- egy egeszseges cim ugy nezne ki, mint egy
    halott, es a rangsor csendben elromlana. Ugyanaz a hiba, amit a
    `financial_bonus` elkerul a 011-es migracioban.

    Elesben merve (2026-08-27): ugyanaz a 2 soros rejects.csv ketszer
    feldolgozva 2-t adott, nem 4-et.
    """
    from leadgen import feedback

    kod = _kod(feedback)
    # A tiltott minta: a szamlalo sajat magabol szamolva
    assert "send_reject_count = send_reject_count" not in kod, \
        "a reject-szamlalot BEALLITANI kell, nem inkrementalni"
    assert "send_reject_count + " not in kod


def test_a_reject_nem_tesz_suppressionbe():
    """Az SMTP-elutasitas a KULDO oldalarol szol, nem a cegrol.

    Suppressionbe tenni egy leadet azert, mert a mi szerverunk epp limitbe
    utkozott, csendben megsemmisitene a listat. A megorzo leadmodell
    (2026-08-25) szerint valodi tiltas csak leiratkozas, negativ valasz,
    hard bounce, meglevo ugyfel, kezi tiltas vagy versenytars lehet.
    """
    import ast as _ast
    from leadgen import feedback

    forras = Path(feedback.__file__).read_text(encoding="utf-8")
    fa = _ast.parse(forras)
    fn = next(n for n in _ast.walk(fa)
              if isinstance(n, _ast.FunctionDef) and n.name == "_import_rejects")
    torzs = _ast.unparse(fn).lower()
    for tiltott in ("suppression", "_suppress", "status = 'suppressed'"):
        assert tiltott not in torzs, \
            f"a reject-import nem tehet suppressionbe ({tiltott})"
