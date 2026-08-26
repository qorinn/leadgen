#!/usr/bin/env python3
"""Profession.hu allashirdetes-forras (9. szakasz).

    kereses -> hirdetesek -> ceg -> DOMAIN FELOLDAS -> companies

════════════════════════════════════════════════════════════════════════════
A 0.3 ELOTESZT EREDMENYE (2026-08-22, `solidcode/profession-hu-scraper`)

A terv kotelezove teszi, hogy a forrast MERESSEL ellenorizzuk, mielott
epitenenk ra. Amit meresre kaptunk (5-os lekerdezes, "szervizkoordinator",
Budapest -> 2 talalat, $0.005):

  ✅ `description`      MEGVAN, TELJES SZOVEG (1978 karakter az elso talalatnal)
                        Szo szerint benne: "Munkalapok felvetele, kezelese es
                        nyomon kovetese", "Kapcsolattartas a szerelokkel",
                        "adminisztracio elvegzese" -- pontosan az a fajdalom-jel,
                        amit az engine keres.
     FIGYELEM: csak `includeDetails=True` mellett! Enelkul csak a cim jon.

  ✅ `companyName`, `location`, `postedAt`, `url`  -- mind megvan
  ❌ `website` / `domain`  -- NINCS. A ceg weboldala SEHOL nem szerepel.
     A `companyProfileUrl` a profession.hu sajat profiloldalara mutat, es
     azon sincs kulso link (ellenorizve: 0 kulso link a HTML-ben).

Vagyis az engine mukodokepes, de a DOMAIN FELOLDAS valodi munka -- nem
"kiolvassuk a valaszbol".

════════════════════════════════════════════════════════════════════════════
A DOMAIN FELOLDAS HAROM LEPCSOJE (terv 9/4)

Olcsotol a dragaig, es az elso talalat nyer:

  1. A HIRDETES SZOVEGEBEN levo URL      -- ingyen
  2. `name_key` egyezes a mar ismert cegekkel -- ingyen
  3. Google Maps lekerdezes a cegnevre   -- ~$0.005/ceg, KULON KAPCSOLOVAL

Ha egyik sem talal: a ceg BEKERUL `status='error'` allapotban, `name_key`
kulccsal. NEM VESZ EL -- a terv kifejezetten ezt irja elo. Kesobb egy masik
forras (vagy kezi kiegeszites) megadhatja a domaint, es a lead feleled.

MIERT NEM A GOOGLE MAPS AZ ELSO: mert penz. Egy 200 hirdeteses backfill
$1 lenne csak a feloldasra -- miközben a cegek egy resze mar ismert, vagy
a hirdetes szovegeben ott a weboldal.
"""
from __future__ import annotations

import re
from typing import Any

from .. import blocklist, db, labels, normalize, storage
from ..engines import EngineDef
from . import apify

ACTOR = "solidcode/profession-hu-scraper"
SOURCE_TYPE = "profession"

# A hirdetes szovegeben elofordulo weboldal. A profession.hu sajat linkjeit
# es a kozossegi oldalakat nem vesszuk figyelembe.
_URL_MINTA = re.compile(r"\b((?:https?://)?(?:www\.)?[a-z0-9][a-z0-9-]*\.[a-z]{2,}(?:\.[a-z]{2,})?)\b", re.I)
_URL_TILTOTT = ("profession.hu", "gmail.com", "freemail.hu", "citromail.hu")


def _domain_a_szovegbol(szoveg: str, cegnev: str) -> str | None:
    """1. lepcso: a hirdetes szovegeben szereplo weboldal. Ingyen.

    Csak akkor fogadjuk el, ha a domain "hasonlit" a cegnevre -- kulonben egy
    veletlen emlitett oldal (partner, szoftvernev) lenne a ceg domainje.
    """
    kulcs = normalize.normalize_company_name(cegnev) or ""
    szavak = {sz for sz in kulcs.split() if len(sz) >= 4}
    if not szavak:
        return None

    for talalat in _URL_MINTA.findall(szoveg or ""):
        domain = normalize.normalize_domain(talalat)
        if not domain or domain in _URL_TILTOTT or blocklist.is_platform(domain):
            continue
        torzs = normalize.strip_accents(domain.split(".")[0].lower())
        # A cegnev valamelyik szava szerepeljen a domainben (vagy forditva).
        if any(sz in torzs or torzs in sz for sz in szavak):
            return domain
    return None


