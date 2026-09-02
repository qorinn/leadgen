/**
 * A fetch-reteg. MINDEN API-hivas ezen megy at.
 *
 * MIERT: a tipusok a `lib/api-types.ts`-bol jonnek, amit az `npm run types`
 * general a FastAPI OpenAPI semajabol. A frontend SOHA nem definial kezzel
 * API-tipust (WEBUI-TERV.md) -- ha egy mezo neve megvaltozik a Pythonban,
 * a `npm run types` utan itt TypeScript-hiba lesz, nem csendes `undefined`
 * a kepernyon.
 *
 * Az uzleti szabalyokat (melyik statusz letezik, melyik kampany
 * jovahagyott, mik a suppression-okok) a `getMeta()` adja -- ezeket TILOS
 * ide vagy barmelyik komponensbe bedrotozni.
 */
import type { components, operations } from "./api-types";

// Csak localhost (WEBUI-TERV.md Invariansok #5). A DB valodi ceg- es
// szemelyes adatot tarol, nincs kitett port.
const API_BASE = "http://127.0.0.1:8000";

export type Schemas = components["schemas"];

export type Health = Schemas["HealthResponse"];
export type Meta = Schemas["MetaResponse"];
export type Daily = Schemas["DailyResponse"];
export type Funnel = Schemas["FunnelResponse"];
export type CompanyList = Schemas["CompanyListResponse"];
export type CompanyListItem = Schemas["CompanyListItem"];
export type CompanyDetail = Schemas["CompanyDetailResponse"];
export type Replies = Schemas["RepliesResponse"];
export type Alerts = Schemas["AlertsResponse"];
export type Costs = Schemas["CostsResponse"];
export type DailyCosts = Schemas["DailyCostsResponse"];
export type Runs = Schemas["RunsResponse"];
export type Grounding = Schemas["GroundingResponse"];
export type Economic = Schemas["EconomicResponse"];
export type Campaign = Schemas["CampaignResponse"];
export type SenderCsv = Schemas["SenderCsvResponse"];
export type ScheduleStatus = Schemas["ScheduleStatusResponse"];
export type ScheduleAction = Schemas["ScheduleActionResponse"];
export type LogTail = Schemas["LogResponse"];
export type Settings = Schemas["SettingsResponse"];
export type Diagnostics = Schemas["DiagnosticsResponse"];
export type ReviewAction = Schemas["ReviewActionResponse"];
export type SuppressedList = Schemas["SuppressedListResponse"];
export type FinancialsImportResult = Schemas["FinancialsImportResponse"];
export type CompanyFinancialsBody = Schemas["CompanyFinancialsBody"];
export type FinancialsSaveResult = Schemas["FinancialsSaveResponse"];
export type JobCatalog = Schemas["JobCatalogResponse"];
export type JobCatalogItem = Schemas["JobCatalogItem"];
export type JobItem = Schemas["JobItem"];
export type JobResult = Schemas["JobResponse"];
export type JobCurrent = Schemas["JobCurrentResponse"];
export type JobHistory = Schemas["JobHistoryResponse"];
/** Az SSE-esemenyek is EZT az alakot kuldik (webui/api/routers/jobs.py
 *  `_json_job`) -- ezert nincs kulon, kezzel irt tipus a streamre. */
export type JobOutput = Schemas["JobOutputResponse"];
export type SendPreview = Schemas["SendPreviewResponse"];
export type SendLevel = Schemas["SendLevel"];
export type SendKontakt = Schemas["SendKontakt"];
export type SendSample = Schemas["SendSampleResponse"];

