#!/usr/bin/env python3
"""Kozos enrichment engine: egy domainbol strukturalt kivonat.

EZT EGYSZER IRJUK MEG, es MINDEN engine ezt hasznalja. Az ugynoksegi, az
allashirdetes-, a hirdetes- es a kiallito-engine mind ugyanezzel toltie le es
nezi meg a cegek weboldalat -- csak a MINOSITES kulonbozik utana (engines.py).

Amit kiszed:
  - a fobb aloldalak szovege (kapcsolat, rolunk, szolgaltatasok, impresszum)
  - email cimek, telefonszamok, kozossegi linkek
  - tech ujjlenyomat (7.5): CMS, webshop platform, copyright ev, viewport
  - a footer HTML-je (a 8.2 "halott fejleszto" engine ebbol dolgozik majd)

Amit NEM csinal: nem tarolja el az egesz weboldalt az adatbazisban. A nyers
HTML a cache/ konyvtarba kerul (gitignore-olva), hogy az evidence grounding
(10. szakasz) utolag ellenorizheto legyen; a DB-be csak a kivonat megy.

UDVARIASSAG: robots.txt-et tiszteletben tartunk, es kesleltetunk a keresek
kozott. Nem versenyzunk a cel-szerverrel; nehany oldalt kerunk le cegenkent.
"""
from __future__ import annotations

import re
import time
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import httpx
from selectolax.parser import HTMLParser

from . import config, normalize

UA = "Mozilla/5.0 (compatible; PaladiLeadBot/1.0; +https://paladi-web.hu)"

# A TELJES fejleckeszlet. NEM ALCAZAS: a User-Agent tovabbra is megmondja,
# kik vagyunk, es hol lehet utananezni (`+https://paladi-web.hu`).
#
# MIERT KELL MEGIS A TOBBI FEJLEC: egy `Accept` es `Accept-Language` nelkuli
# keres technikailag hianyos -- minden valodi bongeszo kuldi oket --, es a
# WAF-ok (Cloudflare, Sucuri) ezt onmagaban gyanus mintanak veszik. Merve
# (2026-09-02, 12 db 403-as domainen): harom oldal PUSZTAN ettol a
# kulonbsegtol adott 403 helyett 200-at, valtozatlan User-Agenttel --
# yours-creative.com, mebs.world, aimarketingugynokseg.hu.
#
# Amelyik oldal a bot-UA MIATT tilt (kmumarketing.hu), az tovabbra is tilt,
# es ez igy helyes: azt tiszteletben tartjuk, nem kerulgetjuk.
FEJLECEK = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "hu-HU,hu;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
}
TIMEOUT = 20.0
DELAY = 1.0          # masodperc ket keres kozott, ugyanannal a domainnel
MAX_PAGES = 6        # a fooldalon felul ennyi aloldal

# Ezeket az utvonalakat keressuk (ekezet nelkuli illesztes a linkek szovegen/href-jen).
PAGE_HINTS = {
    "contact": ("kapcsolat", "contact", "elerhetoseg"),
    "about": ("rolunk", "about", "magunkrol", "cegunk", "bemutatkozas"),
    "services": ("szolgaltatas", "services", "mit-csinalunk", "amit-csinalunk"),
    "imprint": ("impresszum", "imprint", "jogi"),
    "team": ("csapat", "team", "munkatars", "rolunk/csapat"),
    "careers": ("karrier", "career", "allas", "csatlakozz"),
}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+36|06)[\s\-/]?\(?\d{1,2}\)?[\s\-/]?\d{3}[\s\-/]?\d{3,4}")
SOCIAL_HOSTS = ("facebook.com", "instagram.com", "linkedin.com", "youtube.com", "tiktok.com")

# Nem cim, csak szemet: kepfajlok, sablon-placeholderek, példák.
EMAIL_JUNK = re.compile(
    r"(\.(png|jpe?g|gif|svg|webp|css|js)$)|(^(example|sample|your|email|name|user)@)",
    re.I,
)

