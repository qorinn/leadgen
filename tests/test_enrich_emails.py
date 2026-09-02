"""Az email-kinyeres tesztjei.

MIERT VAN ITT TESZT (CLAUDE.md: "csak a nema hibakra irunk tesztet"):

Egy rosszul kinyert email-cim NEM DOB HIBAT. A lead vegigmegy a teljes
lancon -- minositest kap, AI-mondatot kap, exportalodik --, es a hiba csak
akkor derul ki, amikor a level mar KIMENT, es visszapattant. A bounce pedig
az egyetlen hiba a rendszerben, ami VISSZAMENOLEG is kart okoz: rontja a
kuldo domain hirnevet, es onnantol a JO leadeknek sem erkezik meg a level.

Mindket itteni eset VALODI, eles incidensbol szarmazik.
"""
from __future__ import annotations

from selectolax.parser import HTMLParser

from leadgen import enrich


def _kinyer(html: str, domain: str) -> tuple[list[str], dict[str, str]]:
    """PONTOSAN azok a forrasok, amiket a `fetch_site` is hasznal.

    Ha ez elcsuszik a `fetch_site`-tol, a tesztek olyasmit merenek, ami
    elesben nem fut -- ezert a ket helyet egyutt kell modositani.
    """
    tree = HTMLParser(html)
    mailto = enrich._mailto_addrs(tree)
    szoveg_forrasu = enrich._cf_szoveg_addrs(tree) + enrich._jsonld_addrs(tree)
    szoveg = enrich._text_of(HTMLParser(html)) + " " + " ".join(szoveg_forrasu)
    return enrich._clean_emails(mailto, szoveg, domain)


# ─── 1. incidens: urlap-placeholder (2026-08-31) ───────────────────────────


def test_az_urlap_placeholder_nem_email_cim():
    """Egy `<input placeholder="...">` MINTASZOVEG, nem elerhetoseg.

    ELES ESET: a thepitch.hu hirlevel-urlapjanak placeholderében
    `padavan@thepitch.hu` allt. A regi kod a NYERS HTML-t regexelte, tehat ezt
    valodi cimnek vette, es a rendszer erre a nem letezo cimre kuldott levelet
    -- hard bounce lett belole.

    A javitas: csak `mailto:` linkbol es LATHATO SZOVEGBOL gyujtunk. Ez a
    teszt azt orzi, hogy senki ne allitsa vissza a nyers HTML regexeleset.
    """
    html = """
    <html><body>
      <form><input type="email" placeholder="padavan@thepitch.hu"></form>
      <p>Valodi cim: hello@thepitch.hu</p>
    </body></html>
    """
    emailek, _ = _kinyer(html, "thepitch.hu")
    assert "padavan@thepitch.hu" not in emailek, \
        "placeholder-bol SOHA nem szabad cimet kinyerni"
    assert emailek == ["hello@thepitch.hu"]


def test_a_data_attributumbol_sem_nyerunk_cimet():
    """Ugyanaz az elv, mas attributum. Egy `data-*` mezo sem elerhetoseg."""
    html = '<html><body><div data-default-email="nem@kell.hu">Szoveg</div></body></html>'
    emailek, _ = _kinyer(html, "kell.hu")
    assert emailek == []


# ─── 2. incidens: Cloudflare email-obfuszkacio (2026-09-02) ────────────────


def test_a_cloudflare_altal_elrejtett_mailto_megtalalhato():
    """A Cloudflare alapertelmezetten ELREJTI a cimeket a kiszolgalt HTML-ben.

    ELES ESET: a thepitch.hu oldalan HAROM helyen is ott volt a
    `hello@thepitch.hu` egy "Irj nekunk" gomb mogott -- de `mailto:` helyett
    `/cdn-cgi/l/email-protection#<hex>` alakban. A rendszer emiatt ugy
    tuntette fel a ceget, mintha egyaltalan nem lenne elerhetosege.

    A kodolas determinisztikus (elso bajt = XOR kulcs), tehat NEM kell hozza
    JavaScriptet futtatni. E nelkul MINDEN Cloudflare mogotti oldalon vakok
    lennenk -- ami a magyar weboldalak jelentos reszet jelenti.
    """
    # A `hello@thepitch.hu` valodi, az eles oldalrol kimasolt kodolt alakja.
    html = ('<html><body><a href="/cdn-cgi/l/email-protection#'
            '1c74797070735c6874796c75687f74327469">Írj nekünk</a></body></html>')
    emailek, forrasok = _kinyer(html, "thepitch.hu")
    assert emailek == ["hello@thepitch.hu"]
    # Ez eredetileg `mailto:` LINK volt -- a legmegbizhatobb jel.
    assert forrasok["hello@thepitch.hu"] == "mailto"


