"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Grid } from "@/components/charts/grid";
import { Line } from "@/components/charts/line";
import { LineChart } from "@/components/charts/line-chart";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";
import { UresAllapot } from "@/components/ures-allapot";
import { api, ApiError, type Costs, type DailyCosts } from "@/lib/api";
import { formatDatum } from "@/lib/format";
import { Szekcio } from "./szekcio";

// A merteknyi USD-osszegek gyakran $0,0007 nagysagrenduek (lasd
// leadgen/pricing.py) -- a KoltsegJelveny 2 tizedesjegye itt mindent
// $0,00-ra kerekitene, ezert sajat, pontosabb formazas kell.
function formatUsd(usd: number): string {
  return `$${usd.toLocaleString("hu-HU", { minimumFractionDigits: 4, maximumFractionDigits: 6 })}`;
}

export function Koltsegek() {
  const [koltseg, setKoltseg] = useState<Costs | null>(null);
  const [napi, setNapi] = useState<DailyCosts | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    Promise.all([api.costs(), api.costsDaily()])
      .then(([k, n]) => {
        setKoltseg(k);
        setNapi(n);
      })
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  useEffect(betolt, [betolt]);

  if (hiba) return <HibaAllapot uzenet={hiba} ujra={betolt} />;
  if (!koltseg || !napi) return <Betoltes sorok={6} />;

  if (!koltseg.has_data) {
    return (
      <UresAllapot
        cim="Még nem futott egyetlen mért LLM-hívás sem"
        lepes="Indítsd: ./leadgen.sh llm-check"
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Szekcio cim="Napi költség" ures={napi.days.length < 2}>
        <div className="max-w-3xl">
          <LineChart data={napi.days} xDataKey="date">
            <Grid />
            <Line dataKey="usd" />
          </LineChart>
        </div>
      </Szekcio>

      <Szekcio cim={`Összesen: ${formatUsd(koltseg.total_usd)}`}>
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Modell</TableHead>
                <TableHead>Hívás</TableHead>
                <TableHead>Be (token)</TableHead>
                <TableHead>Ki (token)</TableHead>
                <TableHead>$</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Object.entries(koltseg.by_model)
                .sort()
                .map(([model, t]) => (
                  <TableRow key={model}>
                    <TableCell>{model}</TableCell>
                    <TableCell>{t.hivasok}</TableCell>
                    <TableCell>{t.be.toLocaleString("hu-HU")}</TableCell>
                    <TableCell>{t.ki.toLocaleString("hu-HU")}</TableCell>
                    <TableCell>{formatUsd(t.usd)}</TableCell>
                  </TableRow>
                ))}
            </TableBody>
          </Table>
        </div>
        <p className="text-xs text-muted-foreground">
          Első mérés: {formatDatum(koltseg.first_ts) ?? "—"} · utolsó: {formatDatum(koltseg.last_ts) ?? "—"}
        </p>
      </Szekcio>
    </div>
  );
}
