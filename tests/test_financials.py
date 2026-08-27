"""7.1 penzugyi enrichment -- a nema hibak elleni tesztek.

A penzugyi adat hibai NEM dobnak kivetelt: egy ezer forintban ertett
arbevetel csendben LOW-ba teszi a ceget, egy ketszer lefuttatott import
csendben megduplazza a signal_score bonuszt. Ezert van ide teszt.
"""
import ast
from pathlib import Path

import pytest

from leadgen import config, financials

REPO = Path(__file__).resolve().parent.parent
MIGRATION = REPO / "leadgen" / "migrations" / "011_financials.sql"


def _kod(modul) -> str:
    """A modul forrasa KOMMENT es DOCSTRING nelkul.

    Miert kell: az alabbi tesztek tiltott szavakat keresnek a kodban ("altcha",
    "rejected"). Ezek a szavak a MAGYARAZO SZOVEGBEN is elofordulnak -- pont
    azert, mert a fejlec elmagyarazza, miert nem szabad oket hasznalni. Nyers
    szoveges keresessel tehat a sajat dokumentacionk buktatna el a tesztet.
    Az `ast.unparse` a kommenteket eldobja, a valodi string-literalokat
    (pl. SQL-t) viszont megtartja -- pont ez kell.
    """
    fa = ast.parse(Path(modul.__file__).read_text(encoding="utf-8"))
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


# ─── economic_value ────────────────────────────────────────────────────────

def test_magas_arbevetel_high():
    assert financials.economic_value(config.REVENUE_HIGH_HUF, 2) == "HIGH"


def test_a_letszam_onmagaban_is_emel():
    """Egy 30 fos ceg akkor is komoly szervezet, ha alacsony az arrese."""
    assert financials.economic_value(1_000_000, config.HEADCOUNT_HIGH) == "HIGH"
    assert financials.economic_value(1_000_000, config.HEADCOUNT_MEDIUM) == "MEDIUM"


def test_kozepes_es_alacsony():
    assert financials.economic_value(config.REVENUE_MEDIUM_HUF, 1) == "MEDIUM"
    assert financials.economic_value(5_000_000, 1) == "LOW"


def test_adat_nelkul_nincs_ertek():
    """Hianyzo adat nem LOW. A LOW allitas, a None viszont bevallott nemtudas."""
    assert financials.economic_value(None, None) is None


# ─── bonusz ────────────────────────────────────────────────────────────────

def test_high_bonusz_15():
    assert financials.bonus("HIGH", config.REVENUE_HIGH_HUF, None) == 15


def test_dobozos_webshop_bonusz_osszeadodik():
    """Terv 2512 + 2518: +15 magas arbevetel, +25 dobozos webshop + magas arbevetel."""
    assert financials.bonus("HIGH", config.REVENUE_HIGH_HUF, "Shoprenter") == 40


def test_a_webshop_bonusz_kuszobhoz_kotott():
    kicsi = config.WEBSHOP_REVENUE_MIN_HUF - 1
    assert financials.bonus("LOW", kicsi, "Shoprenter") == 0


def test_low_ceg_nem_kap_bonuszt():
    assert financials.bonus("LOW", 1_000_000, None) == 0


# ─── szamertelmezes ────────────────────────────────────────────────────────

@pytest.mark.parametrize("nyers,vart", [
    ("350000000", 350_000_000),
    ("350 000 000", 350_000_000),
    ("350.000.000", 350_000_000),
    ("350000000 Ft", 350_000_000),
    (" 350000000", 350_000_000),
    ("", None),
    (None, None),
])
def test_szam_ertelmezese(nyers, vart):
    assert financials._szam(nyers) == vart


def test_az_ertelmezhetetlen_szam_hiba_nem_nulla():
    """A csendes nulla ugy nezne ki, mint egy valodi, nullas arbevetel."""
    with pytest.raises(ValueError):
        financials._szam("kb. otszazmillio")


# ─── Az ezer-forint csapda ─────────────────────────────────────────────────

