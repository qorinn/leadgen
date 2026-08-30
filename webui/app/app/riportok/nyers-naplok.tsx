"use client";

import { useCallback, useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import { useMeta } from "@/lib/use-meta";
import { api, ApiError, type SenderCsv } from "@/lib/api";

function NaploTablazat({ nev }: { nev: string }) {
  const [adat, setAdat] = useState<SenderCsv | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .senderCsv(nev)
      .then(setAdat)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, [nev]);

  useEffect(betolt, [betolt]);

  if (hiba) return <HibaAllapot uzenet={hiba} ujra={betolt} />;
  if (!adat) return <Betoltes sorok={5} />;
  if (!adat.exists) return <UresAllapot cim="Ez a fájl még nem létezik" />;
  if (!adat.total) return <UresAllapot cim="A fájl üres" />;

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">
        {adat.total <= 200
          ? `${adat.total} sor`
          : `az utolsó 200 sor (összesen ${adat.total})`}
      </p>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {adat.columns.map((c) => (
                <TableHead key={c}>{c}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {adat.rows.map((r, i) => (
              <TableRow key={i}>
                {adat.columns.map((c) => (
                  <TableCell key={c} className="max-w-80 truncate">
                    {r[c] ?? "—"}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

/** A kuldo nyers CSV-i, tablazatosan -- az ertelmezett adat mar a DB-ben
 * van, ez csak a nyers ellenorzeshez kell (WEBUI-TERV.md F9). A fajlnevek
 * a /api/meta-bol jonnek (report.SENDER_CSV_NEVEK), nem itt vannak
 * bedrotozva: az elso fajlnev egybeesne egy companies.status ertekkel,
 * es a webui-kontraktus teszt pont ezt a fajta veletlen atfedest is
 * ellenorzi. */
export function NyersNaplok() {
  const { meta } = useMeta();
  const nevek = meta?.kuldo_csv_nevek ?? [];

  if (!nevek.length) return <Betoltes sorok={4} />;

  return (
    <Tabs defaultValue={nevek[0]}>
      <TabsList>
        {nevek.map((n) => (
          <TabsTrigger key={n} value={n}>
            {n}.csv
          </TabsTrigger>
        ))}
      </TabsList>
      {nevek.map((n) => (
        <TabsContent key={n} value={n}>
          <NaploTablazat nev={n} />
        </TabsContent>
      ))}
    </Tabs>
  );
}
