#!/usr/bin/env python3
"""A feldolgozasi lanc: new -> enriched -> ready/scored/review/suppressed.

BATCH-ELT, ROVID FUTASOK. A terv "Fontos: mi fut hol" fejezete ezt irja elo:
minden lepes a DB `status` oszlopabol olvassa, hol tart, dolgozik egy adagot,
majd visszair. Ha egy futas elszall, csak az adott adag marad `error`-ban, a
tobbi ep -- es a kovetkezo futas automatikusan a kovetkezo adagot viszi.

Ettol lesz a rendszer ujraindithato: nincs allapot a folyamat memoriajaban.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import db, enrich, labels
from .engines import EngineDef


# ─── Enrichment ────────────────────────────────────────────────────────────

def run_enrich(limit: int = 25, verbose: bool = True) -> dict:
    """A `new` statuszu cegek weboldalanak feldolgozasa."""
    stats = {"feldolgozva": 0, "sikeres": 0, "hiba": 0, "kapcsolat": 0, "domain_nelkul": 0}

    rows = db.query(
        """
        select id, company_name, normalized_domain, domain,
               scored_at, personalization, campaign
          from companies
         where status = 'new'
         order by signal_score desc nulls last, first_seen_at
         limit %s
        """,
        (limit,),
    )
    if not rows:
        if verbose:
            print("  Nincs feldolgozando ceg (`new` statuszban).")
        return stats

    for row in rows:
        stats["feldolgozva"] += 1
        domain = row["normalized_domain"]

        if not domain:
            # Csak platform-oldal (Facebook stb.) -- nincs mit letolteni.
            with db.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "update companies set status = 'error', status_note = %s where id = %s",
                    ("nincs sajat domain (csak platform-oldal)", row["id"]),
                )
                labels.set_label(cur, row["id"], "domain_missing",
                                 {"reason": "nincs sajat domain"})
            stats["domain_nelkul"] += 1
            continue

        # Az EREDETI URL-t adjuk at (a forras tudja legjobban, hol el az oldal),
        # a normalizalt domain csak fallback.
        extract = enrich.fetch_site(domain, original_url=row.get("domain"), verbose=verbose)

        with db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into sources (company_id, source_type, source_url, raw_signal)
                     values (%s, 'website_crawl', %s, %s)
                on conflict (source_type, source_url) do update
                        set raw_signal = excluded.raw_signal, detected_at = now()
                """,
                (row["id"], f"https://{domain}", db.Json(extract.as_json())),
            )

            if not extract.ok:
                cur.execute(
                    "update companies set status = 'error', status_note = %s where id = %s",
                    (f"enrichment: {extract.error}"[:200], row["id"]),
                )
                stats["hiba"] += 1
                continue

            for email, email_type, source_kind in enrich.pick_contacts(extract, domain):
                cur.execute(
                    """
                    insert into contacts (company_id, email, email_type,
                                          source_kind, local_check, source_url)
                         values (%s, %s, %s, %s, 'pass', %s)
                    on conflict (email) do nothing
                    """,
                    (row["id"], email, email_type, source_kind, f"https://{domain}"),
                )
                if cur.rowcount:
                    stats["kapcsolat"] += 1

            cur.execute("""
                select count(*) as n from contacts
                 where company_id = %s
                   and local_check is distinct from 'fail'
                   and coalesce(verify_result, '') <> 'invalid'
                   and coalesce(bounce_state, '') <> 'hard_bounce'
            """, (row["id"],))
            kapcsolatok = int(cur.fetchone()["n"])
            if kapcsolatok:
                labels.clear_label(cur, row["id"], "contact_missing")
            else:
                labels.set_label(cur, row["id"], "contact_missing",
                                 {"checked_url": f"https://{domain}"})
            labels.clear_label(cur, row["id"], "domain_missing")

            # A tech ujjlenyomat es a footer a cegre kerul: a 8.2 ("halott
            # fejleszto") engine kesobb ebbol dolgozik, ujra-letoltes nelkul.
            kovetkezo_status = "enriched"
            if row.get("scored_at"):
                kovetkezo_status = (
                    "ready" if kapcsolatok and row.get("personalization")
                    and row.get("campaign") else "scored"
                )
            cur.execute(
                """
                update companies
                   set status = %s,
                       status_note = null,
                       signal_score = signal_score
                                      + case when %s then 15 else 0 end
                 where id = %s
                """,
                (kovetkezo_status,
                 bool(extract.tech.get("copyright_year"))
                 and extract.tech["copyright_year"] <= 2023, row["id"]),
            )
            stats["sikeres"] += 1

    if verbose:
        print(f"\n  feldolgozva={stats['feldolgozva']} sikeres={stats['sikeres']} "
              f"hiba={stats['hiba']} uj kapcsolat={stats['kapcsolat']}")
    return stats


