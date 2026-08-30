"use client";

import { AlertTriangle } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { api, ApiError } from "@/lib/api";

interface FinancialsFormProps {
  companyId: string;
  /** Iras utan ujratoltes -- nincs optimista frissites (WEBUI-TERV.md F5). */
  onKesz: () => void;
}

/** A penzugyi adat kezi bevitele, cegenkent (WEBUI-TERV.md F5, 2. pont).
 * A tomeges worklist le-/feltoltes a Beallitasok oldalon van -- ez csak az
 * egy-ceges urlap (`POST /api/companies/{id}/financials`). */
export function FinancialsForm({ companyId, onKesz }: FinancialsFormProps) {
  const [revenue, setRevenue] = useState("");
  const [headcount, setHeadcount] = useState("");
  const [ev, setEv] = useState("");
  const [nincsBeszamolo, setNincsBeszamolo] = useState(false);
  const [figyelmeztetes, setFigyelmeztetes] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [mentes, setMentes] = useState(false);

  async function ment() {
    setHiba(null);
    setFigyelmeztetes(null);
    setMentes(true);
    try {
      const eredmeny = await api.companyFinancials(companyId, {
        revenue: nincsBeszamolo || revenue === "" ? null : Number(revenue),
        headcount: nincsBeszamolo || headcount === "" ? null : Number(headcount),
        financial_year: nincsBeszamolo || ev === "" ? null : Number(ev),
        missing: nincsBeszamolo,
      });
      if (eredmeny.figyelmeztetes) setFigyelmeztetes(eredmeny.figyelmeztetes);
      setRevenue("");
      setHeadcount("");
      setEv("");
      setNincsBeszamolo(false);
      onKesz();
    } catch (err) {
      setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
    } finally {
      setMentes(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-md border p-3">
      <p className="text-sm font-medium">Pénzügyi adat kézi bevitele</p>

      <div className="flex items-center gap-2">
        <Switch
          id="nincs-beszamolo"
          checked={nincsBeszamolo}
          onCheckedChange={(v) => setNincsBeszamolo(!!v)}
        />
        <Label htmlFor="nincs-beszamolo">Nincs közzétett beszámoló</Label>
      </div>

      {!nincsBeszamolo && (
        <div className="flex flex-wrap gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="revenue">Árbevétel (Ft)</Label>
            <Input
              id="revenue"
              type="number"
              placeholder="pl. 85000000"
              value={revenue}
              onChange={(e) => setRevenue(e.target.value)}
              className="w-40"
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="headcount">Létszám</Label>
            <Input
              id="headcount"
              type="number"
              value={headcount}
              onChange={(e) => setHeadcount(e.target.value)}
              className="w-28"
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="ev">Pénzügyi év</Label>
            <Input
              id="ev"
              type="number"
              placeholder="pl. 2025"
              value={ev}
              onChange={(e) => setEv(e.target.value)}
              className="w-28"
            />
          </div>
        </div>
      )}

      <Button
        size="sm"
        className="w-fit"
        disabled={mentes || (!nincsBeszamolo && revenue === "" && headcount === "")}
        onClick={ment}
      >
        {mentes ? "Mentés…" : "Mentés"}
      </Button>

      {figyelmeztetes && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <AlertTriangle className="size-4 shrink-0" />
          {figyelmeztetes}
        </p>
      )}
      {hiba && <p className="text-sm text-destructive">{hiba}</p>}
    </div>
  );
}
