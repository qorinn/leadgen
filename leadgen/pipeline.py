#!/usr/bin/env python3
"""A feldolgozasi lanc: new -> enriched -> ready/rejected.

BATCH-ELT, ROVID FUTASOK. A terv "Fontos: mi fut hol" fejezete ezt irja elo:
minden lepes a DB `status` oszlopabol olvassa, hol tart, dolgozik egy adagot,
majd visszair. Ha egy futas elszall, csak az adott adag marad `error`-ban, a
tobbi ep -- es a kovetkezo futas automatikusan a kovetkezo adagot viszi.

Ettol lesz a rendszer ujraindithato: nincs allapot a folyamat memoriajaban.
"""
from __future__ import annotations

from . import db, enrich
from .engines import EngineDef


# ─── Enrichment ────────────────────────────────────────────────────────────

def run_enrich(limit: int = 25, verbose: bool = True) -> dict:
    """A `new` statuszu cegek weboldalanak feldolgozasa."""
    stats = {"feldolgozva": 0, "sikeres": 0, "hiba": 0, "kapcsolat": 0, "domain_nelkul": 0}

    rows = db.query(
        """
        select id, company_name, normalized_domain, domain
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
            db.execute(
                "update companies set status = 'error', status_note = %s where id = %s",
                ("nincs sajat domain (csak platform-oldal)", row["id"]),
            )
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

            for email, email_type in enrich.pick_contacts(extract, domain):
                cur.execute(
                    """
                    insert into contacts (company_id, email, email_type,
                                          local_check, source_url)
                         values (%s, %s, %s, 'pass', %s)
                    on conflict (email) do nothing
                    """,
                    (row["id"], email, email_type, f"https://{domain}"),
                )
                if cur.rowcount:
                    stats["kapcsolat"] += 1

            # A tech ujjlenyomat es a footer a cegre kerul: a 8.2 ("halott
            # fejleszto") engine kesobb ebbol dolgozik, ujra-letoltes nelkul.
            cur.execute(
                """
                update companies
                   set status = 'enriched',
                       status_note = null,
                       signal_score = signal_score
                                      + case when %s then 15 else 0 end
                 where id = %s
                """,
                (bool(extract.tech.get("copyright_year"))
                 and extract.tech["copyright_year"] <= 2023, row["id"]),
            )
            stats["sikeres"] += 1

    if verbose:
        print(f"\n  feldolgozva={stats['feldolgozva']} sikeres={stats['sikeres']} "
              f"hiba={stats['hiba']} uj kapcsolat={stats['kapcsolat']}")
    return stats


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
            db.execute(
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
            stats["atnezendo"] = stats.get("atnezendo", 0) + 1
            continue

        if not q.ok:
            db.execute(
                "update companies set status = 'rejected', status_note = %s where id = %s",
                (q.reason[:200], row["id"]),
            )
            stats["nem_fit"] += 1
            continue

        if not row["kapcsolatok"]:
            db.execute(
                "update companies set status = 'rejected', status_note = %s where id = %s",
                ("minositest atment, de nincs email cim", row["id"]),
            )
            stats["nincs_email"] += 1
            continue

        db.execute(
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
        stats["ready"] += 1

    if verbose:
        print(f"  vizsgalt={stats['vizsgalt']}  READY={stats['ready']}  "
              f"ATNEZENDO={stats['atnezendo']}  versenytars={stats['versenytars']}  "
              f"nem fit={stats['nem_fit']}  nincs email={stats['nincs_email']}")
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
