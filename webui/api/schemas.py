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
    # Var-e emberi dontes ezen a statuszon (leadgen/review.py
    # DONTESRE_VARO_STATUSZOK). A felulet ebbol tudja, hol adjon
    # jovahagyas/elutasitas gombot -- sajat statuszlista nelkul.
    dontesre_var: bool


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
    surgos: bool
    attekintendo: bool


class MetaResponse(BaseModel):
    statuszok: list[StatuszMeta]
    kampanyok: list[KampanyMeta]
    engine_ek: list[EngineMeta]
    suppression_okok: list[str]
    valasz_osztalyok: list[ValaszOsztalyMeta]
    cimkek: list[str]
    kuszobok: dict[str, float]
    kuldo_csv_nevek: list[str]


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


# ─── /api/report/grounding ─────────────────────────────────────────────────


class GroundingCompany(BaseModel):
    """Egy minositett ceg. A `kept`/`dropped` szandekosan dict[str, Any]:
    vagy az `opportunity_angles` sorai, vagy a regi `evidence` JSONB tartalma
    -- a ket alak mezoi nem egyeznek (report.grounding_adat legacy agа)."""
    id: Uuid
    company_name: str | None
    normalized_domain: str | None
    status: str
    best_offer: str | None
    scores: dict[str, float]
    personalization: str | None
    legacy: bool
    kept: list[dict[str, Any]]
    dropped: list[dict[str, Any]]


class GroundingResponse(BaseModel):
    total: int
    ready: int
    dropped_directions: int
    companies: list[GroundingCompany]


# ─── /api/report/economic ──────────────────────────────────────────────────


class EconomicRow(BaseModel):
    id: Uuid
    company_name: str | None
    normalized_domain: str | None
    revenue: float | None
    headcount: int | None
    financial_year: int | None
    economic_value: str | None
    webshop_platform: str | None
    signal_score: float | None


class EconomicResponse(BaseModel):
    total: int
    by_value: dict[str, int]
    checked: int
    with_revenue: int
    thresholds: dict[str, float]
    rows: list[EconomicRow]
    missing_labels: dict[str, int]


# ─── /api/report/campaign ──────────────────────────────────────────────────


class CampaignRow(BaseModel):
    id: Uuid
    company_name: str | None
    normalized_domain: str | None
    status: str
    economic_value: str | None
    revenue: float | None
    webshop_platform: str | None
    signal_score: float | None
    personalization: str | None


class CampaignResponse(BaseModel):
    name: str
    approved: bool
    total: int
    by_status: dict[str, int]
    rows: list[CampaignRow]


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
    # A kizaro/allapot indoklasa. A `review` statuszu cegeknel ez a dontesi
    # alap -- a lista enelkul nem hasznalhato atnezesre.
    status_note: str | None
    # A ceg weboldala, EREDETI URL-kent (a normalizalt domain csak fallback).
    website: str | None


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
    body: str | None
    classification: str | None
    confidence: float | None
    model: str | None
    rationale: str | None
    error: str | None
    classified_at: dt.datetime | None
    company_id: Uuid | None
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


# ─── /api/costs/daily ───────────────────────────────────────────────────────


class NapiKoltseg(BaseModel):
    date: str
    usd: float


class DailyCostsResponse(BaseModel):
    has_data: bool
    days: list[NapiKoltseg]


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


class ScheduleActionResponse(BaseModel):
    """A telepites/eltavolitas eredmenye (F10). A `hiba` csak telepitesnel
    toltodik ki; a `volt_telepitve` csak eltavolitasnal (a ket muvelet
    Python-oldali eredmenye mas alaku, lasd leadgen/schedule.py)."""
    ok: bool
    hiba: str | None = None
    volt_telepitve: bool | None = None


# ─── /api/logs/{nev} ───────────────────────────────────────────────────────


class LogResponse(BaseModel):
    name: str
    path: str
    exists: bool
    lines: list[str]


# ─── /api/report/sender-csv/{nev} ──────────────────────────────────────────


class SenderCsvResponse(BaseModel):
    """A kuldo egy nyers CSV-jenek sorai (F9, 'Nyers naplok'). Az `columns`
    a fajl fejlecebol jon -- nem drotozzuk be a kuldo store.py HEADER
    listait, mert az egy masik interpreteren fut (CLAUDE.md invariansok)."""
    name: str
    exists: bool
    columns: list[str]
    total: int
    rows: list[dict[str, str]]