def rescan_contacts(limit: int = 25, verbose: bool = True) -> dict:
    """Ujra megnezi a weboldalakat, es CSAK HOZZAAD cimeket. Nem torol, es a
    ceg statuszahoz sem nyul.

    MIERT NEM A `redo()` VALO ERRE: az `redo()` TOROL (a regi, gyanus
    kontaktokat) es `new`-ra allitja a statuszt. Az helyes, ha egy konkret
    ceg cime hibasnak bizonyult -- de rossz, ha csak TOBB cimet szeretnenk
    osszegyujteni egy mar mukodo cegnel:

      - a torles utan, ha a letoltes epp elszall, a ceg elveszti a MEGLEVO,
        jo cimet is;
      - a `new` statusz kiutne a folyamatban levo cegeket a tolcserbol.

    Ez a fuggveny ezert kizarolag `insert ... on conflict do nothing`-ot
    csinal. Ujrafuttathato, es a legrosszabb esetben nem talal semmit.

    MIKOR KELL: ha az `enrich.py` kinyerese BOVULT (uj forras, pl. a
    2026-09-02-i Cloudflare-visszafejtes es JSON-LD), es a mar feldolgozott
    cegeknel utolag is meg akarjuk talalni, amit korabban nem lattunk.
    """
    stats = {"nezve": 0, "uj_kapcsolat": 0, "hiba": 0}
    rows = db.query(
        """
        select id, company_name, normalized_domain, domain
          from companies
         where normalized_domain is not null
           and status <> 'new'
         order by signal_score desc nulls last, first_seen_at
         limit %s
        """,
        (limit,))

    for row in rows:
        stats["nezve"] += 1
        domain = row["normalized_domain"]
        extract = enrich.fetch_site(domain, original_url=row.get("domain"), verbose=False)
        if not extract.ok:
            stats["hiba"] += 1
            if verbose:
                print(f"  -    {domain:34} {extract.error[:60]}")
            continue

        ujak = []
        with db.connect() as conn, conn.cursor() as cur:
            for email, email_type, source_kind in enrich.pick_contacts(extract, domain):
                cur.execute(
                    """
                    insert into contacts (company_id, email, email_type,
                                          source_kind, local_check, source_url)
                         values (%s, %s, %s, %s, 'pass', %s)
                    on conflict (email) do nothing
                    """,
                    (row["id"], email, email_type, source_kind, f"https://{domain}"))
                if cur.rowcount:
                    ujak.append(email)
                    stats["uj_kapcsolat"] += 1
            if ujak:
                labels.clear_label(cur, row["id"], "contact_missing")
        if verbose and ujak:
            print(f"  + {len(ujak):2} {domain:34} {', '.join(ujak[:3])}"
                  f"{' ...' if len(ujak) > 3 else ''}")

    if verbose:
        print(f"\n  megnezve={stats['nezve']} uj kapcsolat={stats['uj_kapcsolat']} "
              f"elerhetetlen={stats['hiba']}")
    return stats


