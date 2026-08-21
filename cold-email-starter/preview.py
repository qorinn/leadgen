#!/usr/bin/env python3
"""Elonezet es teszt-kuldes. A kikuldes ELOTTI utolso ellenorzes.

    python3 preview.py                          # TELJES levelek a kepernyore
    python3 preview.py --stage follow_up_1      # a 2. level elonezete
    python3 preview.py --send-to en@sajat.hu --limit 2

MIBEN MAS, MINT A `sender.py --dry`:
  - a teljes levelet mutatja, nem az elso 400 karaktert
  - barmelyik fokot (cold / follow_up_1 / follow_up_2) tudja renderelni,
    nem csak azt, ami eppen esedekes
  - el tudja kuldeni MAGADNAK a mintat, a valodi cimzett erintese nelkul

FONTOS, MIT NEM CSINAL A --send-to:
  - NEM ir a sent.csv-be, tehat a valodi lead szekvenciaja erintetlen marad
    (kulonben a ceg ugy szerepelne, mint akinek mar kuldtunk)
  - NEM szamit bele a napi keretbe a mi rendszerunkben
  - a GOOGLE viszont valodi levelnek szamolja (a Workspace napi limitjebe
    beleszamit) -- nehany teszt-level mellett ez erdektelen
"""
from __future__ import annotations

import argparse
import sys

import config
import mailer
import store
import templates

SEP = "═" * 74


def _leads(limit: int) -> list[dict]:
    out, latott = [], set()
    for lead in store.leads():
        addr = (lead.get("email") or "").strip().lower()
        if not addr or addr in latott:
            continue
        latott.add(addr)
        out.append(lead)
        if limit and len(out) >= limit:
            break
    return out


def _render(lead: dict, stage: str) -> dict:
    cold, fu1, fu2 = templates.for_campaign(lead.get("campaign"))
    return {"cold": cold, "follow_up_1": fu1, "follow_up_2": fu2}[stage](lead)


def main() -> int:
    ap = argparse.ArgumentParser(description="Levelek elonezete es teszt-kuldes")
    ap.add_argument("--stage", default="cold",
                    choices=("cold", "follow_up_1", "follow_up_2"))
    ap.add_argument("--limit", type=int, default=0, help="ennyi leadet nezz/kuldj")
    ap.add_argument("--send-to", metavar="CIM",
                    help="ELESBEN elkuldi a mintakat erre a cimre (magadnak)")
    args = ap.parse_args()

    store.init_all()
    leads = _leads(args.limit)
    if not leads:
        print("Nincs lead a data/leads.csv-ben. Futtasd: ./leadgen.sh export")
        return 1

    if not args.send_to:
        print(f"{len(leads)} lead | fok: {args.stage}\n")
        for lead in leads:
            msg = _render(lead, args.stage)
            print(SEP)
            print(f"CIMZETT : {lead.get('email')}")
            print(f"CEG     : {lead.get('company')}")
            print(f"KAMPANY : {lead.get('campaign') or '(alapertelmezett)'}")
            print(f"FORRAS  : {lead.get('source_url') or '-'}")
            print(f"TARGY   : {msg['subject']}")
            print("─" * 74)
            print(msg["body"])
            print()
        return 0

    # ─── Teszt-kuldes magadnak ────────────────────────────────────────────
    accounts = config.smtp_accounts()
    if not accounts:
        print("HIBA: nincs beallitva SMTP_ACCOUNTS.")
        return 1

    print(f"TESZT-KULDES -> {args.send_to}")
    print(f"  {len(leads)} minta, fok: {args.stage}")
    print("  A valodi cimzettek NEM kapnak semmit, es a sent.csv sem valtozik.\n")

    kuldve = 0
    for lead in leads:
        msg = _render(lead, args.stage)
        # A targyba jelolest teszunk, hogy a postafiokodban azonnal lasd,
        # melyik teszt-level melyik ceghez tartozott.
        targy = f"[TESZT: {lead.get('company') or lead.get('email')}] {msg['subject']}"
        ok, err = mailer.send(args.send_to, targy, msg["body"], accounts[0])
        if ok:
            kuldve += 1
            print(f"  OK   {lead.get('company')}")
        else:
            print(f"  HIBA {lead.get('company')}: {err}")

    print(f"\nKikuldve: {kuldve}/{len(leads)}")
    print("A sent.csv NEM valtozott -- a valodi leadek tovabbra is varakoznak.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