# ─── /api/review/* (F5) ─────────────────────────────────────────────────────


class ReviewActionResponse(BaseModel):
    """A jovahagyas/elutasitas eredmenye -- ugyanaz az uj allapot, amit a
    CLI is kiirna (leadgen/review.py, egy forras a ket hivonak)."""
    uj_status: str


class RejectBody(BaseModel):
    """A `reason` a /api/meta `suppression_okok` listajabol valaszthato a
    fronton -- ez a mezo itt csak nyers string, az ervenyesseget a DB CHECK
    constraint es a leadgen/review.py donti el, nem a webui."""
    reason: str = "manual_block"


class SuppressedCompanyItem(BaseModel):
    id: Uuid
    normalized_domain: str | None
    company_name: str | None
    status_note: str | None
    title: str | None


class SuppressedListResponse(BaseModel):
    items: list[SuppressedCompanyItem]


# ─── /api/financials/*, /api/companies/{id}/financials (F5) ────────────────


class FinancialsImportResponse(BaseModel):
    olvasott: int
    frissitett: int
    ures: int
    hibas: int
    ismeretlen: int
    ezer_forint_gyanu: list[str]
    ertekek: dict[str, int]
    dry: bool


class CompanyFinancialsBody(BaseModel):
    revenue: float | None = None
    headcount: int | None = None
    financial_year: int | None = None
    # "nincs kozzetett beszamolo" kapcsolo -- ilyenkor a revenue/headcount
    # figyelmen kivul marad (leadgen.financials.jelold_hianyzonak).
    missing: bool = False


class FinancialsSaveResponse(BaseModel):
    economic_value: str | None
    # Nem None, ha a megadott arbevetel gyanusan kicsi (financials.py
    # GYANUSAN_KICSI_HUF alatt) -- a beszamolo urlapja "E Ft-ban" mutat, ez a
    # leggyakoribb elirasi hiba (WEBUI-TERV.md F5).
    figyelmeztetes: str | None


# ─── /api/jobs/* (F6) ──────────────────────────────────────────────────────


class JobParamMeta(BaseModel):
    """Egy allithato keret. Az `alap` a CLI sajat argparse-abol jon
    (webui/api/jobs.py `_alap_ertekek`), nem kezi masolatbol."""
    nev: str
    flag: str
    cimke: str
    alap: int
    minimum: int
    maximum: int


class JobKoltseg(BaseModel):
    """A becsult koltseg NYERSANYAGA, nem egy kesz szam.

    Az Apify-resz szorzas (egysegar x darab), tehat a felulet ki tudja
    szamolni, amint a felhasznalo allit a kereten. Az AI-resz elore NEM
    becsulheto (tokenenkent szamlazodik) -- ilyenkor `ai_tokenenkent=True`,
    es a felulet ezt irja ki, nem egy kitalalt osszeget (WEBUI-TERV.md F6).
    """
    fizetos: bool
    apify_egysegar_usd: float | None
    apify_fix_darab: int | None
    apify_darab_parametere: str | None
    ai_tokenenkent: bool
    magyarazat: str


class JobCatalogItem(BaseModel):
    kulcs: str
    cimke: str
    magyarazat: str
    # Amit a terminalban gepelnel ugyanerre -- a felulet es a CLI igy
    # ugyanazt a nevet hasznalja ugyanarra a futasra.
    parancs: str
    parameterek: list[JobParamMeta]
    koltseg: JobKoltseg
    # Igaz, ha ez a lepes a napi lancnak is resze (`schedule.lepesek()`) --
    # a felulet ez alapjan halvanyitja el azt, amit ugyis magatol lefuttat
    # az utemezes, es emeli ki, amit tenyleg neked kell kezzel elinditanod.
    naponta_fut: bool


class JobCatalogResponse(BaseModel):
    items: list[JobCatalogItem]


class JobItem(BaseModel):
    id: str
    kulcs: str
    cimke: str
    parancs: str
    fut: bool
    # Gepi kulcs (`running`/`ok`/`failed`/`cancelled`) es a hozza tartozo
    # magyar felirat. A frontend a `fut`-ot hasznalja logikara, a cimket
    # megjelenitesre -- igy nem kell allapotlistat TS-be masolni.
    allapot: str
    allapot_cimke: str
    started_at: dt.datetime
    finished_at: dt.datetime | None
    seconds: float | None
    exit_code: int | None


