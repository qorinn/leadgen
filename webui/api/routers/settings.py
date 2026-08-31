"""GET /api/settings, GET /api/diagnostics -- maszkolt .env-ertekek es
rendszer-diagnosztika (WEBUI-TERV.md F10).

A felulet SOHA nem irja a `.env`-et -- ez a modul csak olvas. A titkok
maszkolasa a `leadgen.config.settings_adat()`-ban dol el, nem itt (WEBUI-TERV.md
Invariansok #4: a titok soha nem mehet ki teljes ertekben). Az engine-ek es a
jovahagyott kampanyok listaja mar a `/api/meta`-ban megvan -- ide nem
masoljuk at ujra, a felulet onnan olvassa.
"""
from __future__ import annotations

from fastapi import APIRouter

from leadgen import config, db

from ..schemas import DiagnosticsResponse, SettingsResponse

router = APIRouter()


@router.get("/api/settings", response_model=SettingsResponse)
def settings() -> dict:
    return {"tetelek": config.settings_adat()}


@router.get("/api/diagnostics", response_model=DiagnosticsResponse)
def diagnostics() -> dict:
    return {
        "migraciok": db.migrations_adat(),
        "feedback_watermark": db.feedback_watermark_adat(),
    }
