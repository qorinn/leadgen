"""A minosites tesztjei.

MIERT ER TESZTET: ez donti el, hogy egy ceg lead lesz-e, versenytars, vagy
emberi atnezesre kerul. Mindket iranyu hiba nema:
  - tul szigoru  -> jo ugynoksegeket dobunk el (a celcsoport VEGES, 100-300 ceg)
  - tul megengedo -> versenytarsaknak irunk partner-ajanlatot
Egyik sem dob kivetelt, es csak a valodi weboldalakon latszana.
"""
import pytest

from leadgen import engines

AGENCY = engines.AGENCY_PARTNER.qualifier


class TestEkezetkezeles:
    def test_ekezetes_szoveg_illeszkedik(self):
        # A kulcsszolistak ASCII-ban vannak, a magyar oldalak ekezetesek.
        assert AGENCY.check("Keresőoptimalizálás és kampánykezelés").ok

    def test_kis_es_nagybetu(self):
        assert AGENCY.check("PPC KAMPÁNYOK").ok


class TestJoLead:
    @pytest.mark.parametrize("szoveg", [
        "PPC kampányok, SEO és tartalommarketing",
        "Google Ads kezelés és közösségi média",
        "Branding, arculat, marketing stratégia",
    ])
    def test_tiszta_marketing_ugynokseg(self, szoveg):
        q = AGENCY.check(szoveg)
        assert q.ok and q.hits


class TestErosKizaras:
    """Ezek egyertelmuen sajat fejlesztoi kapacitasra utalnak -> azonnal versenytars."""

    @pytest.mark.parametrize("szoveg", [
        "SEO szolgáltatás és egyedi fejlesztés",
        "PPC kezelés, saját fejlesztő csapatunkkal",
        "Marketing és szoftverfejlesztés",
        "Google Ads és React alapú alkalmazások",
    ])
    def test_azonnal_versenytars(self, szoveg):
        q = AGENCY.check(szoveg)
        assert not q.ok
        assert q.is_competitor is True
        assert q.needs_review is False


class TestGyengeKizaras:
    """Ezek gyakran ugyfel-referenciaban vagy blogcikkben szerepelnek.

    Valos eset (2026-08-21, elso eles futas): a plus-kreativ.hu-nal a
    "webfejlesztesi feladatokat" kifejezes egy UGYFEL velemenyeben allt --
    "...managelik a portfoliónkhoz tartozó ... webfejlesztési feladatokat.
    Dr. Imre Máté CEO, Pannon Disztributor Kft." Automatikus kizarassal egy
    jo leadet vesztettunk volna el, csendben.
    """

    def test_emberi_dontesre_kerul_nem_kizarasra(self):
        q = AGENCY.check("Branding és kreatív kampányok, valamint webfejlesztés")
        assert not q.ok
        assert q.needs_review is True
        assert q.is_competitor is False

    def test_marketing_jel_nelkul_viszont_kizar(self):
        # Ha nincs marketing-kulcsszo, akkor ez nem ugynokseg, hanem webstudio.
        q = AGENCY.check("Weboldal készítés és webshop készítés")
        assert not q.ok
        assert q.needs_review is False
        assert q.is_competitor is True

    def test_az_eros_jel_eroősebb_a_gyengenel(self):
        q = AGENCY.check("SEO, webfejlesztés és saját fejlesztő csapat")
        assert q.is_competitor is True and q.needs_review is False


class TestNemFit:
    def test_nem_marketinges_ceg(self):
        q = AGENCY.check("Könyvelés és bérszámfejtés kisvállalkozásoknak")
        assert not q.ok and not q.is_competitor and not q.needs_review


class TestPersonalizacio:
    def test_csak_megtalalt_kulcsszora_utal(self):
        """Ez ingyenes evidence grounding: a mondat csak olyan szolgaltatast
        emlit, amit SZO SZERINT megtalaltunk az oldalon."""
        q = AGENCY.check("PPC kampányok és keresőoptimalizálás")
        mondat = engines.AGENCY_PARTNER.personalization(q, {})
        assert "PPC" in mondat or "keresőoptimalizálás" in mondat
        assert "fejlesztést viszont nem" in mondat

    def test_ures_talalatnal_sem_omlik_ossze(self):
        mondat = engines.AGENCY_PARTNER.personalization(
            engines.QualifyResult(ok=True, reason=""), {})
        assert mondat and "{" not in mondat


class TestKonfiguralhatosag:
    """Az iparag ADAT legyen, ne kod -- uj vertikum = uj EngineDef blokk."""

    def test_van_kikapcsolt_pelda_definicio(self):
        assert "field_service" in engines.ALL_ENGINES
        assert engines.ALL_ENGINES["field_service"].enabled is False

    def test_kikapcsolt_engine_nem_futtathato(self):
        with pytest.raises(SystemExit):
            engines.get("field_service")

    def test_ismeretlen_engine_beszedes_hibat_ad(self):
        with pytest.raises(SystemExit):
            engines.get("nincs-ilyen")