def _domain_a_dbbol(cegnev: str, varos: str | None) -> str | None:
    """2. lepcso: mar ismerjuk ezt a ceget? Ingyen.

    A `name_key` a normalizalt cegnev (jogi forma nelkul, ekezettelenul) --
    ugyanaz a kulcs, amit a blocklist.company_key hasznal.
    """
    kulcs = normalize.normalize_company_name(cegnev)
    if not kulcs:
        return None
    rows = db.query(
        "select normalized_domain from companies "
        " where name_key = %s and normalized_domain is not null limit 2",
        (kulcs,))
    # Ha ket kulonbozo ceg is ugyanazon a neven fut, NEM talalgatunk.
    if len(rows) == 1:
        return rows[0]["normalized_domain"]
    return None


def _domain_a_mapsbol(cegnev: str, varos: str | None) -> str | None:
    """3. lepcso: Google Maps lekerdezes. FIZETOS (~$0.005/ceg).

    Csak akkor fut, ha a hivo oldal kifejezetten kerte (`--resolve-maps`).
    """
    kereses = f"{cegnev} {varos or 'Hungary'}".strip()
    try:
        items = apify.run_actor("compass/crawler-google-places", {
            "searchStringsArray": [kereses],
            "maxCrawledPlacesPerSearch": 1,
            "language": "hu",
        }, timeout=300, verbose=False)
    except Exception:  # noqa: BLE001
        return None
    for it in items or []:
        domain = normalize.normalize_domain(it.get("website") or "")
        if domain and not blocklist.is_platform(domain):
            return domain
    return None


def _feloldas(hirdetes: dict, maps: bool) -> tuple[str | None, str]:
    """A harom lepcso egymas utan. (domain, honnan)."""
    cegnev = hirdetes.get("companyName") or ""
    varos = hirdetes.get("addressLocality") or hirdetes.get("location")
    szoveg = " ".join(str(hirdetes.get(k) or "") for k in
                      ("description", "responsibilities", "requirements"))

    d = _domain_a_szovegbol(szoveg, cegnev)
    if d:
        return d, "hirdetes szovege"
    d = _domain_a_dbbol(cegnev, varos)
    if d:
        return d, "mar ismert ceg"
    if maps:
        d = _domain_a_mapsbol(cegnev, varos)
        if d:
            return d, "google maps"
    return None, "nem sikerult"


# ─── Az ingest ─────────────────────────────────────────────────────────────

def _mar_futott(engine: EngineDef, refresh_days: int) -> set[tuple[str, str]]:
    """Mely (kifejezes + telepules) parosok futottak le a friss ablakban.

    KET SZINTU ISMETLODES-VEDELEM VAN, ES A KETTO MAS:

      REKORD-szint (`sources` UNIQUE)  -- ugyanaz a HIRDETES nem kerul be
                                         ketszer. Ez mindig aktiv.
      LEKERDEZES-szint (`source_runs`) -- ugyanaz a KERESES nem FUT LE ujra
                                         a friss ablakon belul. Ez sporol.

    A masodik nelkul a napon belul megismetelt futas ujra kifizetne az
    Apify-lekerdezest, hiaba nem lenne belole egyetlen uj hirdetes sem.
    (Merve: a 9. szakasz eles tesztjenek 2. futasa $0.01-be kerult ugy, hogy
    0 uj hirdetest hozott. Ezt a hianyt a felhasznalo kerdese talalta meg.)

    MIERT 1 NAP AZ ALAPERTELMEZES, ES NEM 30 (mint a Mapsnel): allashirdetes
    NAPONTA jelenik meg uj. A Maps-nel egy cegkereses eredmenye hetekig
    ugyanaz, itt viszont pont a frissesseg a lenyeg.
    """
    rows = db.query(
        """
        select term, location from source_runs
         where engine_key = %s and actor = %s
           and (%s = 0 or run_at > now() - make_interval(days => %s))
        """,
        (engine.key, ACTOR, refresh_days, refresh_days))
    return {(r["term"], r["location"]) for r in rows}


