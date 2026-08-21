#!/usr/bin/env python3
"""Normalizalas: domain, cegnev, telefon, email. Tiszta fuggvenyek, nulla I/O.

MIERT VAN ERRE KULON MODUL ES KULON TESZT (a kuldoben nincs test suite):
a normalizalas hibai NEMAK. Ha ket ceg ugyanarra a kulcsra esik, osszeolvadnak
es az egyik nyomtalanul eltunik; ha egy ceg ket kulcsot kap, ketszer kap
levelet -- es ezzel serul az aranyszabaly (egy domain = egy sequence).
Egyik esetben sem dob hibat semmi. Ezert ez az egyetlen hely, ahova tesztet
irunk.

A domain a FO dedupe kulcs. Email alapjan SOHA ne deduplikalj: egy cegnek
tobb cime van, es a cim valtozik.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

# ─── Publikus suffixek ─────────────────────────────────────────────────────
# A naiv "vedd az utolso ket cimket" szabaly konkret adatvesztest okoz:
# a valami.shop.hu-bol shop.hu lenne, es minden shop.hu alatti ceg egyetlen
# ceggé olvadna. A .hu regisztrator veges masodszintu listaja ezert be van
# drotozva. (A teljes Public Suffix List tullone a celon; ha valaha kell,
# ez az egy halmaz cserelendo.)
_HU_SECOND_LEVEL = {
    "2000.hu", "agrar.hu", "bolt.hu", "casino.hu", "city.hu", "co.hu",
    "erotica.hu", "erotika.hu", "film.hu", "forum.hu", "games.hu", "hotel.hu",
    "info.hu", "ingatlan.hu", "jogasz.hu", "konyvelo.hu", "lakas.hu",
    "media.hu", "news.hu", "org.hu", "priv.hu", "reklam.hu", "sex.hu",
    "shop.hu", "sport.hu", "suli.hu", "szex.hu", "tm.hu", "tozsde.hu",
    "utazas.hu", "video.hu",
}
_OTHER_MULTI_LEVEL = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk",
    "com.au", "net.au", "org.au",
    "co.nz", "co.at", "or.at", "com.br", "co.jp", "com.tr", "co.rs",
}
MULTI_LABEL_SUFFIXES = _HU_SECOND_LEVEL | _OTHER_MULTI_LEVEL

_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def strip_accents(text: str) -> str:
    """'Paládi' -> 'Paladi'. A magyar o" es u" is helyesen bomlik."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _host_from(raw: str) -> str | None:
    """Kiszedi a hosztnevet barmibol: URL, 'www.x.hu/utvonal', puszta domain."""
    value = (raw or "").strip().lower()
    if not value:
        return None
    # Az urlsplit sema nelkul az egeszet utvonalnak veszi.
    if "//" not in value:
        value = "//" + value
    host = urlsplit(value).hostname or ""
    host = host.strip().rstrip(".")
    if not host or "." not in host:
        return None
    labels = host.split(".")
    if not all(_LABEL_RE.match(label) for label in labels):
        return None
    return host


def public_suffix(host: str) -> str:
    """A leghosszabb ismert publikus suffix, kulonben az utolso cimke."""
    labels = host.split(".")
    for i in range(len(labels) - 1):
        candidate = ".".join(labels[i:])
        if candidate in MULTI_LABEL_SUFFIXES:
            return candidate
    return labels[-1]


def normalize_domain(raw: str) -> str | None:
    """A regisztralhato domain kisbetusen. None, ha nem ertelmezheto.

    https://www.Example.HU/kapcsolat?x=1  -> example.hu
    shop.example.hu                       -> example.hu
    valami.co.hu                          -> valami.co.hu
    co.hu                                 -> None  (ez maga a suffix)
    """
    host = _host_from(raw)
    if host is None:
        return None
    suffix = public_suffix(host)
    if host == suffix:
        return None  # onmagaban egy publikus suffix, nem ceg
    prefix_labels = host[: -(len(suffix) + 1)].split(".")
    return f"{prefix_labels[-1]}.{suffix}"


def domain_host(raw: str) -> str | None:
    """A teljes hosztnev aldomainnel egyutt (naplozashoz, platform_url-hez)."""
    return _host_from(raw)


