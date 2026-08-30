"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Bar } from "@/components/charts/bar";
import { BarChart } from "@/components/charts/bar-chart";
import { Grid } from "@/components/charts/grid";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";
import { useMeta } from "@/lib/use-meta";
import { api, ApiError, type Funnel } from "@/lib/api";
import { ListaUres, Szekcio } from "./szekcio";

const KAPCSOLAT_CIMKE: Record<string, string> = {
  personal: "személyes",
  generic: "generikus (info@ jellegű)",
  role: "szerepkör",
  unknown: "ismeretlen",
};

const OUTREACH_CIMKE: Record<string, string> = {
  queued: "sorban áll",
  sent: "kiment",
  replied: "válaszolt",
  done: "lezárult",
  stopped: "leállítva",
};

export function Tolcser() {
  const { meta } = useMeta();
  const [adat, setAdat] = useState<Funnel | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .reportFunnel()
      .then(setAdat)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  useEffect(betolt, [betolt]);

  const chartAdat = useMemo(() => {
    if (!adat || !meta) return [];
    return meta.statuszok
      .filter((s) => adat.by_status[s.kulcs])
      .map((s) => ({ cimke: s.cimke, ertek: adat.by_status[s.kulcs] }));
  }, [adat, meta]);

  if (hiba) return <HibaAllapot uzenet={hiba} ujra={betolt} />;
  if (!adat) return <Betoltes sorok={8} />;

  if (!adat.companies_total) {
    return (
      <ListaUres szoveg="Még egy cég sincs a DB-ben. Kezdd itt: ./leadgen.sh ingest maps --engine <engine> --max-results 50" />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Szekcio cim={`Cégek státusz szerint (${adat.companies_total})`}>
        {chartAdat.length > 0 && (
          <>
            {/* A statusz-cimkek tul hosszuak egy oszlop ala (pl. "feldolgozva
                (minositesre var)") -- BarXAxis nelkul rajzoljuk, a
                cimke->szam parositast a chart alatti lista adja, ugyanugy,
                mint a CLI `report` szoveges kimenete. */}
            <BarChart data={chartAdat} xDataKey="cimke">
              <Grid />
              <Bar dataKey="ertek" />
            </BarChart>
            <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm sm:grid-cols-2 lg:grid-cols-3">
              {chartAdat.map((s) => (
                <div key={s.cimke} className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">{s.cimke}</dt>
                  <dd className="font-medium">{s.ertek}</dd>
                </div>
              ))}
            </dl>
          </>
        )}
        {Object.keys(adat.unknown_status).length > 0 && (
          <p className="text-sm text-muted-foreground">
            Ismeretlen státusz:{" "}
            {Object.entries(adat.unknown_status)
              .map(([k, n]) => `${k} (${n})`)
              .join(", ")}
          </p>
        )}
      </Szekcio>

      <Szekcio cim="Kapcsolatok" ures={!Object.keys(adat.contacts).length}>
        <div className="flex flex-wrap gap-4 text-sm">
          {Object.entries(adat.contacts).map(([k, n]) => (
            <span key={k}>
              {KAPCSOLAT_CIMKE[k] ?? k}: <strong>{n}</strong>
            </span>
          ))}
        </div>
      </Szekcio>

      <Szekcio cim="Email-validáció" ures={!adat.email_validation}>
        {adat.email_validation && (
          <>
            <p className="text-sm">
              Mód: <strong>{adat.email_validation.mode}</strong>
            </p>
            <p className="text-sm text-muted-foreground">{adat.email_validation.summary}</p>
          </>
        )}
      </Szekcio>

      <Szekcio cim="Tiltólista" ures={!Object.keys(adat.suppression).length}>
        <div className="flex flex-wrap gap-4 text-sm">
          {Object.entries(adat.suppression)
            .sort((a, b) => b[1] - a[1])
            .map(([k, n]) => (
              <span key={k}>
                {k}: <strong>{n}</strong>
              </span>
            ))}
        </div>
      </Szekcio>

      <Szekcio cim="Címkék" ures={!Object.keys(adat.labels).length}>
        <div className="flex flex-wrap gap-4 text-sm">
          {Object.entries(adat.labels)
            .sort((a, b) => b[1] - a[1])
            .map(([k, n]) => (
              <span key={k}>
                {k}: <strong>{n}</strong>
              </span>
            ))}
        </div>
      </Szekcio>

      <Szekcio cim="Megkeresések (outreach)" ures={!Object.keys(adat.outreach).length}>
        <div className="flex flex-wrap gap-4 text-sm">
          {Object.entries(adat.outreach).map(([k, n]) => (
            <span key={k}>
              {OUTREACH_CIMKE[k] ?? k}: <strong>{n}</strong>
            </span>
          ))}
        </div>
        {adat.unlinked_sources > 0 && (
          <p className="text-xs text-muted-foreground">
            {adat.unlinked_sources} nyers forráselem még nincs céghez kapcsolva.
          </p>
        )}
      </Szekcio>

      <Szekcio cim="Következő lépés" ures={!adat.next_steps.length}>
        <div className="flex flex-col gap-1">
          {adat.next_steps.map((l) => {
            const cimke = meta?.statuszok.find((s) => s.kulcs === l.status)?.cimke ?? l.status;
            return (
              <p key={l.status} className="text-sm">
                <strong>{l.count}</strong> {cimke} →{" "}
                <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{l.action}</code>
              </p>
            );
          })}
        </div>
      </Szekcio>
    </div>
  );
}
