#!/usr/bin/env python3
"""SMTP kuldes es IMAP olvasas. Csak stdlib.

Postafiok-rotacio: minden kuldes a soron kovetkezo fiokot hasznalja, igy a
volumen eloszlik. Egy fiok kiesese nem allitja meg a tobbit.
"""
from __future__ import annotations

import email
import imaplib
import smtplib
import ssl
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

import config
import store

_rotation_index = 0


def next_account() -> dict | None:
    global _rotation_index
    accounts = config.smtp_accounts()
    if not accounts:
        return None
    acc = accounts[_rotation_index % len(accounts)]
    _rotation_index += 1
    return acc


def send(to_email: str, subject: str, body: str, account: dict) -> tuple[bool, str]:
    """Egy plain-text level. (siker, hibauzenet) parost ad vissza.

    A List-Unsubscribe fejlec nem kozvetlenul javitja a kezbesitest, de a
    fogadok pozitivan ertekelik, es a felhasznalonak konnyebb kilepni, mint
    spamnek jelolni. Ez utobbi a fontos: egy spam-jeloles sokkal tobbet art,
    mint egy leiratkozas.
    """
    msg = EmailMessage()
    msg["From"] = formataddr((config.FROM_NAME, account["user"])) if config.FROM_NAME else account["user"]
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=account["user"].split("@")[-1])
    if config.REPLY_TO:
        msg["Reply-To"] = config.REPLY_TO
    msg["List-Unsubscribe"] = f"<mailto:{config.REPLY_TO or account['user']}?subject=unsubscribe>"
    msg.set_content(body)

    try:
        ctx = ssl.create_default_context()
        if config.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=ctx, timeout=30) as s:
                s.login(account["user"], account["password"])
                s.send_message(msg)
        else:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as s:
                s.starttls(context=ctx)
                s.login(account["user"], account["password"])
                s.send_message(msg)
        return True, ""
    except Exception as exc:  # noqa: BLE001 - a hibat naplozzuk, nem nyeljuk el
        return False, f"{type(exc).__name__}: {exc}"


def _decode(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value or ""


def fetch_recent(account: dict, days: int = 14, folder: str = "INBOX") -> list[dict]:
    """Beerkezo levelek az elmult N napbol.

    FIGYELEM (draga tanulsag): ha az IMAP-kapcsolat hibara fut, EZ A FUGGVENY
    KIVETELT DOB, nem ures listat ad vissza. Egy ures lista ugyanis
    megkulonboztethetetlen a "senki nem valaszolt" allapottol, es a hivo
    oldal ilyenkor vigan kikuldene a follow-upot annak is, aki mar valaszolt.
    A "nem tudom" SOHA nem lehet egyenlo a "nincs"-csel.
    """
    import datetime

    since = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%d-%b-%Y")
    out: list[dict] = []
    with imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT) as imap:
        imap.login(account["user"], account["password"])
        imap.select(folder, readonly=True)
        status, data = imap.search(None, f'(SINCE {since})')
        if status != "OK":
            raise RuntimeError(f"IMAP search sikertelen: {status}")
        for uid in (data[0].split() if data and data[0] else []):
            status, raw = imap.fetch(uid, "(RFC822)")
            if status != "OK" or not raw or not raw[0]:
                continue
            msg = email.message_from_bytes(raw[0][1])
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                        except Exception:
                            body = ""
                        break
            else:
                try:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
                except Exception:
                    body = ""
            out.append({
                "from": _decode(msg.get("From", "")),
                "subject": _decode(msg.get("Subject", "")),
                "body": body,
                "uid": uid.decode(),
            })
    return out


def check_accounts() -> int:
    """Onteszt: bejelentkezik minden fiokba. Elso indulaskor futtasd."""
    accounts = config.smtp_accounts()
    if not accounts:
        store.log("HIBA: nincs beallitva SMTP_ACCOUNTS a .env-ben.")
        return 1
    failed = 0
    for acc in accounts:
        ok, err = True, ""
        try:
            ctx = ssl.create_default_context()
            if config.SMTP_USE_SSL:
                with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=ctx, timeout=20) as s:
                    s.login(acc["user"], acc["password"])
            else:
                with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as s:
                    s.starttls(context=ctx)
                    s.login(acc["user"], acc["password"])
        except Exception as exc:  # noqa: BLE001
            ok, err = False, f"{type(exc).__name__}: {exc}"
        store.log(f"SMTP {acc['user']}: {'OK' if ok else 'HIBA - ' + err}")
        failed += 0 if ok else 1
    return failed
