#!/usr/bin/env python3
"""Kozponti konfiguracio. MINDEN ertek kornyezeti valtozobol jon.

Ebben a fajlban SOHA ne legyen valodi kulcs, jelszo vagy postafiok-cim.
Masold a .env.example fajlt .env-re es azt toltsd ki.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)


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


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# ─── Kuldo postafiokok ─────────────────────────────────────────────────────
# Tobb postafiok = rotacio. Formatum (vesszovel elvalasztva):
#   SMTP_ACCOUNTS=user1@sajatdomain.hu:jelszo1,user2@sajatdomain.hu:jelszo2
# A jelszavak a .env-ben vannak, ide SOHA ne ird be oket.
def smtp_accounts() -> list[dict]:
    raw = os.environ.get("SMTP_ACCOUNTS", "").strip()
    out = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        user, password = chunk.split(":", 1)
        out.append({"user": user.strip(), "password": password.strip()})
    return out


SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = _int("SMTP_PORT", 465)
SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "true").lower() in ("1", "true", "yes")

IMAP_HOST = os.environ.get("IMAP_HOST", "")
IMAP_PORT = _int("IMAP_PORT", 993)

FROM_NAME = os.environ.get("FROM_NAME", "")
REPLY_TO = os.environ.get("REPLY_TO", "")

# ─── Alairas ───────────────────────────────────────────────────────────────
# Ami nincs kitoltve, az KIMARAD az alairasbol -- nem lesz belole ures sor es
# nem lesz belole "<TELEFON>" placeholder. Ugyanaz a szabaly, mint a
# templates._greeting()-nel: nyers placeholder SOHA ne menjen ki.
#
# A telefonszam es a weboldal a hitelesseget noveli (egy ember irja, akit el
# lehet erni), es a Gmail Promociok-besorolasat NEM rontja: egyetlen sajat
# domainre mutato link egy alairasban a normalis emberi level jegye.
# Marketing-URL-t, kovetokodot, UTM-parametert viszont NE tegyel ide.
SIGNATURE_PHONE = os.environ.get("SIGNATURE_PHONE", "").strip()
SIGNATURE_URL = os.environ.get("SIGNATURE_URL", "").strip()

# ─── Volumen es utemezes ───────────────────────────────────────────────────
# FONTOS: uj domainnel/postafiokkal NE indulj magas szammal. A limits.py
# fokozatosan emeli, ha a kezbesitesi jelek tisztak.
DAILY_CAP_START = _int("DAILY_CAP_START", 20)       # elso napi keret / postafiok
DAILY_CAP_CEILING = _int("DAILY_CAP_CEILING", 200)  # felso plafon / postafiok
RAMP_STEP = _int("RAMP_STEP", 20)                   # ennyivel emel egy lepesben
RAMP_STEP_DAYS = _int("RAMP_STEP_DAYS", 3)          # ennyi tiszta nap kell egy emeleshez

SEND_WINDOW_START = _int("SEND_WINDOW_START", 8)    # ora, helyi ido
SEND_WINDOW_END = _int("SEND_WINDOW_END", 17)
SEND_ON_WEEKEND = os.environ.get("SEND_ON_WEEKEND", "false").lower() in ("1", "true", "yes")

MIN_DELAY_SECS = _int("MIN_DELAY_SECS", 25)   # ket kuldes kozotti szunet
MAX_DELAY_SECS = _int("MAX_DELAY_SECS", 90)

# ─── Follow-up letra ───────────────────────────────────────────────────────
# Mindketto az EREDETI cold email datumatol szamit, nem egymastol.
FU1_DELAY_DAYS = _int("FU1_DELAY_DAYS", 5)
FU2_DELAY_DAYS = _int("FU2_DELAY_DAYS", 10)

# ─── Kezbesitesi kuszobok (riasztas) ───────────────────────────────────────
REJECT_RATE_ALERT = float(os.environ.get("REJECT_RATE_ALERT", "0.03"))
BOUNCE_RATE_ALERT = float(os.environ.get("BOUNCE_RATE_ALERT", "0.04"))

# ─── Adatfajlok ────────────────────────────────────────────────────────────
LEADS_CSV = DATA / "leads.csv"
SENT_CSV = DATA / "sent.csv"
DNC_CSV = DATA / "do-not-contact.csv"
BOUNCE_CSV = DATA / "bounces.csv"
# A beerkezo valaszok szovege. A guards.py irja, a scraper olvassa
# (AI valasz-osztalyozas). Enelkul a valasz szovege eldobodna: eddig csak
# egy DNC-sor maradt belole, ok-koddal.
REPLIES_CSV = DATA / "replies.csv"
RAMP_JSON = DATA / "ramp_state.json"
LOG_FILE = DATA / "sender.log"