def ingest(engine: EngineDef, max_results: int = 50, dry: bool = False,
           location: str = "", terms: tuple[str, ...] = (),
           resolve_maps: bool = False, refresh_days: int = 1,
           force: bool = False, verbose: bool = True) -> dict:
    """Hirdetesek betoltese. KET SZINTEN inkrementalis (lasd `_mar_futott`)."""
    kifejezesek = terms or _alapkifejezesek(engine)
    stats = {"lekerdezes": 0, "talalat": 0, "uj_hirdetes": 0, "mar_ismert": 0,
             "uj_ceg": 0, "domain_nelkul": 0, "kihagyva": 0, "kihagyott_kereses": 0}

    futott = set() if force else _mar_futott(engine, refresh_days)
    varo = [k for k in kifejezesek if (k, location) not in futott]
    stats["kihagyott_kereses"] = len(kifejezesek) - len(varo)

    if dry:
        print(f"[SZARAZ] {len(varo)} kifejezes futna, max {max_results} talalat:")
        for k in varo:
            print(f"    {k!r} @ {location or 'orszagos'}")
        if stats["kihagyott_kereses"]:
            print(f"\n  {stats['kihagyott_kereses']} kereses KIHAGYVA: "
                  f"{refresh_days} napon belul mar lefutott.")
            print("  Ha megis kell: --force vagy --refresh-days 0")
        print("\n  Ez NEM kolt. Eles futas: a --dry nelkul.")
        return stats

    if not varo:
        print(f"Minden kereses lefutott mar {refresh_days} napon belul -- "
              f"nem koltunk.")
        print("  Holnap ujra futtathato, vagy most: --force")
        return stats

    keret = max_results
    for kifejezes in varo:
        if keret <= 0:
            break
        payload: dict[str, Any] = {
            "searchQuery": kifejezes,
            "includeDetails": True,      # ⚠️ ENELKUL NINCS `description`
            "descriptionFormat": "text",
            "maxResults": min(keret, 50),
        }
        if location:
            payload["location"] = location

        if verbose:
            print(f"\n  kereses: {kifejezes!r}")
        try:
            items = apify.run_actor(ACTOR, payload, timeout=900, verbose=verbose)
        except apify.ApifyError as exc:
            print(f"    HIBA: {exc}")
            continue

        stats["lekerdezes"] += 1
        stats["talalat"] += len(items)
        keret -= len(items)

        for hirdetes in items:
            _feldolgoz(hirdetes, resolve_maps, stats, verbose,
                       term=kifejezes, location=location)

        # A LEKERDEZES rogzitese -- ez akadalyozza meg, hogy ugyanazert a
        # keresesert ma megegyszer fizessunk.
        db.execute("""
            insert into source_runs (engine_key, actor, term, location,
                                     results, new_companies)
                 values (%s, %s, %s, %s, %s, %s)
            on conflict (engine_key, actor, term, location) do update
                    set results = excluded.results,
                        new_companies = excluded.new_companies,
                        run_at = now()
        """, (engine.key, ACTOR, kifejezes, location, len(items), stats["uj_ceg"]))

    if verbose:
        _riport(stats)
    return stats


def _alapkifejezesek(engine: EngineDef) -> tuple[str, ...]:
    from ..engines import _OPS_PAIN_SEARCHES
    return _OPS_PAIN_SEARCHES


