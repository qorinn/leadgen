"""Tesztek a normalizalasra es a platform-blocklistre.

MIERT CSAK EZEKRE: a projekt tobbi resze halozatot vagy adatbazist hasznal,
ott a szakaszvegi kezi ellenorzes tobbet er, mint egy mockolt teszt. A
normalizalas viszont tiszta fuggveny, ES a hibai nemak -- ket ceg csendben
osszeolvad, vagy egy ceg ketszer kap levelet. Ez az a hely, ahol a teszt
tenyleg megter.
"""
import pytest

from leadgen import blocklist, normalize


class TestNormalizeDomain:
    @pytest.mark.parametrize("raw", [
        "https://www.example.hu",
        "http://example.hu/",
        "shop.example.hu",
        "example.hu/contact",
        "HTTPS://WWW.EXAMPLE.HU/kapcsolat?utm=1#x",
        "  example.hu  ",
        "www.example.hu.",
    ])
    def test_mind_ugyanarra_a_kulcsra_esik(self, raw):
        assert normalize.normalize_domain(raw) == "example.hu"

    def test_hu_masodszintu_suffix_nem_olvad_ossze(self):
        # A naiv "utolso ket cimke" szabaly ezeket mind shop.hu-ra vinne,
        # es minden shop.hu alatti ceg egyetlen ceggé olvadna.
        assert normalize.normalize_domain("elso.shop.hu") == "elso.shop.hu"
        assert normalize.normalize_domain("masodik.shop.hu") == "masodik.shop.hu"
        assert normalize.normalize_domain("a.b.co.hu") == "b.co.hu"

    def test_tobbszintu_kulfoldi_suffix(self):
        assert normalize.normalize_domain("www.valami.co.uk") == "valami.co.uk"

    @pytest.mark.parametrize("raw", ["", "   ", "nincs-benne-pont", "co.hu", "hu", None])
    def test_ertelmetlen_bemenetre_none(self, raw):
        assert normalize.normalize_domain(raw) is None


class TestNormalizeCompanyName:
    @pytest.mark.parametrize("raw", [
        "Paládi Klíma Kft.",
        "PALÁDI KLÍMA KFT",
        "Paládi Klíma Korlátolt Felelősségű Társaság",
        "  paladi   klima  kft  ",
        "Paládi-Klíma Kft.",
    ])
    def test_mind_ugyanarra_a_kulcsra_esik(self, raw):
        assert normalize.normalize_company_name(raw) == "paladi klima"

    def test_tarsasagi_formak(self):
        assert normalize.normalize_company_name("Teszt Bt.") == "teszt"
        assert normalize.normalize_company_name("Teszt Zrt.") == "teszt"
        assert normalize.normalize_company_name("Teszt Nonprofit Kft.") == "teszt"

    def test_ures(self):
        assert normalize.normalize_company_name("") is None
        assert normalize.normalize_company_name("Kft.") is None


class TestNormalizePhone:
    @pytest.mark.parametrize("raw", [
        "+36 30 123 4567", "06301234567", "0036/30-123-4567", "+36301234567",
    ])
    def test_mobil(self, raw):
        assert normalize.normalize_phone(raw) == "+36301234567"

    def test_vezetekes(self):
        assert normalize.normalize_phone("06 1 234 5678") == "+3612345678"

    @pytest.mark.parametrize("raw", ["", "1234", "abc", "12"])
    def test_hihetetlen_hosszra_none(self, raw):
        assert normalize.normalize_phone(raw) is None


class TestNormalizeEmail:
    def test_azonos_szabaly_mint_a_kuldoben(self):
        # A kuldo mindenhol .strip().lower()-t hasznal. Ha ez eltérne,
        # a feedback-import csendben nem talalna ra a leadre.
        assert normalize.normalize_email("  INFO@Pelda.HU ") == "info@pelda.hu"

    @pytest.mark.parametrize("raw", ["", "nincs-kukac", "a@b", "a@@b.hu"])
    def test_ervenytelen(self, raw):
        assert normalize.normalize_email(raw) is None

    @pytest.mark.parametrize("raw", [
        "%20peter@mpmarketing.hu",   # URL-kodolt szokoz egy mailto: linkbol
        ".peter@pelda.hu",           # vezeto pont (a regexp elotte alloszoveget kapott)
        "peter.@pelda.hu",           # zaro pont
        "pe..ter@pelda.hu",          # ketto pont egymas utan
        "peter@pelda_hu.hu",         # alahuzas a domainben
        "peter@-pelda.hu",           # kotojellel kezdodo cimke
        "árvíz@pelda.hu",            # ekezet
    ])
    def test_biztos_bounce_alaku_cimek(self, raw):
        # Ezek mind ATMENTEK a korabbi ([^@\s]+) mintan. Eles kuldesnel hard
        # bounce-t okoztak volna, az pedig VISSZAMENOLEG rontja a kuldo domain
        # reputaciojat -- utana a jo leadeknek sem erkezik meg a level.
        assert normalize.normalize_email(raw) is None

    @pytest.mark.parametrize("raw", [
        "kis.eszter@pelda.hu", "peter+cimke@pelda.hu", "info@al.pelda.co.uk",
        "b_a-lint@pelda.hu",
    ])
    def test_valodi_cimek_atmennek(self, raw):
        # A szigoritas masik oldala: egy JO cim elvesztese dragabb, mint egy
        # felrement level, mert a celcsoport veges.
        assert normalize.normalize_email(raw) == raw


class TestPlatformBlocklist:
    @pytest.mark.parametrize("raw", [
        "facebook.com/paladiklima",
        "https://www.instagram.com/valamiceg",
        "cegnev.wixsite.com/home",
        "cegnev.business.site",
        "linktr.ee/valami",
        "cylex.hu/ceg/x",
    ])
    def test_platform(self, raw):
        assert blocklist.is_platform(raw) is True

    @pytest.mark.parametrize("raw", ["paladi-web.hu", "https://www.klima.hu", "valami.shop.hu"])
    def test_nem_platform(self, raw):
        assert blocklist.is_platform(raw) is False

    def test_platformbol_nem_lesz_company_key(self):
        # EZ A LENYEG: kulonben minden Facebook-oldalas ceg egyetlen
        # "facebook.com" nevu ceggé olvadna, es a tobbi nemán eltunne.
        a = blocklist.resolve_company_key(
            website="facebook.com/elsoceg", company_name="Első Cég Kft.", city="Szeged")
        b = blocklist.resolve_company_key(
            website="facebook.com/masodikceg", company_name="Második Cég Kft.", city="Pécs")
        assert a.normalized_domain is None and b.normalized_domain is None
        assert a.value != b.value
        assert a.platform_url and b.platform_url   # de a signal megmarad


class TestResolveCompanyKey:
    def test_a_domain_nyer(self):
        key = blocklist.resolve_company_key(
            website="https://www.klima.hu", tax_number="12345678", company_name="X Kft.")
        assert (key.kind, key.value) == ("domain", "klima.hu")

    def test_fallback_sorrend(self):
        assert blocklist.resolve_company_key(tax_number="12345678-2-42").kind == "tax"
        assert blocklist.resolve_company_key(company_name="X Kft.", city="Szeged").kind == "name_city"
        assert blocklist.resolve_company_key(phone="+36301234567").kind == "phone"
        assert blocklist.resolve_company_key().kind == "none"

    def test_kulcs_nelkul_nem_hasznalhato(self):
        assert blocklist.resolve_company_key().usable is False
