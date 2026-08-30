"""POST /api/review/{id}/approve, POST /api/review/{id}/reject,
GET /api/review/suppressed.

A tenyleges donteshozatal a leadgen/review.py-ban van (EGY forras, a CLI
`review --approve/--reject/--suppressed` es ez a router UGYANEZEKET a
fuggvenyeket hivja -- lasd annak modul-docstringjet). Ez a modul csak az
id -> domain feloldast vegzi, es HTTP-formara alakitja a valaszt.
"""
from __future__ import annotations

import psycopg
from fastapi import APIRouter, HTTPException

from leadgen import db, review

from ..schemas import RejectBody, ReviewActionResponse, SuppressedListResponse

router = APIRouter()


def _domain_for(company_id: str) -> str:
    """company_id -> normalized_domain, mert a leadgen/review.py fuggvenyei
    (a CLI-vel megegyezoen) domain szerint dolgoznak."""
    try:
        rows = db.query(
            "select normalized_domain from companies where id = %s", (company_id,))
    except psycopg.errors.InvalidTextRepresentation:
        raise HTTPException(status_code=400, detail="ervenytelen ceg-azonosito")
    if not rows:
        raise HTTPException(status_code=404, detail="nincs ilyen ceg")
    domain = rows[0]["normalized_domain"]
    if not domain:
        raise HTTPException(
            status_code=409,
            detail="a cegnek nincs domainje -- a review ezen nem tud dolgozni",
        )
    return domain


@router.post("/api/review/{company_id}/approve", response_model=ReviewActionResponse)
def review_approve(company_id: str) -> dict:
    domain = _domain_for(company_id)
    eredmeny = review.approve(domain)
    if not eredmeny.talalt:
        raise HTTPException(
            status_code=409,
            detail="a ceg nincs jovahagyhato allapotban "
                   "(review / hold / rejected / automatikusan kizart versenytars)",
        )
    return {"uj_status": eredmeny.uj_status}


@router.post("/api/review/{company_id}/reject", response_model=ReviewActionResponse)
def review_reject(company_id: str, body: RejectBody) -> dict:
    domain = _domain_for(company_id)
    eredmeny = review.reject(domain, body.reason)
    if not eredmeny.talalt:
        raise HTTPException(
            status_code=409,
            detail="a ceg nincs elutasithato allapotban, vagy mar tiltolistan van",
        )
    return {"uj_status": "suppressed"}


@router.get("/api/review/suppressed", response_model=SuppressedListResponse)
def review_suppressed() -> dict:
    return {"items": review.suppressed_competitors()}
