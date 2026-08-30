"""GET /api/costs, /api/costs/daily, GET /api/runs -- koltsegmeres es
forras-futasok elozmenye.

A koltseg a `llmcheck.osszesites_adat()`-ot (modellenkent) es a
`llmcheck.napi_koltseg_adat()`-ot (naponkent, F9 vonal-chart) hivja -- mindket
fuggveny ugyanazt a `data/llm_usage.csv`-t osszegzi, csak mas tengely menten
(ugyanaz az adat, mint a `llm-check --summary`). A `source_runs` tablanak
nincs meg meglevo olvaso fuggvenye -- itt egy egyszeru `db.query`.
"""
from __future__ import annotations

from fastapi import APIRouter

from leadgen import db, llmcheck

from ..schemas import CostsResponse, DailyCostsResponse, RunsResponse

router = APIRouter()


@router.get("/api/costs", response_model=CostsResponse)
def costs() -> dict:
    return llmcheck.osszesites_adat()


@router.get("/api/costs/daily", response_model=DailyCostsResponse)
def costs_daily() -> dict:
    return llmcheck.napi_koltseg_adat()


@router.get("/api/runs", response_model=RunsResponse)
def runs(limit: int = 100) -> dict:
    rows = db.query(
        """
        select engine_key, actor, term, location, results, new_companies, run_at
          from source_runs
      order by run_at desc
         limit %s
        """,
        (limit,),
    )
    return {"items": rows, "total": len(rows)}
