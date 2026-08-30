"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { StatusBadge } from "@/components/status-badge";
import { UresAllapot } from "@/components/ures-allapot";
import { useMeta } from "@/lib/use-meta";
import { api, ApiError, type Campaign } from "@/lib/api";
import { formatForint, formatSzam } from "@/lib/format";
import { Szekcio } from "./szekcio";

export function Kampany() {
  const { meta } = useMeta();
  const [nev, setNev] = useState<string | null>(null);
  const [adat, setAdat] = useState<Campaign | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  // A kampanylista es a jovahagyasi allapot a /api/meta-bol jon -- itt nincs
  // bedrotozva egyetlen kampanynev sem (WEBUI-TERV.md Invariansok #1). Az
  // elso kampanyt automatikusan kivalasztjuk, hogy legyen mit mutatni.
  useEffect(() => {
    if (nev || !meta?.kampanyok.length) return;
    setNev(meta.kampanyok[0].kulcs);
  }, [meta, nev]);

  const betolt = useCallback(() => {
    if (!nev) return;
    setHiba(null);
    setAdat(null);
    api
      .reportCampaign(nev)
      .then(setAdat)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, [nev]);

  useEffect(betolt, [betolt]);

  if (!meta) return <Betoltes sorok={6} />;

  if (!meta.kampanyok.length) {
    return <UresAllapot cim="Még nincs egyetlen kampány sem" />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <Label>Kampány</Label>
        <Select value={nev ?? ""} onValueChange={(v) => v && setNev(v)}>
          <SelectTrigger className="w-64">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {meta.kampanyok.map((k) => (
              <SelectItem key={k.kulcs} value={k.kulcs}>
                {k.kulcs}
                {!k.jovahagyott && " (vázlat)"}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {hiba ? (
        <HibaAllapot uzenet={hiba} ujra={betolt} />
      ) : !adat ? (
        <Betoltes sorok={6} />
      ) : (
        <>
          <Szekcio cim={`${adat.name} (${adat.total} cég)`}>
            <Badge variant={adat.approved ? "default" : "outline"}>
              {adat.approved ? "JÓVÁHAGYVA — exportálható" : "VÁZLAT — NEM exportálható"}
            </Badge>
            {!adat.approved && (
              <p className="text-xs text-muted-foreground">
                A szöveget át kell írni (cold-email-starter/templates.py), majd felvenni
                a leadgen/contract.py APPROVED_CAMPAIGNS listájába.
              </p>
            )}
            {Object.keys(adat.by_status).length > 0 && (
              <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                {Object.entries(adat.by_status)
                  .sort()
                  .map(([k, n]) => (
                    <span key={k}>
                      {k}: <strong>{n}</strong>
                    </span>
                  ))}
              </div>
            )}
          </Szekcio>

          {!adat.total ? (
            <UresAllapot cim="Még egy cég sincs ebben a kampányban" />
          ) : (
            <div className="overflow-x-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Cég</TableHead>
                    <TableHead>Státusz</TableHead>
                    <TableHead>Érték</TableHead>
                    <TableHead>Árbevétel</TableHead>
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
                      <TableCell>
                        <StatusBadge status={r.status} />
                      </TableCell>
                      <TableCell>
                        {r.economic_value ? (
                          <Badge variant="secondary">{r.economic_value}</Badge>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell>{formatForint(r.revenue) ?? "—"}</TableCell>
                      <TableCell>{r.webshop_platform ?? "—"}</TableCell>
                      <TableCell>{formatSzam(r.signal_score) ?? "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
