#!/usr/bin/env python3
"""Nyers scraper-talalatok vesztesegmentes tarolasa."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from . import db


def stable_source_url(item: dict[str, Any], prefix: str,
                      id_fields: Iterable[str] = ()) -> str:
    """Valodi URL, szolgaltatoi ID vagy stabil hash egy forraselemhez.

    A hash csak deduplikacios azonosito. A teljes eredeti rekord ettol
    fuggetlenul a `raw_signal` mezoben marad.
    """
    url = str(item.get("url") or "").strip()
    if url:
        return url
    for field in id_fields:
        value = str(item.get(field) or "").strip()
        if value:
            return f"{prefix}:{value}"
    canonical = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{prefix}:sha256:{digest}"


def save_source(cur, source_type: str, source_url: str,
                raw_signal: dict[str, Any], company_id=None,
                processing_status: str = "discovered",
                processing_note: str | None = None) -> tuple[Any, bool]:
    """Elmenti a nyers rekordot meg cegazonositas elott is.

    Ujrafutasnal frissiti a nyers payloadot, de egy mar letrejott cegkapcsolatot
    soha nem nullaz le.
    """
    cur.execute(
        """
        insert into sources (company_id, source_type, source_url, raw_signal,
                             processing_status, processing_note)
             values (%s, %s, %s, %s, %s, %s)
        on conflict (source_type, source_url) do update
                set raw_signal = excluded.raw_signal,
                    detected_at = now(),
                    company_id = coalesce(sources.company_id, excluded.company_id),
                    processing_status = case
                      when coalesce(sources.company_id, excluded.company_id) is not null
                      then 'linked' else excluded.processing_status end,
                    processing_note = excluded.processing_note
          returning id, (xmax = 0) as inserted
        """,
        (company_id, source_type, source_url, db.Json(raw_signal),
         processing_status, processing_note),
    )
    row = cur.fetchone()
    return row["id"], bool(row["inserted"])


def link_source(cur, source_id, company_id) -> None:
    cur.execute(
        """
        update sources
           set company_id = %s, processing_status = 'linked', processing_note = null
         where id = %s
        """,
        (company_id, source_id),
    )
