"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";
import { UresAllapot } from "@/components/ures-allapot";
import { api, ApiError, type Alerts } from "@/lib/api";
import { formatDatum } from "@/lib/format";
import { NaploReszlet } from "./naplo-reszlet";

type RiasztasSor = Alerts["aktiv"][number];

function korCimke(v: string | null | undefined): string | null {
  if (!v) return null;
  const napok = Math.floor((Date.now() - new Date(v).getTime()) / (24 * 60 * 60 * 1000));
  return napok > 0 ? `${napok} napja tart` : "ma kezdődött";
}

function RiasztasKartya({ r }: { r: RiasztasSor }) {
  const kor = korCimke(r.first_seen);
  return (
    <div className="flex flex-col gap-2 rounded-md border border-amber-500/40 bg-amber-500/5 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{r.tipus}</Badge>
        {kor && <Badge variant="secondary">{kor}</Badge>}
      </div>
      <p className="text-sm whitespace-pre-wrap">{r.uzenet}</p>
      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
        <span>Első előfordulás: {formatDatum(r.first_seen) ?? "—"}</span>
        <span>Utoljára látva: {formatDatum(r.last_seen) ?? "—"}</span>
        <span>Utoljára értesítve: {formatDatum(r.last_notified) ?? "—"}</span>
      </div>
    </div>
  );
}

function LezartKartya({ r }: { r: RiasztasSor }) {
  return (
    <div className="flex flex-col gap-2 rounded-md border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{r.tipus}</Badge>
        <Badge variant="secondary">lezárva</Badge>
      </div>
      <p className="text-sm whitespace-pre-wrap text-muted-foreground">{r.uzenet}</p>
      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
        <span>Első előfordulás: {formatDatum(r.first_seen) ?? "—"}</span>
        <span>Lezárva: {formatDatum(r.resolved_at) ?? "—"}</span>
      </div>
    </div>
  );
}

export default function RiasztasokPage() {
  const [adat, setAdat] = useState<Alerts | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .alerts()
      .then(setAdat)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  useEffect(betolt, [betolt]);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Riasztások</h1>

      {hiba ? (
        <HibaAllapot uzenet={hiba} ujra={betolt} />
      ) : !adat ? (
        <Betoltes sorok={5} />
      ) : (
        <Tabs defaultValue="aktiv">
          <TabsList>
            <TabsTrigger value="aktiv">Aktív ({adat.aktiv.length})</TabsTrigger>
            <TabsTrigger value="lezart">Lezárt ({adat.lezart.length})</TabsTrigger>
          </TabsList>

          <TabsContent value="aktiv">
            {adat.aktiv.length === 0 ? (
              <UresAllapot cim="Nincs aktív riasztás" />
            ) : (
              <div className="flex flex-col gap-3">
                {adat.aktiv.map((r) => (
                  <RiasztasKartya key={r.kulcs} r={r} />
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="lezart">
            {adat.lezart.length === 0 ? (
              <UresAllapot cim="Még nincs lezárt riasztás" />
            ) : (
              <div className="flex flex-col gap-3">
                {adat.lezart.map((r, i) => (
                  <LezartKartya key={r.kulcs + String(r.resolved_at) + i} r={r} />
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      )}

      <NaploReszlet />
    </div>
  );
}
