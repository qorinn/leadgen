"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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
import { UresAllapot } from "@/components/ures-allapot";
import { useMeta } from "@/lib/use-meta";
import { api, ApiError, type Replies } from "@/lib/api";
import { formatDatum, formatSzam } from "@/lib/format";
import { ValaszDialog } from "./valasz-dialog";

type ReplyItem = Replies["items"][number];

const MINDEN = "__minden__";

// A valasz-ablak 24 ora -- ez NEM a /api/meta kuszobeibol jon, mert a
// Pythonban sincs kulon config-ertek ra, csak a report.py-ba es a
// WEBUI-TERV.md-be van bedrotozva ugyanez a szam (leadgen/report.py
// "24 oran belul valaszolj"). Ha ez valaha konfiguralhato lesz a
// Pythonban, ide is a /api/meta-bol kell johetnie.
const VALASZ_ABLAK_ORA = 24;

function hataridoCimke(receivedAt: string | null): { szoveg: string; lejart: boolean } | null {
  if (!receivedAt) return null;
  const hatarido = new Date(receivedAt).getTime() + VALASZ_ABLAK_ORA * 60 * 60 * 1000;
  const hatra = hatarido - Date.now();
  if (hatra <= 0) return { szoveg: "lejárt a 24 óra", lejart: true };
  const orak = Math.floor(hatra / (60 * 60 * 1000));
  const percek = Math.floor((hatra % (60 * 60 * 1000)) / (60 * 1000));
  return { szoveg: `${orak} óra ${percek} perc van hátra`, lejart: false };
}

function ReplySor({ r, onMegnyit }: { r: ReplyItem; onMegnyit: () => void }) {
  return (
    <button
      type="button"
      onClick={onMegnyit}
      className="flex w-full flex-col gap-1 rounded-md border p-3 text-left hover:bg-muted/50"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{r.company_name || r.normalized_domain || r.email}</span>
        <span className="text-sm text-muted-foreground">{r.email}</span>
      </div>
      {r.subject && <p className="text-sm">{r.subject}</p>}
    </button>
  );
}

