#!/usr/bin/env python3
"""Kozponti konfiguracio a scraperhez. MINDEN ertek kornyezeti valtozobol jon.

Ugyanaz a minta, mint a kuldo config.py-jaban, szandekosan: egy fejlesztonek
egy szokast kell megtanulnia. Ebben a fajlban SOHA ne legyen valodi kulcs.

FIGYELEM: os.environ.setdefault-ot hasznalunk, tehat egy mar beallitott
valodi kornyezeti valtozo FELULIRJA a .env erteket, nem forditva. Ez teszi
lehetove, hogy egy futast ideiglenesen felulvezerelj:
    EMAIL_VALIDATION=off .venv/bin/python -m leadgen.cli export
"""
from __future__ import annotations

import os
from pathlib import Path

# A repo gyokere (a leadgen/ csomag szuloje).
BASE = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _load_dotenv() -> None:
    """Minimalis .env beolvaso (nincs kulso fuggoseg)."""
    env_path = BASE / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def _path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    p = Path(raw)
    return p if p.is_absolute() else (BASE / p).resolve()


# ─── Adatbazis ─────────────────────────────────────────────────────────────
# Supabase -> Connect -> Session pooler -> URI. A 6543-as (transaction) pooler
# NEM jo: nem tamogat prepared statementet, es a migraciok elhasalnanak rajta.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# ─── A kuldo rendszer helye ────────────────────────────────────────────────
# Innen olvassuk a feedbacket, ide irjuk a leads.csv-t (2-3. szakasz).
SENDER_DIR = _path("SENDER_DIR", BASE / "cold-email-starter")
SENDER_DATA = SENDER_DIR / "data"

# ─── Riasztasok (12. szakasz) ──────────────────────────────────────────────
# A riasztasok naploja a KULDO data/ konyvtaraban van, nem a scrapereben:
# a `report --daily` es a napi rutin ott keresi a tobbi allapotfajlt is, es
# igy egy helyen van minden, amit egy uzemeltetesi kerdesnel meg kell nezni.
ALERTS_LOG = SENDER_DATA / "alerts.log"

# Ide megy a riasztasi ertesites. HA URES, CSAK A FAJL-NAPLO KESZUL EL --
# a riasztas maga sosem marad el, csak a kenyelmi ertesites.
#
# Sajat cim legyen (a tied), nem ugyfele: ez uzemeltetesi ertesites.
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "").strip()


def _sender_env() -> dict[str, str]:
    """A KULDO .env-je, beolvasva -- de a kornyezetbe NEM szivarogtatva.

    MIERT NEM os.environ.setdefault, mint a sajat _load_dotenv()-ben: a kuldo
    .env-je SMTP-jelszavakat tartalmaz. Ha ezeket beleraknank a scraper
    kornyezetebe, minden kesobb inditott alfolyamat (Apify-hivas, subprocess)
    orokolne oket. Egy uzemeltetesi ertesites kedveert nem terjesztunk
    jelszot: beolvassuk, hasznaljuk, es itt marad.

    A ket rendszernek KET kulon titok-fajlja van, es ez igy is marad
    (CLAUDE.md). Ez a fuggveny csak OLVAS.
    """
    out: dict[str, str] = {}
    env_path = SENDER_DIR / ".env"
    if not env_path.exists():
        return out
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def sender_smtp_accounts() -> list[dict]:
    """A kuldo SMTP-fiokjai. Ugyanaz a formatum, mint a kuldo config.py-jaban."""
    raw = _sender_env().get("SMTP_ACCOUNTS", "").strip()
    out = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        user, password = chunk.split(":", 1)
        out.append({"user": user.strip(), "password": password.strip()})
    return out


SENDER_SMTP_HOST = _sender_env().get("SMTP_HOST", "")
SENDER_SMTP_PORT = int(_sender_env().get("SMTP_PORT", "465") or 465)
SENDER_SMTP_SSL = _sender_env().get("SMTP_USE_SSL", "true").lower() in ("1", "true", "yes")

# ─── Email validacio ───────────────────────────────────────────────────────
EMAIL_VALIDATION = os.environ.get("EMAIL_VALIDATION", "local_only").strip().lower()
REOON_API_KEY = os.environ.get("REOON_API_KEY", "").strip()
# Ennel frissebb Reoon eredmenyt nem kerdezunk le ujra (kredit = penz).
VERIFY_CACHE_DAYS = int(os.environ.get("VERIFY_CACHE_DAYS", "90"))

# A catch-all szabaly tier-hatarai (terv 2136-2141). A "tier" a lead
# jelerossege; kulon oszlop meg nincs ra, ezert a signal_score savjaira
# kepezzuk. AZERT ALLITHATO .env-bol, mert ez a ket szam donti el, hany
# lead esik ki, ha bekapcsolod a fizetos validaciot -- es ezt tuningolni
# kell tudni kodmodositas nelkul.
TIER_A_SCORE = int(os.environ.get("TIER_A_SCORE", "70"))
TIER_B_SCORE = int(os.environ.get("TIER_B_SCORE", "45"))

