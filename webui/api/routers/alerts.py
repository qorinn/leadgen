"""GET /api/alerts -- aktiv es lezart riasztasok.

Csak olvas: `leadgen.alerts.aktiv_riasztasok()` / `lezart_riasztasok()`.
"""
from __future__ import annotations

from fastapi import APIRouter

from leadgen import alerts

from ..schemas import AlertsResponse

router = APIRouter()


@router.get("/api/alerts", response_model=AlertsResponse)
def list_alerts() -> dict:
    return {
        "aktiv": alerts.aktiv_riasztasok(),
        "lezart": alerts.lezart_riasztasok(),
    }
