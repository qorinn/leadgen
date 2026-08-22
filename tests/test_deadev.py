"""A 8.2 „halott fejleszto" felismeres tesztje.

MIERT ER EZ TESZTET (a repo szabalya: csak a NEMA hibak helyere irunk):

A felismeres eredmenye SZO SZERINT bekerul egy kimeno emailbe:

    "...feltunt, hogy a weboldalukat annak idejen az XY keszitette.
     Ugy tunik, ok mar nem mukodnek."

Ha ez teved, az nem apro pontatlansag, hanem kinos -- es semmi nem dob hibat
kozben. Ket iranyban lehet tevedni, es mindketto draga:

  hamis pozitiv -> rossz nevet irunk a levelbe (pl. a tarhelyszolgaltatoet,
                   vagy a ceg SAJAT szolgaltatas-menujet fejlesztonek nezve)
  hamis negativ -> elveszik a terv legerosebb objektiv signalja

AZ ALABBI ESETEK VALOS ADATBOL SZARMAZNAK. A 49 letoltott oldal footerein
merve: a puszta kulcsszo 7 helyen talalt, de ebbol csak 1 volt valodi kredit.
A tobbi 6 mindegyike kulon teszteset lett.
"""
import pytest

from leadgen import deadev, scoring


def _footer(belso: str) -> str:
    return f"<html><body><footer>{belso}</footer></body></html>"


class TestValodiKredit:
    def test_a_klasszikus_alak(self):
        html = _footer('© 2019 Pelda Kft. | Készítette: '
                       '<a href="https://xydesign.hu">XY Design</a>')
        k = deadev.kredit_a_footerbol(html, "pelda.hu")
        assert k is not None
        assert k.developer_domain == "xydesign.hu"
        assert k.developer_name == "XY Design"

    def test_a_valodi_eset_a_gyujtott_adatbol(self):
        """`marketingmost.hu` -> Infiniteq. Ez volt az EGYETLEN valodi
        kredit a 49 letoltott oldalon."""
        html = _footer('Leiratkozás © Minden jog fenntartva 2021 '
                       'Weboldalkészítés <a href="https://infiniteq.hu">Infiniteq</a>')
        k = deadev.kredit_a_footerbol(html, "marketingmost.hu")
        assert k is not None
        assert k.developer_domain == "infiniteq.hu"

    def test_az_idezet_megmarad_emberi_atnezeshez(self):
        html = _footer('Fejlesztette: <a href="https://abc.hu">ABC Web</a>')
        k = deadev.kredit_a_footerbol(html, "pelda.hu")
        assert "Fejlesztette" in k.idezet, (
            "a footer szo szerinti szovege nelkul az ember nem tudja ellenorizni")


class TestHamisPozitivok:
    """Mind a hat eset VALOS adatbol. Ha barmelyik atmenne, rossz nev kerulne
    egy kimeno levelbe."""

    def test_sajat_szolgaltatas_menu(self):
        """A leggyakoribb hiba (4 a 7-bol): a ceg footerében ott a SAJAT
        szolgaltatas-listaja, benne a "Weboldal keszites" menuponttal --
        ami a SAJAT domainjere mutat."""
        html = _footer('SEO Google Ads '
                       '<a href="https://amarketingese.hu/weboldal-keszites">'
                       'Weboldal készítés</a> Social media')
        assert deadev.kredit_a_footerbol(html, "amarketingese.hu") is None

    def test_relativ_link_a_sajat_oldalra(self):
        # Ugyanaz, de relativ URL-lel -- ilyen is van a valos adatban.
        html = _footer('Szolgáltatások: <a href="/weboldal-keszites">Weboldal készítés</a>')
        assert deadev.kredit_a_footerbol(html, "pelda.hu") is None

    def test_stock_foto_kredit(self):
        """`innowa.hu`: "Photo design by: Freepik" -- ez nem fejleszto."""
        html = _footer('Adatvédelem | ÁSZF Photo design by: '
                       '<a href="https://freepik.com">Freepik</a>')
        assert deadev.kredit_a_footerbol(html, "innowa.hu") is None

    def test_cms_kredit(self):
        html = _footer('Powered by <a href="https://wordpress.org">WordPress</a>')
        assert deadev.kredit_a_footerbol(html, "pelda.hu") is None

    def test_tarhelyszolgaltato_a_link_szovegeben(self):
        """`onlinemarketing.hu`: a "Hosting:" szo MAGABAN a link szovegeben
        van, nem elotte. Ezt a valos adat talalta meg."""
        html = _footer('© 2026 Pelda | Powered by WordPress '
                       '<a href="http://www.smartsector.hu/">Hosting: Smartsector</a>')
        assert deadev.kredit_a_footerbol(html, "pelda.hu") is None

    def test_tarhelyszolgaltato_a_link_elott(self):
        html = _footer('Készítette: Tárhely: <a href="https://rackhost.hu">Rackhost</a>')
        assert deadev.kredit_a_footerbol(html, "pelda.hu") is None

    def test_tavoli_link_nem_szamit(self):
        """Link-suru footerben barmelyik link "kozel" lehet. Egy valodi
        kreditben a nev KOZVETLENUL a kifejezes utan all."""
        tavol = "szoveg " * 30
        html = _footer(f'Powered by WordPress {tavol}'
                       f'<a href="https://valami.hu">Valami</a>')
        assert deadev.kredit_a_footerbol(html, "pelda.hu") is None

    def test_a_minta_elotti_link_nem_szamit(self):
        """A kredit "Keszitette: <link>" alaku -- a link a kifejezes UTAN jon.
        Egy elotte allo link mas footer-elem."""
        html = _footer('<a href="https://blog.hu">Blog</a> | Powered by WordPress')
        assert deadev.kredit_a_footerbol(html, "pelda.hu") is None


