"""GET /api/report/daily, GET /api/report/funnel.

Csak a `leadgen.report` mar meglevo `*_adat()` fuggvenyeit hivja (F1
elofeltetel: a report.py refaktora) -- itt nem szamolunk ujra semmit.
"""
from __future__ import annotations

from fastapi import APIRouter

from leadgen import report

from ..schemas import DailyResponse, FunnelResponse

router = APIRouter()


@router.get("/api/report/daily", response_model=DailyResponse)
def report_daily() -> dict:
    return report.daily_adat()


@router.get("/api/report/funnel", response_model=FunnelResponse)
def report_funnel() -> dict:
    return report.funnel_adat()
