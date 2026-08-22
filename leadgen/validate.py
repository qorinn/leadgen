#!/usr/bin/env python3
"""Email-validacio: ket lepcso, hogy majdnem ingyen legyen.

    EMAIL_VALIDATION = off | local_only | full

    off         -- semmit nem ellenoriz (csak fejlesztes kozben)
    local_only  -- INGYENES helyi szuro (ez az alapertelmezes)
    full        -- helyi szuro + Reoon a tulelokre (fizetos)

MIERT NEM MINDEN CIM MEGY REOONBA (terv 2088-2155): a helyi szuro fizetes
nelkul kiszedi a nyilvanvaloan rossz cimeket, tehat a Reoon-koltseg a
toredekere csokken. Az ar nem is a fo indok -- a bounce a draga: az az
egyetlen hiba a rendszerben, ami VISSZAMENOLEG is kart okoz, mert rontja a
kuldo domain hirnevét, es onnantol a JO leadeknek sem erkezik meg a level.

────────────────────────────────────────────────────────────────────────────
HAROM DOLOG, AMI ITT NEM KOZMETIKA:

1. A "NEM TUDOM" SOHA NEM EGYENLO A "ROSSZ"-SZAL.
   Ha a Reoon API elszall, timeoutol, vagy elfogyott a kredit, az eredmeny
   `unknown` -- SOHA nem `invalid`. Egy fel percnyi API-kimaradas kulonben
   csendben ervenytelennek jelolne az egesz listat, es a kovetkezo export
   nem adna ki senkit. Ugyanez az elv, mint a kuldo verify.py-jaban.

2. A `role_account` NEM ERVENYTELEN CIM. (Lasd a _STATUS_MAP kommentjet.)
   Ez a legdragabb hiba, amit itt el lehetne kovetni.

3. A CACHE PENZ. Ugyanarra a cimre 90 napon belul nem kerdezunk ra ujra.
   Erre kotelezo teszt van (tests/test_validate.py), mert egy elromlott
   cache nem hibat dob, hanem szamlat.
"""
from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import httpx

from . import config, db
from .normalize import email_domain

REOON_URL = "https://emailverifier.reoon.com/api/v1/verify"

# A Reoon egy vegponton max 5 parhuzamos szalat enged. Ennel tobbet inditani
# nem gyorsit, csak hibat termel.
_MAX_PARHUZAM = 5

# A POWER mod cimenkent masodpercektol egy percig tarthat (a Reoon sajat
# doksija szerint). Ezert kell a nagyvonalu timeout ES a parhuzamossag.
_TIMEOUT = 75.0

# ─── A LEKEPEZES: Reoon statusz -> a mi negy ertekunk ──────────────────────
#
# A DB `contacts.verify_result` oszlopa negy erteket ismer:
#   valid | invalid | catch_all | unknown
#
# ⚠️ A LEGFONTOSABB SOR EBBEN A FAJLBAN: a `role_account` -> `valid`.
#
# A Reoon kulon statuszkent jelzi, ha egy cim szerepkori cim (info@, office@,
# sales@). Ha ezt `invalid`-nak vennenk, a magyar KKV-lista NAGY RESZE eltunne:
# a jelenlegi 46 kapcsolatbol 31 `generic` tipusu, tulnyomorészt `info@`.
# A magyar kisvallalkozasoknal ez gyakran az EGYETLEN letezo cim -- es a
# rendszer ezt tudatosan vallalja (lasd enrich.ROLE_PREFIXES, ahol az `info`
# szandekosan NINCS a tiltott prefixek kozt).
#
# A `role_account` tehat azt jelenti: "ez a cim letezik, es szerepkori" --
# nem azt, hogy rossz. A szerepkoriseget mi amugy is tudjuk (`email_type`).
#
# `inbox_full`: a postafiok LETEZIK, csak most tele van. Nem ervenytelen cim,
# de ma valoszinuleg visszapattanna -> `unknown`, tehat a szigorubb tier-szabaly
# vonatkozik ra, de nem zarjuk ki veglegesen.
#
# `spamtrap`: EZ A LEGVESZELYESEBB. Spamcsapdara kuldeni a leggyorsabb ut a
# blokklistara. Feltetel nelkul `invalid`.
_STATUS_MAP = {
    # POWER mod
    "safe": "valid",
    "role_account": "valid",        # <-- lasd a fenti magyarazatot
    "catch_all": "catch_all",
    "inbox_full": "unknown",
    "unknown": "unknown",
    "invalid": "invalid",
    "disabled": "invalid",
    "disposable": "invalid",
    "spamtrap": "invalid",
    # QUICK mod (ha valaha atallnank ra)
    "valid": "valid",
}

# Eldobhato / egyszer hasznalatos domainek. Nem teljes lista -- a Reoon ezt
# amugy is elkapja. Ez a HELYI szuro, aminek az a dolga, hogy a nyilvanvalo
# eseteket fizetes nelkul kiszedje.
_ELDOBHATO = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    "throwaway.email", "yopmail.com", "trashmail.com", "sharklasers.com",
    "getnada.com", "temp-mail.org", "fakeinbox.com", "maildrop.cc",
    "dispostable.com", "mailnesia.com", "spamgourmet.com",
}

