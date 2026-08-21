#!/usr/bin/env python3
"""Google Maps -> companies. A 4. szakasz forrasa.

A keresokifejezesek NEM itt vannak, hanem az engine definiciojaban
(leadgen/engines.py). Ez a modul iparag-fuggetlen: barmelyik EngineDef
maps_searches mezojet vegre tudja hajtani.

KOLTSEG: ~$5 / 1000 talalat (merve 2026-08-21). A `--max-results` ezert
kotelezo vedokorlat, es minden futas kiirja a tenyleges koltseget.
"""
from __future__ import annotations

from .. import db
from ..blocklist import resolve_company_key
from ..engines import EngineDef
from . import apify

ACTOR = "compass/crawler-google-places"


def _upsert_company(cur, item: dict, engine: EngineDef) -> str | None:
    """Egy Maps-talalat beirasa. None, ha nem azonosithato ceggé."""
    website = (item.get("website") or "").strip()
    key = resolve_company_key(
        website=website,
        company_name=item.get("title"),
        city=item.get("city"),
        phone=item.get("phone"),
    )
    if not key.usable:
        return None

    from ..normalize import normalize_company_name, normalize_phone

    cur.execute(
        """
        insert into companies (company_name, name_key, domain, normalized_domain,
                               platform_url, industry, city, phone,
                               campaign, best_offer, signal_score, status)
             values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'new')
        on conflict (normalized_domain) where normalized_domain is not null
        do update set
              last_seen_at = now(),
              phone = coalesce(companies.phone, excluded.phone),
              city  = coalesce(companies.city, excluded.city),
              -- EGY MASIK ENGINE UJRA ERTEKELHETI A "NEM FIT" CEGET.
              -- A `rejected` azt jelenti: "ehhez a kampanyhoz nem illik" --
              -- NEM azt, hogy "ez a ceg sosem lehet lead". Egy ceg, amit az
              -- ugynoksegi engine elutasitott (nincs marketing kulcsszo),
              -- kivalo lead lehet az allashirdetes-engine-nek.
              -- A `suppressed` viszont NEM allitodik vissza: a leiratkozas,
              -- a versenytars es a bounce a CEG tulajdonsaga, nem a kampanye.
              status = case
                  when companies.status = 'rejected'
                   and companies.campaign is distinct from excluded.campaign
                  then 'new' else companies.status end,
              campaign = case
                  when companies.status = 'rejected'
                   and companies.campaign is distinct from excluded.campaign
                  then excluded.campaign else companies.campaign end,
              best_offer = case
                  when companies.status = 'rejected'
                   and companies.campaign is distinct from excluded.campaign
                  then excluded.best_offer else companies.best_offer end,
              status_note = case
                  when companies.status = 'rejected'
                   and companies.campaign is distinct from excluded.campaign
                  then null else companies.status_note end
          returning id, (xmax = 0) as uj_sor
        """,
        (item.get("title"), normalize_company_name(item.get("title") or ""),
         website or None, key.normalized_domain, key.platform_url,
         item.get("categoryName"), item.get("city"),
         normalize_phone(item.get("phone") or ""),
         engine.campaign, engine.best_offer, engine.base_score),
    )
    row = cur.fetchone()
    return row["id"] if row else None


def _mar_lefutott(engine: EngineDef, refresh_days: int) -> set[tuple[str, str]]:
    """A mar vegrehajtott (kifejezes, telepules) parosok.

    A `refresh_days`-nel regebbi futasok ujra engedelyezettek: a Google Maps
    tartalma valtozik, uj cegek jelennek meg. Nulla = soha ne ismetelj.
    """
    rows = db.query(
        """
        select term, location from source_runs
         where engine_key = %s and actor = %s
           and (%s = 0 or run_at > now() - make_interval(days => %s))
        """,
        (engine.key, ACTOR, refresh_days, refresh_days),
    )
    return {(r["term"], r["location"]) for r in rows}


