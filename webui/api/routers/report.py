"""GET /api/report/* -- a `leadgen.report` mar meglevo `*_adat()`
fuggvenyeit hivja (F1 elofeltetel: a report.py refaktora) -- itt nem
szamolunk ujra semmit, csak atadjuk, amit a CLI is mutat.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from leadgen import report

from ..schemas import (CampaignResponse, DailyResponse, EconomicResponse,
                        FunnelResponse, GroundingResponse, SenderCsvResponse)

router = APIRouter()


@router.get("/api/report/daily", response_model=DailyResponse)
def report_daily() -> dict:
    return report.daily_adat()


@router.get("/api/report/funnel", response_model=FunnelResponse)
def report_funnel() -> dict:
    return report.funnel_adat()


@router.get("/api/report/grounding", response_model=GroundingResponse)
def report_grounding() -> dict:
    return report.grounding_adat()


@router.get("/api/report/economic", response_model=EconomicResponse)
def report_economic() -> dict:
    return report.economic_adat()


@router.get("/api/report/campaign", response_model=CampaignResponse)
def report_campaign(name: str = Query(..., min_length=1)) -> dict:
    return report.campaign_adat(name)


@router.get("/api/report/sender-csv/{nev}", response_model=SenderCsvResponse)
def report_sender_csv(nev: str) -> dict:
    try:
        return report.sender_csv_adat(nev)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