# Kozismert freemail-szolgaltatok. Ha egy cegnel NINCS sajat-domainu cim,
# csak ezekrol fogadunk el tartalek cimet (lasd pick_contacts) -- egy magyar
# KKV-nal a `ceghu@gmail.com` gyakran a valodi, hasznalt uzleti cim, tehat
# ezt nem szabad elvetni. Egy TETSZOLEGES idegen UZLETI domain viszont nem
# megbizhato tartalek: az lehet tarhelyszolgaltato, widget-szolgaltato vagy
# a weboldalt keszito fejleszto cime -- lasd a pick_contacts docstringjet.
FREEMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "outlook.hu", "hotmail.com",
    "hotmail.hu", "yahoo.com", "yahoo.hu", "icloud.com", "freemail.hu",
    "citromail.hu", "t-online.hu", "upcmail.hu", "vipmail.hu", "indamail.hu",
    "chello.hu", "externet.hu", "invitel.hu", "protonmail.com", "gmx.com", "gmx.net",
}

# 7.5 tech ujjlenyomat -- mind bizonyithato teny a HTML-bol, nulla AI, nulla plusz keres.
PLATFORMS = {
    "shoprenter": "Shoprenter", "unas.hu": "Unas", "cdn.shopify.com": "Shopify",
    "woocommerce": "WooCommerce", "wix.com": "Wix", "squarespace": "Squarespace",
    "webnode": "Webnode", "prestashop": "PrestaShop", "magento": "Magento",
}


@dataclass
class SiteExtract:
    domain: str
    ok: bool = False
    error: str = ""
    status: int = 0
    title: str = ""
    meta_description: str = ""
    emails: list[str] = field(default_factory=list)
    email_kind: dict[str, str] = field(default_factory=dict)   # email -> 'mailto'|'text'
    phones: list[str] = field(default_factory=list)
    socials: list[str] = field(default_factory=list)
    pages_found: list[str] = field(default_factory=list)
    nav_text: str = ""      # menu/fejlec szovege -- ez a "sajat szolgaltatas" jele
    texts: dict[str, str] = field(default_factory=dict)   # kulcs -> oldal szovege
    footer_html: str = ""
    tech: dict = field(default_factory=dict)

    @property
    def all_text(self) -> str:
        """A minositeshez hasznalt osszefuzott szoveg."""
        return " \n".join(self.texts.values())

    def as_json(self) -> dict:
        return {
            "title": self.title, "meta_description": self.meta_description,
            "emails": self.emails, "email_kind": self.email_kind,
            "phones": self.phones, "socials": self.socials,
            "pages_found": self.pages_found, "tech": self.tech,
            "nav_text": self.nav_text,
            "text_len": len(self.all_text), "status": self.status,
        }


_ROBOTS_CACHE: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def _robots_ok(base: str, path: str) -> bool:
    """robots.txt ellenorzes -- SAJAT letoltessel, nem RobotFileParser.read()-del.

    MIERT NEM A BEEPITETT read(): az urllib alapertelmezett User-Agentjevel tolt
    le, amit a WAF-fal (Cloudflare stb.) vedett oldalak 403-mal utasitanak el --
    a RobotFileParser pedig a 403-at "minden tiltva"-kent ertelmezi. Merve
    (2026-08-21): a marketing21.hu es a 2100labs.com robots.txt-je kifejezetten
    ENGEDELYEZ mindent (`Disallow:` uresen), a beepitett parser megis tiltast
    jelzett mindkettore. Igy az enrichment minden ilyen oldalon NEMAN elbukott
    volna -- nem hibaval, hanem "robots.txt tiltja" uzenettel.

    A helyes viselkedes: sajat UA-val letoltjuk, es CSAK a tenylegesen
    beolvasott szabalyokat vesszuk figyelembe. Ha a fajl nem elerheto (404,
    403, timeout), akkor engedunk -- a robots.txt HIANYA nem tiltas, es
    masodpercenkent egy keres nehany publikus oldalra normal bongeszes.
    """
    host = urlsplit(base).hostname or base
    if host not in _ROBOTS_CACHE:
        parser: urllib.robotparser.RobotFileParser | None = None
        try:
            with httpx.Client(timeout=10, follow_redirects=True,
                              headers=FEJLECEK) as c:
                r = c.get(urljoin(base, "/robots.txt"))
            if r.status_code == 200 and r.text.strip():
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(r.text.splitlines())
        except Exception:
            parser = None
        _ROBOTS_CACHE[host] = parser

    parser = _ROBOTS_CACHE[host]
    if parser is None:
        return True
    return parser.can_fetch(UA, urljoin(base, path))


