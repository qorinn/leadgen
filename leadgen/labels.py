#!/usr/bin/env python3
"""Ujraszamolhato cegcimkek kozos irasi muveletei."""
from __future__ import annotations

from typing import Any

from . import db


def set_label(cur, company_id, label: str, details: dict[str, Any] | None = None,
              source_id=None) -> None:
    """Atomikusan letrehozza vagy frissiti egy ceg aktualis cimkejet."""
    cur.execute(
        """
        insert into company_labels (company_id, label, details, source_id)
             values (%s, %s, %s, %s)
        on conflict (company_id, label) do update
                set details = excluded.details,
                    source_id = coalesce(excluded.source_id, company_labels.source_id)
        """,
        (company_id, label, db.Json(details or {}), source_id),
    )


def clear_label(cur, company_id, label: str) -> None:
    """Eltavolit egy mar nem igaz, ujraszamolhato cimket."""
    cur.execute(
        "delete from company_labels where company_id = %s and label = %s",
        (company_id, label),
    )