# Nem letezo, fenntartott TLD-k (RFC 2606). A dev seed ezeket hasznalja.
_TESZT_TLD = (".invalid", ".test", ".example", ".localhost")


# ─── Tier-szabaly (terv 2136-2141) ─────────────────────────────────────────
#
#   valid       -> mehet minden tierbe
#   catch_all   -> csak Tier A es B
#   invalid     -> eldobas
#   unknown     -> csak Tier A
#
# A "tier" a terv szerint a lead JELERŐSSÉGE. Kulon oszlop meg nincs ra
# (az a 9-10. szakasz offer arbitrationjével jon), ezert a `signal_score`
# savjaira kepezzuk le. A hatarok szandekosan itt vannak, egy helyen:
# ha kesobb valodi tier-oszlop lesz, EZT a ket szamot kell kicserelni.
def tier_of(signal_score) -> str:
    pont = float(signal_score or 0)
    if pont >= config.TIER_A_SCORE:
        return "A"
    if pont >= config.TIER_B_SCORE:
        return "B"
    return "C"


def kikuldheto(verify_result: str | None, signal_score) -> tuple[bool, str]:
    """Mehet-e level erre a cimre? (mehet, indok)."""
    eredmeny = (verify_result or "").strip() or "unknown"
    tier = tier_of(signal_score)

    if eredmeny == "invalid":
        return False, "a validacio ervenytelennek merte"
    if eredmeny == "valid":
        return True, ""
    if eredmeny == "catch_all":
        if tier in ("A", "B"):
            return True, ""
        return False, f"catch-all cim, es a lead Tier {tier} (csak A/B mehet)"
    # unknown
    if tier == "A":
        return True, ""
    return False, f"a validacio nem tudott donteni, es a lead Tier {tier} (csak A mehet)"


# ─── 1. lepcso: INGYENES helyi szuro ───────────────────────────────────────

_mx_cache: dict[str, bool] = {}


def van_mx(domain: str) -> bool:
    """Van-e levelezoszervere a domainnek. Folyamaton belul cache-elve.

    Eloszor dnspython (ha telepitve van), aztan a rendszer `dig`-je --
    ugyanaz a sorrend, mint a kuldo verify.py-jaban, hogy a ket oldal
    ugyanugy dontson ugyanarrol a domainrol.
    """
    if domain in _mx_cache:
        return _mx_cache[domain]

    talalat = False
    try:
        import dns.resolver  # type: ignore
        resolver = dns.resolver.Resolver()
        resolver.lifetime = 5.0
        talalat = bool(list(resolver.resolve(domain, "MX")))
    except ImportError:
        try:
            proc = subprocess.run(["dig", "+short", "MX", domain],
                                  capture_output=True, text=True, timeout=8)
            talalat = bool(proc.stdout.strip())
        except Exception:
            # Nem tudjuk eldonteni -> NEM zarunk ki. "Nem tudom" != "rossz".
            talalat = True
    except Exception:
        talalat = False

    _mx_cache[domain] = talalat
    return talalat


def helyi_ellenorzes(email: str) -> tuple[str, str]:
    """Az ingyenes szuro. ('pass'|'fail', indok).

    Ez fut `local_only` ES `full` modban is -- a `full` csak annyit tesz
    hozza, hogy a tulelokre Reoont is hiv.
    """
    cim = (email or "").strip().lower()
    if not cim or "@" not in cim:
        return "fail", "hibas formatum"

    domain = email_domain(cim)
    if not domain:
        return "fail", "ertelmezhetetlen domain"
    if cim.endswith(_TESZT_TLD):
        return "fail", "teszt-domain (nem letezo TLD)"
    if domain in _ELDOBHATO:
        return "fail", "eldobhato email-szolgaltato"
    if not van_mx(domain):
        return "fail", "a domainnek nincs MX rekordja"
    return "pass", ""


# ─── 2. lepcso: Reoon ──────────────────────────────────────────────────────

@dataclass
class VerifyStats:
    cache_talalat: int = 0
    lekerdezve: int = 0
    hiba: int = 0
    helyi_bukas: int = 0
    eredmenyek: dict[str, int] = field(default_factory=dict)

    def szamol(self, eredmeny: str) -> None:
        self.eredmenyek[eredmeny] = self.eredmenyek.get(eredmeny, 0) + 1


