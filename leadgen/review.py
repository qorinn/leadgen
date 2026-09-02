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
class BounceOverrideResult:
    talalt: bool
    cim: str | None = None


def bounce_override(domain: str) -> BounceOverrideResult:
    """Egy hard bounce miatt kizart ceg visszahozasa -- EMBERI dontes.

    MIKOR JOGOS: ha a visszapattanast nem a ceg okozta, hanem MI. Valos eset
    (2026-09-02): az enrichment egy urlap-placeholderbol
    (`<input placeholder="x@y.hu">`) olvasott ki cimet, tehat a cim sosem
    letezett. A konzervativ hard-bounce szabaly (feedback.py, 2026-08-20)
    azt feltetelezi, hogy a cim egy ELAVULT FORRASBOL jott, es ezert a
    masodik cim is rossz lenne -- ez itt nem all.

    AMI NEM VALTOZIK: a CIM-szintu suppression marad. A rossz cimre soha tobbe
    nem megy level; a ceg viszont megkeresheto egy masik, ujra kinyert cimen.
    A `bounce_override` cimke tartos: a `feedback` ezt latva nem teszi vissza
    a ceget suppressionbe, amikor a guards kesobb ujra beolvassa ugyanazt a
    bounce-ot a postafiokbol.
    """
    with db.connect() as conn, conn.cursor() as cur:
        # A FELTETEL A HARD BOUNCE LETE, NEM A CEG MAI ALLAPOTA. A ket eset,
        # amiben ezt hivni kell, kulonbozo statuszban talalja a ceget:
        #   - a guards mar lefutott  -> a ceg `suppressed`
        #   - a guards MEG NEM futott -> a ceg meg `sent`/`queued`, es a
        #     felulbiralas MEGELOZI a suppressiont (a cimke miatt a feedback
        #     mar nem fogja kizarni, amikor a bounce-ot beolvassa)
        # A masodik eset nelkul a parancsot csak azutan lehetne hasznalni,
        # hogy a rendszer mar kizarta a ceget -- vagyis meg kellene varni egy
        # olyan allapotot, amit epp meg akarunk elozni.
        cur.execute(
            """
            select c.id,
                   (select ct.email from contacts ct
                     where ct.company_id = c.id and ct.bounce_state = 'hard_bounce'
                     order by ct.updated_at desc limit 1) as bounced
              from companies c
             where c.normalized_domain = %s
               and (
                 exists (select 1 from contacts ct
                          where ct.company_id = c.id
                            and ct.bounce_state = 'hard_bounce')
                 or c.status_note like 'hard bounce:%%'
               )
            """,
            (domain,))
        hit = cur.fetchone()
        if not hit:
            return BounceOverrideResult(talalt=False)

        labels.set_label(cur, hit["id"], "bounce_override",
                         {"reason": "a cim kinyerese volt hibas, nem a ceg"})
        # A ceg visszaall feldolgozasra. A kontaktja (a rossz cim) tovabbra is
        # `hard_bounce`, tehat az export nem veszi figyelembe -- uj cim kell.
        cur.execute(
            "update companies set status = 'new', "
            "status_note = 'bounce felulbiralva -- uj cim kell' where id = %s",
            (hit["id"],))
    return BounceOverrideResult(talalt=True, cim=hit["bounced"])


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


def contacts_for(domain: str) -> list[dict]:
    """Egy ceghez tartozo OSSZES ismert kontakt, a `review --pick-contact`
    valasztasahoz. Tobb valodi cim (support@, info@, szemelynevek) kozul
    algoritmus nem tudja eldonteni, melyik a helyes -- ez emberi dontes."""
    return db.query(
        """
        select ct.id, ct.email, ct.email_type, ct.source_kind, ct.verify_result,
               ct.local_check, ct.bounce_state,
               (c.preferred_contact_id = ct.id) as preferred
          from contacts ct
          join companies c on c.id = ct.company_id
         where c.normalized_domain = %s
         order by (c.preferred_contact_id = ct.id) desc, ct.created_at
        """,
        (domain,))


@dataclass
class PickContactResult:
    talalt: bool


def pick_contact(domain: str, email: str) -> PickContactResult:
    """Kezi kivalasztas: ez a cim menjen kikuldesre, a rangsor helyett
    (lasd export.SQL_NEW -- a `preferred_contact_id` mindent felulir)."""
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            update companies set preferred_contact_id = ct.id
              from contacts ct
             where companies.normalized_domain = %s
               and ct.company_id = companies.id
               and ct.email = %s
            returning companies.id
            """,
            (domain, (email or "").strip().lower()))
        hit = cur.fetchone()
    return PickContactResult(talalt=bool(hit))


def review_queue() -> list[dict]:
    """Az emberi dontesre varo cegek (`review` statuszuak)."""
    return db.query("""
        select c.id, c.normalized_domain, c.company_name, c.status_note, c.signal_summary,
               (select ct.email from contacts ct where ct.company_id = c.id limit 1) as email
          from companies c where c.status = 'review'
         order by c.signal_score desc nulls last, c.company_name
    """)
