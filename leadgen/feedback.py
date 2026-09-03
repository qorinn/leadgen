#!/usr/bin/env python3
"""Feedback-import: a kuldo CSV-i -> DB.

    sent.csv            -> outreach.status / stage / sent_at, companies.status
    do-not-contact.csv  -> suppression, companies.status
    bounces.csv         -> contacts.bounce_state
    replies.csv         -> reply_events   (osztalyozatlanul, a 6. szakasz tolti)
    rejects.csv         -> contacts.send_reject_count / send_error (12. szakasz)

MIERT EZ A LEGFONTOSABB MODUL AZ EGESZ INTEGRACIOBAN: e nelkul a scraper
holnap ujra kiadja azt a leadet, aki ma nemet mondott. A kuldo tudja, ki
valaszolt es ki pattant vissza -- a scraper nem. Ez a fajl az egyetlen ut
visszafele.

HAROM TERVEZESI DONTES:

1. FAJL-OLVASAS, NEM API. Ugyanaz a gep, ugyanaz a repo. A CSV-k append-only,
   idobelyegzett naplok: pontosan az az adatstruktura, amit inkrementalisan
   olvasni a legegyszerubb. Egy webhook-reteg futo szolgaltatast igenyelne --
   pont azt az uzemeltetesi terhet, amit a terv kerulni akar.

2. WATERMARK = FELDOLGOZOTT SOROK SZAMA. A fajlok csak nonek, tehat a
   sorszam megbizhato jelolo. Ha megis rovidebb lett a fajl (kezi
   szerkesztes, rotalas), a watermark nullazodik es ujra feldolgozunk
   mindent -- ez biztonsagos, mert minden iras upsert.

3. MINDEN EGY TRANZAKCIOBAN. Ha barmelyik fajl feldolgozasa elszall, a
   watermarkok sem lepnek elore. Igy nincs olyan allapot, hogy "a felet
   beolvastuk, de nem tudjuk, melyik felet".
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import config, db, labels
from .enrich import FREEMAIL_DOMAINS as _FREEMAIL
from .normalize import email_domain, normalize_email

# A cegek allapota, amit a feedback NEM irhat felul. Ha valaki mar valaszolt
# vagy tiltva van, egy kesobb feldolgozott sent.csv sor ne huzza vissza
# 'sent'-be. (A CSV-k sorrendje a feldolgozas sorrendje, nem az esemenyeke.)
_TERMINAL = ("replied", "suppressed", "rejected")


@dataclass
class FeedbackStats:
    sent_rows: int = 0
    sent_matched: int = 0
    sequences_done: int = 0
    dnc_rows: int = 0
    replied: int = 0
    suppressed: int = 0
    bounce_rows: int = 0
    reply_rows: int = 0
    reject_rows: int = 0
    rejects_matched: int = 0
    unknown_emails: set[str] = field(default_factory=set)
    reset_files: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (self.sent_rows + self.dnc_rows + self.bounce_rows
                + self.reply_rows + self.reject_rows)


class FeedbackError(RuntimeError):
    """A kuldo allapota nem olvashato. A hivo oldal ilyenkor NE exportaljon."""


def _read_new(cur, path: Path, required: bool = True) -> tuple[list[dict[str, Any]], int, bool]:
    """A watermark ota keletkezett sorok. Hianyzo fajl eseten hibat dob.

    Miert hiba a hianyzo fajl es nem ures lista: pontosan ugyanaz a logika,
    mint a kuldo mailer.fetch_recent()-jenel. A "nem tudom" soha nem lehet
    egyenlo azzal, hogy "nem tortent semmi" -- kulonben ugy exportalnank,
    hogy fogalmunk sincs, ki iratkozott le kozben.
    """
    if not path.exists():
        if required:
            raise FeedbackError(
                f"nem talalhato: {path}\n"
                "  A kuldo meg nem futott le, vagy rossz a SENDER_DIR."
            )
        return [], 0, False

    with path.open(encoding="utf-8-sig", newline="") as f:
        all_rows = list(csv.DictReader(f))

    cur.execute("select last_row from feedback_watermark where file = %s", (path.name,))
    row = cur.fetchone()
    watermark = int(row["last_row"]) if row else 0

    was_reset = watermark > len(all_rows)
    if was_reset:
        # A fajl megrovidult -> ujra feldolgozunk mindent. Biztonsagos, mert
        # minden iras upsert; a hivo oldal viszont lassa, hogy ez tortent.
        watermark = 0

    return all_rows[watermark:], len(all_rows), was_reset


def _set_watermark(cur, path: Path, processed_total: int) -> None:
    cur.execute(
        """
        insert into feedback_watermark (file, last_row, updated_at)
             values (%s, %s, now())
        on conflict (file) do update
                set last_row = excluded.last_row, updated_at = now()
        """,
        (path.name, processed_total),
    )


def _contact(cur, email: str) -> dict | None:
    cur.execute("select id, company_id from contacts where email = %s", (email,))
    return cur.fetchone()


def _valaszolo_cege(cur, email: str) -> dict | None:
    """A VALASZOLO cege, ha a cime nem ismert kontakt -- domain szerint.

    MIERT KELL: az ember ritkan arrol a cimrol valaszol, amire irtunk. Az
    `info@ceg.hu`-ra kuldott levelre a sajat cimerol jon a valasz
    (`nagy.eszter@ceg.hu`). A `_contact()` pontos cim-egyezest keres, tehat
    ilyenkor `None`-t ad -- es akkor a ceg NEM kerul `replied` allapotba, az
    outreach sora NYITVA marad, es a rendszer follow-upot kuld annak, aki
    mar valaszolt.

    Merve (2026-09-03): ket valodi valasz erkezett, mindketto szemelyes
    cimrol, es mindket ceg `sent` allapotban maradt -- ket nap mulva
    megkaptak volna a kovetkezo levelet.

    A `guards.py` ugyanezt a parositast vegzi a kuldo oldalan
    (`_is_reply_from_lead`); ez itt a DB-oldali parja. FREEMAIL DOMAINT
    SZANDEKOSAN NEM parositunk: egy tetszoleges gmail-cimrol jovo level nem
    annak a leadnek a valasza, akinek `valaki@gmail.com` cimere irtunk.
    """
    domain = email_domain(email)
    if not domain or domain in _FREEMAIL:
        return None
    cur.execute(
        """
        select ct.id, ct.company_id
          from contacts ct
          join companies c on c.id = ct.company_id
          join outreach o on o.company_id = c.id and o.contact_id = ct.id
         where c.normalized_domain = %s
           and o.status in ('queued', 'sent')
         order by o.queued_at desc
         limit 1
        """,
        (domain,))
    return cur.fetchone()


# ─── sent.csv ──────────────────────────────────────────────────────────────

def _import_sent(cur, rows: list[dict], stats: FeedbackStats) -> None:
    for row in rows:
        stats.sent_rows += 1
        email = normalize_email(row.get("email") or "")
        if not email:
            continue
        contact = _contact(cur, email)
        if contact is None:
            # Kezzel felvett lead, vagy mar torolt ceg. Nem hiba.
            stats.unknown_emails.add(email)
            continue

        template = (row.get("template") or "").strip()
        ts = (row.get("ts") or "").strip() or None
        finished = template == "follow_up_2"

        cur.execute(
            """
            update outreach
               set status         = %s,
                   stage          = %s,
                   -- az ELSO kikuldes ideje szamit (a cold email datuma),
                   -- mert a follow-up utemezes ahhoz kepest megy
                   sent_at        = coalesce(sent_at, %s::timestamptz),
                   sender_account = coalesce(%s, sender_account)
             where contact_id = %s and status in ('queued', 'sent')
            """,
            ("done" if finished else "sent", template or None, ts,
             (row.get("account") or "").strip() or None, contact["id"]),
        )
        if cur.rowcount:
            stats.sent_matched += 1

        if finished:
            stats.sequences_done += 1
            # A szekvencia valasz nelkul ert veget -> 90 napos ceg-cooldown
            # (SCRAPER-PLAN "Cooldown"). Ha kozben megis valaszol, a DNC-import
            # 'replied'-re allitja, es az felulirja ezt.
            cur.execute(
                """
                update companies
                   set status = 'done',
                       cooldown_until = coalesce(%s::timestamptz, now()) + interval '90 days'
                 where id = %s and status <> all(%s)
                """,
                (ts, contact["company_id"], list(_TERMINAL)),
            )
        else:
            cur.execute(
                "update companies set status = 'sent' where id = %s and status <> all(%s)",
                (contact["company_id"], list(_TERMINAL)),
            )


# ─── do-not-contact.csv ────────────────────────────────────────────────────

def _import_dnc(cur, rows: list[dict], stats: FeedbackStats) -> None:
    for row in rows:
        stats.dnc_rows += 1
        email = normalize_email(row.get("email") or "")
        if not email:
            continue
        reason = (row.get("reason") or "").strip()
        ts = (row.get("ts") or "").strip() or None
        contact = _contact(cur, email)

        if reason == "replied":
            # NEM suppression. A valaszolo forro lead lehet -- csak EMBER
            # valaszoljon neki, ne a robot. (INTEGRATION-PLAN 4. ellentmondas.)
            #
            # Ha a valasz nem a megkeresett cimrol jott, domain szerint
            # keressuk meg a ceget -- kulonben az outreach sora nyitva
            # maradna, es follow-upot kuldenenk annak, aki mar valaszolt
            # (lasd `_valaszolo_cege`).
            contact = contact or _valaszolo_cege(cur, email)
            stats.replied += 1
            if contact:
                cur.execute(
                    """
                    update outreach set status = 'replied',
                                        replied_at = coalesce(replied_at, %s::timestamptz)
                     where contact_id = %s and status in ('queued', 'sent')
                    """,
                    (ts, contact["id"]),
                )
                cur.execute(
                    "update companies set status = 'replied' where id = %s and status <> 'suppressed'",
                    (contact["company_id"],),
                )
            continue

        if reason == "unsubscribe_request":
            _suppress(cur, email, "unsubscribe", "a kuldo DNC-jebol")
            stats.suppressed += 1
            if contact:
                # Az outreach sort is le KELL zarni, kulonben a domain lock
                # reszleges indexe szerint a szekvencia orokre "aktiv" marad,
                # es a ceg sosem kaphatna uj outreach sort. (Ezt a hibat a
                # 3. szakasz eletciklus-tesztje talalta meg.)
                cur.execute(
                    "update outreach set status = 'stopped' where contact_id = %s and status in ('queued','sent')",
                    (contact["id"],),
                )
                cur.execute(
                    "update companies set status = 'suppressed' where id = %s",
                    (contact["company_id"],),
                )
            continue

        if reason == "hard_bounce":
            # KONZERVATIV VISELKEDES (felhasznaloi dontes, 2026-08-20):
            # hard bounce utan a ceget NEM probaljuk ujra masik cimmel.
            # A bounce az egyetlen hiba a rendszerben, ami VISSZAMENOLEG is
            # kart okoz: rontja a kuldo domain reputaciojat, es onnantol a
            # JO leadeknek sem erkezik meg a level. Egyetlen ceg megmentese
            # nem eri meg ezt a kockazatot -- foleg ugy, hogy a masodik cim
            # ugyanabbol a (nyilvanvaloan elavult) forrasbol szarmazik.
            #
            _suppress(cur, email, "hard_bounce", "hard bounce")
            stats.suppressed += 1
            if contact:
                cur.execute(
                    """
                    update contacts set verify_result = 'invalid',
                                        bounce_state = 'hard_bounce'
                     where id = %s
                    """,
                    (contact["id"],),
                )
                cur.execute(
                    "update outreach set status = 'stopped' where contact_id = %s and status in ('queued','sent')",
                    (contact["id"],),
                )
                # A `bounce_override` cimke EMBERI dontes: "ezen a cegen a
                # visszapattanas nem a ceg hibaja volt". Valos eset
                # (2026-09-02): az enrichment egy urlap-placeholderbol olvasott
                # ki cimet (`<input placeholder="x@y.hu">`), tehat a cim SOSEM
                # letezett. A fenti konzervativ szabaly indoka -- "a masodik
                # cim ugyanabbol az elavult forrasbol jon" -- ilyenkor nem all:
                # nem a forras volt elavult, hanem a kinyeres volt hibas.
                #
                # A CIM-SZINTU suppression ettol fuggetlenul MEGMARAD (fent,
                # `_suppress`): a rossz cimre soha tobbe nem megy level. Csak a
                # CEG marad megkeresheto -- egy masik, ujra kinyert cimen.
                cur.execute(
                    """
                    update companies
                       set status = 'suppressed',
                           status_note = 'hard bounce: ' || %s
                                         || ' -- ujraprobalas kikapcsolva (reputacio-vedelem)'
                     where id = %s and status <> all(%s)
                       and not exists (
                         select 1 from company_labels cl
                          where cl.company_id = companies.id
                            and cl.label = 'bounce_override'
                       )
                    """,
                    (email, contact["company_id"], list(_TERMINAL)),
                )
                labels.set_label(cur, contact["company_id"], "contact_invalid",
                                 {"email": email, "reason": "hard_bounce"})
            continue

        # Ismeretlen ok -> nem talalgatunk, de naplozzuk.
        _suppress(cur, email, "manual_block", f"ismeretlen DNC ok: {reason}")
        stats.suppressed += 1


def _suppress(cur, email: str, reason: str, note: str) -> None:
    cur.execute(
        """
        insert into suppression (email, reason, note) values (%s, %s, %s)
        on conflict (email) where email is not null do nothing
        """,
        (email, reason, note),
    )


# ─── bounces.csv ───────────────────────────────────────────────────────────

def _import_bounces(cur, rows: list[dict], stats: FeedbackStats) -> None:
    for row in rows:
        stats.bounce_rows += 1
        email = normalize_email(row.get("email") or "")
        reason = (row.get("reason") or "").strip()
        if not email or not reason:
            continue
        # A soft bounce NEM zar ki senkit (atmeneti hiba: tele a postafiok).
        # Csak jelolunk, hogy a kesobbi ujravalidalas lassa.
        cur.execute("update contacts set bounce_state = %s where email = %s", (reason, email))


# ─── rejects.csv ───────────────────────────────────────────────────────────
# AZ ELUTASITAS NEM ZAR KI SENKIT. A ramp mar tanul beloluk (volumen-szabalyozas);
# ez az import azert kell, hogy a scraper CIMENKENT is lassa oket: "ezt a cimet
# erdemes-e meg egyszer megprobalni?"
#
# Suppression SZANDEKOSAN nincs: az SMTP-hiba a KULDO oldalarol szol (rate
# limit, atmeneti hiba), nem a cegrol. Suppressionbe tenni egy leadet azert,
# mert a mi szerverunk epp limitbe utkozott, csendben megsemmisitene a listat.

def _import_rejects(cur, rows: list[dict], stats: FeedbackStats) -> None:
    """Az elutasitasok osszesitese cimenkent.

    A SZAMLALOT NEM INKREMENTALJUK, HANEM BEALLITJUK. A watermark ujra
    nullazodhat (ha a CSV megrovidul), es olyankor ugyanazokat a sorokat
    megegyszer feldolgoznank -- `+ 1` alakban irva a szamlalo felfele
    torzulna, es egy egeszseges cim ugy nezne ki, mint egy halott.
    Ugyanaz a szabaly, mint a `financial_bonus`-nal: kumulativ oszlopot sosem
    irunk `oszlop + x` alakban, ha a forras ujraolvashato.

    Ezert a TELJES fajlbol szamolunk, nem csak az uj sorokbol -- a hivo oldal
    ezt a `_read_all` jelzessel adja at.
    """
    szamlalo: dict[str, int] = {}
    utolso: dict[str, tuple[str, str]] = {}
    for row in rows:
        stats.reject_rows += 1
        email = normalize_email(row.get("email") or "")
        if not email:
            continue
        szamlalo[email] = szamlalo.get(email, 0) + 1
        utolso[email] = ((row.get("error") or "").strip(),
                         (row.get("ts") or "").strip())

    for email, darab in szamlalo.items():
        hiba, ts = utolso[email]
        cur.execute(
            """
            update contacts
               set send_reject_count = %s,
                   send_error        = %s,
                   send_rejected_at  = %s::timestamptz
             where email = %s
            """,
            (darab, hiba or None, ts or None, email),
        )
        if cur.rowcount:
            stats.rejects_matched += 1


# ─── replies.csv ───────────────────────────────────────────────────────────

def _import_replies(cur, rows: list[dict], stats: FeedbackStats) -> None:
    for row in rows:
        stats.reply_rows += 1
        email = normalize_email(row.get("email") or "")
        if not email:
            continue
        cur.execute(
            """
            insert into reply_events (msg_id, email, received_at, subject, body)
                 values (%s, %s, %s::timestamptz, %s, %s)
            on conflict (msg_id) where msg_id is not null do nothing
            """,
            ((row.get("msg_id") or "").strip() or None, email,
             (row.get("ts") or "").strip() or None,
             row.get("subject") or "", row.get("body") or ""),
        )


# ─── Fo belepesi pont ──────────────────────────────────────────────────────

# (fajlnev, feldolgozo, kotelezo-e, TELJES-fajlt-olvasunk-e)
#
# A negyedik mezo a `rejects.csv` miatt van. A tobbi importer INKREMENTALIS:
# minden sor egy esemeny, amit egyszer kell feldolgozni. A rejects viszont egy
# KUMULATIV szamlalot tolt (`send_reject_count`), es azt nem `+1`-gyel irjuk,
# hanem beallitjuk -- kulonben egy watermark-nullazas felfele torzitana. Ehhez
# viszont a TELJES fajl kell, nem csak az uj sorok.
_FILES = (
    ("sent.csv", _import_sent, True, False),
    ("bounces.csv", _import_bounces, True, False),
    ("do-not-contact.csv", _import_dnc, True, False),
    ("replies.csv", _import_replies, False, False),   # csak a 3. szakasz ota letezik
    ("rejects.csv", _import_rejects, False, True),    # csak a 12. szakasz ota letezik
)


def run(verbose: bool = True) -> FeedbackStats:
    """Minden uj sor beolvasasa. Idempotens: ujra futtatva 0 sort dolgoz fel."""
    stats = FeedbackStats()

    with db.connect() as conn, conn.cursor() as cur:
        for name, handler, required, teljes in _FILES:
            path = config.SENDER_DATA / name
            rows, total, was_reset = _read_new(cur, path, required=required)
            if not path.exists():
                continue
            if was_reset:
                stats.reset_files.append(name)
            if teljes and total:
                # Kumulativ szamlalohoz a teljes fajl kell (lasd _FILES).
                # A watermark ettol fuggetlenul elorelep: a `total` a
                # feldolgozott sorok szama, es ez akadalyozza meg, hogy
                # ugyanaz a fajl minden futasnal ujra vegigolvasodjon,
                # ha kozben nem valtozott.
                if not rows and not was_reset:
                    continue          # nincs uj sor -> nincs mit ujraszamolni
                with path.open(encoding="utf-8-sig", newline="") as f:
                    rows = list(csv.DictReader(f))
            handler(cur, rows, stats)
            _set_watermark(cur, path, total)

    if verbose:
        _report(stats)
    return stats


def _report(stats: FeedbackStats) -> None:
    print(f"feldolgozott uj sor: {stats.total}")
    if stats.sent_rows:
        print(f"  sent.csv           : {stats.sent_rows} "
              f"({stats.sent_matched} parositva, {stats.sequences_done} szekvencia lezarult)")
    if stats.bounce_rows:
        print(f"  bounces.csv        : {stats.bounce_rows}")
    if stats.dnc_rows:
        print(f"  do-not-contact.csv : {stats.dnc_rows}")
    if stats.reply_rows:
        print(f"  replies.csv        : {stats.reply_rows}")
    if stats.reject_rows:
        print(f"  rejects.csv        : {stats.reject_rows} "
              f"({stats.rejects_matched} cim frissitve)")

    if stats.replied:
        print(f"\n>>> {stats.replied} VALASZ erkezett -- ezeket EMBER kezelje, "
              f"a robot innentol nem ir nekik.")
    if stats.suppressed:
        print(f"    {stats.suppressed} cim suppressionbe kerult.")
    if stats.unknown_emails:
        sample = ", ".join(sorted(stats.unknown_emails)[:3])
        print(f"\nFIGYELEM: {len(stats.unknown_emails)} cim nincs a DB-ben "
              f"(kezzel felvett lead?): {sample}")
    if stats.reset_files:
        print(f"\nFIGYELEM: rovidebb lett, ujra feldolgozva: {', '.join(stats.reset_files)}")
