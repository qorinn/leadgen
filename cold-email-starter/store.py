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

LEADS_HEADER = ["email", "company", "contact_name", "website", "industry", "city", "notes"]
SENT_HEADER = ["ts", "email", "domain", "stage", "template", "subject", "account"]
DNC_HEADER = ["ts", "email", "reason", "notes"]
BOUNCE_HEADER = ["ts", "email", "reason", "raw_subject"]


def _ensure(path: Path, header: list[str]) -> None:
    if not path.exists():
        with path.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(header)


def init_all() -> None:
    _ensure(config.LEADS_CSV, LEADS_HEADER)
    _ensure(config.SENT_CSV, SENT_HEADER)
    _ensure(config.DNC_CSV, DNC_HEADER)
    _ensure(config.BOUNCE_CSV, BOUNCE_HEADER)


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


def log(message: str) -> None:
    line = f"[{now()}] {message}"
    print(line, flush=True)
    with config.LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
