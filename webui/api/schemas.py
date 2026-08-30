"""Pydantic valasz-modellek -- EZEKBOL LESZ A FRONTEND TIPUSA.

MIERT KELL MINDEN ENDPOINTRA MODELL (es miert nem eleg a `-> dict`):

A terv szabalya: "A frontend soha nem definial kezzel API-tipust" -- a
`npm run types` az OpenAPI semabol general (`lib/api-types.ts`). Csakhogy egy
`-> dict` visszateresu FastAPI endpoint OpenAPI semaja URES objektum, tehat a
generalt tipus `{[key: string]: unknown}` lesz: hasznalhatatlan. A frontend
ilyenkor kenytelen lenne sajat kezi tipust irni -- pont azt, amit a szabaly
tilt. A tipus tehat NEM kenyelmi extra: enelkul a szabaly betarthatatlan.

AHOL SZANDEKOSAN `dict[str, Any]` MARAD: a `select *`-gal olvasott sorok
(`companies`, `contacts`, `sources`, ...). Azok oszlopait a migraciok
bovitik, es egy itt kezzel karbantartott masolat csendben elmaradna toluk --
a `013_rejects.sql` harom uj oszlopa pont igy tunt volna el. Ezeknel a
BURKOLO alakja (mely kulcs milyen listat tartalmaz) tipusos, a soron beluli
mezok nem. Ahol viszont az oszloplistat MI irjuk le a lekerdezesben
(cegek listaja, valaszok, futasok), ott teljes a modell.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel

# A psycopg UUID-oszlopot `uuid.UUID` peldanykent ad vissza, nem stringkent.
# Ha a modell `str`-t varna, a valasz-validacio 500-zal elszallna -- ezert
# `uuid.UUID` a tipus, amit a Pydantic stringge sorosit a JSON-ban.
Uuid = uuid.UUID

# ─── /api/health ───────────────────────────────────────────────────────────


class DbAllapot(BaseModel):
    ok: bool
    tablak: int


class SenderDirAllapot(BaseModel):
    ok: bool
    ut: str


class MigraciokAllapot(BaseModel):
    alkalmazott: int
    utolso: str | None


class HealthResponse(BaseModel):
    db: DbAllapot
    sender_dir: SenderDirAllapot
    migraciok: MigraciokAllapot
    verzio: str


# ─── /api/meta ─────────────────────────────────────────────────────────────


class StatuszMeta(BaseModel):
    kulcs: str
    cimke: str
    sorrend: int


class KampanyMeta(BaseModel):
    kulcs: str
    jovahagyott: bool


class EngineMeta(BaseModel):
    kulcs: str
    cimke: str
    aktiv: bool


class ValaszOsztalyMeta(BaseModel):
    kulcs: str
    cimke: str


class MetaResponse(BaseModel):
    statuszok: list[StatuszMeta]
    kampanyok: list[KampanyMeta]
    engine_ek: list[EngineMeta]
    suppression_okok: list[str]
    valasz_osztalyok: list[ValaszOsztalyMeta]
    cimkek: list[str]
    kuszobok: dict[str, float]


# ─── /api/report/daily ─────────────────────────────────────────────────────


class RiasztasSor(BaseModel):
    kulcs: str
    tipus: str
    uzenet: str
    first_seen: dt.datetime | None = None
    last_seen: dt.datetime | None = None
    last_notified: dt.datetime | None = None
    resolved_at: dt.datetime | None = None


class RiasztasBlokk(BaseModel):
    ok: bool
    aktiv: list[RiasztasSor]
    error: str | None


class SenderAllapot(BaseModel):
    """A kuldo sajat szamai. `ok=False` -> nem tudtuk megkerdezni, es akkor a
    tobbi mezo nulla -- NEM talalt szam, hanem "nem tudjuk" (report.py)."""
    ok: bool
    cap: int
    sent_today: int
    remaining: int
    leads_rows: int
    bounces_today: int
    rejects_today: int
    error: str | None


class DailyResponse(BaseModel):
    riasztasok: RiasztasBlokk
    sender: SenderAllapot
    queued: int
    ready: int
    replied: int
    review: int
    # None, ha a kuldo allapota nem olvashato -- nem 0. A ketto nem ugyanaz:
    # a 0 azt jelentene, hogy nincs sor, a None azt, hogy nem tudjuk.
    days_of_backlog: float | None


# ─── /api/report/funnel ────────────────────────────────────────────────────


class EmailValidacio(BaseModel):
    mode: str
    summary: str


class KovetkezoLepes(BaseModel):
    status: str
    count: int
    action: str


class FunnelResponse(BaseModel):
    companies_total: int
    by_status: dict[str, int]
    unknown_status: dict[str, int]
    contacts: dict[str, int]
    email_validation: EmailValidacio | None
    suppression: dict[str, int]
    labels: dict[str, int]
    unlinked_sources: int
    outreach: dict[str, int]
    next_steps: list[KovetkezoLepes]


# ─── /api/companies ────────────────────────────────────────────────────────


class CompanyListItem(BaseModel):
    """A lista-nezet oszlopai. Ezt a lekerdezes NEV SZERINT valasztja ki
    (nem `select *`), ezert itt teljes a modell."""
    id: Uuid
    company_name: str | None
    normalized_domain: str | None
    status: str
    campaign: str | None
    economic_value: str | None
    signal_score: float | None
    city: str | None
    industry: str | None
    best_offer: str | None
    updated_at: dt.datetime | None
    # A cegnek tobb kontaktusa is lehet -- ez a "legjobb" (report.py
    # _CONTACT_TYPE_ORDER szerinti) email, a reszletnezetben mind lathato.
    email: str | None


class CompanyListResponse(BaseModel):
    items: list[CompanyListItem]
    page: int
    per_page: int
    total: int
    total_pages: int


class CompanyDetailResponse(BaseModel):
    """A reszletes nezet. A sorok `select *`-gal jonnek (lasd a modul
    docstringjet), ezert a BURKOLO tipusos, a sorok mezoi nem."""
    company: dict[str, Any]
    sources: list[dict[str, Any]]
    contacts: list[dict[str, Any]]
    opportunity_angles: list[dict[str, Any]]
    company_labels: list[dict[str, Any]]
    outreach: list[dict[str, Any]]
    suppression: list[dict[str, Any]]


# ─── /api/replies ──────────────────────────────────────────────────────────


class ReplyItem(BaseModel):
    id: Uuid
    email: str
    received_at: dt.datetime | None
    subject: str | None
    classification: str | None
    confidence: float | None
    rationale: str | None
    error: str | None
    classified_at: dt.datetime | None
    company_name: str | None
    normalized_domain: str | None


class RepliesResponse(BaseModel):
    items: list[ReplyItem]
    total: int


# ─── /api/alerts ───────────────────────────────────────────────────────────


class AlertsResponse(BaseModel):
    aktiv: list[RiasztasSor]
    lezart: list[RiasztasSor]


# ─── /api/costs ────────────────────────────────────────────────────────────


class ModellKoltseg(BaseModel):
    hivasok: int
    be: int
    ki: int
    usd: float


class CostsResponse(BaseModel):
    has_data: bool
    by_model: dict[str, ModellKoltseg]
    total_usd: float
    first_ts: str | None
    last_ts: str | None


# ─── /api/runs ─────────────────────────────────────────────────────────────


class SourceRunItem(BaseModel):
    engine_key: str
    actor: str
    term: str | None
    location: str | None
    results: int | None
    new_companies: int | None
    run_at: dt.datetime | None


class RunsResponse(BaseModel):
    items: list[SourceRunItem]
    total: int


# ─── /api/schedule/status ──────────────────────────────────────────────────


class ScheduleStatusResponse(BaseModel):
    installed: bool
    loaded: bool
    launchctl_lines: list[str]
    start_time: str
    log_path: str
    log_last_written: str | None
    log_last_lines: list[str]


# ─── /api/logs/{nev} ───────────────────────────────────────────────────────


class LogResponse(BaseModel):
    name: str
    path: str
    exists: bool
    lines: list[str]