def _text_of(tree: HTMLParser) -> str:
    for tag in tree.css("script, style, noscript, svg"):
        tag.decompose()
    body = tree.body or tree
    return re.sub(r"\s+", " ", body.text(separator=" ")).strip()


def _cache_write(domain: str, key: str, html: str) -> None:
    d = config.CACHE_DIR / domain
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{key}.html").write_text(html, encoding="utf-8")


def _tech_fingerprint(html: str, tree: HTMLParser) -> dict:
    low = html.lower()
    tech: dict = {}

    gen = tree.css_first('meta[name="generator"]')
    if gen and gen.attributes.get("content"):
        tech["generator"] = gen.attributes["content"][:120]
    if "wp-content" in low or "wordpress" in low:
        tech["cms"] = "WordPress"
    for needle, name in PLATFORMS.items():
        if needle in low:
            tech["platform"] = name
            break

    tech["has_viewport"] = bool(tree.css_first('meta[name="viewport"]'))

    years = re.findall(r"(?:©|&copy;|copyright)[^0-9]{0,20}(20\d{2})", low)
    if years:
        tech["copyright_year"] = max(int(y) for y in years)

    tech["has_form"] = bool(tree.css_first("form"))
    tech["has_shop"] = any(k in low for k in ("kosar", "kosár", "cart", "webshop", "penztar"))
    tech["has_booking"] = any(k in low for k in ("idopontfoglalas", "időpontfoglalás", "booking", "foglalas"))
    return tech


def _cf_dekod(hexszoveg: str) -> str:
    """Cloudflare "Email Address Obfuscation" visszafejtese.

    A Cloudflare (alapertelmezetten BEKAPCSOLT funkcio) minden email-cimet
    kicserel a kiszolgalt HTML-ben, hogy a spam-robotok ne talaljak meg:

        <a href="mailto:hello@ceg.hu">              eredeti
        <a href="/cdn-cgi/l/email-protection#1c74...">  amit mi latunk

    A kodolas trivialis es determinisztikus: az elso bajt a kulcs, a tobbi a
    cim bajtjai azzal XOR-olva. A bongeszoben egy Cloudflare-szkript fejti
    vissza -- nekunk nem kell JavaScriptet futtatni hozza, csak XOR-ozni.

    MIERT SZAMIT: e nelkul MINDEN Cloudflare mogotti oldalon vakok vagyunk a
    cimekre. Merve (2026-09-02, thepitch.hu): az oldalon HAROM helyen is ott
    volt a `hello@thepitch.hu`, es egyiket sem lattuk -- a rendszer ugy
    tuntette fel a ceget, mintha nem lenne elerhetosege.

    Hibas bemenetre ures stringet ad, nem dob: egy elrontott attributum ne
    vigye el az egesz oldal feldolgozasat.
    """
    try:
        b = bytes.fromhex(hexszoveg)
    except ValueError:
        return ""
    if len(b) < 2:
        return ""
    kulcs = b[0]
    try:
        return "".join(chr(x ^ kulcs) for x in b[1:])
    except ValueError:  # pragma: no cover -- vedelmi ag
        return ""


# A Cloudflare ket alakban rejti el a cimet, es a KETTO MAST JELENT:
#   <a href="/cdn-cgi/l/email-protection#HEX">  <- eredetileg `mailto:` LINK volt
#   <span data-cfemail="HEX">                   <- eredetileg LATHATO SZOVEG volt
# Ezert kulon szedjuk oket: a link a megbizhatobb jel (lasd `source_kind`).
_CF_HREF_RE = re.compile(r"/cdn-cgi/l/email-protection#([0-9a-fA-F]+)")


