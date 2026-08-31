"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";
import { UresAllapot } from "@/components/ures-allapot";
import { type JobHistory, api, ApiError } from "@/lib/api";

/**
 * Mikor, mi, meddig futott, es mi lett a kilepesi kod (WEBUI-TERV.md F6).
 *
 * A forras a `data/webui_jobs.jsonl` naplo (webui/api/jobs.py) -- azert
 * fajl es nem memoria, hogy egy API-ujraindulas ne torolje ki, mi futott ma.
 */
export function Elozmenyek({ frissites }: { frissites: number }) {
  const [adat, setAdat] = useState<JobHistory | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .jobHistory(30)
      .then(setAdat)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  useEffect(betolt, [betolt, frissites]);

  if (hiba) return <HibaAllapot uzenet={hiba} ujra={betolt} />;
  if (!adat) return <Betoltes sorok={3} />;

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-muted-foreground">Előzmények</h2>
      {adat.items.length === 0 ? (
        <UresAllapot cim="Még nem futott semmi a felületről" />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Mikor</TableHead>
                <TableHead>Mi</TableHead>
                <TableHead>Parancs</TableHead>
                <TableHead className="text-right">Meddig</TableHead>
                <TableHead>Eredmény</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {adat.items.map((j) => (
                <TableRow key={j.id}>
                  <TableCell className="whitespace-nowrap text-muted-foreground">
                    {new Date(j.started_at).toLocaleString("hu-HU")}
                  </TableCell>
                  <TableCell>{j.cimke}</TableCell>
                  <TableCell>
                    <code className="text-xs">{j.parancs}</code>
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap">
                    {j.seconds != null ? `${j.seconds.toFixed(1)} mp` : "—"}
                  </TableCell>
                  <TableCell>
                    <Badge variant={j.exit_code === 0 ? "secondary" : "destructive"}>
                      {j.allapot_cimke}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  );
}
