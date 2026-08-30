#!/usr/bin/env python3
"""Emberi dontes: review/hold/rejected vagy automatikusan versenytarskent
kizart cegek jovahagyasa/elutasitasa.

EGY FORRAS, KET HIVO (WEBUI-TERV.md F5, ugyanaz a minta, mint a
report.py *_adat() fuggvenyei -- lasd annak modul-docstringjet): a CLI
`review --approve/--reject/--suppressed` es a webui `/api/review/*` router
UGYANEZEKET a fuggvenyeket hivja. Korabban ez a logika a cli.py-ban, egy
argparse-kezelo torzsebe volt irva -- ha a webui kulon SQL-t irna ugyanerre,
ket hely donthetne el csendben maskepp, melyik statusz-atmenet engedelyezett.

A fuggvenyek DOMAIN szerint dolgoznak, nem company_id szerint -- ez szandekos:
igy a CLI (`--approve <domain>`, `--reject <domain>`) viselkedese es kimenete
szo szerint valtozatlan marad. A webui router (id-bol jon a URL-ben) old fel
id -> domain iranyban, mielott ide hivna.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import db, labels


@dataclass
class ApproveResult:
    talalt: bool
    uj_status: str | None = None


def approve(domain: str) -> ApproveResult:
    """A gep automatikus VERSENYTARS-dontese (es a review/hold/rejected
    allapot) felulbiralhato innen. Mas suppression-ok (leiratkozas, bounce)
    ezen a fuggvenyen at sem oldhatok fel veletlenul -- a WHERE-ben nincsenek
    benne."""
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select c.id,
                   exists (
                     select 1 from contacts ct
                      where ct.company_id = c.id
                        and ct.local_check is distinct from 'fail'
                        and coalesce(ct.verify_result, '') <> 'invalid'
                        and coalesce(ct.bounce_state, '') <> 'hard_bounce'
                   ) as van_kapcsolat
              from companies c
             where c.normalized_domain = %s
               and (
                 c.status in ('review', 'hold', 'rejected')
                 or (c.status = 'suppressed' and exists (
                   select 1 from suppression sp
                    where sp.normalized_domain = c.normalized_domain
                      and sp.reason = 'competitor'
                 ))
               )
            """,
            (domain,))
        hit = cur.fetchone()
        if not hit:
            return ApproveResult(talalt=False)

        cur.execute("delete from suppression where normalized_domain = %s "
                    "and reason = 'competitor'", (domain,))
        uj_status = "ready" if hit["van_kapcsolat"] else "scored"
        cur.execute(
            "update companies set status = %s, status_note = 'kezi jovahagyas' "
            "where id = %s", (uj_status, hit["id"]))
        for label in ("manual_review", "enterprise_hold", "legacy_rejected"):
            labels.clear_label(cur, hit["id"], label)
    return ApproveResult(talalt=True, uj_status=uj_status)


@dataclass
class RejectResult:
    talalt: bool


def reject(domain: str, reason: str = "manual_block") -> RejectResult:
    """MIERT NEM CSAK `review` ALLAPOTBOL: az 5. szakasz emberi feladata az,
    hogy a kikuldes elott VEGIGOLVASD a dry-run kimenetet -- "ez az utolso
    visszafordithato pont". Csakhogy amit ott latsz, az mar `queued`:
    exportalva van a leads.csv-be. Ha innen nem lehetne kihuzni egy ceget, a
    felulvizsgalatnak nem lenne eszkoze. A `sent` is benne van: onnan a
    kihuzas a MEG HATRALEVO follow-upokat allitja le."""
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("select id from companies where normalized_domain = %s "
                    "and status in ('review','queued','sent','ready','enriched','new')",
                    (domain,))
        hit = cur.fetchone()
        if not hit:
            return RejectResult(talalt=False)

        cur.execute("update companies set status = 'suppressed', status_note = %s "
                    "where id = %s",
                    (f"kezi elutasitas: {reason}", hit["id"]))
        cur.execute("insert into suppression (normalized_domain, reason, note) "
                    "values (%s, %s, 'kezi elutasitas') "
                    "on conflict (normalized_domain) where normalized_domain is not null "
                    "and email is null do nothing", (domain, reason))
        # A folyamatban levo megkereses lezarasa. Enelkul a domain lock
        # reszleges indexe szerint a szekvencia orokre "aktiv" maradna.
        cur.execute("update outreach set status = 'stopped' "
                    "where company_id = %s and status in ('queued','sent')",
                    (hit["id"],))
    return RejectResult(talalt=True)


def suppressed_competitors() -> list[dict]:
    """A rendszer altal AUTOMATIKUSAN kizart versenytarsak, felulbiralhatok
    (`review --suppressed`, `GET /api/review/suppressed`)."""
    return db.query("""
        select c.id, c.normalized_domain, c.company_name, c.status_note,
               s.raw_signal->>'title' as title
          from companies c
          left join sources s on s.company_id = c.id and s.source_type = 'website_crawl'
         where c.status = 'suppressed' and c.status_note like 'versenytars%'
         order by c.normalized_domain
    """)


def review_queue() -> list[dict]:
    """Az emberi dontesre varo cegek (`review` statuszuak)."""
    return db.query("""
        select c.id, c.normalized_domain, c.company_name, c.status_note, c.signal_summary,
               (select ct.email from contacts ct where ct.company_id = c.id limit 1) as email
          from companies c where c.status = 'review'
         order by c.signal_score desc nulls last, c.company_name
    """)