def _feldolgoz(hirdetes: dict, maps: bool, stats: dict, verbose: bool,
               term: str = "", location: str = "") -> None:
    source_url = storage.stable_source_url(
        hirdetes, "profession", ("jobId", "id", "positionId", "professionId"))
    cegnev = (hirdetes.get("companyName") or "").strip()
    raw = dict(hirdetes)
    raw["_ingest_context"] = {"term": term, "location": location,
                              "actor": ACTOR}

    # RAW-FIRST: kulon commit. A cegfeloldas vagy upsert kesobbi hibaja nem
    # torolheti el a mar visszakapott hirdetest.
    with db.connect() as raw_conn, raw_conn.cursor() as raw_cur:
        source_id, uj_forras = storage.save_source(
            raw_cur, SOURCE_TYPE, source_url, raw,
            processing_status="discovered")

    with db.connect() as conn, conn.cursor() as cur:
        if not uj_forras:
            cur.execute("select company_id from sources where id = %s", (source_id,))
            mar = cur.fetchone()
            if mar and mar["company_id"]:
                stats["mar_ismert"] += 1
                return

        if not cegnev:
            cur.execute(
                """
                update sources set processing_status = 'unmatched',
                                   processing_note = 'hianyzik a cegnev'
                 where id = %s
                """,
                (source_id,),
            )
            stats["kihagyva"] += 1
            if uj_forras:
                stats["uj_hirdetes"] += 1
            return

        if uj_forras:
            stats["uj_hirdetes"] += 1

        domain, honnan = _feloldas(hirdetes, maps)
        varos = hirdetes.get("addressLocality") or ""
        kulcs = normalize.normalize_company_name(cegnev)

        if verbose:
            jel = "✅" if domain else "❔"
            print(f"    {jel} {cegnev[:34]:<36} "
                  f"{domain or '(nincs domain)':<24} {honnan}")

        if not domain and not kulcs:
            cur.execute(
                """
                update sources set processing_status = 'unmatched',
                                   processing_note = 'nincs stabil cegazonosito'
                 where id = %s
                """,
                (source_id,),
            )
            stats["kihagyva"] += 1
            return

        # A ceg: domain szerint, vagy ha nincs, nev+telepules szerint.
        if domain:
            cur.execute("select id from companies where normalized_domain = %s", (domain,))
        else:
            cur.execute("select id from companies where name_key = %s and city = %s",
                        (kulcs, varos))
        letezo = cur.fetchone()

        if letezo:
            company_id = letezo["id"]
        else:
            cur.execute("""
                insert into companies (company_name, name_key, normalized_domain,
                                       domain, city, industry, campaign,
                                       signal_score, status, status_note)
                     values (%s, %s, %s, %s, %s, %s, 'ops_pain', %s, %s, %s)
                  returning id
            """, (cegnev, kulcs, domain,
                  f"https://{domain}" if domain else None, varos,
                  hirdetes.get("category") or "", 40,
                  # A domain nelkuli ceg NEM VESZ EL: `error` allapotban var,
                  # amig valamelyik kesobbi forras megadja a domaint.
                  "new" if domain else "error",
                  None if domain else f"nincs feloldhato domain ({honnan})"))
            company_id = cur.fetchone()["id"]
            stats["uj_ceg"] += 1
            if not domain:
                stats["domain_nelkul"] += 1

        # A teljes, eredeti hirdetes mar a cegazonositas ELOTT bekerult. Itt
        # csak hozzakapcsoljuk a ceghez es feljegyezzuk a feloldas modjat.
        raw["domain_resolution"] = honnan
        storage.save_source(cur, SOURCE_TYPE, source_url, raw,
                            company_id=company_id, processing_status="linked")
        storage.link_source(cur, source_id, company_id)
        if domain:
            labels.clear_label(cur, company_id, "domain_missing")
        else:
            labels.set_label(cur, company_id, "domain_missing",
                             {"resolution": honnan}, source_id)


