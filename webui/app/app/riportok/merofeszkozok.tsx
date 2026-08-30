"use client";

import { useCallback, useEffect, useState } from "react";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";
import { api, ApiError, type Costs } from "@/lib/api";
import { formatDatum } from "@/lib/format";
import { Szekcio } from "./szekcio";

/** A bake-off (`eval`) es az `llm-check` EREDMENYE -- csak olvashatoan,
 * gomb nelkul (WEBUI-TERV.md F9, felhasznaloi dontes). */
export function Merofeszkozok() {
  const [koltseg, setKoltseg] = useState<Costs | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .costs()
      .then(setKoltseg)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  useEffect(betolt, [betolt]);

  if (hiba) return <HibaAllapot uzenet={hiba} ujra={betolt} />;
  if (!koltseg) return <Betoltes sorok={4} />;

  return (
    <div className="flex flex-col gap-4">
      <Szekcio cim="llm-check — kulcs- és költségellenőrzés">
        {koltseg.has_data ? (
          <p className="text-sm">
            Utoljára futtatva: <strong>{formatDatum(koltseg.last_ts) ?? "—"}</strong>. A
            részletes, modellenkénti bontás a <strong>Költségek</strong> fülön látszik.
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">
            Még nem futott. Indítsd terminálból:{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
              ./leadgen.sh llm-check
            </code>
          </p>
        )}
      </Szekcio>

      <Szekcio cim="Bake-off (eval) — modell-összehasonlítás">
        <p className="text-sm text-muted-foreground">
          Az eredménye csak a terminálban jelenik meg egy táblázatként, nem íródik fájlba
          vagy adatbázisba — a felület ezért nem tudja megmutatni, futott-e már. Indítsd
          terminálból:{" "}
          <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
            ./leadgen.sh eval bakeoff
          </code>
        </p>
      </Szekcio>
    </div>
  );
}