class JobStartBody(BaseModel):
    kulcs: str
    params: dict[str, int] = {}


class JobResponse(BaseModel):
    job: JobItem


class JobCurrentResponse(BaseModel):
    job: JobItem | None


class JobHistoryResponse(BaseModel):
    items: list[JobItem]


class JobOutputResponse(BaseModel):
    job: JobItem
    lines: list[str]
    # A kovetkezo kereshez visszaadando sor-index. Nem a lista hossza: a
    # regi sorok kieshetnek a memoriabol, es a kurzor akkor is helyes marad.
    cursor: int


# ─── /api/send/* (F7) ──────────────────────────────────────────────────────


class SendLevel(BaseModel):
    """Egy levele a mai tervnek, TELJES torzzsel -- nem az elso 400 karakter
    (WEBUI-TERV.md F7). A `fok` a `sender._stage_of` szerinti szekvencia-fok
    (cold / follow_up_1 / follow_up_2), leadenkent kulon."""
    cimzett: str
    ceg: str
    fok: str
    targy: str
    torzs: str


class SendKontakt(BaseModel):
    """Egy valaszthato cim egy ceghez. A `cserehetetlen` dontest NEM itt
    hozzuk meg: a `valaszthato` szotar csak azoknal a cimzetteknel kap
    bejegyzest, ahol a csere egyaltalan megengedett (lasd
    `leadgen.send.CSEREHETO_FOK`)."""
    email: str
    email_type: str
    source_kind: str
    verify_result: str
    preferred: bool


class SendKontaktBody(BaseModel):
    """Cimzett-csere egy cegnel, a kuldes elott."""
    regi_email: str
    uj_email: str


class SendPreviewResponse(BaseModel):
    # A terv tartalmi hash-ehez kotott, 10 percig ervenyes, EGYSZER
    # hasznalhato token. A frontend szamara atlatszatlan string.
    token: str
    lejar: dt.datetime
    levelek: list[SendLevel]
    mai_keret: int
    terv_meret: int
    # A KULDESI IDOABLAK. Nincs a terv F7 JSON-peldajaban, de nelkule a
    # felhasznalo csak az elo naploban szembesulne azzal, hogy a
    # `sender.py --live` az ablakon kivul exit 0-val, kuldes nelkul kilep
    # (felhasznaloi dontes, 2026-08-30 -- lasd WEBUI-TESZTELENDO.md).
    ablak_nyitva: bool
    ablak_ok: str
    # cimzett email -> a valaszthato cimek. CSAK ott van bejegyzes, ahol tobb
    # hasznalhato cim van ES a fok engedi a cseret (`cold`). A frontend ebbol
    # tudja, hol jelenjen meg a select -- nem sajat szabalybol.
    valaszthato: dict[str, list[SendKontakt]] = {}


class SendLiveBody(BaseModel):
    """A `/api/send/preview`-tol kapott token. Enelkul nincs eles kuldes."""
    token: str


class SendSampleBody(BaseModel):
    cim: str
    limit: int = 1
    fok: str = "cold"


class SendSampleResponse(BaseModel):
    """A `preview.py --send-to` kimenete. A valodi cimzettek nem kapnak
    semmit, es a `sent.csv` sem valtozik."""
    ok: bool
    sorok: list[str]
    error: str | None


# ─── /api/settings, /api/diagnostics (F10) ─────────────────────────────────


class SettingsItem(BaseModel):
    """Egy .env-ertek, maszkolva -- lasd `leadgen.config.settings_adat()`.
    A `titok` mezo NEM dontes itt: mar maszkolt `ertek`-et kap a router,
    csak a felulet tudja belole, hogy pl. jelszo-ikont mutasson-e."""
    csoport: str
    kulcs: str
    ertek: str
    titok: bool


class SettingsResponse(BaseModel):
    tetelek: list[SettingsItem]


class MigrationRow(BaseModel):
    filename: str
    applied_at: dt.datetime


class FeedbackWatermarkRow(BaseModel):
    file: str
    last_ts: str | None
    last_row: int
    updated_at: dt.datetime


class DiagnosticsResponse(BaseModel):
    migraciok: list[MigrationRow]
    feedback_watermark: list[FeedbackWatermarkRow]
