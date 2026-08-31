"""GET /api/schedule/status, POST /api/schedule/install, POST
/api/schedule/uninstall -- fut-e az utemezett napi lanc, es telepitheto/
eltavolithato-e a feluletrol (WEBUI-TERV.md F10).

A tenyleges launchd-muveletet a `leadgen.schedule` vegzi (`telepit_adat()` /
`eltavolit_adat()`) -- ugyanaz a ket fuggveny all a CLI `schedule install`/
`uninstall` mogott is, egy forras."""
from __future__ import annotations

from fastapi import APIRouter

from leadgen import schedule

from ..schemas import ScheduleActionResponse, ScheduleStatusResponse

router = APIRouter()


@router.get("/api/schedule/status", response_model=ScheduleStatusResponse)
def schedule_status() -> dict:
    return schedule.allapot_adat()


@router.post("/api/schedule/install", response_model=ScheduleActionResponse)
def schedule_install() -> dict:
    return schedule.telepit_adat()


@router.post("/api/schedule/uninstall", response_model=ScheduleActionResponse)
def schedule_uninstall() -> dict:
    return schedule.eltavolit_adat()