def _mailto_addrs(tree: HTMLParser) -> list[str]:
    """A `mailto:` linkek cimei -- ez a LEGMEGBIZHATOBB forras, mert az oldal
    keszitoje kifejezetten kapcsolatfelvetelre szanta.

    A Cloudflare-rel elrejtett `mailto:` linkek is ide tartoznak: azok is
    valodi kapcsolatfelvetelre szant linkek voltak, csak a kiszolgalo
    kicserelte oket (lasd `_cf_dekod`)."""
    out = []
    for a in tree.css('a[href^="mailto:"]'):
        href = (a.attributes.get("href") or "")[len("mailto:"):]
        addr = unquote(href.split("?")[0]).strip().lower().strip(" .")
        if addr:
            out.append(addr)
    for a in tree.css('a[href*="/cdn-cgi/l/email-protection"]'):
        talalat = _CF_HREF_RE.search(a.attributes.get("href") or "")
        if talalat:
            addr = _cf_dekod(talalat.group(1)).strip().lower().strip(" .")
            if addr:
                out.append(addr)
    return out


def _cf_szoveg_addrs(tree: HTMLParser) -> list[str]:
    """A Cloudflare altal elrejtett, eredetileg LATHATO SZOVEGKENT szereplo
    cimek (`data-cfemail`). Ezek a sima szoveges talalattal egyenertekuek."""
    out = []
    for el in tree.css("[data-cfemail]"):
        addr = _cf_dekod(el.attributes.get("data-cfemail") or "").strip().lower().strip(" .")
        if addr:
            out.append(addr)
    return out


def _jsonld_addrs(tree: HTMLParser) -> list[str]:
    """Cimek a JSON-LD strukturalt adatbol (`application/ld+json`).

    MIERT SZABAD EBBOL OLVASNI, ha a nyers HTML-bol nem: a JSON-LD nem
    markup-belsoseg, hanem a ceg SAJAT, gepi olvasasra SZANT leirasa
    magarol (schema.org). Egy `placeholder` attributum veletlen szemet; egy
    JSON-LD `email` vagy `description` mezo szandekosan kozzetett adat.

    Merve (2026-09-02, doppio.hu): a `hello@doppio.hu` KIZAROLAG itt
    szerepelt, egy `description` mezoben ("Írj nekünk a hello@doppio.hu
    címre") -- a `_text_of` viszont a `<script>` tageket eldobja, tehat a
    lathato szovegben sosem lattuk.

    A talalt cimek SZOVEG-erteku forrasnak szamitanak (nem `mailto`): ez
    publikalt leiras, nem kattinthato kapcsolatfelvetel.
    """
    out: list[str] = []
    for s in tree.css('script[type="application/ld+json"]'):
        for nyers in EMAIL_RE.findall(s.text() or ""):
            addr = nyers.strip().lower().strip(" .")
            if addr and addr not in out:
                out.append(addr)
    return out


def _discover_links(tree: HTMLParser, base_url: str, host: str) -> dict[str, str]:
    """Belso linkek besorolasa a PAGE_HINTS alapjan."""
    found: dict[str, str] = {}
    for a in tree.css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        # EGY HIBAS LINK NE VIGYE EL AZ EGESZ CEGET. A `parts.hostname`
        # ERTELMEZI a hosztot, es ervenytelenre ValueError-t dob -- pl. a
        # `http://[object Object]/...` alaku linkre, amit egy elrontott
        # JavaScript hagy a HTML-ben (merve: kyovideo.com, 2026-09-02). A
        # kivetel a `fetch_site` kulso `try`-jaig szallt fel, es a ceg
        # `status='error'`-ba esett -- pedig csak EGY linkje volt rossz.
        try:
            absolute = urljoin(base_url, href)
            parts = urlsplit(absolute)
            idegen = bool(parts.hostname) and host not in parts.hostname
        except ValueError:
            continue
        if idegen:
            continue
        needle = normalize.strip_accents((parts.path + " " + a.text()).lower())
        for key, hints in PAGE_HINTS.items():
            if key in found:
                continue
            if any(h in needle for h in hints):
                found[key] = absolute
                break
    return found


