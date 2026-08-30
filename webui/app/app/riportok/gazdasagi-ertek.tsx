"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Bar } from "@/components/charts/bar";
import { BarChart } from "@/components/charts/bar-chart";
import { BarXAxis } from "@/components/charts/bar-x-axis";
import { Grid } from "@/components/charts/grid";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";
import { UresAllapot } from "@/components/ures-allapot";
import { api, ApiError, type Economic } from "@/lib/api";
import { formatForint, formatSzam } from "@/lib/format";
import { Szekcio } from "./szekcio";

const ERTEK_CIMKE: Record<string, string> = {
  HIGH: "HIGH", MEDIUM: "MEDIUM", LOW: "LOW", none: "nincs adat",
};
const ERTEK_SORREND = ["HIGH", "MEDIUM", "LOW", "none"];

export function GazdasagiErtek() {
  const [adat, setAdat] = useState<Economic | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .reportEconomic()
      .then(setAdat)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  useEffect(betolt, [betolt]);

  const chartAdat = useMemo(() => {
    if (!adat) return [];
    return ERTEK_SORREND.filter((k) => adat.by_value[k]).map((k) => ({
      cimke: ERTEK_CIMKE[k] ?? k,
      ertek: adat.by_value[k],
    }));
  }, [adat]);

  if (hiba) return <HibaAllapot uzenet={hiba} ujra={betolt} />;
  if (!adat) return <Betoltes sorok={6} />;

  return (
    <div className="flex flex-col gap-4">
      <Szekcio cim={`Gazdasági érték (${adat.total} cég)`}>
        {chartAdat.length > 0 && (
          <div className="max-w-md">
            <BarChart data={chartAdat} xDataKey="cimke">
              <Grid />
              <Bar dataKey="ertek" />
              <BarXAxis />
            </BarChart>
          </div>
        )}
        <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
          <span>
            megvizsgálva: <strong>{adat.checked}</strong>
          </span>
          <span>
            van árbevétel: <strong>{adat.with_revenue}</strong>
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          küszöbök (.env): MEDIUM ≥ {(adat.thresholds.revenue_medium_huf / 1e6).toFixed(0)} M Ft
          vagy {adat.thresholds.headcount_medium} fő &nbsp;·&nbsp; HIGH ≥{" "}
          {(adat.thresholds.revenue_high_huf / 1e6).toFixed(0)} M Ft vagy{" "}
          {adat.thresholds.headcount_high} fő
        </p>
      </Szekcio>

      {!adat.with_revenue ? (
        <UresAllapot
          cim="Még egy cégről sincs pénzügyi adat"
          lepes="Indítsd: ./leadgen.sh enrich financials"
        />
      ) : (
        <Szekcio cim="Cégek árbevétel szerint">
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Cég</TableHead>
                  <TableHead>Árbevétel</TableHead>
                  <TableHead>Fő</TableHead>
                  <TableHead>Év</TableHead>
                  <TableHead>Érték</TableHead>
                  <TableHead>Platform</TableHead>
                  <TableHead>Pontszám</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {adat.rows.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>
                      <Link href={`/cegek/${r.id}`} className="hover:underline">
                        {r.company_name || r.normalized_domain || "—"}
                      </Link>
                    </TableCell>
                    <TableCell>{formatForint(r.revenue) ?? "—"}</TableCell>
                    <TableCell>{r.headcount ?? "—"}</TableCell>
                    <TableCell>{r.financial_year ?? "—"}</TableCell>
                    <TableCell>
                      {r.economic_value ? (
                        <Badge variant="secondary">{r.economic_value}</Badge>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell>{r.webshop_platform ?? "—"}</TableCell>
                    <TableCell>{formatSzam(r.signal_score) ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {Object.keys(adat.missing_labels).length > 0 && (
            <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
              {Object.entries(adat.missing_labels)
                .sort()
                .map(([k, n]) => (
                  <span key={k}>
                    {k}: {n}
                  </span>
                ))}
            </div>
          )}
        </Szekcio>
      )}
    </div>
  );
}
