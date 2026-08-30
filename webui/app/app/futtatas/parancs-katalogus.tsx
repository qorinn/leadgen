"use client";

import { useCallback, useEffect, useState } from "react";
import { Play } from "lucide-react";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";
import { KoltsegJelveny } from "@/components/koltseg-jelveny";
import { MegerositoDialog } from "@/components/megerosito-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError, type JobCatalogItem, type JobItem } from "@/lib/api";
import { EloNaplo } from "./elo-naplo";
import { Elozmenyek } from "./elozmenyek";

/**
 * Az indithato parancsok (WEBUI-TERV.md F6).
 *
 * A LISTA A SZERVERTOL JON (`/api/jobs/catalog`) -- itt nincs bedrotozott
 * parancsnev, keret vagy koltseg (Invariansok #1). A `sender.py --live` ezert
 * nem is szerepelhet: nincs a katalogusban, es a felulet nem tud olyat
 * inditani, amit a szerver nem kinal fel.
 */
export function ParancsKatalogus() {
  const [katalogus, setKatalogus] = useState<JobCatalogItem[] | null>(null);
  const [futo, setFuto] = useState<JobItem | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [indulasHiba, setIndulasHiba] = useState<string | null>(null);
  const [elozmenyFrissites, setElozmenyFrissites] = useState(0);

  const betolt = useCallback(() => {
    setHiba(null);
    Promise.all([api.jobCatalog(), api.jobCurrent()])
      .then(([k, f]) => {
        setKatalogus(k.items);
        setFuto(f.job);
      })
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  useEffect(betolt, [betolt]);

  const naploValtozas = useCallback((job: JobItem) => {
    setFuto(job);
    // A befejezodott futas bekerul az elozmenyek koze -- toltsuk ujra.
    if (!job.fut) setElozmenyFrissites((n) => n + 1);
  }, []);

  async function indit(kulcs: string, params: Record<string, number>) {
    setIndulasHiba(null);
    try {
      const valasz = await api.jobStart(kulcs, params);
      setFuto(valasz.job);
    } catch (err) {
      // 409: mar fut valami. A szerver uzenete megmondja, MI fut -- azt
      // mutatjuk, nem egy sajat szoveget.
      // Nem dobjuk tovabb: a MegerositoDialog `onMegerosit`-jenek elszallo
      // promise-a kezeletlen hiba lenne a konzolon, es a felhasznalo ugyis
      // az itt kiirt szerver-uzenetet olvassa.
      setIndulasHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
    }
  }

  if (hiba) return <HibaAllapot uzenet={hiba} ujra={betolt} />;
  if (!katalogus) return <Betoltes sorok={6} />;

  const futEppen = futo?.fut ?? false;

  return (
    <div className="flex flex-col gap-6">
      {futo && (
        <section className="flex flex-col gap-2 rounded-lg border p-4">
          <h2 className="text-sm font-semibold text-muted-foreground">
            {futEppen ? "Most fut" : "Legutóbbi futás"}
          </h2>
          <EloNaplo job={futo} onValtozas={naploValtozas} />
        </section>
      )}

      {indulasHiba && <p className="text-sm text-destructive">{indulasHiba}</p>}

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-muted-foreground">Parancsok</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {katalogus.map((p) => (
            <ParancsKartya key={p.kulcs} parancs={p} tiltva={futEppen} onIndit={indit} />
          ))}
        </div>
      </section>

      <Elozmenyek frissites={elozmenyFrissites} />
    </div>
  );
}