def ingest(engine: EngineDef, max_results: int = 50, dry: bool = False,
           refresh_days: int = 30, force: bool = False,
           location: str | None = None) -> dict:
    """A engine maps_searches lekerdezeseinek vegrehajtasa.

    FOLYTATOLAGOS: a mar lefuttatott (kifejezes + telepules) parosokat
    kihagyja, es a kovetkezo, meg nem futott lekerdezessel folytatja. Igy egy
    ujabb `ingest` UJ cegeket hoz, nem ugyanazokert fizet megegyszer.

    A `max_results` a TELJES futasra vonatkozo felso korlat -- ez vedi a keretet.
    """
    stats = {"lekerdezes": 0, "talalat": 0, "uj_ceg": 0, "mar_ismert": 0,
             "kulcs_nelkul": 0, "kihagyva": 0, "hatralevo": 0}
    osszes = [
        (term, loc, search)
        for search in engine.maps_searches
        for term in search.terms
        for loc in search.locations
    ]

    if location:
        # Egy telepulesre szukites: igy tudod eloszor a legigeretesebb
        # varost vegigvinni, es abbol dontheted el, kell-e tobb.
        osszes = [p for p in osszes if location.lower() in p[1].lower()]
        if not osszes:
            print(f"  Nincs '{location}' nevu telepules az engine kereseseiben.")
            return stats

    kesz = set() if force else _mar_lefutott(engine, refresh_days)
    tervezett = [p for p in osszes if (p[0], p[1]) not in kesz]
    stats["kihagyva"] = len(osszes) - len(tervezett)

    if dry:
        print(f"  osszes lekerdezes : {len(osszes)}")
        print(f"  mar lefutott      : {stats['kihagyva']}  (kihagyva)")
        print(f"  most futna        : {len(tervezett)}, max {max_results} talalatig\n")
        for term, loc, _ in tervezett[:10]:
            print(f"    - {term!r} @ {loc}")
        if len(tervezett) > 10:
            print(f"    ... es meg {len(tervezett) - 10}")
        print(f"\n  Becsult koltseg: ~${max_results * 0.005:.2f}")
        return stats

    if not tervezett:
        print(f"  Minden lekerdezes lefutott mar (utolso {refresh_days} napban).")
        print("  Ujrafuttatas: --force, vagy uj kereso-kifejezes/telepules")
        print("  felvetele a leadgen/engines.py maps_searches mezojebe.")
        return stats

    maradek = max_results
    with db.connect() as conn, conn.cursor() as cur:
        for term, loc, search in tervezett:
            if maradek <= 0:
                stats["hatralevo"] = len(tervezett) - stats["lekerdezes"]
                break
            payload = {
                "searchStringsArray": [term],
                "locationQuery": loc,
                "maxCrawledPlacesPerSearch": min(maradek, search.max_per_search),
                "language": "hu",
                "skipClosedPlaces": True,
            }
            if search.only_with_website:
                # Akinek nincs weboldala, azt nem tudjuk feldolgozni -- ne is
                # fizessunk erte. Az actor forrasnal szuri, nem utana.
                payload["website"] = "withWebsite"
            items = apify.run_actor(ACTOR, payload)
            stats["lekerdezes"] += 1
            maradek -= len(items)

            for item in items:
                stats["talalat"] += 1
                company_id = _upsert_company(cur, item, engine)
                if company_id is None:
                    stats["kulcs_nelkul"] += 1
                    continue

                cur.execute(
                    """
                    insert into sources (company_id, source_type, source_url, raw_signal)
                         values (%s, %s, %s, %s)
                    on conflict (source_type, source_url) do nothing
                      returning id
                    """,
                    (company_id, engine.key,
                     item.get("url") or f"maps:{item.get('placeId')}",
                     db.Json({"title": item.get("title"),
                              "category": item.get("categoryName"),
                              "website": item.get("website"),
                              "term": term, "location": loc})),
                )
                if cur.fetchone():
                    stats["uj_ceg"] += 1
                else:
                    stats["mar_ismert"] += 1

            # A lekerdezes lefutott -- jegyezzuk fel, hogy legkozelebb ne
            # fizessunk ugyanezert megegyszer.
            cur.execute(
                """
                insert into source_runs (engine_key, actor, term, location,
                                         results, new_companies)
                     values (%s, %s, %s, %s, %s, %s)
                on conflict (engine_key, actor, term, location) do update
                        set results = excluded.results,
                            new_companies = excluded.new_companies,
                            run_at = now()
                """,
                (engine.key, ACTOR, term, loc, len(items), stats["uj_ceg"]),
            )
    return stats
