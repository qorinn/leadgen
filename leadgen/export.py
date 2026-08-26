#!/usr/bin/env python3
"""Export: DB -> cold-email-starter/data/leads.csv

EZ AZ EGYETLEN HELY, AHOL A SCRAPER A KULDO FAJLJAIBA IR. Es pontosan egy
fajlba ir: a leads.csv-be. A sent.csv / do-not-contact.csv / bounces.csv a
kuldo tulajdona, azokat sosem modositjuk.

HAROM DONTES, AMIT ERDEMES ERTENI:

1. TELJES UJRAIRAS, NEM APPEND.
   A store.py-ban nincs upsert es nincs dedup: a build_plan ismetlodo email
   eseten CSENDBEN az utolso sort veszi. Append mellett minden export
   duplikalna. Az ujrairas ezen kivul idempotens teszi az exportot: barmikor
   ujrafuttathato, ugyanaz jon ki.

2. AZ EXPORT UNIOT IR: uj jeloltek + MINDEN FOLYAMATBAN LEVO lead.
   Ez a legkonnyebben elrontheto pont az egesz integracioban. A
   sender.build_plan a leads.csv SORABOL indul ki: ha egy mar megkeresett
   lead kimarad a fajlbol, akkor NEM KAPJA MEG a follow-upjait -- nem hibaval,
   hanem csendben. Ezert a folyamatban levo (queued/sent) leadek mindig
   bekerulnek, amig a szekvenciajuk le nem zarul.

3. A DOMAIN-SZINTU TILTAS AZ UJRAIRASBOL VALO KIHAGYASSAL ERVENYESUL.
   Nem kell a do-not-contact.csv-be irnunk (az marad a guards.py tulajdona):
   eleg kihagyni a sort, mert a build_plan csak a leads.csv-ben szereplo
   cimeket veszi figyelembe. A sent.csv-ben az elozmeny igy is megmarad, tehat
   a guards bounce-parositasa (store.already_contacted) tovabbra is mukodik.
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import config, db, feedback, validate
from .contract import APPROVED_CAMPAIGNS, LEADS_HEADER

# A suppression a lead kiadasanak LEGELSO lepese, nem az utolso (SCRAPER-PLAN 0.4).
# Email-szintu ES domain-szintu tiltast is nez.
_SUPPRESSED = """
  not exists (
    select 1 from suppression sp
     where (sp.email is not null and sp.email = ct.email)
        or (sp.email is null
            and sp.normalized_domain is not null
            and sp.normalized_domain = c.normalized_domain)
  )
"""

# Csak olyan cim mehet ki, amit a helyi szuro atengedett, a Reoon nem mondott
# ervenytelennek, es meg nem pattant vissza veglegesen.
_CONTACT_USABLE = """
      ct.local_check is distinct from 'fail'
  and coalesce(ct.verify_result, '') <> 'invalid'
  and coalesce(ct.bounce_state, '') <> 'hard_bounce'
"""

_COMMON_FIELDS = """
  ct.email                                as email,
  c.company_name                          as company,
  ct.name                                 as contact_name,
  coalesce(c.domain, c.platform_url)      as website,
  c.industry                              as industry,
  c.city                                  as city,
  c.signal_summary                        as notes,
  c.signal_score                          as signal_score,
  coalesce(
    (select s.source_type from sources s
      where s.company_id = c.id and s.source_type <> 'website_crawl'
      order by s.created_at, s.detected_at limit 1),
    (select s.source_type from sources s
      where s.company_id = c.id order by s.created_at, s.detected_at limit 1)
  )                                       as lead_source_type,
  coalesce(
    (select s.source_url from sources s
      where s.company_id = c.id and s.source_type <> 'website_crawl'
      order by s.created_at, s.detected_at limit 1),
    (select s.source_url from sources s
      where s.company_id = c.id order by s.created_at, s.detected_at limit 1)
  )                                       as lead_source_url,
  ct.source_url                           as contact_source_url,
  ct.unsub_token                          as unsub_token,
  c.id                                    as company_id,
  c.normalized_domain                     as normalized_domain,
  coalesce(
    (select max(s.detected_at) from sources s where s.company_id = c.id),
    c.first_seen_at
  )                                       as scraped_at
