"""8.3 webshop-felismeres -- a MERT hamis pozitivok regresszios tesztjei.

Minden `NEM_WEBSHOP` eset egy VALODI oldalrol szarmazik a cache/ konyvtarbol
(merve 2026-08-26, 49 letoltott ugynoksegi oldal). Az `enrich.tech.platform`
mezo mind a tizenkettore talalatot adott, es MIND a tizenketto teves volt.
Ha valaki visszalazitja a felismerest, ezek a tesztek hasalnak el, nem az
eles futas -- es nem egy levelben derul ki, hogy nincs is webshopjuk.
"""
from pathlib import Path

import pytest

from leadgen import webshop

REPO = Path(__file__).resolve().parent.parent
MIGRATION = REPO / "leadgen" / "migrations" / "011_financials.sql"

KOSAR = '<a href="/kosar">Kosár</a>'


# ─── Hamis pozitivok: a kulcsszo ott van, de nem az o webshopja ────────────

def test_partner_logo_linkje_nem_webshop():
    """ndmarketing.hu: <a href="https://www.shoprenter.hu/"> egy partner-logo
    korul. Egy <a href> nem betoltott ESZKOZ -- nem bizonyit platformot."""
    html = f'<html><body><a href="https://www.shoprenter.hu/">' \
           f'<img src="/logo.png"></a>{KOSAR}</body></html>'
    assert webshop.platform_felismeres(html, "ndmarketing.hu") is None


def test_partner_logo_kepe_a_sajat_domainrol_nem_webshop():
    """thepitch.hu: img src=".../partners/shoprenter.png" -- a platform neve
    az UTVONALBAN van, de a HOST a sajat domain. A host donti el."""
    html = f'<html><body><img src="https://thepitch.hu/wp-content/themes/x/' \
           f'partners/shoprenter.png">{KOSAR}</body></html>'
    assert webshop.platform_felismeres(html, "thepitch.hu") is None


def test_szakerto_profil_link_nem_webshop():
    """futuremanagement.hu: link a sajat profiljara a
    szakertok.shoprenter.hu partner-katalogusban."""
    html = f'<html><body><a href="https://szakertok.shoprenter.hu/szakerto/x/">' \
           f'Shoprenter szakértő</a>{KOSAR}</body></html>'
    assert webshop.platform_felismeres(html, "futuremanagement.hu") is None


def test_szolgaltatas_szoveg_nem_webshop():
    """growcorp.hu: a "webaruhaz fejlesztes woocommerce es shopify platformon"
    -- ez a ceg SAJAT SZOLGALTATASA, nem az o rendszere."""
    html = ('<html><body><h3>e-commerce</h3><p>profi webáruház fejlesztés '
            'woocommerce és shopify platformon</p></body></html>')
    assert webshop.platform_felismeres(html, "growcorp.hu") is None


def test_tema_css_szelektor_nem_webshop():
    """citymarketing.hu: a WordPress tema CSS-e tartalmaz `.woocommerce`
    szelektorokat akkor is, ha a plugin nincs bekapcsolva."""
    html = ('<html><head><style>.woocommerce a.button{color:red}'
            '.woocommerce #respond input#submit{}</style></head>'
            f'<body>{KOSAR}</body></html>')
    assert webshop.platform_felismeres(html, "citymarketing.hu") is None


def test_kikommentelt_eszkoz_nem_szamit():
    """ndmarketing.hu: <!-- <link id='trydo-woocommerce-css' ...> -->

    Ez azert nem talal, mert PARSZOLUNK, es nem nyers szovegben keresunk.
    Ha valaki visszairja regexre, ez a teszt hasal el."""
    html = ("<html><head><!-- <link rel='stylesheet' href='/wp-content/"
            "plugins/woocommerce/assets/css/woocommerce.css'> --></head>"
            f"<body>{KOSAR}</body></html>")
    assert webshop.platform_felismeres(html, "ndmarketing.hu") is None


def test_platform_marker_bolt_gepezet_nelkul_keves():
    """Egy WordPress oldalon ott lehet a plugin ugy is, hogy bolt nincs."""
    html = ('<html><head><link href="/wp-content/plugins/woocommerce/assets/'
            'css/woocommerce.css" rel="stylesheet"></head>'
            '<body><a href="/kapcsolat">Kapcsolat</a></body></html>')
    assert webshop.platform_felismeres(html, "pelda.hu") is None


def test_idegen_webshopra_mutato_link_nem_bolt_gepezet():
    """Egy blogcikk vagy referencia-lista linkelhet MAS webshopjara."""
    html = ('<html><head><link href="/wp-content/plugins/woocommerce/assets/'
            'css/woocommerce.css" rel="stylesheet"></head>'
            '<body><a href="https://masikbolt.hu/kosar">ügyfelünk boltja</a>'
            '</body></html>')
    assert webshop.platform_felismeres(html, "pelda.hu") is None


# ─── Valodi talalatok ──────────────────────────────────────────────────────

def test_shopify_cdn_host_es_kosar():
    html = ('<html><head><script src="https://cdn.shopify.com/s/files/x.js">'
            '</script></head><body><a href="/collections/all">Termékek</a>'
            '</body></html>')
    jel = webshop.platform_felismeres(html, "bolt.hu")
    assert jel and jel.platform == "Shopify" and jel.marker_tipus == "host"
    assert jel.dobozos


def test_woocommerce_plugin_utvonal_es_kosar():
    html = ('<html><head><link rel="stylesheet" href="/wp-content/plugins/'
            'woocommerce/assets/css/woocommerce.css"></head>'
            f'<body>{KOSAR}</body></html>')
    jel = webshop.platform_felismeres(html, "bolt.hu")
    assert jel and jel.platform == "WooCommerce" and jel.marker_tipus == "utvonal"


