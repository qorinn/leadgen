#!/usr/bin/env python3
"""leadgen parancssor.

    .venv/bin/python -m leadgen.cli db migrate
    .venv/bin/python -m leadgen.cli db check

Ez a modul SZANDEKOSAN vekony: csak argumentumot elemez es kiir. Minden
uzleti logika a tobbi modul fuggvenyeiben van, hogy a 13. szakasz webes
felulete ugyanazokat hivhassa -- a CLI ne legyen zsakutca.

Parancscsoportok:
    db      -- migracio, allapot, kapcsolodasi adatok
    export  -- DB -> cold-email-starter/data/leads.csv
    dev     -- fejlesztoi teszt-adat (sosem eles)
"""
from __future__ import annotations

import argparse
import sys

from . import config, db, dev, engines, export, feedback, pipeline
from .sources import maps


def _cmd_db_migrate(_args: argparse.Namespace) -> int:
    print(f"Migraciok innen: {config.MIGRATIONS_DIR}")
    applied = db.migrate()
    print(f"\nKesz. Ujonnan alkalmazva: {len(applied)}")
    return 0


def _cmd_db_check(_args: argparse.Namespace) -> int:
    info = db.server_info()
    version = str(info.get("version", "?")).split(",")[0]
    print(f"Szerver : {version}")
    print(f"Adatbazis: {info.get('db')}")
    print()

    counts = db.check()
    missing = [t for t, n in counts.items() if n is None]
    width = max(len(t) for t in counts)
    for table, n in counts.items():
        state = "HIANYZIK" if n is None else f"{n} sor"
        print(f"  {table:<{width}}  {state}")

    if missing:
        print(f"\nHIBA: {len(missing)} tabla hianyzik. Futtasd: db migrate")
        return 1
    print(f"\nMind a {len(counts)} tabla megvan.")
    return 0


