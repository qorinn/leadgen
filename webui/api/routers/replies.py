"""GET /api/replies -- a beerkezett valaszok, szurve osztaly szerint."""
from __future__ import annotations

from fastapi import APIRouter

from leadgen import db

from ..schemas import RepliesResponse

router = APIRouter()


@router.get("/api/replies", response_model=RepliesResponse)
def list_replies(classification: str | None = None) -> dict:
    where = "where r.classification = %s" if classification else ""
    params = (classification,) if classification else ()
    rows = db.query(
        f"""
        select r.id, r.email, r.received_at, r.subject, r.body, r.classification,
               r.confidence, r.model, r.rationale, r.error, r.classified_at,
               c.id as company_id, c.company_name, c.normalized_domain
          from reply_events r
     left join contacts ct on ct.email = r.email
     left join companies c on c.id = ct.company_id
          {where}
      order by r.received_at desc nulls last
        """,
        params,
    )
    return {"items": rows, "total": len(rows)}