def redo_errors(limit: int = 50) -> int:
    """A `status='error'` cegek visszaallitasa `new`-ra, ujraprobalasra.

    MIERT KELL: egy `error` cegert SOHA semmi nem nyul ujra. A `run_enrich`
    csak `new` statuszt olvas, tehat egy PILLANATNYI hiba -- timeout, egy
    perces kiszolgalo-kimaradas, egy 403 -- veglegesen kiejti a ceget a
    tolcserbol. Merve (2026-09-02): a kontakt nelkuli 61 cegbol 26 volt
    `error`, es ebbol OT MAR UGYANABBAN A PERCBEN elerheto volt kezzel
    probalva (allinagency.hu, publica.hu, chiro.hu, exaline.hu,
    marketing-consulting.hu). Nem a weboldaluk volt rossz, hanem a
    pillanat, amikor megneztuk.

    A kontaktokhoz NEM nyul (ellentetben a `redo()`-val): itt nincs okunk
    gyanakodni a meglevo cimekre, csak ujra meg akarjuk nezni az oldalt.
    """
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            update companies set status = 'new', status_note = 'ujraprobalas (error)'
             where id in (
               select id from companies where status = 'error'
                order by signal_score desc nulls last, first_seen_at
                limit %s
             )
            """,
            (limit,))
        return cur.rowcount


@dataclass
class RedoResult:
    talalt: bool
    blocked: bool = False
    torolt_kapcsolat: int = 0


def redo(domain: str) -> RedoResult:
    """Egy mar feldolgozott ceg ujra `new` statuszba allitasa, hogy a
    kovetkezo `enrich` futas ujra letoltse es kinyerje a kontaktjait --
    pl. az enrich.py egy javitasa (2026-09-02: HTML-attributumbol tevesen
    kiolvasott placeholder-email) utan.

    A `source_kind IS NULL` kontaktokat -- ezeket a JAVITAS ELOTTI kod irta,
    tehat a HTML-attributumbol is szarmazhatnak -- torli, DE csak akkor, ha
    semmilyen outreach sor nem hivatkozik rajuk (a kuldesi elozmenyt sosem
    torli csendben). Ha egy ilyen cimre mar ment level, azt kezzel kell
    atnezni (`review --contacts <domain>`).

    Ha a cegnek FOLYAMATBAN levo (`queued`/`sent`) megkeresese van, a redo
    NEM fut le -- eloszor `review --reject <domain>`-nel le kell zarni,
    kulonben a domain lock alatt fel-ujraindulna a szekvencia.
    """
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("select id from companies where normalized_domain = %s", (domain,))
        hit = cur.fetchone()
        if not hit:
            return RedoResult(talalt=False)

        cur.execute(
            "select 1 from outreach where company_id = %s and status in ('queued','sent') limit 1",
            (hit["id"],))
        if cur.fetchone():
            return RedoResult(talalt=True, blocked=True)

        cur.execute(
            """
            delete from contacts
             where company_id = %s
               and source_kind is null
               and not exists (
                 select 1 from outreach where outreach.contact_id = contacts.id
               )
            """,
            (hit["id"],))
        torolt = cur.rowcount

        cur.execute(
            "update companies set status = 'new', status_note = 'ujra-enrichment' "
            "where id = %s", (hit["id"],))

    return RedoResult(talalt=True, torolt_kapcsolat=torolt)


# ─── Minosites ─────────────────────────────────────────────────────────────

def run_qualify(engine: EngineDef, limit: int = 200, verbose: bool = True) -> dict:
    """Az `enriched` cegek minositese az engine kulcsszavai alapjan."""
    stats = {"vizsgalt": 0, "ready": 0, "versenytars": 0, "atnezendo": 0,
             "nem_fit": 0, "nincs_email": 0}

    rows = db.query(
        """
        select c.id, c.company_name, c.normalized_domain,
               s.raw_signal,
               (select count(*) from contacts ct where ct.company_id = c.id) as kapcsolatok
          from companies c
          join sources s on s.company_id = c.id and s.source_type = 'website_crawl'
         where c.status = 'enriched' and c.campaign = %s
         order by c.signal_score desc nulls last
         limit %s
        """,
        (engine.campaign, limit),
    )

    for row in rows:
        stats["vizsgalt"] += 1
        raw = row["raw_signal"] or {}
        # A minositeshez a letoltott oldalak szoveget hasznaljuk. A raw_signal
        # csak a kivonatot orzi, ezert a cache-bol olvassuk vissza a szoveget.
        szoveg = _cached_text(row["normalized_domain"])
        szoveg += " " + (raw.get("title") or "") + " " + (raw.get("meta_description") or "")

        # Cim + meta leiras + menu = "eros kontextus". Ami itt szerepel, az a
        # ceg sajat ajanlata, nem ugyfel-referencia.
        eros = " ".join(filter(None, (
            raw.get("title"), raw.get("meta_description"), raw.get("nav_text"))))
        q = engine.qualifier.check(szoveg, strong_context=eros)

        if not q.ok and q.is_competitor:
            db.execute(
                """
                insert into suppression (normalized_domain, reason, note)
                     values (%s, 'competitor', %s)
                on conflict (normalized_domain) where normalized_domain is not null
                                                 and email is null do nothing
                """,
                (row["normalized_domain"], f"kizaro kulcsszo: {', '.join(q.blockers[:3])}"),
            )
            db.execute(
                "update companies set status = 'suppressed', status_note = %s where id = %s",
                (f"versenytars: {', '.join(q.blockers[:3])}"[:200], row["id"]),
            )
            stats["versenytars"] += 1
            continue

        if not q.ok and q.needs_review:
            # Gyenge kizaro jel: lehet ugyfel-referencia vagy blogcikk is.
            # NEM dobjuk el -- a `leadgen review` listazza emberi dontesre.
            with db.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    update companies set status = 'review',
                                         personalization = %s,
                                         signal_summary = %s,
                                         status_note = %s
                     where id = %s
                    """,
                    (engine.personalization(q, raw),
                     f"{engine.label} | kulcsszavak: {', '.join(q.hits[:5])}"[:300],
                     f"ATNEZENDO -- gyenge kizaro jel: {', '.join(q.blockers[:3])}"[:200],
                     row["id"]),
                )
                labels.set_label(cur, row["id"], "manual_review",
                                 {"blockers": q.blockers[:3]})
            stats["atnezendo"] = stats.get("atnezendo", 0) + 1
            continue

        if not q.ok:
            # Ez csak azt jelenti, hogy EHHEZ a kampanyhoz nincs eleg eros
            # jel. A ceg ettol meg mas szolgaltatasi iranyban jo lead lehet.
            with db.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "update companies set status = 'scored', status_note = %s where id = %s",
                    (f"nincs alatamasztott kampanyszog: {q.reason}"[:200], row["id"]),
                )
                labels.set_label(cur, row["id"], "personalization_missing",
                                 {"reason": q.reason, "campaign": engine.campaign})
            stats["nem_fit"] += 1
            continue

        if not row["kapcsolatok"]:
            with db.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    update companies
                       set status = 'scored', personalization = %s,
                           signal_summary = %s,
                           status_note = 'minositest atment, de nincs email cim'
                     where id = %s
                    """,
                    (engine.personalization(q, raw),
                     f"{engine.label} | talalt kulcsszavak: {', '.join(q.hits[:5])}"[:300],
                     row["id"]),
                )
                labels.set_label(cur, row["id"], "contact_missing",
                                 {"campaign": engine.campaign})
            stats["nincs_email"] += 1
            continue

        with db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update companies
                   set status = 'ready',
                       personalization = %s,
                       signal_summary = %s,
                       status_note = null,
                       signal_score = signal_score + 10
                 where id = %s
                """,
                (engine.personalization(q, raw),
                 f"{engine.label} | talalt kulcsszavak: {', '.join(q.hits[:5])}"[:300],
                 row["id"]),
            )
            labels.clear_label(cur, row["id"], "contact_missing")
            labels.clear_label(cur, row["id"], "personalization_missing")
            labels.clear_label(cur, row["id"], "manual_review")
        stats["ready"] += 1

    if verbose:
        print(f"  vizsgalt={stats['vizsgalt']}  READY={stats['ready']}  "
              f"ATNEZENDO={stats['atnezendo']}  versenytars={stats['versenytars']}  "
              f"nincs kampanyszog={stats['nem_fit']}  nincs email={stats['nincs_email']}")
        if stats["atnezendo"]:
            print(f"\n  {stats['atnezendo']} ceg emberi dontesre var: leadgen review")
    return stats


def _cached_text(domain: str) -> str:
    """A letoltott HTML-bol kinyert szoveg, ujra-letoltes nelkul."""
    from selectolax.parser import HTMLParser
    from . import config

    d = config.CACHE_DIR / domain
    if not d.exists():
        return ""
    parts = []
    for f in sorted(d.glob("*.html")):
        try:
            parts.append(enrich._text_of(HTMLParser(f.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return " \n".join(parts)
