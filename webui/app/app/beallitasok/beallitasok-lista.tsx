"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Lock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";
import { api, ApiError, type Settings } from "@/lib/api";

/** A .env ertekei maszkolva -- a felulet nem irja a .env-et, csak mutatja
 * (WEBUI-TERV.md F10, Invariansok #4: titok soha nem megy ki teljes
 * ertekben). A maszkolas es a csoportositas Pythonban dol el
 * (leadgen/config.py `settings_adat()`), itt csak megjelenites van. */
export function BeallitasokLista() {
  const [adat, setAdat] = useState<Settings | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .settings()
      .then(setAdat)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  useEffect(betolt, [betolt]);

  const csoportok = useMemo(() => {
    const map = new Map<string, Settings["tetelek"]>();
    for (const t of adat?.tetelek ?? []) {
      const lista = map.get(t.csoport) ?? [];
      lista.push(t);
      map.set(t.csoport, lista);
    }
    return map;
  }, [adat]);

  if (hiba) return <HibaAllapot uzenet={hiba} ujra={betolt} />;
  if (!adat) return <Betoltes sorok={8} />;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Beállítások</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <p className="text-sm text-muted-foreground">
          A <code className="rounded bg-muted px-1 py-0.5 text-xs">.env</code> értékei —
          a felület nem írja őket, kézi szerkesztés marad. A titkok (
          <Lock className="inline size-3" /> ikonnal jelölve) soha nem jelennek meg
          teljes értékben.
        </p>
        {Array.from(csoportok.entries()).map(([csoport, tetelek]) => (
          <div key={csoport} className="flex flex-col gap-2">
            <h3 className="text-sm font-semibold text-muted-foreground">{csoport}</h3>
            <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
              {tetelek.map((t) => (
                <div key={t.kulcs} className="flex items-baseline justify-between gap-3">
                  <dt className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
                    {t.titok && <Lock className="size-3 shrink-0" />}
                    {t.kulcs}
                  </dt>
                  <dd
                    className={
                      t.ertek === "HIANYZIK"
                        ? "text-sm text-destructive"
                        : "text-sm font-medium"
                    }
                  >
                    {t.ertek}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