function ParancsKartya({
  parancs,
  tiltva,
  onIndit,
}: {
  parancs: JobCatalogItem;
  tiltva: boolean;
  onIndit: (kulcs: string, params: Record<string, number>) => Promise<void>;
}) {
  const [params, setParams] = useState<Record<string, number>>(() =>
    Object.fromEntries(parancs.parameterek.map((p) => [p.nev, p.alap])),
  );

  const usd = becsultUsd(parancs, params);

  return (
    <div className="flex flex-col gap-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <span className="font-medium">{parancs.cimke}</span>
          <code className="text-xs text-muted-foreground">{parancs.parancs}</code>
        </div>
        {parancs.koltseg.fizetos && (
          <span className="flex items-center gap-1">
            {usd != null && <KoltsegJelveny usd={usd} />}
            {parancs.koltseg.ai_tokenenkent && (
              <Badge variant="secondary" title={parancs.koltseg.magyarazat}>
                💰 AI
              </Badge>
            )}
          </span>
        )}
      </div>

      <p className="text-sm text-muted-foreground">{parancs.magyarazat}</p>

      {parancs.parameterek.map((p) => (
        <div key={p.nev} className="flex items-center gap-2">
          <Label htmlFor={`${parancs.kulcs}-${p.nev}`} className="text-xs">
            <code>{p.flag}</code>
          </Label>
          <Input
            id={`${parancs.kulcs}-${p.nev}`}
            type="number"
            className="h-8 w-24"
            min={p.minimum}
            max={p.maximum}
            value={params[p.nev]}
            onChange={(e) =>
              setParams((elozo) => ({ ...elozo, [p.nev]: Number(e.target.value) }))
            }
          />
          <span className="text-xs text-muted-foreground">{p.cimke}</span>
        </div>
      ))}

      {parancs.koltseg.fizetos ? (
        <MegerositoDialog
          trigger={
            <Button size="sm" disabled={tiltva}>
              <Play className="size-3.5" />
              Indítás
            </Button>
          }
          cim={`${parancs.cimke} — ez pénzbe kerül`}
          kovetkezmeny={
            <span className="flex flex-col gap-1">
              <span>{parancs.magyarazat}</span>
              {usd != null && (
                <span>
                  Becsült Apify-költség: <strong>{formatUsd(usd)}</strong>
                </span>
              )}
              {/* Az AI-resz TOKENENKENT szamlazodik -- itt szandekosan nem
                  all dollarosszeg, mert az a bemenettol fugg. A tenyleges
                  koltseget a futas utan a Riportok / Koltsegek mutatja. */}
              {parancs.koltseg.ai_tokenenkent && (
                <span>
                  <strong>AI-költség:</strong> tokenenként számlázódik, előre nem
                  becsülhető.
                </span>
              )}
              <span className="text-xs">{parancs.koltseg.magyarazat}</span>
              {parancs.parameterek.map((p) => (
                <span key={p.nev} className="text-xs">
                  Keret: <code>{p.flag} {params[p.nev]}</code>
                </span>
              ))}
            </span>
          }
          megerositoSzoveg="Indítom"
          onMegerosit={() => onIndit(parancs.kulcs, params)}
        />
      ) : (
        <Button
          size="sm"
          variant="outline"
          disabled={tiltva}
          onClick={() => void onIndit(parancs.kulcs, params).catch(() => {})}
        >
          <Play className="size-3.5" />
          Indítás
        </Button>
      )}
    </div>
  );
}

/**
 * A becsult koltseg. `null`, ha nem becsulheto elore.
 *
 * A SZORZAS a szerver adataibol jon (egysegar x darab, `/api/jobs/catalog`) --
 * itt NINCS bedrotozott ar. Ahol a szerver azt mondja, hogy a koltseg
 * tokenenkent all elo, ott `null`-t adunk: inkabb ne mutassunk szamot, mint
 * hogy kitalaljunk egyet (WEBUI-TERV.md F6).
 */
function becsultUsd(
  parancs: JobCatalogItem,
  params: Record<string, number>,
): number | null {
  const k = parancs.koltseg;
  if (k.apify_egysegar_usd == null) return null;
  const darab =
    k.apify_fix_darab ?? (k.apify_darab_parametere ? params[k.apify_darab_parametere] : null);
  if (darab == null || Number.isNaN(darab)) return null;
  return darab * k.apify_egysegar_usd;
}

function formatUsd(usd: number): string {
  return `~$${usd.toLocaleString("hu-HU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
