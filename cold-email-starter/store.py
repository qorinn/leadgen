#!/usr/bin/env python3
"""CSV-alapu tarolas. Szandekosan nincs adatbazis: igy barmikor kezzel is
megnyithato, verziokezelheto es athelyezheto.

Negy fajl:
  leads.csv          - a lead-lista (te toltod fel)
  sent.csv           - minden kimeno level egy sor (igazsagforras a volumenre)
  do-not-contact.csv - suppression. Aki itt van, annak SOHA nem megy level.
  bounces.csv        - visszapattant cimek naploja
"""
from __future__ import annotations

import csv
import datetime
from pathlib import Path

import config

# A scraper altal irt mezok is itt vannak. Biztonsagos bovites: minden olvasas
# es iras csv.DictReader/DictWriter, tehat NEV szerinti, nem pozicio szerinti --
# amig az `email` mezo megvan, egyik modul sem torik el.
#
# FIGYELEM: ennek a listanak egyeznie kell a leadgen/contract.py LEADS_HEADER-evel.
# Ha csak az egyik oldalt irod at, a tests/test_contract.py elhasal.
LEADS_HEADER = [
    "email", "company", "contact_name", "website", "industry", "city", "notes",
    "campaign", "personalization", "source_url", "scraped_at", "company_id",
    "unsub_url",
]
SENT_HEADER = ["ts", "email", "domain", "stage", "template", "subject", "account"]
DNC_HEADER = ["ts", "email", "reason", "notes"]
BOUNCE_HEADER = ["ts", "email", "reason", "raw_subject"]
# `msg_id`: a level Message-ID fejlece. EZ A DEDUP KULCS -- a guards minden
# futasnal ujraolvassa a teljes 14 napos postafiokot, tehat ugyanaz a valasz
# tobbszor is elenk kerul. Message-ID nelkul minden futas duplikalna.
# `classified`: a scraper (6. szakasz) tolti ki, a kuldo nem nyul hozza.
REPLIES_HEADER = ["ts", "msg_id", "email", "subject", "body", "classified"]


def _ensure(path: Path, header: list[str]) -> None:
    if not path.exists():
        with path.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(header)


def init_all() -> None:
    _ensure(config.LEADS_CSV, LEADS_HEADER)
    _ensure(config.SENT_CSV, SENT_HEADER)
    _ensure(config.DNC_CSV, DNC_HEADER)
    _ensure(config.BOUNCE_CSV, BOUNCE_HEADER)
    _ensure(config.REPLIES_CSV, REPLIES_HEADER)


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _append(path: Path, header: list[str], row: dict) -> None:
    _ensure(path, header)
    with path.open("a", encoding="utf-8", newline="") as f:
        csv.DictWriter(f, fieldnames=header).writerow(row)


def now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def today() -> str:
    return datetime.date.today().isoformat()


# ─── Leadek ────────────────────────────────────────────────────────────────

def leads() -> list[dict]:
    return _read(config.LEADS_CSV)


# ─── Kuldes-naplo ──────────────────────────────────────────────────────────

def sent_rows() -> list[dict]:
    return _read(config.SENT_CSV)


def record_send(email: str, stage: str, template: str, subject: str, account: str) -> None:
    email = email.strip().lower()
    _append(config.SENT_CSV, SENT_HEADER, {
        "ts": now(),
        "email": email,
        "domain": email.split("@")[-1] if "@" in email else "",
        "stage": stage,
        "template": template,
        "subject": subject,
        "account": account,
    })


def sent_today_count() -> int:
    d = today()
    return sum(1 for r in sent_rows() if (r.get("ts") or "").startswith(d))


def already_contacted() -> set[str]:
    """Minden cim, akinek valaha kuldtunk barmit."""
    return {(r.get("email") or "").strip().lower() for r in sent_rows()}


# ─── Suppression (DNC) ─────────────────────────────────────────────────────

def dnc_emails() -> set[str]:
    return {(r.get("email") or "").strip().lower() for r in _read(config.DNC_CSV)}


def add_to_dnc(email: str, reason: str, notes: str = "") -> bool:
    """Idempotens: ha mar bent van, nem duplikal. True, ha most kerult be."""
    email = email.strip().lower()
    if not email or email in dnc_emails():
        return False
    _append(config.DNC_CSV, DNC_HEADER, {
        "ts": now(), "email": email, "reason": reason, "notes": notes,
    })
    return True


# ─── Bounce-naplo ──────────────────────────────────────────────────────────

def bounce_rows() -> list[dict]:
    return _read(config.BOUNCE_CSV)


def record_bounce(email: str, reason: str, raw_subject: str = "") -> None:
    _append(config.BOUNCE_CSV, BOUNCE_HEADER, {
        "ts": now(), "email": email.strip().lower(),
        "reason": reason, "raw_subject": raw_subject[:200],
    })


# ─── Valasz-naplo ──────────────────────────────────────────────────────────
# MIERT VAN ERRE SZUKSEG: a guards.py eddig beolvasta a valasz szoveget,
# mintat illesztett ra, majd ELDOBTA. Csak egy DNC-sor maradt belole. Emiatt
# a tervezett AI valasz-osztalyozasnak (ami a suppression tablat toltene)
# egyszeruen nem volt bemenete. Ez a fajl az a bemenet.
#
# A kuldo csak IR ide. Az osztalyozast a scraper vegzi, es a `classified`
# oszlopot is o tolti -- a kuldo sosem olvassa vissza.

def reply_rows() -> list[dict]:
    return _read(config.REPLIES_CSV)


def reply_msg_ids() -> set[str]:
    """A mar naplozott valaszok Message-ID-jai (dedup a guards ujrafutasa ellen)."""
    return {(r.get("msg_id") or "").strip() for r in reply_rows() if (r.get("msg_id") or "").strip()}


def record_reply(msg_id: str, email: str, subject: str, body: str) -> None:
    _append(config.REPLIES_CSV, REPLIES_HEADER, {
        "ts": now(),
        "msg_id": (msg_id or "").strip(),
        "email": email.strip().lower(),
        "subject": (subject or "")[:300],
        # 2000 karakter boven eleg az osztalyozashoz, es igy a fajl nem hizik
        # el az idezett elozmenyektol (a valaszok gyakran tartalmazzak a mi
        # sajat levelunket is, teljes egeszeben).
        "body": (body or "")[:2000],
        "classified": "",
    })


def log(message: str) -> None:
    line = f"[{now()}] {message}"
    print(line, flush=True)
    with config.LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