function ValaszokTartalom() {
  const { meta } = useMeta();
  const [items, setItems] = useState<ReplyItem[] | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [szuro, setSzuro] = useState(MINDEN);
  const [reszletek, setReszletek] = useState<ReplyItem | null>(null);
  const [dialogNyitva, setDialogNyitva] = useState(false);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .replies()
      .then((res) => setItems(res.items))
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  useEffect(betolt, [betolt]);

  const megnyit = (r: ReplyItem) => {
    setReszletek(r);
    setDialogNyitva(true);
  };

  // A surgos / attekintendo szerep a /api/meta-bol jon -- egyik konkret
  // besorolas-kulcs sincs ide bedrotozva, azt a
  // test_a_frontend_nem_drotoz_be_uzleti_listat tiltja (WEBUI-TERV.md
  // Invariansok #1).
  const surgosKulcsok = useMemo(
    () => new Set((meta?.valasz_osztalyok ?? []).filter((o) => o.surgos).map((o) => o.kulcs)),
    [meta]
  );
  const attekintendoKulcsok = useMemo(
    () =>
      new Set((meta?.valasz_osztalyok ?? []).filter((o) => o.attekintendo).map((o) => o.kulcs)),
    [meta]
  );

  const erdeklodok = useMemo(
    () => (items ?? []).filter((r) => r.classification && surgosKulcsok.has(r.classification)),
    [items, surgosKulcsok]
  );
  const bizonytalanok = useMemo(
    () =>
      (items ?? []).filter((r) => r.classification && attekintendoKulcsok.has(r.classification)),
    [items, attekintendoKulcsok]
  );
  const hibasak = useMemo(() => (items ?? []).filter((r) => r.error), [items]);

  const szurtSorok = useMemo(() => {
    if (!items) return [];
    if (szuro === MINDEN) return items;
    return items.filter((r) => r.classification === szuro);
  }, [items, szuro]);

  if (hiba) return <HibaAllapot uzenet={hiba} ujra={betolt} />;
  if (!items) return <Betoltes sorok={6} />;

  return (
    <div className="flex flex-col gap-6">
      {erdeklodok.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold text-amber-600 dark:text-amber-500">
            ÉRDEKLŐDIK — válaszolj neki ({erdeklodok.length})
          </h2>
          <div className="flex flex-col gap-2">
            {erdeklodok.map((r) => {
              const hd = hataridoCimke(r.received_at);
              return (
                <div key={r.id} className="flex items-center gap-3">
                  <div className="flex-1">
                    <ReplySor r={r} onMegnyit={() => megnyit(r)} />
                  </div>
                  {hd && (
                    <Badge variant={hd.lejart ? "destructive" : "outline"} className="shrink-0">
                      {hd.szoveg}
                    </Badge>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {bizonytalanok.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold text-muted-foreground">
            Bizonytalan — nézd át kézzel ({bizonytalanok.length})
          </h2>
          <div className="flex flex-col gap-2">
            {bizonytalanok.map((r) => (
              <ReplySor key={r.id} r={r} onMegnyit={() => megnyit(r)} />
            ))}
          </div>
        </section>
      )}

      {hibasak.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold text-destructive">
            Osztályozási hiba ({hibasak.length})
          </h2>
          <div className="flex flex-col gap-2">
            {hibasak.map((r) => (
              <ReplySor key={r.id} r={r} onMegnyit={() => megnyit(r)} />
            ))}
          </div>
        </section>
      )}

      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <h2 className="text-sm font-semibold text-muted-foreground">Minden válasz</h2>
          <div className="ml-auto flex flex-col gap-1">
            <Label>Besorolás</Label>
            <Select value={szuro} onValueChange={(v) => setSzuro(v ?? MINDEN)}>
              <SelectTrigger className="w-56">
                <SelectValue>
                  {(v: string | null) =>
                    !v || v === MINDEN
                      ? "Összes"
                      : (meta?.valasz_osztalyok.find((o) => o.kulcs === v)?.cimke ?? v)
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={MINDEN}>Összes</SelectItem>
                {(meta?.valasz_osztalyok ?? []).map((o) => (
                  <SelectItem key={o.kulcs} value={o.kulcs}>
                    {o.cimke}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {szurtSorok.length === 0 ? (
          <UresAllapot cim="Nincs a szűrésnek megfelelő válasz" />
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Cég</TableHead>
                  <TableHead>Cím</TableHead>
                  <TableHead>Tárgy</TableHead>
                  <TableHead>Besorolás</TableHead>
                  <TableHead>Bizonyosság</TableHead>
                  <TableHead>Modell</TableHead>
                  <TableHead>Dátum</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {szurtSorok.map((r) => {
                  const cimke =
                    meta?.valasz_osztalyok.find((o) => o.kulcs === r.classification)?.cimke ??
                    r.classification;
                  return (
                    <TableRow
                      key={r.id}
                      className="cursor-pointer"
                      onClick={() => megnyit(r)}
                    >
                      <TableCell>{r.company_name || r.normalized_domain || "—"}</TableCell>
                      <TableCell>{r.email}</TableCell>
                      <TableCell className="max-w-64 truncate">{r.subject || "—"}</TableCell>
                      <TableCell>
                        {r.error ? (
                          <Badge variant="destructive">hiba</Badge>
                        ) : cimke ? (
                          <Badge variant="outline">{cimke}</Badge>
                        ) : (
                          <Badge variant="secondary">nincs osztályozva</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        {r.confidence !== null ? `${formatSzam(r.confidence * 100, 0)}%` : "—"}
                      </TableCell>
                      <TableCell>{r.model || "—"}</TableCell>
                      <TableCell className="whitespace-nowrap text-muted-foreground">
                        {formatDatum(r.received_at) ?? "—"}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      <ValaszDialog valasz={reszletek} nyitva={dialogNyitva} onNyitvaValtoz={setDialogNyitva} />
    </div>
  );
}

export default function ValaszokPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Válaszok</h1>
      <ValaszokTartalom />
    </div>
  );
}