def resolve_pending(limit: int = 20, dry: bool = False,
                    verbose: bool = True) -> dict:
    """A domain nelkul beragadt cegek feloldasa Google Maps-szel. FIZETOS.

    MIERT KELL KULON PARANCS, ES MIERT NEM AZ INGEST RESZE:
    az ingest INKREMENTALIS -- a mar latott hirdetest kiejti, MIELOTT a
    feloldasig jutna. Vagyis egy `--resolve-maps`-szel megismetelt ingest
    NEM oldana fel a korabban beragadt cegeket: azok hirdeteseit mar
    ismerjuk, tehat meg sem neznenk oket. Ez a parancs a CEGEKBOL indul,
    nem a hirdetesekbol -- ezert eri utol oket.

    (Ezt a hibat a 9. szakasz eles tesztje talalta meg: 11 ceg maradt
    domain nelkul, es semmilyen ingest-kapcsoloval nem lehetett volna
    utolerni oket.)
    """
    stats = {"vizsgalt": 0, "feloldva": 0, "sikertelen": 0}
    rows = db.query("""
        select c.id, c.company_name, c.city
          from companies c
         where c.normalized_domain is null
           and c.campaign = 'ops_pain'
           and c.status = 'error'
         order by c.first_seen_at
         limit %s
    """, (limit,))

    if not rows:
        if verbose:
            print("Nincs feloldasra varo ceg.")
        return stats

    if verbose:
        koltseg = len(rows) * 0.005
        print(f"{len(rows)} ceg feloldasa Google Maps-szel  (~${koltseg:.3f})"
              + ("   [SZARAZ FUTAS]" if dry else ""))

    for row in rows:
        stats["vizsgalt"] += 1
        if dry:
            print(f"    lekerdezne: {row['company_name']} @ {row['city'] or 'Hungary'}")
            continue

        domain = _domain_a_mapsbol(row["company_name"], row["city"])
        if not domain:
            stats["sikertelen"] += 1
            if verbose:
                print(f"    ❔ {row['company_name'][:40]:<42} nem talalt")
            db.execute("update companies set status_note = %s where id = %s",
                       ("Maps-feloldas sikertelen", row["id"]))
            continue

        # Ha kozben mar letezik ez a domain (masik forrasbol), NE hozzunk
        # letre duplikatumot -- a domain a fo dedupe kulcs.
        utkozes = db.query(
            "select id from companies where normalized_domain = %s and id <> %s",
            (domain, row["id"]))
        if utkozes:
            stats["sikertelen"] += 1
            if verbose:
                print(f"    ⚠ {row['company_name'][:40]:<42} {domain} (mar letezik)")
            db.execute("update companies set status_note = %s where id = %s",
                       (f"a feloldott domain ({domain}) mar mas ceghez tartozik",
                        row["id"]))
            continue

        stats["feloldva"] += 1
        if verbose:
            print(f"    ✅ {row['company_name'][:40]:<42} {domain}")
        with db.connect() as conn, conn.cursor() as cur:
            cur.execute("""
                update companies
                   set normalized_domain = %s, domain = %s,
                       status = 'new', status_note = 'domain feloldva: google maps'
                 where id = %s
            """, (domain, f"https://{domain}", row["id"]))
            labels.clear_label(cur, row["id"], "domain_missing")

    if verbose:
        print(f"\n  feloldva={stats['feloldva']}  sikertelen={stats['sikertelen']}")
        if stats["feloldva"]:
            print("  A feloldott cegek `new` allapotba kerultek -> jon az enrich:")
            print("    ./leadgen.sh enrich")
    return stats


def _riport(stats: dict) -> None:
    print(f"\n  lekerdezes={stats['lekerdezes']}  talalat={stats['talalat']}")
    print(f"  uj hirdetes={stats['uj_hirdetes']}  mar ismert={stats['mar_ismert']} "
          f"(kihagyva)")
    print(f"  uj ceg={stats['uj_ceg']}  ebbol domain nelkul={stats['domain_nelkul']}")
    if stats.get("kihagyott_kereses"):
        print(f"  kihagyott kereses={stats['kihagyott_kereses']} "
              f"(a friss ablakon belul mar lefutott -- nem koltottunk ra)")
    if stats["domain_nelkul"]:
        print(f"\n  {stats['domain_nelkul']} ceghez nem talaltunk domaint. NEM VESZTEK EL:")
        print("  `error` allapotban varnak. Ha kesz vagy fizetni a feloldasert:")
        print("    ./leadgen.sh ingest ops-pain --resolve-maps")
    if stats["mar_ismert"] and not stats["uj_hirdetes"]:
        print("\n  Minden hirdetest lattunk mar -- az inkrementalitas mukodik.")