def test_az_ezer_forintos_ertek_gyanus(tmp_path, monkeypatch):
    """A beszamolo urlapja "adatok E Ft-ban" -- ez a leggyakoribb eliras.

    350000 beirva 350 M Ft helyett: a ceg csendben LOW lenne. Az importer
    ezt nem javitja ki (nem talalhat ki adatot), de HANGOSAN szol rola.
    """
    csv_path = tmp_path / "w.csv"
    csv_path.write_text(
        "company_id,company_name,revenue_huf,headcount\n"
        ",Pelda Kft.,350000,4\n", encoding="utf-8")
    monkeypatch.setattr(financials, "_azonosit", lambda sor: None)
    stats = financials.import_csv(csv_path, dry=True, verbose=False)
    assert stats.ezer_forint_gyanu, "a gyanusan kicsi arbevetel nem lett megjelolve"


# ─── Az importer parositasa ────────────────────────────────────────────────

def test_cegnev_szerint_nem_parositunk():
    """Fuzzy nevegyezes rossz ceghez irna arbevetelt -- onnan pedig az mar
    egy levelbe kerulo teves allitas."""
    azonosit = _kod(financials).split("def _azonosit(")[1].split("\ndef ")[0]
    assert "company_name" not in azonosit
    for kulcs in ("company_id", "tax_number", "normalized_domain"):
        assert kulcs in azonosit


# ─── A megorzo leadmodell ──────────────────────────────────────────────────

def test_a_penzugyi_adat_nem_zar_ki_leadet():
    """2026-08-25: nincs "csak MEDIUM+ megy outreachbe" kapu. A modul
    semmilyen uton nem allithat `rejected` vagy `suppressed` statuszt."""
    kod = _kod(financials)
    # OLVASNI szabad a statuszt (a worklist kihagyja a mar tiltott cegeket) --
    # IRNI nem. A kulonbseg pontosan ez a ket allitas.
    assert "status =" not in kod, "a penzugyi modul nem irhat `status`-t"
    assert "insert into suppression" not in kod


def test_a_hianyzo_adat_csak_cimke():
    kod = _kod(financials)
    assert "financials_missing" in kod
    jelold = kod.split("def jelold_hianyzonak(")[1].split("\ndef ")[0]
    assert "status" not in jelold


# ─── A 0.3 eloteszt eredmenye: NINCS portal-lekeres ────────────────────────

def test_a_modul_nem_kerdezi_le_a_portalt():
    """A Felhasznalasi Feltetelek szerint a captcha megkerulese nevesitett,
    feljelentessel jaro eset -- es a rendeltetesszeru hasznalat definicioja
    (hitelezovedelmi cel) sem fedi a cellista-epitest.

    Ha egy kesobbi valtoztatas HTTP-klienst hoz be ebbe a modulba, az szinte
    biztosan a portal automatikus lekerdezese. Ez a teszt akkor hasal el."""
    kod = _kod(financials)
    for tiltott in ("import httpx", "import requests", "urllib.request", "altcha"):
        assert tiltott not in kod, f"tiltott portal-lekeres: {tiltott}"


def test_a_worklist_fejlece_tartalmazza_a_kitoltendo_mezoket():
    for mezo in ("revenue_huf", "headcount", "financial_year"):
        assert mezo in financials.WORKLIST_HEADER
    # A kereses_url nelkul a kezi munka lassabb, mint amennyi ido a
    # generalasaba telik.
    assert "kereses_url" in financials.WORKLIST_HEADER


# ─── A migracio ────────────────────────────────────────────────────────────

def test_a_migracio_nem_torol():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "drop column" not in sql
    assert "delete from" not in sql


def test_a_migracio_taroja_az_alkalmazott_bonuszt():
    """Enelkul minden ujrafuttatas ujra hozzaadna a +15/+25 pontot."""
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "financial_bonus" in sql


def test_a_migracio_vedi_az_economic_value_ertekeit():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "companies_economic_value_check" in sql
    for ertek in ("'low'", "'medium'", "'high'"):
        assert ertek in sql


def test_a_bonusz_frissites_idempotens():
    """A `ment()` a regi bonuszt levonja, mielott az ujat hozzaadna."""
    ment = _kod(financials).split("def ment(")[1].split("\ndef ")[0]
    assert "regi_bonusz" in ment
    assert "signal_score = greatest(coalesce(signal_score, 0) - %s + %s, 0)" in ment