def _reoon_egy(email: str) -> tuple[str, str]:
    """Egy cim lekerdezese. (a mi ertekunk, nyers Reoon statusz).

    SOSEM DOB: minden hiba `unknown`. Reszletes indoklas a modul tetején.
    """
    try:
        r = httpx.get(REOON_URL, timeout=_TIMEOUT, params={
            "email": email,
            "key": config.REOON_API_KEY,
            "mode": "power",
        })
    except Exception as exc:  # noqa: BLE001
        return "unknown", f"halozati hiba: {type(exc).__name__}"

    if r.status_code != 200:
        return "unknown", f"HTTP {r.status_code}"

    try:
        data = r.json()
    except Exception:  # noqa: BLE001
        return "unknown", "olvashatatlan valasz"

    nyers = str(data.get("status") or "").strip().lower()
    return _STATUS_MAP.get(nyers, "unknown"), nyers or "(ures statusz)"


def _lejart(verified_at) -> bool:
    """Kell-e ujra kerdezni. Hianyzo idobelyeg = igen."""
    if verified_at is None:
        return True
    import datetime as _dt
    hatar = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=config.VERIFY_CACHE_DAYS)
    ts = verified_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=_dt.timezone.utc)
    return ts < hatar


def ensure_verified(emails: list[str], verbose: bool = True) -> VerifyStats:
    """A megadott cimek validalasa, cache-elve. A `contacts` tablaba ir.

    A CACHE A LENYEG: ugyanarra a cimre `VERIFY_CACHE_DAYS` (90) napon belul
    NEM kerdezunk ra ujra. Ez nem optimalizacio, hanem koltsegvedelem --
    egy elromlott cache nem hibat dob, hanem szamlat.
    """
    stats = VerifyStats()
    mod = config.EMAIL_VALIDATION

    if mod == "off" or not emails:
        return stats

    cimek = sorted({(e or "").strip().lower() for e in emails if e})
    rows = db.query(
        "select email, verify_result, verified_at, local_check from contacts "
        "where email = any(%s)", (cimek,))
    allapot = {r["email"]: r for r in rows}

    # ── 1. lepcso: helyi szuro (ingyenes, mindig fut) ────────────────────
    tulelok: list[str] = []
    with db.connect() as conn, conn.cursor() as cur:
        for cim in cimek:
            eredmeny, indok = helyi_ellenorzes(cim)
            if eredmeny == "fail":
                stats.helyi_bukas += 1
                cur.execute(
                    "update contacts set local_check = 'fail', local_check_reason = %s "
                    "where email = %s", (indok, cim))
                if verbose:
                    print(f"    helyi szuro KIZART: {cim} -- {indok}")
                continue
            cur.execute(
                "update contacts set local_check = 'pass', local_check_reason = null "
                "where email = %s", (cim,))
            tulelok.append(cim)

    if mod != "full":
        return stats

    if not config.REOON_API_KEY:
        print("!!! EMAIL_VALIDATION=full, de nincs REOON_API_KEY a .env-ben.")
        print("    A Reoon lepcso KIMARAD -- csak a helyi szuro futott le.")
        return stats

    # ── 2. lepcso: Reoon, csak a cache-bol hianyzokra ────────────────────
    kerdezendo = [c for c in tulelok if _lejart((allapot.get(c) or {}).get("verified_at"))]
    stats.cache_talalat = len(tulelok) - len(kerdezendo)

    if verbose:
        print(f"  Reoon: {len(kerdezendo)} lekerdezes, "
              f"{stats.cache_talalat} cache-talalat "
              f"({config.VERIFY_CACHE_DAYS} napos cache)")
    if not kerdezendo:
        return stats

    with ThreadPoolExecutor(max_workers=_MAX_PARHUZAM) as pool:
        eredmenyek = list(pool.map(_reoon_egy, kerdezendo))

    with db.connect() as conn, conn.cursor() as cur:
        for cim, (ertek, nyers) in zip(kerdezendo, eredmenyek):
            stats.lekerdezve += 1
            stats.szamol(ertek)
            if ertek == "unknown" and not nyers.startswith(("unknown", "inbox_full")):
                stats.hiba += 1
            cur.execute(
                "update contacts set verify_result = %s, verified_at = now() "
                "where email = %s", (ertek, cim))
            if verbose:
                print(f"    {cim:<38} {ertek:<10} (reoon: {nyers})")

    if stats.hiba and verbose:
        print(f"\n  FIGYELEM: {stats.hiba} cimnel a Reoon nem valaszolt rendesen.")
        print("  Ezek 'unknown'-kent vannak elmentve, NEM 'invalid'-kent -- egy")
        print("  API-kimaradas nem zarhatja ki a listat. Futtasd ujra kesobb.")
    return stats


def report_sor() -> str:
    """Egy sor a `report` kimenetebe: mennyi kreditet hasznaltunk el."""
    rows = db.query("""
        select count(*) filter (where verified_at >= now() - interval '30 days') as h30,
               count(*) filter (where verified_at is not null) as osszes,
               count(*) filter (where verify_result = 'invalid') as ervenytelen
          from contacts
    """)
    r = rows[0] if rows else {}
    return (f"validalva osszesen {r.get('osszes', 0)} cim "
            f"(ebbol 30 napon belul {r.get('h30', 0)}), "
            f"ervenytelen {r.get('ervenytelen', 0)}")
