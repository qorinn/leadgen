#!/usr/bin/env python3
"""leadgen parancssor.

    .venv/bin/python -m leadgen.cli db migrate
    .venv/bin/python -m leadgen.cli db check

Ez a modul SZANDEKOSAN vekony: csak argumentumot elemez es kiir. Minden
uzleti logika a tobbi modul fuggvenyeiben van, hogy a 13. szakasz webes
felulete ugyanazokat hivhassa -- a CLI ne legyen zsakutca.

Az 1. szakaszban csak a `db` parancscsoport letezik. Uzleti logika nincs.
"""
from __future__ import annotations

import argparse
import sys

from . import config, db


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

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
