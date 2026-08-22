"""Evidence grounding + offer arbitration tesztje.

MIERT ER EZ TESZTET (a repo szabalya: csak a NEMA hibak helyere irunk):

A terv szerint ez "a legveszelyesebb pont az egesz pipeline-ban". Ha az AI
kitalal egy tenyt, es az bekerul az emailbe, a hatas NEGATIV -- a cimzett
azonnal latja, hogy gepi es pontatlan. Egy generikus level unalmas; egy
magabiztosan TEVES szemelyre szabott level hiteltelenne tesz.

Es mindez NEMA: az AI ugyanolyan magabiztosan adja vissza a kitalalt idezetet,
mint a valodit. Semmi nem dob hibat.
"""
import pytest

from leadgen import grounding, score

FORRAS = ("Főbb feladatok: Munkalapok felvétele,  kezelése\nés nyomon követése. "
          "Kapcsolattartás a szerelőkkel a javítások menetéről.")


class TestIdezetEllenorzes:
    def test_szo_szerinti_idezet_atmegy(self):
        ok, _ = grounding.idezet_ervenyes(
            "Munkalapok felvétele, kezelése és nyomon követése", FORRAS)
        assert ok

    def test_mas_tordeles_atmegy(self):
        """Ugyanaz a mondat mas sortoressel NEM hallucinacio -- formazasi
        kulonbseg. Ha ezt bukasnak vennenk, minden modell megbukna."""
        ok, _ = grounding.idezet_ervenyes(
            "kezelése és nyomon követése", FORRAS)
        assert ok

    def test_kis_nagybetu_nem_szamit(self):
        ok, _ = grounding.idezet_ervenyes(
            "MUNKALAPOK FELVÉTELE, KEZELÉSE", FORRAS)
        assert ok

    def test_KITALALT_idezet_bukik(self):
        """A terv sajat peldaja: az AI a 'tobb megyeben vallalunk munkat'
        mondatbol kovetkeztetett harom telephelyre."""
        ok, indok = grounding.idezet_ervenyes(
            "kollégáink napi szinten 8-12 helyszínen végeznek karbantartást",
            FORRAS)
        assert not ok
        assert "NEM SZEREPEL" in indok

    def test_atfogalmazas_bukik(self):
        """Az atfogalmazas mar kovetkeztetes, nem idezet -- pontosan az,
        amit ki akarunk szurni."""
        ok, _ = grounding.idezet_ervenyes(
            "táblázatban vezetik a munkalapokat", FORRAS)
        assert not ok

    def test_reszleges_egyezes_atmegy(self):
        """A terv engedmenye: a modellek gyakran hozzatoldanak egy fel
        tagmondatot a vegehez. Az ELEJE viszont pontos szokott lenni."""
        idezet = "Munkalapok felvétele, kezelése és nyomon követése, továbbá EZ MAR NINCS BENNE"
        ok, indok = grounding.idezet_ervenyes(idezet, FORRAS)
        assert ok
        assert "reszleges" in indok

    def test_tul_rovid_idezet_bukik(self):
        """Egy 8 karakteres toredek szinte barmilyen szovegben megtalalhato,
        tehat atmenne az ellenorzesen anelkul, hogy barmit alatamasztana."""
        ok, indok = grounding.idezet_ervenyes("Munkalap", FORRAS)
        assert not ok
        assert "rovid" in indok

    @pytest.mark.parametrize("q", ["", None, "   "])
    def test_ures_idezet_bukik(self, q):
        assert grounding.idezet_ervenyes(q, FORRAS)[0] is False

    def test_ures_forras_eseten_bukik(self):
        # Ha nincs mihez hasonlitani, NEM allitjuk, hogy ervenyes.
        assert grounding.idezet_ervenyes("barmi hosszu idezet ide", "")[0] is False