def test_generator_onmagaban_is_eleg():
    """A generator a platform SAJAT bejelentese magarol -- ennel erosebb
    bizonyitek nincs, tehat nem kerunk melle bolt-gepezetet."""
    html = '<html><head><meta name="generator" content="Shoprenter"></head></html>'
    jel = webshop.platform_felismeres(html, "bolt.hu")
    assert jel and jel.platform == "Shoprenter" and jel.marker_tipus == "generator"


def test_a_bolt_mas_hoston_is_lehet():
    """shop.rossmann.hu a rossmann.hu mellett, demo.myshoprenter.hu a
    demo.shoprenter.hu mellett -- ha a kosar-linket a sajat HOSTHOZ kotnenk,
    ezek mind kiesnenek."""
    html = ('<html><head><script src="https://demo.cdn.shoprenter.hu/x.js">'
            '</script></head><body>'
            '<a href="https://demo.myshoprenter.hu/index.php?route=checkout/cart">'
            'Kosár</a></body></html>')
    jel = webshop.platform_felismeres(html, "demo.shoprenter.hu")
    assert jel and jel.platform == "Shoprenter"


# ─── A "dobozos" halmaz ────────────────────────────────────────────────────

@pytest.mark.parametrize("platform", ["Shoprenter", "Unas", "Shopify", "Wix",
                                      "WooCommerce", "Squarespace"])
def test_a_dobozos_platformok(platform):
    assert platform in webshop.DOBOZOS


@pytest.mark.parametrize("platform", ["Magento", "PrestaShop"])
def test_a_nyilt_rendszerek_nem_dobozosak(platform):
    """Ezeket nem lehet "kinoni": nyiltak es bovithetok. A "kinotted a
    platformot" allitas rajuk egyszeruen nem igaz."""
    assert platform not in webshop.DOBOZOS
    assert platform in webshop.GENERATOR_MARKEREK


# ─── A levelbe kerulo mondat ───────────────────────────────────────────────

def test_a_personalization_nem_tartalmaz_szamot():
    """AZ ARBEVETEL SOHA NEM KERULHET A LEVELBE. A szam a mi rangsorolasunk
    bemenete; leirva azt uzenne, hogy a cimzett penzugyi adatait bogarasszuk."""
    mondat = webshop.personalization(
        webshop.WebshopJel("Shoprenter", "cdn.shoprenter.hu", "host", "/kosar"))
    assert not any(c.isdigit() for c in mondat)


def test_a_personalization_nem_kritizal():
    """A terv: "Ne mondd, hogy rossz a platformjuk." """
    mondat = webshop.personalization(
        webshop.WebshopJel("Unas", "unas.hu", "host", "/kosar")).lower()
    for tiltott in ("rossz", "elavult", "gyenge", "korlátozott", "korlatoz"):
        assert tiltott not in mondat


# ─── A kampany-atvezetes ───────────────────────────────────────────────────

def test_a_kampany_nem_irja_felul_a_meglevot():
    """A domain lock szerint egy ceg egy kampanyba kerul. Ha egy mar
    megvalasztott (esetleg EMBER altal atnezett) kampanyt felulirnank, a ceg
    csendben mas levelet kapna, mint amit jovahagytak."""
    import ast
    fa = ast.parse(Path(webshop.__file__).read_text(encoding="utf-8"))
    forras = next(ast.unparse(n) for n in fa.body
                  if isinstance(n, ast.FunctionDef) and n.name == "_atvezet")
    assert "if not row['campaign']" in forras


def test_a_vazlat_sablon_nincs_jovahagyva():
    """A `templates.py` a felhasznaloe. Amig o at nem irja a szoveget, a
    kampany nem exportalhat."""
    from leadgen.contract import APPROVED_CAMPAIGNS
    assert "webshop_growth" not in APPROVED_CAMPAIGNS

    templates = (REPO / "cold-email-starter" / "templates.py").read_text(encoding="utf-8")
    assert '"webshop_growth": (webshop_cold' in templates


def test_a_kampannyal_egyutt_a_mondat_is_frissul():
    """Elesben latszott (2026-08-26): a ceg megkapta a `webshop_growth`
    kampanyt, de a `personalization` mezoben egy korabbi, UGYNOKSEGI szogbol
    szuletett mondat maradt. A level a webshoprol szolt volna, a nyitomondata
    viszont masrol -- a ket mezo egyutt alkot egy levelet."""
    import ast
    fa = ast.parse(Path(webshop.__file__).read_text(encoding="utf-8"))
    forras = next(ast.unparse(n) for n in fa.body
                  if isinstance(n, ast.FunctionDef) and n.name == "_atvezet")
    assert "campaign = 'webshop_growth'" in forras
    assert "personalization = coalesce" not in forras


@pytest.mark.parametrize("platform,vart", [
    ("Shoprenter", "Shoprenteren"), ("Unas", "Unason"),
    ("Shopify", "Shopifyon"), ("WooCommerce", "WooCommerce-en"),
    ("Wix", "Wixen"),
])
def test_a_platformnev_magyarul_ragozodik(platform, vart):
    """A "{platform}-en" gepies alak minden nevre rossz, es pont abban a
    mondatban, aminek termeszetesnek kell hangzania."""
    mondat = webshop.personalization(
        webshop.WebshopJel(platform, "x", "generator", ""))
    assert vart in mondat


def test_minden_dobozos_platformnak_van_ragozott_alakja():
    assert webshop.DOBOZOS <= set(webshop._RAGOZAS)


def test_a_mondat_ekezetes():
    """Ez nem komment, hanem a levelbe kerulo szoveg."""
    mondat = webshop.personalization(
        webshop.WebshopJel("Shoprenter", "x", "generator", ""))
    assert "Láttam" in mondat