/** A szerver hibauzenete (FastAPI `detail`) megorizve -- azt mutatjuk, amit
 *  a Python mondott, nem egy altalanos "hiba tortent" szoveget. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function hibaUzenet(res: Response): Promise<string> {
  let detail = `HTTP ${res.status}`;
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") detail = body.detail;
  } catch {
    // A hibatest nem mindig JSON -- ilyenkor marad a statuszkod.
  }
  return detail;
}

async function kapcsolat<T>(kereses: () => Promise<Response>): Promise<T> {
  let res: Response;
  try {
    res = await kereses();
  } catch {
    throw new ApiError(0, "Nem érhető el az API. Fut a `./leadgen.sh ui`?");
  }
  if (!res.ok) throw new ApiError(res.status, await hibaUzenet(res));
  return (await res.json()) as T;
}

function urlEpit(path: string, params?: Record<string, unknown>): URL {
  const url = new URL(API_BASE + path);
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }
  return url;
}

function get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  return kapcsolat<T>(() => fetch(urlEpit(path, params).toString()));
}

/** Iras minden esetben POST -- WEBUI-TERV.md F5 irasi mintaja. */
function post<T>(path: string, body?: unknown): Promise<T> {
  return kapcsolat<T>(() =>
    fetch(API_BASE + path, {
      method: "POST",
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  );
}

function postForm<T>(path: string, form: FormData): Promise<T> {
  return kapcsolat<T>(() => fetch(API_BASE + path, { method: "POST", body: form }));
}

type CompanyQuery = NonNullable<
  operations["list_companies_api_companies_get"]["parameters"]["query"]
>;

export const api = {
  health: () => get<Health>("/api/health"),
  meta: () => get<Meta>("/api/meta"),
  reportDaily: () => get<Daily>("/api/report/daily"),
  reportFunnel: () => get<Funnel>("/api/report/funnel"),
  reportGrounding: () => get<Grounding>("/api/report/grounding"),
  reportEconomic: () => get<Economic>("/api/report/economic"),
  reportCampaign: (name: string) => get<Campaign>("/api/report/campaign", { name }),
  senderCsv: (nev: string) => get<SenderCsv>(`/api/report/sender-csv/${nev}`),
  companies: (q?: CompanyQuery) => get<CompanyList>("/api/companies", q),
  company: (id: string) => get<CompanyDetail>(`/api/companies/${id}`),
  replies: (classification?: string) =>
    get<Replies>("/api/replies", { classification }),
  alerts: () => get<Alerts>("/api/alerts"),
  costs: () => get<Costs>("/api/costs"),
  costsDaily: () => get<DailyCosts>("/api/costs/daily"),
  runs: (limit?: number) => get<Runs>("/api/runs", { limit }),
  scheduleStatus: () => get<ScheduleStatus>("/api/schedule/status"),
  scheduleInstall: () => post<ScheduleAction>("/api/schedule/install"),
  scheduleUninstall: () => post<ScheduleAction>("/api/schedule/uninstall"),
  log: (nev: "sender" | "alerts" | "daily", lines?: number) =>
    get<LogTail>(`/api/logs/${nev}`, { lines }),

  // ── F10: uzemeltetes ───────────────────────────────────────────────────
  settings: () => get<Settings>("/api/settings"),
  diagnostics: () => get<Diagnostics>("/api/diagnostics"),

  // ── F5: emberi dontesek ────────────────────────────────────────────────
  reviewApprove: (companyId: string) =>
    post<ReviewAction>(`/api/review/${companyId}/approve`),
  reviewReject: (companyId: string, reason: string) =>
    post<ReviewAction>(`/api/review/${companyId}/reject`, { reason }),
  reviewSuppressed: () => get<SuppressedList>("/api/review/suppressed"),

  financialsWorklistUrl: (limit = 20) =>
    urlEpit("/api/financials/worklist", { limit }).toString(),
  financialsImport: (file: File, dry: boolean) => {
    const form = new FormData();
    form.set("file", file);
    form.set("dry", String(dry));
    return postForm<FinancialsImportResult>("/api/financials/import", form);
  },
  companyFinancials: (companyId: string, body: CompanyFinancialsBody) =>
    post<FinancialsSaveResult>(`/api/companies/${companyId}/financials`, body),

  // ── F6: futtatas ───────────────────────────────────────────────────────
  // A parancsok listajat, a kereteiket es a koltsegbecsles nyersanyagat
  // MIND a szerver adja (/api/jobs/catalog) -- itt nincs bedrotozott
  // parancsnev (WEBUI-TERV.md Invariansok #1).
  jobCatalog: () => get<JobCatalog>("/api/jobs/catalog"),
  jobCurrent: () => get<JobCurrent>("/api/jobs/current"),
  jobHistory: (limit?: number) => get<JobHistory>("/api/jobs/history", { limit }),
  jobStart: (kulcs: string, params: Record<string, number>) =>
    post<JobResult>("/api/jobs/start", { kulcs, params }),
  jobCancel: (jobId: string) => post<JobResult>(`/api/jobs/${jobId}/cancel`),
  jobOutput: (jobId: string, cursor: number) =>
    get<JobOutput>(`/api/jobs/${jobId}`, { cursor }),
  /** Az elo naplo SSE-cime. `EventSource`-nak adjuk at, nem fetchnek. */
  jobStreamUrl: (jobId: string, cursor: number) =>
    urlEpit(`/api/jobs/${jobId}/stream`, { cursor }).toString(),

  // ── F7: kuldes (ketlepcsos) ────────────────────────────────────────────
  // A `token` a szervertol jon es ATLATSZATLAN: a frontend csak
  // tovabbadja. A tenyleges kaput a szerver kenyszeriti ki -- ez a ket
  // fuggveny nem "ket lepes a fronton", hanem ket API-hivas, amibol a
  // masodikat a szerver utasitja el, ha a terv kozben megvaltozott
  // (WEBUI-TERV.md Invariansok #2).
  sendPreview: () => post<SendPreview>("/api/send/preview"),
  sendLive: (token: string) => post<JobResult>("/api/send/live", { token }),
  // A cimzett-csere utan a szerver EXPORTOT indit (a kuldo a leads.csv-bol
  // dolgozik, nem a DB-bol), es a valasz az a job, amit meg kell varni.
  sendKontakt: (regi_email: string, uj_email: string) =>
    post<JobResult>("/api/send/kontakt", { regi_email, uj_email }),
  sendSample: (cim: string, limit: number, fok: string) =>
    post<SendSample>("/api/send/sample", { cim, limit, fok }),
};