class TestEllenorzoFuttatas:
    def test_a_rossz_allitast_dobja_el_nem_a_leadet(self):
        """Elsore az ALLITAS esik ki, nem a lead. A lead csak akkor, ha
        egyetlen alatamasztott allitas sem marad."""
        g = grounding.ellenoriz([
            {"claim": "jo", "quote": "Munkalapok felvétele, kezelése"},
            {"claim": "kitalalt", "quote": "harminc telephelyen dolgoznak naponta"},
        ], FORRAS)
        assert len(g.megtartott) == 1
        assert len(g.eldobott) == 1
        assert g.van_bizonyitek is True

    def test_ha_semmi_nem_marad_nincs_bizonyitek(self):
        g = grounding.ellenoriz(
            [{"claim": "x", "quote": "ez sehol nem szerepel a szovegben soha"}], FORRAS)
        assert g.van_bizonyitek is False
        assert g.bukas_arany == 1.0

    def test_ures_evidence_nem_dob(self):
        for bemenet in ([], None):
            assert grounding.ellenoriz(bemenet, FORRAS).van_bizonyitek is False

    def test_hibas_formatumot_nem_fogad_el(self):
        # Ha a modell stringet ad dict helyett, az NEM bizonyitek.
        g = grounding.ellenoriz(["csak egy string"], FORRAS)
        assert g.van_bizonyitek is False


class TestOfferArbitration:
    """A terv szabalya: egy ceg EGY kampanyba kerul."""

    def test_a_terv_peldaja(self):
        """website=75, webapp=92, mobile=38 -> WEBAPP nyer."""
        ajanlat, kampany, pont = score.arbitral(92, 75, 38)
        assert ajanlat == "webapp"
        assert kampany == "ops_pain"

    def test_a_website_is_tud_nyerni(self):
        ajanlat, kampany, _ = score.arbitral(20, 85, 0)
        assert ajanlat == "website"
        assert kampany == "dead_dev"

    def test_kuszob_alatt_nincs_kampany(self):
        """Ha egyik ajanlat sem eri el a kuszobot, NEM valasztunk
        'legkevesbe rosszat' -- a lead egyszeruen nem fit."""
        ajanlat, kampany, _ = score.arbitral(50, 40, 10)
        assert kampany == ""

    def test_dontetlennel_a_webapp_nyer(self):
        # A terv legerosebb engine-je, ott a legmagasabb a projekt-ertek.
        ajanlat, _, _ = score.arbitral(80, 80, 80)
        assert ajanlat == "webapp"

    def test_a_mobile_nem_kap_kampanyt(self):
        """Az app-store engine nincs megepitve, tehat nincs sablonja sem.
        Ha kampanyt adnank neki, a templates.for_campaign visszaesne az
        ALAPERTELMEZETT (ugynoksegi) sablonra -- egy KKV-nak teljesen
        ertelmetlen levelet kuldve."""
        ajanlat, kampany, _ = score.arbitral(10, 10, 95)
        assert ajanlat == "mobile"
        assert kampany == "", "sablon nelkuli ajanlatbol nem mehet level"

    def test_hianyzo_ertekek_nem_dobnak(self):
        assert score.arbitral(None, None, None)[1] == ""


class TestWebsiteFit:
    """A weboldal-fit NEM AI-bol jon -- a 8.2 halott fejleszto jelbol."""

    def test_a_dead_fejleszto_eros_jel(self):
        assert score.website_fit({"dev_state": "DEAD"}) >= score.FIT_KUSZOB

    def test_a_dormant_gyengebb(self):
        assert (score.website_fit({"dev_state": "DORMANT"})
                < score.website_fit({"dev_state": "DEAD"}))

    def test_az_alive_nem_ad_pontot(self):
        assert score.website_fit({"dev_state": "ALIVE"}) == 0

    def test_hianyzo_ertek_nem_dob(self):
        assert score.website_fit({}) == 0


class TestSablonKapu:
    """Vazlat sablonnal nem mehet ki eles level."""

    def test_csak_az_atnezett_kampany_van_jovahagyva(self):
        from leadgen.contract import APPROVED_CAMPAIGNS
        assert "agency_partner" in APPROVED_CAMPAIGNS
        assert "ops_pain" not in APPROVED_CAMPAIGNS, (
            "az ops_pain sablon meg VAZLAT -- a felhasznalonak at kell irnia")
        assert "dead_dev" not in APPROVED_CAMPAIGNS

    def test_minden_jovahagyott_kampanynak_van_sablonja(self):
        """Ha egy jovahagyott kampanyhoz nincs sablon, a
        templates.for_campaign csendben az alapertelmezettre esne vissza --
        es rossz szoveg menne ki."""
        import ast
        from pathlib import Path
        from leadgen.contract import APPROVED_CAMPAIGNS
        src = (Path(__file__).resolve().parent.parent
               / "cold-email-starter" / "templates.py").read_text(encoding="utf-8")
        for kampany in APPROVED_CAMPAIGNS:
            assert f'"{kampany}"' in src, f"nincs sablon a {kampany} kampanyhoz"
