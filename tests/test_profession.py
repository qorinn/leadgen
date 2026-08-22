"""A Profession.hu forras es a domain-feloldas tesztje.

MIERT ER EZ TESZTET (a repo szabalya: csak a NEMA hibak helyere irunk):

A domain a rendszer FO DEDUPE KULCSA. Ha a feloldas rossz domaint ad vissza,
akkor egy allashirdetes alapjan EGY MASIK CEGET keresnenk meg -- es a level
teljesen ertelmetlen lenne a cimzettnek. Semmi nem dobna hibat: a lead ugy
nezne ki, mint barmelyik masik.

Merve az eles futason (2026-08-22): a hirdetes szovegeben SOHA nem szerepelt
a ceg weboldala (12 hirdetesbol 0), tehat a "hasonlit-e a domain a cegnevre"
szabaly az egyetlen vedelem a veletlen talalatok ellen.
"""
import pytest

from leadgen import engines
from leadgen.sources import profession


class TestDomainASzovegbol:
    """1. lepcso: a hirdetes szovegeben szereplo weboldal (ingyen)."""

    def test_a_cegnevhez_illeszkedo_domaint_elfogadja(self):
        d = profession._domain_a_szovegbol(
            "Bovebb informacio: www.gumiprofi.hu oldalon.", "GUMI-PROFI TEAM Kft")
        assert d == "gumiprofi.hu"

    def test_semas_url_is_jo(self):
        d = profession._domain_a_szovegbol(
            "Latogasson el a https://palla-autojavito.hu oldalra!",
            "Palla Autójavító Kft.")
        assert d == "palla-autojavito.hu"

    def test_idegen_domaint_NEM_fogad_el(self):
        """A LEGFONTOSABB TESZT ITT.

        Egy hirdetesben sok URL szerepelhet: partner, szoftvernev, hirportal.
        Ha barmelyiket elfogadnank, egy MASIK CEG domainje kerulne be a
        leadhez -- es a level rossz cegnek menne.
        """
        szoveg = ("Munkank soran a sap.com rendszert hasznaljuk, "
                  "partnerunk a mol.hu, hirdetesunk az index.hu-n jelent meg.")
        assert profession._domain_a_szovegbol(szoveg, "Palla Autójavító Kft.") is None

    def test_profession_sajat_linkjet_kihagyja(self):
        assert profession._domain_a_szovegbol(
            "Jelentkezes: www.profession.hu/allas/123", "Profession Kft.") is None

    def test_ekezetes_cegnev_illeszkedik(self):
        # A domain ASCII, a cegnev ekezetes -- a normalizalasnak at kell hidalnia.
        d = profession._domain_a_szovegbol(
            "Honlapunk: autojavito.hu", "Autójavító Kft.")
        assert d == "autojavito.hu"

    def test_platform_domaint_kihagy(self):
        assert profession._domain_a_szovegbol(
            "Kovess minket: facebook.com/gumiprofi", "GUMI-PROFI TEAM Kft") is None

    @pytest.mark.parametrize("szoveg", ["", None, "semmi url nincs itt"])
    def test_ures_bemenet_nem_dob(self, szoveg):
        assert profession._domain_a_szovegbol(szoveg, "Valami Kft.") is None

    def test_ures_cegnev_eseten_nem_talalgat(self):
        # Cegnev nelkul nincs mihez hasonlitani -> inkabb semmit.
        assert profession._domain_a_szovegbol("www.valami.hu", "") is None

    def test_rovid_szavakra_nem_illeszt(self):
        """A 4 karakternel rovidebb szavak (Kft, Bt, es) veletlen egyezest
        adnanak szinte barmelyik domainre."""
        assert profession._domain_a_szovegbol(
            "Nezze meg a bt-kereso.hu oldalt", "BT Kft.") is None


class TestEngineDefinicio:
    def test_az_ops_pain_letezik(self):
        assert "ops_pain" in engines.ALL_ENGINES

    def test_alapbol_KI_van_kapcsolva(self):
        """A minosites nelkul (10. szakasz) nem szabad leadet kiadni belole.

        Ha ez valaha `True` lenne a sablonok es az AI-classifier elott, a
        hirdetesekbol azonnal kimenne level -- minosites nelkul."""
        assert engines.ALL_ENGINES["ops_pain"].enabled is False

    def test_a_kikapcsolt_engine_qualifyra_hibat_dob(self):
        with pytest.raises(SystemExit):
            engines.get("ops_pain")

    def test_a_kizaras_NEM_versenytarsat_jelent(self):
        """Egy 'programozo' pozíciót hirdeto ceg nem versenytars, csak nem
        fit. Ha versenytarskent kezelnenk, veglegesen tiltolistara kerulne."""
        assert engines.ALL_ENGINES["ops_pain"].qualifier.exclude_means_competitor is False

    def test_a_valos_hirdetes_szovege_atmenne_a_szuron(self):
        """A 0.3 elotesztbol szo szerint vett szoveg (Palla Autojavito Kft.).
        Ha a kulcsszolista elcsuszna, a valodi talalatok nemán kiesnenek."""
        from leadgen.engines import fold
        szoveg = fold(
            "Ügyfelekkel történő telefonos és e-mailes kapcsolattartás "
            "Gépjárművek átvételéhez kapcsolódó adminisztráció elvégzése "
            "Munkalapok felvétele, kezelése és nyomon követése")
        eng = engines.ALL_ENGINES["ops_pain"]
        assert any(k in szoveg for k in eng.qualifier.require_any), (
            "a valos hirdetes-szoveg nem illeszkedik egyetlen kulcsszora sem")


class TestForrasAllandok:
    def test_a_source_type_stabil(self):
        """Az inkrementalitas a (source_type, source_url) parosra epul.
        Ha a source_type megvaltozna, MINDEN korabbi hirdetes ujra
        feldolgozodna -- es ujra fizetnenk ertuk."""
        assert profession.SOURCE_TYPE == "profession"

    def test_az_actor_azonosito_rogzitve_van(self):
        # A 0.3 eloteszt EZT az actort merte. Masik actor mas mezoket ad.
        assert profession.ACTOR == "solidcode/profession-hu-scraper"
