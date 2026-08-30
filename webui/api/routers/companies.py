"""GET /api/companies, GET /api/companies/{id}.

A frontend nem ir SQL-t (WEBUI-TERV.md Invariansok #7) -- ez a modul az
egyetlen hely, ahol a `companies` listajahoz/reszletehez lekerdezes megy, es
csak `db.query`-t hasznal (leadgen/db.py az egyetlen hely, ahol psycopg-t
hivunk).
"""
from __future__ import annotations

import psycopg
from fastapi import APIRouter, HTTPException, Query

from leadgen import db

from ..schemas import CompanyDetailResponse, CompanyListResponse

router = APIRouter()

_SORT_COLUMNS = {
    "signal_score": "signal_score",
    "company_name": "company_name",
    "updated_at": "updated_at",
}


@router.get("/api/companies", response_model=CompanyListResponse)
def list_companies(
    status: str | None = None,
    campaign: str | None = None,
    engine: str | None = None,
    economic_value: str | None = None,
    label: str | None = None,
    q: str | None = None,
    sort: str = Query("signal_score", pattern="^(signal_score|company_name|updated_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
) -> dict:
    where = []
    params: list = []

    if status:
        where.append("c.status = %s")
        params.append(status)
    if campaign:
        where.append("c.campaign = %s")
        params.append(campaign)
    if engine:
        where.append(
            "exists (select 1 from sources s where s.company_id = c.id "
            "and s.source_type = %s)"
        )
        params.append(engine)
    if economic_value:
        where.append("c.economic_value = %s")
        params.append(economic_value)
    if label:
        where.append(
            "exists (select 1 from company_labels cl where cl.company_id = c.id "
            "and cl.label = %s)"
        )
        params.append(label)
    if q:
        where.append("(c.company_name ilike %s or c.normalized_domain ilike %s)")
        like = f"%{q}%"
        params.extend([like, like])

    where_sql = f"where {' and '.join(where)}" if where else ""
    sort_col = _SORT_COLUMNS[sort]
    order_sql = "asc" if order == "asc" else "desc"

    total = db.query(f"select count(*) as n from companies c {where_sql}", tuple(params))
    total_n = total[0]["n"] if total else 0

    offset = (page - 1) * per_page
    rows = db.query(
        f"""
        select c.id, c.company_name, c.normalized_domain, c.status, c.campaign,
               c.economic_value, c.signal_score, c.city, c.industry,
               c.best_offer, c.updated_at
          from companies c
          {where_sql}
      order by {sort_col} {order_sql} nulls last
         limit %s offset %s
        """,
        tuple(params) + (per_page, offset),
    )

    return {
        "items": rows,
        "page": page,
        "per_page": per_page,
        "total": total_n,
        "total_pages": (total_n + per_page - 1) // per_page if per_page else 0,
    }


@router.get("/api/companies/{company_id}", response_model=CompanyDetailResponse)
def company_detail(company_id: str) -> dict:
    try:
        rows = db.query("select * from companies where id = %s", (company_id,))
    except psycopg.errors.InvalidTextRepresentation:
        raise HTTPException(status_code=400, detail="ervenytelen ceg-azonosito")
    if not rows:
        raise HTTPException(status_code=404, detail="nincs ilyen ceg")
    company = rows[0]

    sources = db.query(
        "select id, source_type, source_url, raw_signal, detected_at, created_at "
        "from sources where company_id = %s order by detected_at desc",
        (company_id,),
    )
    contacts = db.query(
        "select * from contacts where company_id = %s order by created_at",
        (company_id,),
    )
    angles = db.query(
        "select * from opportunity_angles where company_id = %s order by rank",
        (company_id,),
    )
    labels = db.query(
        "select * from company_labels where company_id = %s order by label",
        (company_id,),
    )
    outreach = db.query(
        "select * from outreach where company_id = %s order by queued_at desc",
        (company_id,),
    )

    # A suppression email- VAGY domain-szinten tilthat -- mindket iranyt
    # nezzuk: a ceg domainjet, es a hozza tartozo kontaktusok cimeit.
    contact_emails = [c["email"] for c in contacts]
    suppression = db.query(
        "select * from suppression "
        "where normalized_domain = %s or email = any(%s) "
        "order by created_at desc",
        (company["normalized_domain"], contact_emails),
    )

    return {
        "company": company,
        "sources": sources,
        "contacts": contacts,
        "opportunity_angles": angles,
        "company_labels": labels,
        "outreach": outreach,
        "suppression": suppression,
    }
