"""GET /api/health -- fut-e a ket rendszer, el a kapcsolat.

Csak olvas: a `db.check()` es a `db.migrate` sajat migracios naploja
(`schema_migrations`) adja az adatot, nem uj lekerdezes irja ujra a logikat.
"""
from __future__ import annotations

from fastapi import APIRouter

from leadgen import config, db

from .. import VERSION
from ..schemas import HealthResponse

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse)
def health() -> dict:
    try:
        counts = db.check()
        db_ok = all(n is not None for n in counts.values())
        tablak = len(counts)
    except Exception:  # noqa: BLE001 -- a DB elerhetetlensege sem dobhat 500-at
        db_ok = False
        tablak = 0

    try:
        migraciok_sorai = db.query(
            "select filename from schema_migrations order by filename desc limit 1"
        )
        alkalmazott = db.query("select count(*) as n from schema_migrations")[0]["n"]
        utolso = migraciok_sorai[0]["filename"] if migraciok_sorai else None
    except Exception:  # noqa: BLE001
        alkalmazott, utolso = 0, None

    return {
        "db": {"ok": db_ok, "tablak": tablak},
        "sender_dir": {"ok": config.SENDER_DIR.exists(), "ut": str(config.SENDER_DIR)},
        "migraciok": {"alkalmazott": alkalmazott, "utolso": utolso},
        "verzio": VERSION,
    }