"""

# 1) Folyamatban levo leadek. Ezek MINDIG bekerulnek, kulonben elmaradnak a
#    follow-upjaik. A kampany es a personalization az outreach sorbol jon:
#    ott van BEFAGYASZTVA a sorba allitas pillanataban.
SQL_INFLIGHT = f"""
select {_COMMON_FIELDS},
       o.campaign                         as campaign,
       o.personalization                  as personalization,
       o.status                           as outreach_status
  from outreach o
  join companies c on c.id = o.company_id
  join contacts  ct on ct.id = o.contact_id
 where o.status in ('queued', 'sent')
   and {_SUPPRESSED}
"""

# 2) Uj jeloltek. Cegenkent EGY kapcsolat (a domain lock miatt), a legjobb
#    email-tipus nyer. A rendezes a signal_score szerint megy: a legidoszerubb
#    leadek kerulnek ki eloszor, ha a `--limit` levagja a listat.
SQL_NEW = f"""
with usable as (
  select ct.*,
         row_number() over (
           partition by ct.company_id
           order by
             case ct.email_type
               when 'personal' then 0 when 'generic' then 1
               when 'role'     then 2 else 3 end,
             case ct.verify_result
               when 'valid' then 0 when 'catch_all' then 1
               when 'unknown' then 2 else 3 end,
             ct.created_at
         ) as rn
    from contacts ct
   where {_CONTACT_USABLE}
)
select {_COMMON_FIELDS},
       c.campaign        as campaign,
       c.personalization as personalization,
       c.best_offer      as best_offer,
       ct.id             as contact_id
  from companies c
  join usable ct on ct.company_id = c.id and ct.rn = 1
 where c.status = 'ready'
   and (c.cooldown_until is null or c.cooldown_until <= now())
   and not exists (
     select 1 from outreach o
      where o.company_id = c.id and o.status in ('queued', 'sent')
   )
   and {_SUPPRESSED}
 order by c.signal_score desc nulls last, c.first_seen_at, ct.email