# ─── Cegnev ────────────────────────────────────────────────────────────────
# Sorrend szamit: a hosszu alakokat kell eloszor levagni, kulonben a
# "korlatolt felelossegu tarsasag"-bol maradna szemet.
_LEGAL_FORMS_LONG = (
    "korlatolt felelossegu tarsasag",
    "zartkoruen mukodo reszvenytarsasag",
    "nyilvanosan mukodo reszvenytarsasag",
    "kozkereseti tarsasag",
    "kozhasznu tarsasag",
    "betéti tarsasag",
    "beteti tarsasag",
    "egyeni vallalkozo",
    "egyeni ceg",
    # Tobbszavas alakok KOTELEZOEN ide valok: a _LEGAL_FORMS_SHORT szo szerint
    # szur, ott egy ket szobol allo bejegyzes sosem illeszkedne. (Ezt a hibat a
    # tests/test_normalize.py talalta meg.)
    "nonprofit kft",
    "kozhasznu nonprofit kft",
)
_LEGAL_FORMS_SHORT = (
    "kft", "bt", "zrt", "nyrt", "kkt", "kht", "ev", "ec",
    "gmbh", "ltd", "llc", "inc", "sro", "srl", "bv", "nv", "sa", "ag", "oy",
)
_PUNCT_RE = re.compile(r"[^a-z0-9]+")


def normalize_company_name(raw: str) -> str | None:
    """'Paládi Klíma Kft.' / 'PALÁDI KLÍMA KFT' / '...Korlátolt Felelősségű
    Társaság' -> mind 'paladi klima'.

    Ez a FALLBACK dedupe kulcs: csak akkor hasznaljuk, ha nincs sajat domain
    (pl. a cegnek csak Facebook oldala van). Onmagaban gyengebb, mint a
    domain, ezert mindig telepulessel egyutt parositjuk.
    """
    if not raw:
        return None
    text = strip_accents(raw).lower()
    text = _PUNCT_RE.sub(" ", text).strip()
    if not text:
        return None
    for form in _LEGAL_FORMS_LONG:
        text = text.replace(strip_accents(form), " ")
    words = [w for w in text.split() if w and w not in _LEGAL_FORMS_SHORT]
    result = " ".join(words).strip()
    return result or None


# ─── Telefon ───────────────────────────────────────────────────────────────
_DIGITS_RE = re.compile(r"\D+")


def normalize_phone(raw: str) -> str | None:
    """Magyar szamok +36-os alakra. None, ha nem hihetó hosszusagu.

    Harmadlagos dedupe kulcs (a domain es az adoszam utan), ezert inkabb
    legyen None, mint egy bizonytalan talalat.
    """
    if not raw:
        return None
    digits = _DIGITS_RE.sub("", raw)
    if not digits:
        return None
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("06"):
        digits = "36" + digits[2:]
    elif not digits.startswith("36") and len(digits) in (8, 9):
        digits = "36" + digits          # helyi alak, orszaghivo nelkul
    if not digits.startswith("36") or not (10 <= len(digits) <= 11):
        return None
    return "+" + digits


# ─── Email ─────────────────────────────────────────────────────────────────
# FONTOS: a NORMALIZALAS pontosan ugyanaz, mint a kuldoben (.strip().lower()).
# A ket rendszer email alapjan joinol; ha ez elterne, a feedback csendben nem
# talalna ra a leadre.
#
# A MINTA viszont szigorubb, mint a kuldoe, es ez SZANDEKOS. Valos hiba a
# 4. szakasz exportjaban: egy `mailto:%20peter@mpmarketing.hu` linkbol
# `%20peter@mpmarketing.hu` cim kerult a leads.csv-be. A korabbi minta
# ([^@\s]+) ezt atengedte, mert csak szokozt es kukacot tiltott. Eles kuldesnel
# ez BIZTOS hard bounce lett volna -- es a hard bounce az egyetlen hiba a
# rendszerben, ami visszamenoleg is kart okoz: rontja a kuldo domain
# reputaciojat, tehat utana a JO leadeknek sem erkezik meg a level.
#
# Amit a szigoritas kizar: `%`, szokoz, vezeto/zaro pont, ketto pont egymas
# utan, ekezet, alahuzas a domain-reszben. Amit tovabbra is atenged: `+`, `-`,
# `_`, `'` a lokalis reszben (ezek valodi, letezo cimekben elofordulnak).
_LOCAL = r"[a-z0-9!#$&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$&'*+/=?^_`{|}~-]+)*"
_HOST = r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}"
_EMAIL_RE = re.compile(rf"^{_LOCAL}@{_HOST}$")


def normalize_email(raw: str) -> str | None:
    addr = (raw or "").strip().lower()
    return addr if _EMAIL_RE.match(addr) else None


def email_domain(raw: str) -> str | None:
    addr = normalize_email(raw)
    return normalize_domain(addr.split("@")[-1]) if addr else None
