"""GET /api/logs/{nev} -- egy naplofajl utolso N sora.

A harom naplo a kuldo `data/` konyvtaraban el (WEBUI-TERV.md): `sender`
(kuldes), `alerts` (riasztasok), `daily` (az utemezett lanc kimenete).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from leadgen import config, schedule

from ..schemas import LogResponse

router = APIRouter()

_LOG_PATHS = {
    "sender": config.SENDER_DATA / "sender.log",
    "alerts": config.ALERTS_LOG,
    "daily": schedule.LOG_PATH,
}


@router.get("/api/logs/{nev}", response_model=LogResponse)
def log_tail(nev: str, lines: int = Query(200, ge=1, le=2000)) -> dict:
    path = _LOG_PATHS.get(nev)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail=f"ismeretlen naplo: {nev!r} (valaszthato: {', '.join(_LOG_PATHS)})",
        )
    if not path.exists():
        return {"name": nev, "path": str(path), "exists": False, "lines": []}

    tartalom = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {
        "name": nev,
        "path": str(path),
        "exists": True,
        "lines": tartalom[-lines:],
    }
