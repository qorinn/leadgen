"""GET /api/meta -- a kontraktus, ami megakadalyozza, hogy uzleti szabalyok
atszivarogjanak TypeScriptbe (WEBUI-TERV.md Invariansok #1).

Minden ertek MEGLEVO Python-forrasbol jon, egyiket sem irjuk ujra:
  statuszok       -> report.STATUS_ORDER / STATUS_LABEL
  kampanyok       -> a companies tablaban elofordulo nevek + contract.APPROVED_CAMPAIGNS
  engine_ek       -> engines.ALL_ENGINES
  suppression_okok-> db.suppression_reasons() (a suppression_reason_check CHECK constraint)
  valasz_osztalyok-> report._REPLY_ORDER / _REPLY_LABEL
  cimkek          -> a company_labels tablaban ma elofordulo cimkek (nincs kulon enum)
  kuszobok        -> config.* (scraper) + a kuldo sajat kuszobei (subprocess, mint a _sender_state)
"""
from __future__ import annotations

from fastapi import APIRouter

from leadgen import config, db, engines, report
from leadgen.contract import APPROVED_CAMPAIGNS

from ..schemas import MetaResponse

router = APIRouter()


@router.get("/api/meta", response_model=MetaResponse)
def meta() -> dict:
    statuszok = [
        {"kulcs": s, "cimke": report.STATUS_LABEL.get(s, s), "sorrend": i}
        for i, s in enumerate(report.STATUS_ORDER)
    ]

    campaign_rows = db.query(
        "select distinct campaign from companies where campaign is not null"
    )
    campaign_keys = {r["campaign"] for r in campaign_rows} | set(APPROVED_CAMPAIGNS)
    kampanyok = [
        {"kulcs": k, "jovahagyott": k in APPROVED_CAMPAIGNS}
        for k in sorted(campaign_keys)
    ]

    engine_ek = [
        {"kulcs": e.key, "cimke": e.label, "aktiv": e.enabled}
        for e in sorted(engines.ALL_ENGINES.values(), key=lambda e: e.key)
    ]

    valasz_osztalyok = [
        {"kulcs": k, "cimke": report._REPLY_LABEL.get(k, k)}
        for k in report._REPLY_ORDER
    ]

    cimke_sorok = db.query("select distinct label from company_labels order by label")

    kuszobok = {
        "revenue_medium_huf": config.REVENUE_MEDIUM_HUF,
        "revenue_high_huf": config.REVENUE_HIGH_HUF,
        "headcount_medium": config.HEADCOUNT_MEDIUM,
        "headcount_high": config.HEADCOUNT_HIGH,
        "webshop_revenue_min_huf": config.WEBSHOP_REVENUE_MIN_HUF,
        "tier_a_score": config.TIER_A_SCORE,
        "tier_b_score": config.TIER_B_SCORE,
        **report.sender_thresholds(),
    }

    return {
        "statuszok": statuszok,
        "kampanyok": kampanyok,
        "engine_ek": engine_ek,
        "suppression_okok": db.suppression_reasons(),
        "valasz_osztalyok": valasz_osztalyok,
        "cimkek": [r["label"] for r in cimke_sorok],
        "kuszobok": kuszobok,
    }