def test_a_cloudflare_szoveges_cim_szoveg_forrasu_marad():
    """A `data-cfemail` eredetileg LATHATO SZOVEG volt, nem link.

    A ket alakot azert kulonboztetjuk meg, mert az export rangsora a
    `source_kind`-ot hasznalja: a valodi linkbol szarmazo cim elorebb kerul,
    mint a szovegben talalt. Ha mindkettot `mailto`-nak vennenk, elveszne ez
    a kulonbseg.
    """
    html = ('<html><body><span class="__cf_email__" '
            'data-cfemail="1c74797070735c6874796c75687f74327469">[e-mail]</span>'
            '</body></html>')
    emailek, forrasok = _kinyer(html, "thepitch.hu")
    assert emailek == ["hello@thepitch.hu"]
    assert forrasok["hello@thepitch.hu"] == "text"


def test_a_hibas_cloudflare_kod_nem_dob_kivetelt():
    """Egy elrontott attributum ne vigye el az egesz oldal feldolgozasat.

    A `fetch_site` egy batch resze: ha itt kivetel szallna fel, egyetlen
    hibas oldal allitana meg tobb tucat ceg feldolgozasat.
    """
    for rossz in ("", "x", "zz", "1", "nemhex"):
        assert enrich._cf_dekod(rossz) == ""


def test_a_cloudflare_dekodolas_a_kulcsot_hasznalja():
    """Ugyanaz a cim TOBB kulccsal is kodolva ugyanazt kell adja.

    A Cloudflare futasonkent mas XOR-kulcsot valaszt, tehat ugyanaz a cim
    ugyanazon az oldalon TOBB kulonbozo hex-kent jelenik meg (eles peldak).
    Ha a dekodolas a kulcsot figyelmen kivul hagyna, csak az egyik valtozat
    jonne ki helyesen -- es a hiba veletlenszeruen jelentkezne.
    """
    for hexkod in ("1c74797070735c6874796c75687f74327469",
                   "452d2029292a05312d20352c31262d6b2d30",
                   "92faf7fefefdd2e6faf7e2fbe6f1fabcfae7"):
        assert enrich._cf_dekod(hexkod) == "hello@thepitch.hu"


# ─── 3. incidens: ures attributum (2026-09-02) ─────────────────────────────


def test_az_ures_meta_attributum_nem_dob_kivetelt():
    """A selectolax URES attributumra None-t ad, nem ures stringet.

    ELES ESET (kyovideo.com): az oldalon `<meta name="description" content="">`
    volt. A `.attributes.get("content", "")` NEM ""-t adott vissza, hanem
    None-t -- a default csak hianyzo KULCS eseten lepne be --, es a `None[:400]`
    TypeError-t dobott. Emiatt az egesz ceg `status='error'`-ba esett, holott
    a weboldala tokeletesen elerheto volt.

    Ez a fajta hiba nema: a ceg egyszeruen eltunik a tolcserbol, es semmi nem
    mondja meg, hogy egy ures HTML-attributum miatt.
    """
    from selectolax.parser import HTMLParser as _HP
    md = _HP('<meta name="description" content="">').css_first("meta[name=description]")
    assert md is not None
    # A tenyleges viselkedes rogzitese -- ha ez valaha megvaltozik, tudjunk rola.
    assert md.attributes.get("content", "") is None, \
        "a selectolax viselkedese megvaltozott: ellenorizd a `or \"\"` mintakat"
    # Az `or ""` viszont helyesen kezeli.
    assert (md.attributes.get("content") or "")[:400] == ""


# ─── 4. incidens: JSON-LD strukturalt adat (2026-09-02) ────────────────────


