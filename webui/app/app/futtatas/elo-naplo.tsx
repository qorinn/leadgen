"use client";

import { useEffect, useRef, useState } from "react";
import { Square } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, ApiError, type JobItem, type JobOutput } from "@/lib/api";

/**
 * Egy futas elo naploja (WEBUI-TERV.md F6).
 *
 * MIERT SSE ES NEM POLLING: a lenyeg, hogy a kimenet MENET KOZBEN latszik,
 * ne a vegen egyben. Egy 30 masodperces pollozas pont azt a tajekozodast
 * venne el, amiert ez a kepernyo letezik -- ha a lanc beragad, latni kell,
 * HOL akadt el.
 *
 * A `cursor` a szerver sor-indexe. Ha a kapcsolat megszakad es az
 * `EventSource` ujracsatlakozik, onnan folytatjuk, ahol abbahagytuk -- igy a
 * naplo nem ismetel es nem hagy ki sort.
 */
export function EloNaplo({
  job,
  onValtozas,
}: {
  job: JobItem;
  /** A futas allapotanak minden valtozasakor -- a szulo igy tudja
   *  ujratolteni az elozmenyeket es feloldani az inditas-tiltast. */
  onValtozas: (job: JobItem) => void;
}) {
  const [sorok, setSorok] = useState<string[]>([]);
  const [hiba, setHiba] = useState<string | null>(null);
  const dobozRef = useRef<HTMLPreElement>(null);
  const kovetRef = useRef(true);

  useEffect(() => {
    let elo = true;
    let kurzor = 0;
    let forras: EventSource | null = null;

    // A mar meglevo sorokkal kezdunk (pl. oldal-ujratoltes utan egy mar
    // futo jobnal), csak utana kapcsolodunk a stremre.
    api
      .jobOutput(job.id, 0)
      .then((elozo: JobOutput) => {
        if (!elo) return;
        setSorok(elozo.lines);
        kurzor = elozo.cursor;
        onValtozas(elozo.job);
        if (!elozo.job.fut) return;

        forras = new EventSource(api.jobStreamUrl(job.id, kurzor));
        forras.onmessage = (e) => {
          const adat = JSON.parse(e.data) as JobOutput;
          kurzor = adat.cursor;
          if (adat.lines.length) setSorok((elozoSorok) => [...elozoSorok, ...adat.lines]);
          onValtozas(adat.job);
          if (!adat.job.fut) forras?.close();
        };
        forras.onerror = () => {
          // Az EventSource magatol ujracsatlakozik; a `cursor` miatt ez nem
          // veszit sort. Csak akkor jelzunk, ha vegleg lezarult.
          if (forras?.readyState === EventSource.CLOSED) {
            setHiba("Megszakadt a kapcsolat az elo naploval.");
          }
        };
      })
      .catch((err: unknown) => {
        if (elo) setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });

    return () => {
      elo = false;
      forras?.close();
    };
    // Az `onValtozas` a szuloben `useCallback`-kel stabil -- kulonben
    // minden ujrarendereleskor ujra felepulne az EventSource.
  }, [job.id, onValtozas]);

  // Automatikus gorgetes, DE csak amig a felhasznalo nem gorgetett vissza --
  // kulonben nem lehetne egy korabbi hibauzenetet elolvasni futas kozben.
  useEffect(() => {
    const doboz = dobozRef.current;
    if (doboz && kovetRef.current) doboz.scrollTop = doboz.scrollHeight;
  }, [sorok]);

  function gorgetes() {
    const doboz = dobozRef.current;
    if (!doboz) return;
    kovetRef.current = doboz.scrollHeight - doboz.scrollTop - doboz.clientHeight < 40;
  }

  async function megszakit() {
    setHiba(null);
    try {
      const valasz = await api.jobCancel(job.id);
      onValtozas(valasz.job);
    } catch (err) {
      setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{job.cimke}</span>
        <Badge variant={job.fut ? "default" : job.exit_code === 0 ? "secondary" : "destructive"}>
          {job.allapot_cimke}
        </Badge>
        <code className="text-xs text-muted-foreground">{job.parancs}</code>
        <span className="text-xs text-muted-foreground">
          {job.seconds != null ? `${job.seconds.toFixed(1)} mp` : ""}
        </span>
        <div className="ml-auto">
          {job.fut && (
            <Button size="sm" variant="destructive" onClick={megszakit}>
              <Square className="size-3.5" />
              Megszakítás
            </Button>
          )}
        </div>
      </div>

      {hiba && <p className="text-sm text-destructive">{hiba}</p>}

      <pre
        ref={dobozRef}
        onScroll={gorgetes}
        className="h-96 overflow-auto rounded-md border bg-muted/30 p-3 text-xs leading-relaxed whitespace-pre-wrap"
      >
        {sorok.length ? sorok.join("\n") : "(még nincs kimenet…)"}
      </pre>
    </div>
  );
}
