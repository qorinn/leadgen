"""Az export visszafordithatatlan kapuinak tesztjei."""
from types import SimpleNamespace

from leadgen import export


def _row(campaign: str) -> dict:
    return {
        "email": "info@pelda.invalid",
        "company": "Pelda Kft.",
        "campaign": campaign,
        "lead_source_type": "profession",
        "lead_source_url": "https://profession.hu/allas/123",
        "contact_source_url": "https://pelda.invalid/kapcsolat",
        "source_url": "https://profession.hu/allas/123",
        "local_check": "pass",
        "verify_result": "valid",
        "signal_score": 50,
        "company_id": "company-1",
        "contact_id": "contact-1",
    }


def _setup(monkeypatch, *, inflight=None, candidates=None):
    inflight = list(inflight or [])
    candidates = list(candidates or [])

    def fake_query(sql, params=None):
        if sql == export.SQL_INFLIGHT:
            return inflight
        if sql == export.SQL_NEW:
            return candidates
        if "select email, verify_result" in sql:
            return [{"email": r["email"], "verify_result": "valid",
                     "local_check": "pass"} for r in candidates]
        raise AssertionError(f"varatlan SQL: {sql[:80]}")

    monkeypatch.setattr(export.db, "query", fake_query)
    monkeypatch.setattr(export, "_dnc_emails", lambda: set())
    monkeypatch.setattr(export.config, "EMAIL_VALIDATION", "off")
    monkeypatch.setattr(
        export.validate, "ensure_verified",
        lambda *a, **k: SimpleNamespace(lekerdezve=0, cache_talalat=0,
                                        helyi_bukas=0),
    )


def test_ures_kampany_nem_esik_vissza_alap_sablonra(monkeypatch):
    _setup(monkeypatch, candidates=[_row("")])
    rows, stats, queued = export.collect()
    assert rows == [] and queued == []
    assert stats.skipped_campaign == 1
    assert "(ures)" in stats.blocked_campaigns


def test_nem_jovahagyott_folyamatban_levo_kampany_sem_exportalodik(monkeypatch):
    _setup(monkeypatch, inflight=[_row("ops_pain")])
    rows, stats, _ = export.collect()
    assert rows == []
    assert stats.skipped_campaign == 1
