"""Az adatmegorzesi invariansok regresszios tesztjei."""
from pathlib import Path

from leadgen import storage


REPO = Path(__file__).resolve().parent.parent
MIGRATION = REPO / "leadgen" / "migrations" / "010_retention_and_angles.sql"


def test_url_nelkuli_forraselemnek_stabil_azonositoja_van():
    item = {"companyName": "Pelda Kft.", "title": "Diszpecser"}
    first = storage.stable_source_url(item, "profession", ("jobId",))
    second = storage.stable_source_url(dict(reversed(list(item.items()))),
                                       "profession", ("jobId",))
    assert first == second
    assert first.startswith("profession:sha256:")


def test_szolgaltatoi_id_elsobbseget_kap_a_hashnel():
    assert storage.stable_source_url(
        {"placeId": "abc-123"}, "maps", ("placeId",)) == "maps:abc-123"


def test_a_migracio_megengedi_a_paratlan_nyers_forrast():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "sources alter column company_id drop not null" in sql
    assert "on delete set null" in sql
    assert "processing_status" in sql


def test_a_migracio_nem_torol_ceget_vagy_forrast():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "delete from companies" not in sql
    assert "delete from sources" not in sql


def test_az_uj_public_tablakon_rls_van():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "alter table company_labels enable row level security" in sql
    assert "alter table opportunity_angles enable row level security" in sql
