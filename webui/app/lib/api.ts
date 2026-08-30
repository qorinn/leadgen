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
export type Runs = Schemas["RunsResponse"];
export type ScheduleStatus = Schemas["ScheduleStatusResponse"];
export type LogTail = Schemas["LogResponse"];

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

async function get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const url = new URL(API_BASE + path);
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }

  let res: Response;
  try {
    res = await fetch(url.toString());
  } catch {
    throw new ApiError(0, "Nem érhető el az API. Fut a `./leadgen.sh ui`?");
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // A hibatest nem mindig JSON -- ilyenkor marad a statuszkod.
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

type CompanyQuery = NonNullable<
  operations["list_companies_api_companies_get"]["parameters"]["query"]
>;

export const api = {
  health: () => get<Health>("/api/health"),
  meta: () => get<Meta>("/api/meta"),
  reportDaily: () => get<Daily>("/api/report/daily"),
  reportFunnel: () => get<Funnel>("/api/report/funnel"),
  companies: (q?: CompanyQuery) => get<CompanyList>("/api/companies", q),
  company: (id: string) => get<CompanyDetail>(`/api/companies/${id}`),
  replies: (classification?: string) =>
    get<Replies>("/api/replies", { classification }),
  alerts: () => get<Alerts>("/api/alerts"),
  costs: () => get<Costs>("/api/costs"),
  runs: (limit?: number) => get<Runs>("/api/runs", { limit }),
  scheduleStatus: () => get<ScheduleStatus>("/api/schedule/status"),
  log: (nev: "sender" | "alerts" | "daily", lines?: number) =>
    get<LogTail>(`/api/logs/${nev}`, { lines }),
};
