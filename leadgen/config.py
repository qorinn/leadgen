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

# ─── Email validacio ───────────────────────────────────────────────────────
EMAIL_VALIDATION = os.environ.get("EMAIL_VALIDATION", "local_only").strip().lower()
REOON_API_KEY = os.environ.get("REOON_API_KEY", "").strip()
# Ennel frissebb Reoon eredmenyt nem kerdezunk le ujra (kredit = penz).
VERIFY_CACHE_DAYS = int(os.environ.get("VERIFY_CACHE_DAYS", "90"))

# ─── AI (6. szakasztol) ────────────────────────────────────────────────────
LLM_BULK_MODEL = os.environ.get("LLM_BULK_MODEL", "gemini-2.5-flash-lite").strip()
LLM_QUALITY_MODEL = os.environ.get("LLM_QUALITY_MODEL", "claude-haiku-4-5").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()

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
