"use client";

import { Download } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MegerositoDialog } from "@/components/megerosito-dialog";
import { api, ApiError, type FinancialsImportResult } from "@/lib/api";

/** A penzugyi worklist tomeges le-/feltoltese (WEBUI-TERV.md F5, 2. pont).
 * A cegenkenti urlap a cegek reszletnezeten van -- ez csak a tomeges,
 * nem-ceg-specifikus resz. A portal lekerdezese jogi okbol tiltott, ezert
 * ez a folyamat szandekosan kezi (leadgen/financials.py fejlece). */
export function FinancialsWorklist() {
  const [limit, setLimit] = useState("20");
  const [file, setFile] = useState<File | null>(null);
  const [elonezet, setElonezet] = useState<FinancialsImportResult | null>(null);
  const [vegeredmeny, setVegeredmeny] = useState<FinancialsImportResult | null>(null);
  const [folyamatban, setFolyamatban] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  async function elonezetKer() {
    if (!file) return;
    setHiba(null);
    setFolyamatban(true);
    setVegeredmeny(null);
    try {
      setElonezet(await api.financialsImport(file, true));
    } catch (err) {
      setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
    } finally {
      setFolyamatban(false);
    }
  }

  async function tenylegesImport() {
    if (!file) return;
    setHiba(null);
    try {
      setVegeredmeny(await api.financialsImport(file, false));
      setElonezet(null);
    } catch (err) {
      setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
    }
  }

  const limitSzam = Number(limit) || 20;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pénzügyi worklist</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">
          Az e-beszámoló portál lekérdezése jogi okból tiltott, ezért ez a folyamat
          szándékosan kézi: töltsd le a legjobb leadek listáját, keresd meg a
          beszámolójukat, töltsd ki a CSV-t, majd töltsd fel.
        </p>

        <div className="flex items-end gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="limit">Hány cég a listában</Label>
            <Input
              id="limit"
              type="number"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              className="w-24"
            />
          </div>
          <a href={api.financialsWorklistUrl(limitSzam)} download="financials_worklist.csv">
            <Button variant="outline" size="sm">
              <Download className="size-4" />
              Letöltés
            </Button>
          </a>
        </div>

        <div className="flex flex-col gap-2 border-t pt-4">
          <Label htmlFor="worklist-file">Kitöltött CSV feltöltése</Label>
          <input
            id="worklist-file"
            type="file"
            accept=".csv"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setElonezet(null);
              setVegeredmeny(null);
            }}
            className="text-sm"
          />
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" disabled={!file || folyamatban} onClick={elonezetKer}>
              {folyamatban ? "Előnézet…" : "Előnézet (nem ír a DB-be)"}
            </Button>
            {elonezet && elonezet.frissitett > 0 && (
              <MegerositoDialog
                trigger={<Button size="sm">Tényleges import</Button>}
                cim="Biztosan beírod?"
                kovetkezmeny={`${elonezet.frissitett} cég pénzügyi adata frissül az adatbázisban. Ez a gazdasági érték (LOW/MEDIUM/HIGH) és a rangsoroló pontszám átszámolásával jár.`}
                megerositoSzoveg="Beírom"
                onMegerosit={tenylegesImport}
              />
            )}
          </div>
        </div>

        {hiba && <p className="text-sm text-destructive">{hiba}</p>}

        {(elonezet || vegeredmeny) && (
          <ImportEredmeny
            eredmeny={(vegeredmeny ?? elonezet)!}
            dry={vegeredmeny ? vegeredmeny.dry : true}
          />
        )}
      </CardContent>
    </Card>
  );
}

function ImportEredmeny({
  eredmeny,
  dry,
}: {
  eredmeny: FinancialsImportResult;
  dry: boolean;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-md border p-3 text-sm">
      <p className="font-medium">
        {dry ? "Előnézet -- semmit nem írt a DB-be" : "Beírva"}
      </p>
      <p>
        olvasott sor: {eredmeny.olvasott} · frissítendő/frissített: {eredmeny.frissitett} ·
        üres: {eredmeny.ures} · ismeretlen cég: {eredmeny.ismeretlen} · hibás szám:{" "}
        {eredmeny.hibas}
      </p>
      {Object.keys(eredmeny.ertekek).length > 0 && (
        <p className="text-muted-foreground">
          {Object.entries(eredmeny.ertekek)
            .map(([k, n]) => `${k}: ${n}`)
            .join("   ")}
        </p>
      )}
      {eredmeny.ezer_forint_gyanu.length > 0 && (
        <div className="text-destructive">
          <p>
            {eredmeny.ezer_forint_gyanu.length} árbevétel gyanúsan kicsi (a beszámoló
            űrlapja E Ft-ban mutat, ez a leggyakoribb elírási hiba):
          </p>
          <ul className="list-inside list-disc">
            {eredmeny.ezer_forint_gyanu.slice(0, 10).map((sor) => (
              <li key={sor}>{sor}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