# ─── AI (6. szakasztol) ────────────────────────────────────────────────────
# A PROVIDER A MODELLNEVBOL DERUL KI (lasd llm.provider_of), tehat providert
# valtani = ATIRNI EZT AZ EGY SORT a .env-ben. Nincs kulon kapcsolo.
#
#   gpt-*  /  o1 / o3 / o4   -> OpenAI
#   claude-*                 -> Anthropic
#   gemini*                  -> Google
#
# 2026-08-22: a BULK tier Geminirol OpenAI-ra valtott, felhasznaloi dontes
# alapjan (mar volt OpenAI kreditje). A Gemini-integracio ERINTETLENUL
# MEGMARADT a llm.py-ban -- visszaallni ennyi:
#     LLM_BULK_MODEL=gemini-2.5-flash-lite
LLM_BULK_MODEL = os.environ.get("LLM_BULK_MODEL", "gpt-5.6-luna").strip()
LLM_QUALITY_MODEL = os.environ.get("LLM_QUALITY_MODEL", "claude-haiku-4-5").strip()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
# Nem torolve: a Gemini barmikor visszakapcsolhato a LLM_BULK_MODEL-lel.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

# ─── Leiratkozo link ───────────────────────────────────────────────────────
# A leiratkozo oldal cime, token NELKUL. Az export ehhez fuzi hozza a
# contacts.unsub_token erteket:  <base>/<token>
#
# HA EZ URES, A LEVEL VISSZAESIK a "valaszolj, hogy stop" mondatra -- a
# leiratkozas lehetosege tehat SOHA nem tunik el, csak kenyelmetlenebb lesz.
# Ez szandekos: egy torott vagy hianyzo link rosszabb, mint egy regimodi mondat.
#
# A cim SAJAT DOMAINEN legyen, ugyanazon, ahonnan a level megy. Idegen
# domainre mutato leiratkozo link emberileg gyanus (adathalasznak nez ki),
# es a szuroknek is rosszabb jel.
UNSUB_BASE_URL = os.environ.get("UNSUB_BASE_URL", "").strip()

# ─── Penzugyi kuszobok (11. szakasz, 7.1 + 8.3) ────────────────────────────
# MIND FORINTBAN, nem ezer forintban. A beszamolo urlapja "adatok E Ft-ban"
# formaban jelenik meg -- az atvaltas az importer dolga, itt mar forint van.
#
# AZERT .env-bol allithato, mert EZ NEM TECHNIKAI, HANEM UZLETI DONTES: azt
# mondja meg, mekkora cegtol varhato, hogy fizet egy egyedi fejlesztesert.
# A terv kimondja, hogy a kuszobot az ELSO TALALATOK ALAPJAN kell kalibralni,
# tehat valtozni fog, es ehhez nem szabad kodot modositani.
REVENUE_MEDIUM_HUF = float(os.environ.get("REVENUE_MEDIUM_HUF", "100000000"))   # 100 M Ft
REVENUE_HIGH_HUF = float(os.environ.get("REVENUE_HIGH_HUF", "500000000"))       # 500 M Ft

# Letszam-kuszobok. Onalloan is emelnek: egy 30 fos ceg akkor is MEDIUM+,
# ha az arbevetele alacsony (pl. szolgaltato, alacsony arresu kereskedo).
HEADCOUNT_MEDIUM = int(os.environ.get("HEADCOUNT_MEDIUM", "5"))
HEADCOUNT_HIGH = int(os.environ.get("HEADCOUNT_HIGH", "25"))

# 8.3: ettol az arbeveteltol erdekes a "kinotte a dobozos platformot" szog.
# ALACSONYABB, mint a REVENUE_HIGH_HUF -- egy 300 M Ft-os webshop mar utkozik
# a dobozos platform korlataiba, meg ha a ceg egeszekent nem is "nagy".
WEBSHOP_REVENUE_MIN_HUF = float(os.environ.get("WEBSHOP_REVENUE_MIN_HUF", "300000000"))

# ─── Forrasok (9. szakasztol) ──────────────────────────────────────────────
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()

# ─── Helyi konyvtarak ──────────────────────────────────────────────────────
# A nyers HTML azert marad meg, hogy az evidence grounding (10. szakasz)
# utolag is ellenorizheto legyen. .gitignore kizarja.
CACHE_DIR = _path("CACHE_DIR", BASE / "cache")


def require_database_url() -> str:
    """Beszedes hiba, ha hianyzik -- ne psycopg-stack trace fogadja a felhasznalot."""
    if not DATABASE_URL:
        raise SystemExit(
            "HIBA: nincs beallitva a DATABASE_URL.\n"
            f"  Varom itt: {BASE / '.env'}\n"
            "  Supabase -> Connect -> Session pooler -> URI (5432-es port)."
        )
    return DATABASE_URL
