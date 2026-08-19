#!/usr/bin/env python3
"""Fo futtato: kivalasztja a mai cimzetteket es kikuldi a leveleket.

Hasznalat:
    python3 sender.py --dry     # SEMMIT nem kuld, csak megmutatja a tervet
    python3 sender.py --live    # eles kuldes

ALAPERTELMEZES A SZARAZ FUTAS. Elesben kuldeni csak explicit --live
kapcsoloval lehet. Ez szandekos: a veletlen kikuldes visszafordithatatlan.

A sorrend, amit betart:
  1. Guards (valasz / leiratkozas / bounce) - ha ez hibara fut, MEGALL.
  2. Idoablak es napi keret ellenorzese.
  3. Follow-upok eloszor (a mar elkezdett beszelgetes tobbet er, mint egy uj).
  4. A maradek keretbol friss cold.
"""
from __future__ import annotations

import argparse
import datetime
import sys
import time

import config
import guards
import limits
import mailer
import store
import templates
import verify


def _stage_of(email_addr: str, sent_rows: list[dict]) -> tuple[str | None, datetime.date | None]:
    """Melyik fokon all ez a cim, es mikor ment ki az EREDETI cold?"""
    rows = [r for r in sent_rows if (r.get("email") or "").lower() == email_addr]
    if not rows:
        return None, None
    rows.sort(key=lambda r: r.get("ts", ""))
    original = rows[0]
    try:
        original_date = datetime.date.fromisoformat((original.get("ts") or "")[:10])
    except ValueError:
        original_date = None
    stages = {r.get("template") for r in rows}
    if "follow_up_2" in stages:
        return "done", original_date
    if "follow_up_1" in stages:
        return "follow_up_1", original_date
    return "cold", original_date


def build_plan(limit: int) -> list[tuple[dict, str, callable]]:
    """(lead, fok_neve, sablon_fuggveny) harmasok, prioritas szerint."""
    sent_rows = store.sent_rows()
    dnc = store.dnc_emails()
    today = datetime.date.today()

    lead_by_email = {}
    for lead in store.leads():
        addr = (lead.get("email") or "").strip().lower()
        if addr:
            lead_by_email[addr] = lead

    followups: list = []
    fresh: list = []

    for addr, lead in lead_by_email.items():
        if addr in dnc:
            continue
        if verify.looks_unsendable(addr):
            continue

        stage, original_date = _stage_of(addr, sent_rows)

        if stage is None:
            fresh.append((lead, "cold", templates.cold))
            continue
        if stage == "done" or original_date is None:
            continue

        age = (today - original_date).days
        if stage == "cold" and age >= config.FU1_DELAY_DAYS:
            followups.append((lead, "follow_up_1", templates.follow_up_1))
        elif stage == "follow_up_1" and age >= config.FU2_DELAY_DAYS:
            followups.append((lead, "follow_up_2", templates.follow_up_2))

    return (followups + fresh)[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description="Cold email kuldo")
    parser.add_argument("--live", action="store_true", help="ELES kuldes (enelkul szaraz futas)")
    parser.add_argument("--dry", action="store_true", help="szaraz futas (alapertelmezes)")
    parser.add_argument("--skip-guards", action="store_true", help="csak fejlesztes kozben")
    parser.add_argument("--limit", type=int, default=0, help="felso korlat erre a futasra")
    args = parser.parse_args()

    live = args.live and not args.dry
    store.init_all()

    if not config.smtp_accounts():
        store.log("HIBA: SMTP_ACCOUNTS nincs beallitva. Masold a .env.example-t .env-re.")
        return 1

    # 1. Vedelmi reteg
    if not args.skip_guards:
        try:
            stats = guards.run()
            store.log(f"Guards ok: {stats}")
        except Exception as exc:  # noqa: BLE001
            store.log(f"Guards HIBA -> nem kuldunk semmit: {exc}")
            return 1

    # 2. Idoablak (szaraz futasnal nem akadaly, hogy barmikor tesztelhess)
    open_now, why = limits.in_send_window()
    if live and not open_now:
        store.log(f"Nem kuldunk: {why}")
        return 0

    # 3. Keret
    remaining = limits.remaining_today()
    if args.limit:
        remaining = min(remaining, args.limit)
    if remaining <= 0:
        store.log(f"A mai keret elfogyott ({store.sent_today_count()}/{limits.daily_cap()}).")
        return 0

    plan = build_plan(remaining)
    if not plan:
        store.log("Nincs kuldheto cimzett. Toltsd fel a data/leads.csv fajlt.")
        return 0

    store.log(
        f"Terv: {len(plan)} level | mai keret {limits.daily_cap()} | "
        f"eddig ma {store.sent_today_count()} | mod: {'ELES' if live else 'SZARAZ'}"
    )

    sent = failed = 0
    for lead, stage, render in plan:
        addr = (lead.get("email") or "").strip().lower()
        msg = render(lead)

        if not live:
            print(f"\n--- [{stage}] -> {addr}")
            print(f"Targy: {msg['subject']}")
            print(msg["body"][:400] + ("..." if len(msg["body"]) > 400 else ""))
            continue

        account = mailer.next_account()
        if account is None:
            store.log("Nincs elerheto kuldo fiok.")
            break

        ok, err = mailer.send(addr, msg["subject"], msg["body"], account)
        if ok:
            store.record_send(addr, stage, msg["template"], msg["subject"], account["user"])
            sent += 1
            store.log(f"OK [{stage}] {addr} ({account['user']})")
            time.sleep(limits.send_delay())
        else:
            failed += 1
            store.log(f"HIBA [{stage}] {addr}: {err}")

    if live:
        store.log(f"Futas vege: kikuldve={sent} hiba={failed}")
    else:
        store.log(f"Szaraz futas vege: {len(plan)} level menne ki. Eles kuldes: --live")
    return 0


if __name__ == "__main__":
    sys.exit(main())