class TestNincsTalalat:
    def test_footer_nelkuli_oldal(self):
        assert deadev.kredit_a_footerbol("<html><body>semmi</body></html>", "x.hu") is None

    def test_kredit_nelkuli_footer(self):
        html = _footer('© 2026 Pelda Kft. Minden jog fenntartva. Adatvédelem')
        assert deadev.kredit_a_footerbol(html, "pelda.hu") is None

    def test_hibas_html_nem_dob(self):
        assert deadev.kredit_a_footerbol("<<<>>", "x.hu") is None

    def test_ures_bemenet(self):
        assert deadev.kredit_a_footerbol("", "x.hu") is None


class TestPontszamok:
    def test_a_terv_szerinti_ertekek(self):
        assert deadev.PONT["DEAD"] == 35
        assert deadev.PONT["DORMANT"] == 20

    def test_az_alive_nem_ad_pontot(self):
        # Az elo fejleszto nem teszi jobb leadde a ceget -- ot magat
        # tiltolistara tesszuk versenytarskent.
        assert deadev.PONT["ALIVE"] == 0


class TestLecsenges:
    """A terv "Lecsenges" fejezete (2560-2620)."""

    @pytest.mark.parametrize("nap,vart", [(0, 1.0), (7, 1.0), (8, 0.8),
                                          (30, 0.8), (31, 0.5), (90, 0.5),
                                          (91, 0.2), (180, 0.2), (181, 0.0)])
    def test_meredek_gorbe(self, nap, vart):
        assert scoring.szorzo(nap, "profession") == vart

    def test_a_lapos_gorbe_nem_nullazodik(self):
        """Egy elavult weboldal tegnap es ma is ugyanolyan elavult.
        Ha a lapos gorbe nullazodna, a strukturalis leadek egy ev utan
        csendben eltunnenek a sorbol."""
        assert scoring.szorzo(3000, "dead_dev") >= scoring.LAPOS_MINIMUM

    def test_a_halott_fejleszto_lassan_avul(self):
        # 200 nap utan a meredek gorben 0.0 lenne -- itt meg 0.9.
        assert scoring.szorzo(200, "dead_dev") > scoring.szorzo(200, "profession")

    def test_ismeretlen_forras_a_lapos_gorbet_kapja(self):
        """Biztonsagos alapertelmezes: inkabb tartsuk meg a leadet, mint
        hogy egy elgepelt source_type miatt csendben kiessen."""
        assert scoring.szorzo(100, "valami_uj_forras") == scoring.szorzo(100, "dead_dev")

    def test_negativ_kor_nem_dob(self):
        # Orakulonbseg / idozona miatt elofordulhat.
        assert scoring.szorzo(-5, "profession") == 1.0

    def test_a_ket_gorbe_egyezik_az_sql_valtozattal(self):
        """A gorbe ket helyen van leirva (Python es SQL). Ha csak az egyiket
        modositjak, a rendezes elcsuszna a riporttol -- hiba nelkul."""
        sql = scoring.sql_szorzo("kor", "forras")
        for hatar, ertek in scoring.MEREDEK_GORBE:
            assert f"when kor <= {hatar} then {ertek}" in sql
        for hatar, ertek in scoring.LAPOS_GORBE:
            assert f"when kor <= {hatar} then {ertek}" in sql
        for forras in scoring.MEREDEK_FORRASOK:
            assert f"'{forras}'" in sql