def start_urls(domain: str, original: str | None = None) -> list[str]:
    """Probalkozasi sorrend. TOBB VARIANS KELL, es ez nem elmeleti aggodalom.

    Merve (2026-08-21): a chiro.hu-nal a `https://chiro.hu` HTTP 500-at ad, de a
    `http://www.chiro.hu` 301-et -- vagyis az oldal EL, csak nem ott, ahol
    kerestuk. 60 cegbol 8 esett ki igy, pusztan azert, mert a normalizalt
    domainbol ujraepitett `https://` cimet hasznaltuk a Maps altal visszaadott
    VALODI URL helyett.

    Ezert: eloszor az eredeti URL (a forras tudja a legjobban), utana a
    szokasos variansok.
    """
    jeloltek = []
    if original:
        o = original.strip()
        if o.startswith(("http://", "https://")):
            jeloltek.append(o.rstrip("/"))
    jeloltek += [f"https://{domain}", f"https://www.{domain}", f"http://{domain}"]
    egyedi = []
    for u in jeloltek:
        if u not in egyedi:
            egyedi.append(u)
    return egyedi


def fetch_site(domain: str, original_url: str | None = None,
               verbose: bool = False) -> SiteExtract:
    """Egy ceg weboldalanak feldolgozasa. Halozati hibat NEM dob -- a hibat
    az `ok`/`error` mezokben adja vissza, hogy egy rossz weboldal ne allitsa
    meg a teljes batch-et."""
    out = SiteExtract(domain=domain)

    base = ""
    hibak = []
    for jelolt in start_urls(domain, original_url):
        try:
            with httpx.Client(timeout=TIMEOUT, follow_redirects=True,
                              headers=FEJLECEK) as probe:
                pr = probe.get(jelolt)
            if pr.status_code < 400:
                base = jelolt
                break
            hibak.append(f"{jelolt} -> {pr.status_code}")
        except Exception as exc:
            hibak.append(f"{jelolt} -> {type(exc).__name__}")
    if not base:
        out.error = "; ".join(hibak)[:200]
        if verbose:
            print(f"  HIBA {domain:34} {out.error[:70]}")
        return out

    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True,
                          headers=FEJLECEK) as client:
            if not _robots_ok(base, "/"):
                out.error = "robots.txt tiltja"
                return out

            r = client.get(base)
            out.status = r.status_code
            if r.status_code >= 400:
                out.error = f"HTTP {r.status_code}"
                return out
            base = str(r.url)
            html = r.text
            tree = HTMLParser(html)
            _cache_write(domain, "index", html)

            t = tree.css_first("title")
            out.title = (t.text().strip()[:200] if t else "")
            md = tree.css_first('meta[name="description"]')
            # `or ""` ES NEM a `get()` masodik parametere: a selectolax egy
            # URES attributumra (`content=""`) None-t ad vissza, nem ""-t --
            # a default csak akkor lepne be, ha a kulcs egyaltalan nem lenne
            # ott. Merve (2026-09-02, kyovideo.com): a `None[:400]` TypeError-t
            # dobott, amitol az EGESZ ceg `status='error'`-ba esett, holott az
            # oldala tokeletesen elerheto volt. A modul tobbi helye mar igy
            # csinalja (`_discover_links`, `_socials`) -- ez az egy maradt ki.
            out.meta_description = ((md.attributes.get("content") or "")[:400] if md else "")
            out.tech = _tech_fingerprint(html, tree)

            # A menu/fejlec kulon: ha egy szolgaltatas ITT szerepel, az szinte
            # biztosan a ceg SAJAT ajanlata -- nem ugyfel-referencia, nem blogcikk.
            nav_parts = []
            for sel in ("nav", "header", '[class*="menu"]', '[id*="menu"]'):
                for el in tree.css(sel)[:3]:
                    nav_parts.append(el.text(separator=" "))
            out.nav_text = re.sub(r"\s+", " ", " ".join(nav_parts))[:3000]

            footer = tree.css_first("footer")
            out.footer_html = (footer.html or "")[:4000] if footer else ""

            out.texts["index"] = _text_of(HTMLParser(html))
            out.pages_found.append(base)
            mailto_hits = _mailto_addrs(tree)
            cf_szoveg = _cf_szoveg_addrs(tree) + _jsonld_addrs(tree)

            host = urlsplit(str(r.url)).hostname or domain
            links = _discover_links(tree, str(r.url), domain.split(".")[0])

            for key, url in list(links.items())[:MAX_PAGES]:
                time.sleep(DELAY)
                try:
                    rr = client.get(url)
                    if rr.status_code >= 400:
                        continue
                    sub = HTMLParser(rr.text)
                    out.texts[key] = _text_of(HTMLParser(rr.text))
                    out.pages_found.append(url)
                    _cache_write(domain, key, rr.text)
                    mailto_hits += _mailto_addrs(sub)
                    cf_szoveg += _cf_szoveg_addrs(sub) + _jsonld_addrs(sub)
                    if not out.footer_html:
                        f2 = sub.css_first("footer")
                        out.footer_html = (f2.html or "")[:4000] if f2 else ""
                except Exception:
                    continue

            # Csak KET forrasbol fogadunk el emailt: valodi `mailto:` linkbol,
            # es a LATHATO oldalszovegbol (`out.texts`). A nyers HTML-t
            # (input-placeholderek, data-attributumok, kikommentelt kod)
            # SZANDEKOSAN nem regexeljuk -- egy `<input placeholder="x@y.hu">`
            # korabban pontosan igy kerult be valodi cimkent (2026-09-01,
            # thepitch.hu, `padavan@thepitch.hu` -- nem letezo mailbox, a
            # kikuldes hard bounce-ot kapott).
            # A Cloudflare-rel elrejtett cimek es a JSON-LD-bol kiolvasottak a
            # szoveges talalatokkal egyenertekuek: a `_text_of` egyiket sem
            # latja (a helyettesito jelolest, illetve a <script> tartalmat).
            text_blob = " ".join(out.texts.values()) + " " + " ".join(cf_szoveg)
            out.emails, out.email_kind = _clean_emails(mailto_hits, text_blob, domain)
            out.phones = _clean_phones(text_blob + " " + html)
            out.socials = _socials(tree, str(r.url))
            out.ok = True

    except Exception as exc:
        out.error = f"{type(exc).__name__}: {exc}"[:200]

    if verbose:
        state = "OK " if out.ok else "HIBA"
        print(f"  {state} {domain:34} oldalak={len(out.pages_found)} "
              f"email={len(out.emails)} {out.error}")
    return out