"""


@dataclass
class ExportStats:
    inflight: int = 0
    new_queued: int = 0
    skipped_dnc: int = 0
    skipped_no_source: int = 0
    skipped_validation: int = 0
    skipped_campaign: int = 0
    limited_out: int = 0
    fake_domains: list[str] = field(default_factory=list)
    validation_notes: list[str] = field(default_factory=list)
    blocked_campaigns: set = field(default_factory=set)

    @property
    def written(self) -> int:
        return self.inflight + self.new_queued


def _dnc_emails() -> set[str]:
    """A kuldo do-not-contact.csv-je, kozvetlenul olvasva.

    ATMENETI MEGOLDAS a 3. szakaszig. Akkor ezt a teljes, watermarkos
    feedback-import valtja fel, ami a DB suppression tablat is tolti. Addig
    is helyes: a DNC-lista szent, es nem varhatunk vele egy szakaszt.

    (A kuldo sender.build_plan-je amugy is szur ra minden futasnal, tehat ez
    nem "vedelem" -- attol viszont megovja a leads.csv-t, hogy mar lezart
    cimeket hordozzon magaval.)
    """
    path = config.SENDER_DATA / "do-not-contact.csv"
    if not path.exists():
        return set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {
            (row.get("email") or "").strip().lower()
            for row in csv.DictReader(f)
            if (row.get("email") or "").strip()
        }


def unsub_url(token: Any) -> str:
    """A szemelyre szolo leiratkozo link. Ures string, ha nem epitheto fel.

    HAROM DOLOG MIATT VAN SAJAT FUGGVENYE, ES NEM EGY f-string a hivo helyen:

    1. HIBAS KONFIGURACIO ESETEN INKABB NE LEGYEN LINK, mint torott link.
       Egy "http://localhost:8888/..." cimre mutato leiratkozo gomb rosszabb,
       mint a regimodi "valaszolj, hogy stop" mondat: a cimzett rakattint,
       nem tortenik semmi, es jogosan gondolja, hogy atvertek. Ezert csak
       https:// cimet fogadunk el.

    2. A TOKEN NELKULI URL ERTELMETLEN. Ha valamiert nincs token (kezzel
       felvett kapcsolat egy regi sorbol), ures stringet adunk -- a sablon
       ilyenkor visszaesik a fallback mondatra.

    3. EGY HELYEN LEGYEN AZ OSSZEFUZES. A base URL vegen levo per-jel megy
       vagy nem megy -- ez pontosan az a reszlet, amit ket helyen ketfelekeppen
       irnank meg.
    """
    base = (config.UNSUB_BASE_URL or "").strip()
    if not base or not token:
        return ""
    if not base.startswith("https://"):
        # Nem dobunk kivetelt: az export ne alljon meg egy alairas-reszlet
        # miatt. De legyen zajos, mert ez konfiguracios hiba.
        print(f"!!! UNSUB_BASE_URL nem https:// cimmel kezdodik ({base!r}) "
              f"-> a levelek a 'valaszolj, hogy stop' mondatra esnek vissza.")
        return ""
    return f"{base.rstrip('/')}/{token}"


def _to_csv_row(row: dict[str, Any]) -> dict[str, str]:
    scraped = row.get("scraped_at")
    return {
        "email": (row.get("email") or "").strip().lower(),
        "company": row.get("company") or "",
        "contact_name": row.get("contact_name") or "",
        "website": row.get("website") or "",
        "industry": row.get("industry") or "",
        "city": row.get("city") or "",
        "notes": row.get("notes") or "",
        "campaign": row.get("campaign") or "",
        "personalization": row.get("personalization") or "",
        "lead_source_type": row.get("lead_source_type") or "",
        "lead_source_url": row.get("lead_source_url") or "",
        "contact_source_url": row.get("contact_source_url") or "",
        "source_url": row.get("lead_source_url") or "",
        "scraped_at": scraped.date().isoformat() if hasattr(scraped, "date") else "",
        "company_id": str(row.get("company_id") or ""),
        "unsub_url": unsub_url(row.get("unsub_token")),
    }


def _write_csv(rows: list[dict[str, str]], path: Path) -> None:
    """Atomikus iras: temp fajl + os.replace.

    A store.py-ban nincs lock. Ha az export felbeszakadna iras kozben, egy
    csonka leads.csv maradna, es a kuldo a kovetkezo futasnal ebbol tervezne.
    Az os.replace ugyanazon a fajlrendszeren atomikus: vagy a regi fajl van
    ott, vagy a teljes uj -- felkesz allapot nincs.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEADS_HEADER, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def collect(limit: int = 0) -> tuple[list[dict[str, str]], ExportStats, list[dict]]:
    """Osszeszedi az exportalando sorokat. NEM ir sehova.

    Visszaad: (csv sorok, statisztika, sorba allitando uj jeloltek).
    """
    stats = ExportStats()
    dnc = _dnc_emails()
    out: list[dict[str, str]] = []
    _score: dict[str, float] = {}

    inflight = db.query(SQL_INFLIGHT)
    candidates = db.query(SQL_NEW)

    for row in inflight:
        email = (row.get("email") or "").strip().lower()
        if email in dnc:
            stats.skipped_dnc += 1
            continue
        kampany = (row.get("campaign") or "").strip()
        if kampany not in APPROVED_CAMPAIGNS:
            stats.skipped_campaign += 1
            stats.blocked_campaigns.add(kampany or "(ures)")
            continue
        out.append(_to_csv_row(row))
        _score[email] = float(row.get("signal_score") or 0)
        stats.inflight += 1

    # ═══ A VALIDACIO KAPUJA ═══════════════════════════════════════════════
    # Itt fut, es nem korabban: csak azokra a cimekre koltunk, amelyek
    # tenylegesen kikuldesre keszulnek. Egy `new` statuszu ceg cime meg
    # sokszor valtozhat az enrichment soran.
    #
    # A `--dry` futasnal IS lefut. Ez szandekos: kulonben a szaraz futas mast
    # mutatna, mint az eles, es pont az ellenorzo lepes hazudna. (`off` es
    # `local_only` modban ez amugy sem kerul penzbe.)
    if candidates:
        vstats = validate.ensure_verified(
            [r.get("email") for r in candidates], verbose=True)
        if vstats.lekerdezve or vstats.cache_talalat or vstats.helyi_bukas:
            stats.validation_notes.append(
                f"validacio ({config.EMAIL_VALIDATION}): "
                f"{vstats.lekerdezve} lekerdezes, {vstats.cache_talalat} cache, "
                f"{vstats.helyi_bukas} helyi kizaras")
        # A frissen irt eredmenyeket vissza kell olvasni: a fenti SQL a
        # validacio ELOTTI allapotot hozta.
        friss = {r["email"]: r for r in db.query(
            "select email, verify_result, local_check from contacts where email = any(%s)",
            ([(r.get("email") or "").strip().lower() for r in candidates],))}
        for row in candidates:
            hit = friss.get((row.get("email") or "").strip().lower())
            if hit:
                row["verify_result"] = hit["verify_result"]
                row["local_check"] = hit["local_check"]

    to_queue: list[dict] = []
    for row in candidates:
        email = (row.get("email") or "").strip().lower()
        if email in dnc:
            stats.skipped_dnc += 1
            continue
        if not (row.get("lead_source_url") or "").strip():
            # 0.4 jogi minimum: forras nelkul nem adunk ki leadet.
            stats.skipped_no_source += 1
            continue
        if (row.get("local_check") or "") == "fail":
            stats.skipped_validation += 1
            continue
        # ═══ A SABLON-KAPU ═══════════════════════════════════════════════
        # Egy kampany szovege addig VAZLAT, amig a felhasznalo at nem nezte.
        # Vazlat szoveggel nem megy ki eles level.
        kampany = (row.get("campaign") or "").strip()
        if kampany not in APPROVED_CAMPAIGNS:
            stats.skipped_campaign += 1
            stats.blocked_campaigns.add(kampany or "(ures)")
            continue
        if config.EMAIL_VALIDATION == "full":
            mehet, indok = validate.kikuldheto(
                row.get("verify_result"), row.get("signal_score"))
            if not mehet:
                stats.skipped_validation += 1
                stats.validation_notes.append(f"  {email}: {indok}")
                continue
        if limit and stats.new_queued >= limit:
            stats.limited_out += 1
            continue
        out.append(_to_csv_row(row))
        _score[email] = float(row.get("signal_score") or 0)
        to_queue.append(row)
        stats.new_queued += 1

    # DETERMINISZTIKUS SORREND -- ez nem kozmetika.
    # A sender.build_plan a `fresh` listat a fajl sorrendjeben veszi, es a napi
    # keret levagja a veget. Tehat a sorrend donti el, KI KAP MA LEVELET.
    # Ket kovetelmeny:
    #   1. a legidoszerubb (legmagasabb signal_score) lead legyen elol;
    #   2. ugyanabbol a DB-allapotbol mindig UGYANAZ a fajl szulessen --
    #      kulonben ket egymas utani export mas sorrendet adna (az azonos
    #      queued_at miatt a Postgres sorrendje nem garantalt), es nem lehetne
    #      megmondani, valtozott-e valojaban valami.
    # Ezert a rendezes a KOZOS mezokon tortenik, nem lekerdezesenkent kulon.
    out.sort(key=lambda r: (-_score.get(r["email"], 0.0), r["email"]))

    stats.fake_domains = sorted({
        r["email"].split("@")[-1] for r in out
        if r["email"].endswith((".invalid", ".test", ".example"))
    })
    return out, stats, to_queue


