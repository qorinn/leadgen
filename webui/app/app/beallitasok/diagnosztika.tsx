"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { useMeta } from "@/lib/use-meta";
import { api, ApiError, type Diagnostics } from "@/lib/api";
import { formatDatum } from "@/lib/format";

/** Csak olvashato rendszer-diagnosztika (WEBUI-TERV.md F10): engine-ek es
 * jovahagyott kampanyok a /api/meta-bol (ne masoljuk le ujra), migraciok es
 * a feedback-import allasa egy uj, kizarolag erre a nezetre keszult
 * vegpontbol (/api/diagnostics). */
export function Diagnosztika() {
  const { meta, hiba: metaHiba, ujra: metaUjra } = useMeta();
  const [adat, setAdat] = useState<Diagnostics | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .diagnostics()
      .then(setAdat)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  useEffect(betolt, [betolt]);

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Engine-ek</CardTitle>
        </CardHeader>
        <CardContent>
          {metaHiba ? (
            <HibaAllapot uzenet={metaHiba} ujra={metaUjra} />
          ) : !meta ? (
            <Betoltes sorok={3} />
          ) : (
            <div className="flex flex-wrap gap-2">
              {meta.engine_ek.map((e) => (
                <Badge key={e.kulcs} variant={e.aktiv ? "default" : "outline"}>
                  {e.cimke}
                  {!e.aktiv && " (kikapcsolva)"}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Kampányok</CardTitle>
        </CardHeader>
        <CardContent>
          {metaHiba ? (
            <HibaAllapot uzenet={metaHiba} ujra={metaUjra} />
          ) : !meta ? (
            <Betoltes sorok={3} />
          ) : (
            <div className="flex flex-wrap gap-2">
              {meta.kampanyok.map((k) => (
                <Badge key={k.kulcs} variant={k.jovahagyott ? "default" : "outline"}>
                  {k.kulcs}
                  {!k.jovahagyott && " (vázlat)"}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {hiba ? (
        <HibaAllapot uzenet={hiba} ujra={betolt} />
      ) : !adat ? (
        <Betoltes sorok={6} />
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Migrációk ({adat.migraciok.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Fájl</TableHead>
                      <TableHead>Alkalmazva</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {adat.migraciok.map((m) => (
                      <TableRow key={m.filename}>
                        <TableCell className="font-mono text-xs">{m.filename}</TableCell>
                        <TableCell>{formatDatum(m.applied_at) ?? "—"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Feedback-import állása</CardTitle>
            </CardHeader>
            <CardContent>
              {adat.feedback_watermark.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Még egyszer sem futott feedback-import.
                </p>
              ) : (
                <div className="overflow-x-auto rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Fájl</TableHead>
                        <TableHead>Feldolgozott sor</TableHead>
                        <TableHead>Utoljára frissítve</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {adat.feedback_watermark.map((w) => (
                        <TableRow key={w.file}>
                          <TableCell className="font-mono text-xs">{w.file}</TableCell>
                          <TableCell>{w.last_row}</TableCell>
                          <TableCell>{formatDatum(w.updated_at) ?? "—"}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