# A kuldo verify.ROLE_PREFIXES listaja BOVITVE. A terv Validation fejezete
# az `admin@`, `privacy@`, `gdpr@` cimeket is kizarna, a kuldoe nem tartalmazza
# oket -- a scraper legyen a szigorubb szuro (felfele kompatibilis).
# Az `info@` SZANDEKOSAN NINCS itt: magyar KKV-nal gyakran ez az egyetlen cim.
ROLE_PREFIXES = {
    "abuse", "postmaster", "noreply", "no-reply", "donotreply", "spam",
    "webmaster", "hostmaster", "root", "admin", "administrator", "privacy",
    "gdpr", "adatvedelem", "billing", "szamlazas", "support", "help",
    # Nem dontéshozo, es nem is ajanlat-fogado cimek. A `press@mito.group`
    # az elso eles exportban `personal`-kent minosult, holott sajtokapcsolati
    # cim: oda kuldott ajanlat a legjobb esetben elvesz, a legrosszabban
    # spamnek jelolik.
    "press", "sajto", "media", "pr", "kommunikacio",
    "karrier", "career", "allas", "jobs", "job", "hr", "toborzas",
}
# ERTEKESITESI cimek. KULON TIPUS, NEM `generic` (felhasznaloi dontes,
# 2026-09-03): a `sales@` az a cim, ahol A CEG ad el -- nem az, ahol ajanlatot
# FOGAD. Egy alvallalkozoi megkereses ott a legjobb esetben elvesz a kimeno
# ertekesitesi folyamatban.
SALES_PREFIXES = {
    "sales", "ertekesites", "uzletfejlesztes", "uzletkotes", "bd",
}
GENERIC_PREFIXES = {
    "info", "hello", "hi", "kapcsolat", "iroda", "office", "contact", "mail",
    "marketing", "ugyfelszolgalat", "titkarsag",
}

