#!/usr/bin/env python3
"""Platform-domain blocklist es a cegkulcs feloldasa.

EZ EGY VALODI BUG MEGELOZESE, nem ovatoskodas. A magyar KKV-k jelentos
reszenel a directoryban / kiallitoi listan / Facebook oldalon szereplo
"weboldal" nem a sajat domainjuk:

    facebook.com/paladiklima        cegnev.wixsite.com/home
    instagram.com/valamiceg         cegnev.business.site
    cylex.hu/ceg/...                linktr.ee/valami

Ha ezekre lefut a normal domain-normalizalas, akkor tobb szaz kulonbozo ceg
esik ugyanarra a kulcsra (facebook.com), a dedupe egyetlen ceggé olvasztja
oket, es a tobbi NEMAN eltunik. Ezert a platform-domainbol soha nem lesz
company key -- kulon mezoben (platform_url) viszont megmarad, mert igy is
hasznos: ha egy cegnek csak Facebook oldala van, az onmagaban website signal.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import normalize

# Kozossegi es profil-oldalak
_SOCIAL = {
    "facebook.com", "fb.com", "instagram.com", "linkedin.com", "twitter.com",
    "x.com", "youtube.com", "tiktok.com", "pinterest.com", "vimeo.com",
    "linktr.ee", "taplink.cc", "bio.link",
}
# Weboldal-epito es hoszting platformok (aldomainen adnak "sajat" cimet)
_BUILDERS = {
    "wixsite.com", "wix.com", "business.site", "blogspot.com", "wordpress.com",
    "weebly.com", "webnode.hu", "webnode.com", "jimdo.com", "jimdosite.com",
    "squarespace.com", "godaddysites.com", "netlify.app", "vercel.app",
    "github.io", "gitlab.io", "notion.site", "carrd.co", "webflow.io",
    "shoprenter.hu", "unas.hu", "myshopify.com", "ecwid.com",
}
# Magyar es nemzetkozi katalogusok
_DIRECTORIES = {
    "cylex.hu", "cylex-tudakozo.hu", "aranyoldalak.hu", "telefonkonyv.hu",
    "nevjegy.hu", "ceginformacio.hu", "ceginfo.hu", "opten.hu", "bisnode.hu",
    "nemzeticegtar.hu", "cegjegyzek.hu", "cegkereso.hu", "vallalkozasok.hu",
    "yelp.com", "yellowpages.com", "europages.hu", "europages.com",
    "kisokos.hu", "iranyar.hu", "startlap.hu", "hirdetes.hu",
}
# Altalanos szolgaltatok, amik sosem egy ceg sajat domainje
_GENERIC = {
    "google.com", "google.hu", "maps.google.com", "goo.gl", "bit.ly",
    "gmail.com", "freemail.hu", "citromail.hu", "outlook.com", "hotmail.com",
    "yahoo.com", "t-online.hu", "vipmail.hu", "indamail.hu",
    "example.com", "example.hu", "localhost",
}

PLATFORM_DOMAINS = _SOCIAL | _BUILDERS | _DIRECTORIES | _GENERIC


def is_platform(raw: str) -> bool:
    """Igaz, ha a cim egy platformhoz tartozik, nem egy ceg sajat domainjehez."""
    host = normalize.domain_host(raw)
    if host is None:
        return False
    if host in PLATFORM_DOMAINS:
        return True
    # aldomain is szamit: cegnev.wixsite.com, cegnev.business.site
    return any(host.endswith("." + platform) for platform in PLATFORM_DOMAINS)


@dataclass(frozen=True)
class CompanyKey:
    """A ceg azonositasa. Pontosan egy `kind` nyer, a lenti sorrendben."""

    kind: str          # domain | tax | name_city | phone | none
    value: str | None
    normalized_domain: str | None
    platform_url: str | None

    @property
    def usable(self) -> bool:
        return self.kind != "none"


def resolve_company_key(
    website: str | None = None,
    tax_number: str | None = None,
    company_name: str | None = None,
    city: str | None = None,
    phone: str | None = None,
) -> CompanyKey:
    """A dedupe kulcs feloldasa, a tervben rogzitett sorrendben.

    1. sajat domain            <- ez a fo kulcs, ha van
    2. adoszam / cegjegyzekszam
    3. normalizalt cegnev + telepules
    4. normalizalt telefonszam
    """
    platform_url = None
    normalized = None

    if website:
        if is_platform(website):
            # Megtartjuk, mert signal -- de NEM lehet belole company key.
            platform_url = (website or "").strip()
        else:
            normalized = normalize.normalize_domain(website)

    if normalized:
        return CompanyKey("domain", normalized, normalized, platform_url)

    tax = "".join(ch for ch in (tax_number or "") if ch.isdigit())
    if len(tax) >= 8:
        return CompanyKey("tax", tax, None, platform_url)

    name_key = normalize.normalize_company_name(company_name or "")
    city_key = normalize.strip_accents((city or "").strip().lower()) or None
    if name_key and city_key:
        return CompanyKey("name_city", f"{name_key}|{city_key}", None, platform_url)

    normalized_phone = normalize.normalize_phone(phone or "")
    if normalized_phone:
        return CompanyKey("phone", normalized_phone, None, platform_url)

    return CompanyKey("none", None, None, platform_url)
