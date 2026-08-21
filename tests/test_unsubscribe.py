"""A leiratkozo link felepitesenek tesztje.

MIERT ER EZ TESZTET (a repo szabalya: csak a NEMA hibak helyere irunk):

Ha ez a fuggveny rosszul mukodik, semmi nem dob kivetelt. Harom nema
kimenetel van, es mind a harom draga:

  1. Torott link megy ki -> a cimzett rakattint, nem tortenik semmi, es
     jogosan gondolja, hogy atvertek. Egy cold emailben ez a legrosszabb,
     ami tortenhet: pontosan ugy nez ki, mint egy adathalasz level.
  2. URES link megy ki, fallback NELKUL -> a level kilepesi lehetoseg nelkul
     erkezik, ami a GDPR 6(1)(f) jogalap felteteleit serti.
  3. Rossz token kerul a linkbe -> valaki MAST iratunk le.
"""
import pytest

from leadgen import contract, export

TOKEN = "287f9366-bd19-4249-a62d-9cfb2ac9a8a7"


@pytest.fixture
def base(monkeypatch):
    def _set(value):
        monkeypatch.setattr(export.config, "UNSUB_BASE_URL", value)
    return _set


class TestUnsubUrl:
    def test_osszefuzi_a_tokent(self, base):
        base("https://paladi-web.hu/leiratkozas")
        assert export.unsub_url(TOKEN) == f"https://paladi-web.hu/leiratkozas/{TOKEN}"

    def test_a_zaro_perjel_nem_duplikal(self, base):
        # Ez pontosan az a reszlet, amit ket helyen ketfelekeppen irnank meg.
        base("https://paladi-web.hu/leiratkozas/")
        assert export.unsub_url(TOKEN) == f"https://paladi-web.hu/leiratkozas/{TOKEN}"

    def test_nincs_base_url_eseten_ures(self, base):
        # Nem kivetel, nem placeholder: ures string -> a sablon fallbackre esik.
        base("")
        assert export.unsub_url(TOKEN) == ""

    def test_nincs_token_eseten_ures(self, base):
        base("https://paladi-web.hu/leiratkozas")
        assert export.unsub_url(None) == ""
        assert export.unsub_url("") == ""

    @pytest.mark.parametrize("rossz", [
        "http://paladi-web.hu/leiratkozas",     # nem titkositott
        "http://localhost:8888/leiratkozas",    # fejlesztoi cim eles levelben
        "paladi-web.hu/leiratkozas",            # sema nelkul
    ])
    def test_nem_https_cimet_elutasit(self, base, rossz):
        # Inkabb NE legyen link, mint torott link: a fallback mondat
        # regimodi, de mukodik.
        base(rossz)
        assert export.unsub_url(TOKEN) == ""


def test_az_unsub_url_benne_van_a_kontraktusban():
    """Ha a mezo kiesne a fejlecbol, az export csendben nem irna ki, es
    minden level a fallback mondattal menne -- hiba nelkul."""
    assert "unsub_url" in contract.LEADS_HEADER