# ─── A CIMVALASZTAS RANGSORA -- EZ AZ EGYETLEN FORRAS ──────────────────────
#
# Minden hely, ahol "melyik cim a legjobb ehhez a ceghez" kerdes felmerul,
# EZT hasznalja: az export (`SQL_NEW`), a kuldes elotti valaszto
# (`send.kontakt_valasztek`), a cegek listaja (`webui .../companies.py`) es a
# riport. Korabban az export SAJAT, bedrotozott sorrendet hasznalt -- igy ket
# hely dontott maskepp ugyanarrol.
#
# MIERT A `generic` AZ ELSO (felhasznaloi dontes, 2026-09-03):
# egy `info@` / `iroda@` cimet a ceg AZERT tesz ki, hogy megkeressek rajta.
# Egy talalomra kiszedett szemelyes cim (`panovics.andras@...`) lehet egy
# konyvelo, egy gyakornok vagy egy epp tavozo kollega -- a megkereses ott
# nagyobb esellyel hal el, mint a kozponti cimen. Eles eset: a pticom.hu-nal
# a rendszer egy szemelyes cimet valasztott, holott volt `iroda@` is.
EMAIL_TYPE_SORREND = ("generic", "personal", "sales", "role")

# A `generic` cimeken BELULI sorrend. Tobb kozponti cim is lehet egyszerre
# (`info@` es `marketing@`); a lista eleje a "biztosan olvassak" vege.
GENERIC_SORREND = (
    "info", "hello", "iroda", "hi", "office", "kapcsolat", "contact",
    "mail", "titkarsag", "ugyfelszolgalat", "marketing",
)


def _rang_case(oszlop: str, ertekek: tuple[str, ...]) -> str:
    """SQL `case` kifejezes egy Python-sorrendbol. Igy a rangsor egyetlen
    helyen (fent) van leirva, es nem masolodik be SQL-szovegekbe."""
    agak = " ".join(f"when '{e}' then {i}" for i, e in enumerate(ertekek))
    return f"case {oszlop} {agak} else {len(ertekek)} end"


def email_type_rang_sql(oszlop: str = "ct.email_type") -> str:
    return _rang_case(f"coalesce({oszlop}, 'unknown')", EMAIL_TYPE_SORREND)


def generic_rang_sql(oszlop: str = "ct.email") -> str:
    """A helyi resz (a `@` elotti darab) rangja a GENERIC_SORREND szerint."""
    return _rang_case(f"split_part({oszlop}, '@', 1)", GENERIC_SORREND)


def classify_email(addr: str) -> str:
    """generic | personal | sales | role -- lasd EMAIL_TYPE_SORREND."""
    local = normalize.strip_accents((addr or "").split("@")[0].lower())
    if local in ROLE_PREFIXES:
        return "role"
    if local in SALES_PREFIXES:
        return "sales"
    if local in GENERIC_PREFIXES:
        return "generic"
    # "nagy.eszter", "peter", "oliver" -> szemelynek tuno cim
    return "personal"