def _cmd_db_info(_args: argparse.Namespace) -> int:
    """Kapcsolodasi adatok jelszo NELKUL -- hibakeresesre."""
    from urllib.parse import urlsplit

    u = urlsplit(config.require_database_url())
    print(f"host      = {u.hostname}")
    print(f"port      = {u.port}")
    print(f"felhasznalo = {u.username}")
    print(f"adatbazis = {(u.path or '').lstrip('/')}")
    print(f"jelszo    = {'meg van adva' if u.password else 'HIANYZIK'}")
    if u.port == 6543:
        print("\nFIGYELEM: ez a transaction pooler (6543). A migraciok elhasalnak rajta.")
        print("Kerd a session poolert (5432).")
    print(f"\nkuldo konyvtar = {config.SENDER_DIR}  "
          f"({'letezik' if config.SENDER_DIR.exists() else 'HIANYZIK'})")
    print(f"email validacio = {config.EMAIL_VALIDATION}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    export.run(dry=args.dry, limit=args.limit, skip_feedback=args.skip_feedback)
    return 0


def _cmd_feedback(_args: argparse.Namespace) -> int:
    """Onalloan is futtathato -- pl. ha latsz egy valaszt a postafiokban,
    es azonnal at akarod vezetni a DB-be."""
    feedback.run(verbose=True)
    return 0


def _cmd_dev_seed(_args: argparse.Namespace) -> int:
    created = dev.seed()
    print(f"Teszt-cegek: {created} uj, a tobbi mar letezett.")
    print("Torles: leadgen dev clear-seed")
    return 0


def _cmd_dev_clear_seed(_args: argparse.Namespace) -> int:
    print(f"Torolve: {dev.clear_seed()} teszt-ceg.")
    return 0


def _cmd_ingest_maps(args: argparse.Namespace) -> int:
    engine = engines.get(args.engine)
    print(f"Engine: {engine.label}")
    stats = maps.ingest(engine, max_results=args.max_results, dry=args.dry,
                        refresh_days=args.refresh_days, force=args.force,
                        location=args.location)
    if not args.dry:
        print(f"\n  lefuttatott lekerdezes={stats['lekerdezes']}  "
              f"korabban mar lefutott={stats['kihagyva']} (kihagyva)")
        print(f"  talalat={stats['talalat']} uj ceg={stats['uj_ceg']} "
              f"mar ismert={stats['mar_ismert']} kulcs nelkul={stats['kulcs_nelkul']}")
        if stats["hatralevo"]:
            print(f"\n  Meg {stats['hatralevo']} lekerdezes var -- a keret ({args.max_results}) "
                  f"elfogyott.\n  Futtasd ujra ugyanezt a parancsot: onnan folytatja.")
    return 0


def _cmd_enrich(args: argparse.Namespace) -> int:
    pipeline.run_enrich(limit=args.limit)
    return 0


def _cmd_qualify(args: argparse.Namespace) -> int:
    engine = engines.get(args.engine)
    print(f"Engine: {engine.label}")
    pipeline.run_qualify(engine, limit=args.limit)
    return 0


def _cmd_engines(_args: argparse.Namespace) -> int:
    print(f"{'kulcs':22} {'allapot':10} {'kampany':18} nev")
    print("-" * 80)
    for key, e in sorted(engines.ALL_ENGINES.items()):
        allapot = "aktiv" if e.enabled else "kikapcsolva"
        print(f"{key:22} {allapot:10} {e.campaign:18} {e.label}")
    print("\nUj iparag felvetele: leadgen/engines.py -- az iparag adat, nem kod.")
    return 0


def _cmd_review(args: argparse.Namespace) -> int:
    """Emberi dontes. Az AUTOMATIKUS dontesek is felulbirlhatok innen."""
    if args.approve:
        # `review` ES `suppressed` allapotbol is visszahozhato -- kulonben a
        # gep automatikus versenytars-dontese felulbirlhatatlan lenne, es a
        # felhasznalo nem tudna korrigalni egy tul szigoru kulcsszot.
        with db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "update companies set status = 'ready', status_note = 'kezi jovahagyas' "
                "where normalized_domain = %s and status in ('review','suppressed','rejected')",
                (args.approve,))
            n = cur.rowcount
            if n:
                cur.execute("delete from suppression where normalized_domain = %s "
                            "and reason = 'competitor'", (args.approve,))
        print(f"Jovahagyva: {n} ceg -> ready" if n else
              "Nincs ilyen ceg review/suppressed/rejected allapotban.")
        return 0

    if args.suppressed:
        rows = db.query("""
            select c.normalized_domain, c.company_name, c.status_note,
                   s.raw_signal->>'title' as title
              from companies c
              left join sources s on s.company_id = c.id and s.source_type = 'website_crawl'
             where c.status = 'suppressed' and c.status_note like 'versenytars%'
             order by c.normalized_domain
        """)
        if not rows:
            print("Nincs automatikusan kizart ceg.")
            return 0
        print(f"{len(rows)} ceget a rendszer AUTOMATIKUSAN zart ki versenytarskent.\n")
        print("Ha valamelyiket tevesnek tartod, visszahozhatod:")
        print("  ./leadgen.sh review --approve <domain>\n")
        for r in rows:
            print(f"  https://{r['normalized_domain']}")
            print(f"    {r['company_name']}")
            print(f"    {r['status_note']}")
            print(f"    cim: {(r['title'] or '')[:88]}\n")
        return 0
    if args.reject:
        with db.connect() as conn, conn.cursor() as cur:
            cur.execute("update companies set status = 'suppressed', "
                        "status_note = 'kezi elutasitas: versenytars' "
                        "where normalized_domain = %s and status = 'review'", (args.reject,))
            n = cur.rowcount
            if n:
                cur.execute("insert into suppression (normalized_domain, reason, note) "
                            "values (%s, 'competitor', 'kezi elutasitas') "
                            "on conflict (normalized_domain) where normalized_domain is not null "
                            "and email is null do nothing", (args.reject,))
        print(f"Elutasitva: {n} ceg -> suppressed" if n else "Nincs ilyen ceg `review` allapotban.")
        return 0

    rows = db.query("""
        select c.normalized_domain, c.company_name, c.status_note, c.signal_summary,
               (select ct.email from contacts ct where ct.company_id = c.id limit 1) as email
          from companies c where c.status = 'review'
         order by c.signal_score desc nulls last, c.company_name
    """)
    if not rows:
        print("Nincs atnezendo ceg.")
        return 0
    print(f"{len(rows)} ceg var emberi dontesre.\n")
    print("A gyenge kizaro jel gyakran ugyfel-referenciabol vagy blogcikkbol jon,")
    print("nem a ceg sajat szolgaltatas-listajabol. Nyisd meg az oldalt es dontsd el.\n")
    for r in rows:
        print(f"  https://{r['normalized_domain']}")
        print(f"    {r['company_name']}   {r['email'] or '(nincs email)'}")
        print(f"    {r['status_note']}")
        print(f"    jovahagyas : leadgen review --approve {r['normalized_domain']}")
        print(f"    elutasitas : leadgen review --reject  {r['normalized_domain']}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="leadgen", description="Lead-scraper")
    sub = parser.add_subparsers(dest="group", required=True)

    db_parser = sub.add_parser("db", help="adatbazis-muveletek")
    db_sub = db_parser.add_subparsers(dest="action", required=True)
    db_sub.add_parser("migrate", help="a meg nem futtatott migraciok").set_defaults(
        func=_cmd_db_migrate)
    db_sub.add_parser("check", help="tablak es sorszamok").set_defaults(
        func=_cmd_db_check)
    db_sub.add_parser("info", help="kapcsolodasi adatok (jelszo nelkul)").set_defaults(
        func=_cmd_db_info)

    exp = sub.add_parser("export", help="leadek kiirasa a kuldonek")
    exp.add_argument("--dry", action="store_true",
                     help="csak megmutatja, mit irna ki -- nem ir es nem allit sorba")
    exp.add_argument("--limit", type=int, default=0,
                     help="ennyi UJ leadnel tobbet ne allitson sorba (adagolas)")
    exp.add_argument("--skip-feedback", action="store_true",
                     help="csak fejlesztes kozben: kihagyja a kotelezo feedback-importot")
    exp.set_defaults(func=_cmd_export)

    fb = sub.add_parser("feedback", help="a kuldo CSV-inek beolvasasa a DB-be")
    fb.set_defaults(func=_cmd_feedback)

    sub.add_parser("engines", help="elerheto lead engine-ek").set_defaults(func=_cmd_engines)

    rv = sub.add_parser("review", help="emberi dontesre varo cegek")
    rv.add_argument("--approve", metavar="DOMAIN", help="jo lead -> ready")
    rv.add_argument("--reject", metavar="DOMAIN", help="versenytars -> suppressed")
    rv.add_argument("--suppressed", action="store_true",
                    help="az AUTOMATIKUSAN kizart cegek (felulbirlhatod oket)")
    rv.set_defaults(func=_cmd_review)

    ing = sub.add_parser("ingest", help="cegek betoltese egy forrasbol")
    ing_sub = ing.add_subparsers(dest="source", required=True)
    m = ing_sub.add_parser("maps", help="Google Maps (Apify)")
    m.add_argument("--engine", default="agency_partner")
    m.add_argument("--max-results", type=int, default=50,
                   help="felso korlat a TELJES futasra (~$0.005 / talalat)")
    m.add_argument("--dry", action="store_true", help="csak a terv, nem koltunk")
    m.add_argument("--refresh-days", type=int, default=30,
                   help="ennyi napnal regebbi lekerdezes ujra futhat (0 = soha)")
    m.add_argument("--location", metavar="VAROS",
                   help="csak erre a telepulesre fusson (pl. Budapest)")
    m.add_argument("--force", action="store_true",
                   help="minden lekerdezes ujra fut, meg a mar lefuttatottak is")
    m.set_defaults(func=_cmd_ingest_maps)

    en = sub.add_parser("enrich", help="weboldalak feldolgozasa (`new` -> `enriched`)")
    en.add_argument("--limit", type=int, default=25)
    en.set_defaults(func=_cmd_enrich)

    ql = sub.add_parser("qualify", help="minosites (`enriched` -> `ready`/`rejected`)")
    ql.add_argument("--engine", default="agency_partner")
    ql.add_argument("--limit", type=int, default=200)
    ql.set_defaults(func=_cmd_qualify)

    dev_parser = sub.add_parser("dev", help="fejlesztoi eszkozok")
    dev_sub = dev_parser.add_subparsers(dest="action", required=True)
    dev_sub.add_parser("seed", help="teszt-cegek beszurasa (.invalid domainek)").set_defaults(
        func=_cmd_dev_seed)
    dev_sub.add_parser("clear-seed", help="teszt-cegek torlese").set_defaults(
        func=_cmd_dev_clear_seed)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