def _queue(to_queue: list[dict]) -> None:
    """Az uj jeloltek sorba allitasa: outreach sor + companies.status.

    A `status = 'queued'` NEM jelenti, hogy kiment a level -- csak azt, hogy
    a leads.csv-be bekerult. A 'sent'-et majd a feedback-import allitja a
    sent.csv alapjan (3. szakasz). Kulonben egy lead, ami kikerult a fajlba,
    de a napi keret elfogyasa miatt sosem ment ki, hazudna a riportban.
    """
    if not to_queue:
        return
    with db.connect() as conn, conn.cursor() as cur:
        for row in to_queue:
            cur.execute(
                """
                insert into outreach (company_id, contact_id, campaign, offer,
                                      status, personalization)
                     values (%s, %s, %s, %s, 'queued', %s)
                """,
                (row["company_id"], row["contact_id"],
                 row.get("campaign") or "agency_partner",
                 row.get("best_offer"), row.get("personalization")),
            )
            cur.execute(
                "update companies set status = 'queued' where id = %s and status = 'ready'",
                (row["company_id"],),
            )


def run(dry: bool = False, limit: int = 0, skip_feedback: bool = False) -> ExportStats:
    # ═══ A FEEDBACK-IMPORT KOTELEZO ELSO LEPES ════════════════════════════
    # Ez a kuldo "guards hiba = nem kuldunk semmit" invariansanak a parja.
    # Ha nem tudjuk, ki valaszolt vagy iratkozott le, akkor nem tudjuk, kit
    # szabad kiadni -- tehat inkabb semmit nem irunk. A "nem tudom" itt sem
    # lehet egyenlo azzal, hogy "senki".
    if skip_feedback:
        print("!!! A feedback-import KIHAGYVA (--skip-feedback).\n"
              "    Ez csak fejlesztes kozben megengedett: a DB nem tud a\n"
              "    kozben erkezett valaszokrol es leiratkozasokrol.\n")
    else:
        try:
            print("Feedback-import (kotelezo lepes az export elott)")
            feedback.run(verbose=True)
            print()
        except Exception as exc:
            raise SystemExit(
                f"\nHIBA: a feedback-import elszallt -> NEM EXPORTALUNK.\n"
                f"  {type(exc).__name__}: {exc}\n\n"
                "  A leads.csv erintetlen maradt. Amig nem tudjuk, ki valaszolt\n"
                "  vagy iratkozott le, addig nem adhatunk ki uj leadet."
            ) from exc

    rows, stats, to_queue = collect(limit=limit)
    target = config.SENDER_DATA / "leads.csv"

    if dry:
        print(f"[SZARAZ FUTAS] {len(rows)} sor menne ide: {target}\n")
        for row in rows:
            print(f"  {row['email']:<38} {row['campaign']:<16} {row['company']}")
            if row["personalization"]:
                print(f"      -> {row['personalization'][:100]}")
        print()
    else:
        _write_csv(rows, target)
        _queue(to_queue)

    print(f"folyamatban levo : {stats.inflight}")
    print(f"uj, sorba allitva: {stats.new_queued}")
    print(f"osszesen a fajlban: {stats.written}")
    if stats.skipped_dnc:
        print(f"kihagyva (DNC)   : {stats.skipped_dnc}")
    if stats.skipped_no_source:
        print(f"kihagyva (nincs source_url): {stats.skipped_no_source}")
    if stats.skipped_campaign:
        print(f"\nkihagyva (JOVA NEM HAGYOTT KAMPANY): {stats.skipped_campaign}")
        print(f"  erintett kampanyok: {', '.join(sorted(stats.blocked_campaigns))}")
        print("  Ezeknek a sablonja meg VAZLAT. Elesites:")
        print("    1. ird at: cold-email-starter/templates.py")
        print("    2. nezd meg: cd cold-email-starter && python3 preview.py")
        print("    3. vedd fel: leadgen/contract.py -> APPROVED_CAMPAIGNS")
    if stats.skipped_validation:
        # HANGOSAN, es indoklassal: egy nema validacios kizaras pontosan
        # ugy nezne ki, mintha a lead sosem letezett volna.
        print(f"kihagyva (email-validacio): {stats.skipped_validation}")
    for note in stats.validation_notes:
        print(f"  {note}" if not note.startswith("  ") else note)
    if stats.limited_out:
        print(f"limit miatt varakozik: {stats.limited_out}")
    if not dry:
        print(f"\nMegirva: {target}")

    if stats.fake_domains:
        print(
            "\n!!! FIGYELEM: teszt-domainek vannak a listaban "
            f"({', '.join(stats.fake_domains)}).\n"
            "    Ezek nem letezo cimek: eles kuldesnel hard bounce-t okoznanak,\n"
            "    ami kozvetlenul rontja a kuldo domain reputaciojat.\n"
            "    Eles futas elott: leadgen dev clear-seed"
        )
    return stats