def pick_contacts(extract: SiteExtract, domain: str) -> list[tuple[str, str, str]]:
    """(email, tipus, forras) harmasok, a ceg SAJAT domainjet elonyben reszesitve.

    MIERT SZAMIT: a scrapelt oldalakon idegen cimek is elofordulnak -- a
    tarhelyszolgaltato admin cime, egy partner cege, a weboldalt keszito
    fejleszto sajat cime. Ha ilyet irnank a leads.csv-be, nem a celzott ceget
    keresnenk meg. Merve: a marketingtanacsado.hu-n megjelent egy
    `admin@megacp.com` (tarhely) es egy masik domainhez tartozo cim is.

    HA NINCS SAJAT-DOMAINU CIM: csak ismert FREEMAIL-cimet fogadunk el
    tartalekkent (pl. `ceghu@gmail.com`) -- ez magyar KKV-nal gyakran a
    valodi, hasznalt uzleti cim. Egy TETSZOLEGES idegen UZLETI domaint
    (a fenti admin@megacp.com-hoz hasonlot) korabban tartalekkent
    elfogadtunk -- ez pontosan az a hiba, amit itt tudatosan megszuntetunk:
    inkabb ne legyen kontaktja a cegnek (kezi kutatas kell), mint hogy rossz
    cimre menjen level.

    Minden sajat-domainu (vagy freemail) cim bekerul KULON sorkent -- nem
    csak az elso. Egy cegnel tobb valodi cim is lehet (support@, info@,
    szemelynevek); ezek kozul melyiket hasznaljuk kikuldesre, azt a
    `review --pick-contact` dontheti el kezzel, vagy alapertelmezesben az
    export.py rangsora (forras/tipus/validacio szerint).
    """
    sajat = [e for e in extract.emails if e.endswith("@" + domain)]
    forras = sajat or [e for e in extract.emails
                       if e.split("@")[-1] in FREEMAIL_DOMAINS]
    return [(e, classify_email(e), extract.email_kind.get(e, "text")) for e in forras]


def _clean_emails(mailto_hits: list[str], text_blob: str,
                  domain: str) -> tuple[list[str], dict[str, str]]:
    """(rendezett email lista, email -> forras ('mailto'|'text')).

    KET FORRAS VAN, es EZ SZANDEKOS: valodi `mailto:` linkek (a legmegbizhatobb
    jel -- az oldal keszitoje kifejezetten kapcsolatfelvetelre szanta), es a
    LATHATO oldalszoveg. Nyers HTML-t (attributumok, kikommentelt kod, script)
    itt nem regexelunk -- lasd a fetch_site() hivo hely kommentjet.
    """
    kind: dict[str, str] = {}
    order: list[str] = []

    def add(raw: str, ez_forras: str) -> None:
        # `unquote`: URL-kodolt mailto-cimek, pl. `mailto:%20peter@...`
        # (az oldal keszitoje szokozzel kezdte a cimet) -- dekodolas nelkul
        # `%20peter@...` kerulne be, es hard bounce lenne belole.
        addr = unquote(raw).strip().lower().strip(" .")
        if EMAIL_JUNK.search(addr):
            return
        if not normalize.normalize_email(addr):
            return
        if addr not in kind:
            kind[addr] = ez_forras
            order.append(addr)

    for raw in mailto_hits:
        add(raw, "mailto")
    for raw in EMAIL_RE.findall(text_blob):
        add(raw, "text")

    # Sajat domain elore, azon belul a mailto elore a sima szoveges talalatnal.
    order.sort(key=lambda a: (
        0 if a.endswith("@" + domain) else 1,
        0 if kind[a] == "mailto" else 1,
        a,
    ))
    return order[:12], kind


def _clean_phones(blob: str) -> list[str]:
    out: list[str] = []
    for raw in PHONE_RE.findall(blob):
        p = normalize.normalize_phone(raw)
        if p and p not in out:
            out.append(p)
    return out[:5]


def _socials(tree: HTMLParser, base_url: str) -> list[str]:
    out: list[str] = []
    for a in tree.css("a[href]"):
        # Ugyanaz a vedelem, mint a `_discover_links`-ben: az `urljoin` is
        # ERTELMEZI a hosztot, tehat egy elrontott linkre (`[object Object]`)
        # ValueError-t dob. Enelkul egyetlen rossz link az egesz ceget
        # `status='error'`-ba viszi.
        try:
            href = urljoin(base_url, (a.attributes.get("href") or "").strip())
        except ValueError:
            continue
        if any(h in href for h in SOCIAL_HOSTS) and href not in out:
            out.append(href[:200])
    return out[:8]
