#!/usr/bin/env python3
"""Adatbazis-hozzaferes. EZ AZ EGYETLEN HELY, ahol psycopg-t hivunk.

Miert egy helyen: ha valaha ki kell koltozni a Supabase-bol (sajat Postgres,
vagy vesszhelyzetben SQLite), akkor egy fajl valtozik, nem husz. A tobbi modul
csak a lenti fuggvenyeket hasznalja, connection stringet sehol mashol ne olvass.

Migraciok: sima .sql fajlok a migrations/ alatt, nevsorrendben. Nincs ORM es
nincs migracio-keretrendszer -- egy hatarido elott az a legjobb sema-kezeles,
amit el lehet olvasni.
"""
from __future__ import annotations

import contextlib
import hashlib
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json  # noqa: F401  (a hivo oldalak db.Json-kent hasznaljak)

from . import config

# A migracios naplo. Ezt a runner hozza letre, mielott barmit olvasna.
_MIGRATIONS_TABLE = """
create table if not exists schema_migrations (
  filename   text primary key,
  checksum   text not null,
  applied_at timestamptz not null default now()
)
"""

# A sema tablai, a fuggosegek sorrendjeben (a `db check` ezeket szamolja).
TABLES = (
    "companies", "sources", "contacts", "suppression",
    "outreach", "reply_events", "feedback_watermark",
    "company_labels", "opportunity_angles",
)


@contextlib.contextmanager
def connect() -> Iterator[psycopg.Connection]:
    """Egy tranzakcios kapcsolat. Kilepeskor commit, kivetelnel rollback."""
    conn = psycopg.connect(config.require_database_url(), row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query(sql: str, params: tuple | dict | None = None) -> list[dict[str, Any]]:
    """Egyszeru lekerdezes. Kis eredmenyhalmazokra valo (batch = 50 sor)."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else []


def execute(sql: str, params: tuple | dict | None = None) -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def migrate(verbose: bool = True) -> list[str]:
    """Lefuttatja a meg nem alkalmazott migraciokat, nevsorrendben.

    Idempotens: ujra futtatva nem csinal semmit. Ha egy MAR ALKALMAZOTT fajl
    tartalma megvaltozott, hibaval megall -- ilyenkor uj migracios fajl kell,
    nem a regi atirasa. (Kulonben a te gepeden mas sema lenne, mint az elesben.)
    """
    files = sorted(config.MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        raise SystemExit(f"HIBA: nincs migracios fajl itt: {config.MIGRATIONS_DIR}")

    applied: list[str] = []
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(_MIGRATIONS_TABLE)
            cur.execute("select filename, checksum from schema_migrations")
            known = {row["filename"]: row["checksum"] for row in cur.fetchall()}

        for path in files:
            body = path.read_text(encoding="utf-8")
            digest = _checksum(body)

            if path.name in known:
                if known[path.name] != digest:
                    raise SystemExit(
                        f"HIBA: a {path.name} mar le van futtatva, de a tartalma megvaltozott.\n"
                        "  Egy alkalmazott migraciot nem irunk at -- vegy fel egy uj fajlt\n"
                        "  (pl. 002_valami.sql) a modositassal."
                    )
                if verbose:
                    print(f"  = {path.name} (mar alkalmazva)")
                continue

            with conn.cursor() as cur:
                cur.execute(body)
                cur.execute(
                    "insert into schema_migrations (filename, checksum) values (%s, %s)",
                    (path.name, digest),
                )
            applied.append(path.name)
            if verbose:
                print(f"  + {path.name}")

    return applied


def check() -> dict[str, int | None]:
    """Tablankenti sorszam. None = a tabla nem letezik (migracio hianyzik)."""
    counts: dict[str, int | None] = {}
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select table_name from information_schema.tables
                 where table_schema = 'public'
            """)
            existing = {row["table_name"] for row in cur.fetchall()}

        for table in TABLES:
            if table not in existing:
                counts[table] = None
                continue
            with conn.cursor() as cur:
                cur.execute(f"select count(*) as n from {table}")
                counts[table] = cur.fetchone()["n"]
    return counts


def server_info() -> dict[str, Any]:
    rows = query("select version() as version, current_database() as db, now() as now")
    return rows[0] if rows else {}
