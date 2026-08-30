"""GET /api/schedule/status -- fut-e az utemezett napi lanc."""
from __future__ import annotations

from fastapi import APIRouter

from leadgen import schedule

from ..schemas import ScheduleStatusResponse

router = APIRouter()


@router.get("/api/schedule/status", response_model=ScheduleStatusResponse)
def schedule_status() -> dict:
    return schedule.allapot_adat()
