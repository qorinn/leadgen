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
            "emails": self.emails, "phones": self.phones, "socials": self.socials,
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
                              headers={"User-Agent": UA}) as c:
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


def _discover_links(tree: HTMLParser, base_url: str, host: str) -> dict[str, str]:
    """Belso linkek besorolasa a PAGE_HINTS alapjan."""
    found: dict[str, str] = {}
    for a in tree.css("a[href]"):
        href = (a.attributes.get("href") or "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = urljoin(base_url, href)
        parts = urlsplit(absolute)
        if parts.hostname and host not in parts.hostname:
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
                              headers={"User-Agent": UA}) as probe:
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
                          headers={"User-Agent": UA}) as client:
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
            out.meta_description = (md.attributes.get("content", "")[:400] if md else "")
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
                    if not out.footer_html:
                        f2 = sub.css_first("footer")
                        out.footer_html = (f2.html or "")[:4000] if f2 else ""
                except Exception:
                    continue

            blob = " ".join(out.texts.values()) + " " + html
            out.emails = _clean_emails(blob, domain)
            out.phones = _clean_phones(blob)
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
GENERIC_PREFIXES = {
    "info", "hello", "kapcsolat", "iroda", "office", "contact", "mail",
    "sales", "ertekesites", "marketing", "ugyfelszolgalat", "titkarsag",
}


def classify_email(addr: str) -> str:
    """personal | generic | role -- az export ebben a sorrendben valaszt cimet."""
    local = normalize.strip_accents((addr or "").split("@")[0].lower())
    if local in ROLE_PREFIXES:
        return "role"
    if local in GENERIC_PREFIXES:
        return "generic"
    # "nagy.eszter", "peter", "oliver" -> szemelynek tuno cim
    return "personal"


def pick_contacts(extract: SiteExtract, domain: str) -> list[tuple[str, str]]:
    """(email, tipus) parok, a ceg SAJAT domainjet elonyben reszesitve.

    MIERT SZAMIT: a scrapelt oldalakon idegen cimek is elofordulnak -- a
    tarhelyszolgaltato admin cime, egy partner cege, egy beagyazott widget
    kapcsolattartoja. Ha ilyet irnank a leads.csv-be, nem a celzott ceget
    keresnenk meg. Merve: a marketingtanacsado.hu-n megjelent egy
    `admin@megacp.com` (tarhely) es egy masik domainhez tartozo cim is.
    """
    sajat = [e for e in extract.emails if e.endswith("@" + domain)]
    forras = sajat or extract.emails[:1]     # ha nincs sajat, a legjobb idegen
    return [(e, classify_email(e)) for e in forras]


def _clean_emails(blob: str, domain: str) -> list[str]:
    seen: list[str] = []
    for raw in EMAIL_RE.findall(blob):
        # A blob HTML-t is tartalmaz, tehat nyers `mailto:` hrefek is benne
        # vannak, URL-kodolva. Valos eset: `mailto:%20peter@mpmarketing.hu`
        # (az oldal keszitoje szokozzel kezdte a cimet) -- dekodolas nelkul
        # `%20peter@...` kerult volna a leads.csv-be, es hard bounce lett volna
        # belole. A dekodolas utan a strip() viszi el a szokozt.
        addr = unquote(raw).strip().lower().strip(" .")
        if EMAIL_JUNK.search(addr):
            continue
        if not normalize.normalize_email(addr):
            continue
        if addr not in seen:
            seen.append(addr)
    # A sajat domainhez tartozo cimek elore -- azok a relevansak.
    seen.sort(key=lambda a: (0 if a.endswith("@" + domain) else 1, a))
    return seen[:12]


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
        href = urljoin(base_url, (a.attributes.get("href") or "").strip())
        if any(h in href for h in SOCIAL_HOSTS) and href not in out:
            out.append(href[:200])
    return out[:8]
