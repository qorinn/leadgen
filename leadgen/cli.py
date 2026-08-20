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

from . import config, db, dev, export


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
    export.run(dry=args.dry, limit=args.limit)
    return 0


def _cmd_dev_seed(_args: argparse.Namespace) -> int:
    created = dev.seed()
    print(f"Teszt-cegek: {created} uj, a tobbi mar letezett.")
    print("Torles: leadgen dev clear-seed")
    return 0


def _cmd_dev_clear_seed(_args: argparse.Namespace) -> int:
    print(f"Torolve: {dev.clear_seed()} teszt-ceg.")
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
    exp.set_defaults(func=_cmd_export)

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