def test_a_jsonld_bol_kiolvassuk_a_cimet():
    """A `<script type="application/ld+json">` tartalmat a `_text_of` eldobja.

    ELES ESET (doppio.hu): a `hello@doppio.hu` KIZAROLAG a schema.org
    JSON-LD `description` mezojeben szerepelt -- a lathato szovegben sehol.
    A `_text_of` viszont minden `<script>` taget eltavolit, tehat a cim
    lathatatlan volt szamunkra.

    MIERT SZABAD EBBOL OLVASNI, ha a nyers HTML-bol nem: a JSON-LD a ceg
    SAJAT, gepi olvasasra SZANT leirasa magarol -- nem markup-belsoseg,
    mint egy `placeholder` attributum.
    """
    html = ('<html><head><script type="application/ld+json">'
            '{"@type":"Organization","description":'
            '"Írj nekünk a hello@doppio.hu címre!"}'
            '</script></head><body>Nincs itt cim.</body></html>')
    emailek, forrasok = _kinyer(html, "doppio.hu")
    assert emailek == ["hello@doppio.hu"]
    # Publikalt LEIRAS, nem kattinthato kapcsolatfelvetel -> szoveg-erteku.
    assert forrasok["hello@doppio.hu"] == "text"


# ─── 5. incidens: elrontott link megolte az egesz ceget (2026-09-02) ───────


def test_egy_hibas_link_nem_viszi_el_az_egesz_oldalt():
    """Egy ervenytelen URL NEM allithatja meg a ceg feldolgozasat.

    ELES ESET (kyovideo.com): az oldalon egy elrontott JavaScript
    `http://[object Object]/...` alaku linket hagyott a HTML-ben. A
    `urlsplit(...).hostname` es az `urljoin` is ERTELMEZI a hosztot, es a
    szogletes zarojel miatt IPv6-cimnek nezi -> ValueError. A kivetel a
    `fetch_site` kulso `try`-jaig szallt fel, es a ceg `status='error'`-ba
    esett -- pedig a weboldala tokeletesen elerheto volt, es EGYETLEN
    linkje volt rossz.
    """
    from selectolax.parser import HTMLParser as _HP
    html = ('<html><body>'
            '<a href="http://[object Object]/x">rossz</a>'
            '<a href="/kapcsolat">Kapcsolat</a>'
            '<a href="https://facebook.com/ceg">FB</a>'
            '</body></html>')
    tree = _HP(html)
    # Egyik fuggveny sem dobhat, es a JO linkeket tovabbra is meg kell talalni.
    linkek = enrich._discover_links(tree, "https://ceg.hu/", "ceg")
    assert linkek.get("contact") == "https://ceg.hu/kapcsolat"
    assert enrich._socials(tree, "https://ceg.hu/") == ["https://facebook.com/ceg"]


def test_a_keresek_teljes_fejleckeszlettel_mennek():
    """Hianyos keres = 403 a WAF-októl, es a ceg csendben kiesik.

    Merve (2026-09-02): 12 db 403-as domainbol HAROM pusztan attol adott
    200-at, hogy `Accept` es `Accept-Language` fejlecet is kuldtunk --
    VALTOZATLAN User-Agenttel. Ez nem alcazas: a UA tovabbra is megmondja,
    kik vagyunk.
    """
    assert "PaladiLeadBot" in enrich.FEJLECEK["User-Agent"], \
        "a botnak tovabbra is AZONOSITANIA kell magat"
    assert "paladi-web.hu" in enrich.FEJLECEK["User-Agent"]
    for kulcs in ("Accept", "Accept-Language"):
        assert kulcs in enrich.FEJLECEK, f"hianyzik a {kulcs} fejlec"


# ─── A rescan CSAK hozzaad ─────────────────────────────────────────────────


def test_a_rescan_nem_torol_es_nem_valtoztat_statuszt():
    """A `rescan_contacts` es a `redo` KETTO KULONBOZO eszkoz.

    A `redo()` TOROL (a gyanus, regi kontaktokat) es `new`-ra allit -- ez
    helyes, ha egy konkret cim hibasnak bizonyult. De ha csak TOBB cimet
    akarunk osszeszedni egy mukodo cegnel, a torles karos: ha a letoltes
    epp elszall, a ceg elveszti a MEGLEVO, jo cimet is. A `new` statusz
    pedig kiutne a folyamatban levo cegeket a tolcserbol.

    Ezert a `rescan_contacts` kizarolag `insert ... on conflict do nothing`-ot
    csinalhat.
    """
    import inspect
    from leadgen import pipeline
    forras = inspect.getsource(pipeline.rescan_contacts)
    assert "delete from contacts" not in forras, "a rescan SOHA nem torolhet kontaktot"
    assert "on conflict (email) do nothing" in forras
    assert "set status" not in forras, "a rescan nem valtoztathat ceg-statuszt"
