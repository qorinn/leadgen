// A reszletnezet a `select *`-gal jott, tipus nelkuli mezoket (dict[str, Any]
// -- lasd webui/api/schemas.py docstring) jeleniti meg. Ezek a segedfuggvenyek
// koverte ki az `unknown` erteket a megjelenitheto alakra -- ha egy mezo
// hianyzik vagy mas tipusu, `null`-t adnak, nem dobnak hibat.

export function asStr(v: unknown): string | null {
  return typeof v === "string" && v !== "" ? v : null;
}

export function asNum(v: unknown): number | null {
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  // A Postgres `numeric` oszlopok (pl. financial_bonus, revenue,
  // opportunity_angles.score) a `select *`-os, tipus nelkuli valaszokban
  // STRINGKENT jonnek (FastAPI Decimal -> str, a pontossag megorzesehez) --
  // egy tipusos mezonel (pl. CompanyListItem.signal_score) ez mar nem
  // problema, mert a Pydantic ott float-ta alakitja.
  if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) {
    return Number(v);
  }
  return null;
}

export function asBool(v: unknown): boolean | null {
  return typeof v === "boolean" ? v : null;
}

export function formatDatum(v: unknown): string | null {
  const s = asStr(v);
  if (!s) return null;
  return new Date(s).toLocaleString("hu-HU", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatForint(v: unknown): string | null {
  const n = asNum(v);
  if (n === null) return null;
  return `${n.toLocaleString("hu-HU")} Ft`;
}

export function formatSzam(v: unknown, tizedes = 0): string | null {
  const n = asNum(v);
  if (n === null) return null;
  return n.toLocaleString("hu-HU", {
    minimumFractionDigits: tizedes,
    maximumFractionDigits: tizedes,
  });
}
