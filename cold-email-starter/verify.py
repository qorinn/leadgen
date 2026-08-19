#!/usr/bin/env python3
"""Cim-ellenorzes kuldes ELOTT. Ez a legolcsobb kezbesites-javitas.

Ket reteg:
  1. MX-rekord: letezik-e egyaltalan levelezoszerver a domainhez. Ez mindig
     mukodik, csak DNS kell hozza.
  2. RCPT-probe: a fogadoszervertol megkerdezi, letezik-e a KONKRET cim.
     Ehhez kimeno 25-os port kell.

FIGYELEM, EZ MINKET IS ATVERT: sok felhoszolgaltato (Hetzner, AWS, GCP)
ALAPERTELMEZESBEN blokkolja a kimeno 25-os portot. Ilyenkor a probe minden
cimre "unknown"-t ad, es ha a hivo oldal ezt "halott"-nak veszi, mindenkit
kiszurne. Ezert van kulon egress-teszt, es ezert jelent az "unknown" mindig
"nem tudom", soha nem "rossz".
"""
from __future__ import annotations

import re
import smtplib
import socket
import subprocess

PROBE_SENDER_DEFAULT = "verify-probe@example.com"
TIMEOUT = 6.0

_egress_cache: dict = {"checked": False, "available": False}


def _resolve_mx(domain: str) -> list[str]:
    """MX-rekordok. Eloszor dnspython, ha nincs, akkor a rendszer `dig`-je."""
    try:
        import dns.resolver  # type: ignore

        resolver = dns.resolver.Resolver()
        resolver.lifetime = 5.0
        return [str(r.exchange).rstrip(".").lower() for r in resolver.resolve(domain, "MX")]
    except ImportError:
        pass
    except Exception:
        return []

    try:
        proc = subprocess.run(["dig", "+short", "MX", domain], capture_output=True, text=True, timeout=8)
        hosts = []
        for line in (proc.stdout or "").splitlines():
            parts = line.strip().split()
            if parts:
                hosts.append(parts[-1].rstrip(".").lower())
        return hosts
    except Exception:
        return []


def has_mx(email_or_domain: str) -> bool:
    domain = email_or_domain.split("@")[-1].strip().lower()
    if not domain or "." not in domain:
        return False
    return bool(_resolve_mx(domain))


def smtp_egress_available() -> bool:
    """Kimeno 25-os port teszt ket fuggetlen, ismert MX fele."""
    if _egress_cache["checked"]:
        return _egress_cache["available"]
    ok = False
    for host in ("gmail-smtp-in.l.google.com", "mx1.mail.icloud.com"):
        sock = socket.socket()
        sock.settimeout(5)
        try:
            sock.connect((host, 25))
            ok = True
            break
        except Exception:
            continue
        finally:
            sock.close()
    _egress_cache.update({"checked": True, "available": ok})
    return ok


def probe_mailbox(email_addr: str, probe_sender: str = PROBE_SENDER_DEFAULT) -> str:
    """'alive' | 'dead' | 'unknown'.

    'dead' CSAK vegleges 5xx-nel. Minden mas (timeout, greylisting 4xx,
    blokkolt port) 'unknown', vagyis "nem tudom" -> ne dobd ki a cimet.
    """
    email_addr = (email_addr or "").strip().lower()
    if "@" not in email_addr:
        return "unknown"
    if not smtp_egress_available():
        return "unknown"

    hosts = _resolve_mx(email_addr.split("@")[-1])
    if not hosts:
        return "dead"  # nincs MX: ide biztosan nem lehet levelet kezbesiteni

    for host in hosts[:2]:
        try:
            with smtplib.SMTP(host, 25, timeout=TIMEOUT) as s:
                s.helo(probe_sender.split("@")[-1])
                s.mail(probe_sender)
                code, _ = s.rcpt(email_addr)
            if code == 250:
                return "alive"
            if 500 <= code < 600:
                return "dead"
            return "unknown"
        except Exception:
            continue
    return "unknown"


ROLE_PREFIXES = {
    "abuse", "postmaster", "noreply", "no-reply", "donotreply",
    "spam", "webmaster", "hostmaster", "root",
}


def looks_unsendable(email_addr: str) -> str | None:
    """Olcso, halozat nelkuli szures. None = kuldheto."""
    addr = (email_addr or "").strip().lower()
    if not addr or not re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", addr):
        return "ervenytelen_formatum"
    local = addr.split("@")[0]
    if local in ROLE_PREFIXES:
        return "role_cim"
    return None
