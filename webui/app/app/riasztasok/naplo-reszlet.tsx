"use client";

import { useCallback, useEffect, useState } from "react";
import { RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";
import { api, ApiError, type LogTail } from "@/lib/api";

/** "Az alerts.log is megnezheto" (WEBUI-TERV.md F8) -- a teljes, szures es
 * kovetes nelkuli naplo-nezot a Futtatas oldal adja (F6, `NaploNezo`), itt
 * csak a legutobbi sorok egyszeru megtekintese kell. */
export function NaploReszlet() {
  const [adat, setAdat] = useState<LogTail | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .log("alerts", 200)
      .then(setAdat)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  useEffect(betolt, [betolt]);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold text-muted-foreground">Napló (alerts.log)</h2>
        <Button size="sm" variant="outline" className="ml-auto" onClick={betolt}>
          <RotateCw className="size-3.5" />
          Frissítés
        </Button>
      </div>
      {hiba ? (
        <HibaAllapot uzenet={hiba} ujra={betolt} />
      ) : !adat ? (
        <Betoltes sorok={4} />
      ) : !adat.exists ? (
        <p className="text-sm text-muted-foreground">
          Ez a napló még nem létezik — még nem futott riasztás-ellenőrzés.
        </p>
      ) : (
        <pre className="h-64 overflow-auto rounded-md border bg-muted/30 p-3 text-xs leading-relaxed whitespace-pre-wrap">
          {adat.lines.length ? adat.lines.join("\n") : "(üres napló)"}
        </pre>
      )}
    </div>
  );
}
