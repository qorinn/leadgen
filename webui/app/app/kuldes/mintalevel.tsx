"use client";

import { useState } from "react";
import { Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MegerositoDialog } from "@/components/megerosito-dialog";
import { api, ApiError, type SendSample } from "@/lib/api";

// A harom szekvencia-fok. Ezek a `preview.py --stage` sajat valasztasi
// lehetosegei (`leadgen/send.py` FOKOK), es a szerver ELUTASITJA, ami nem
// ezek egyike -- a lista itt csak a legordulo feltoltese, nem szabaly.
const FOKOK = [
  { ertek: "cold", cimke: "1. levél" },
  { ertek: "follow_up_1", cimke: "2. levél" },
  { ertek: "follow_up_2", cimke: "3. levél" },
];

/**
 * Mintalevel a sajat cimedre (WEBUI-TERV.md F7).
 *
 * A `preview.py --send-to` megfeleloje: VALODI levelet kuld, de a valodi
 * cimzettek nem kapnak semmit, es a kuldo elozmeny-fajlja sem valtozik --
 * tehat a leadek szekvenciaja erintetlen marad.
 */
export function Mintalevel() {
  const [cim, setCim] = useState("");
  const [fok, setFok] = useState("cold");
  const [eredmeny, setEredmeny] = useState<SendSample | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  async function kuld() {
    setHiba(null);
    setEredmeny(null);
    try {
      setEredmeny(await api.sendSample(cim, 1, fok));
    } catch (err) {
      setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border p-4">
      <div className="flex flex-col gap-1">
        <h2 className="font-medium">Mintalevél magadnak</h2>
        <p className="text-sm text-muted-foreground">
          Egy valódi levél a saját címedre, hogy lásd, hogyan néz ki egy
          postafiókban. A valódi címzettek nem kapnak semmit, és a küldési
          előzményük sem változik. A leiratkozó link tesztcímre mutat —
          nyugodtan rákattinthatsz.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="minta-cim" className="text-xs">
            A te címed
          </Label>
          <Input
            id="minta-cim"
            type="email"
            placeholder="en@sajatcimem.hu"
            className="h-8 w-64"
            value={cim}
            onChange={(e) => setCim(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Melyik levél</Label>
          <Select value={fok} onValueChange={(v) => setFok(v ?? "cold")}>
            <SelectTrigger className="h-8 w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {FOKOK.map((f) => (
                <SelectItem key={f.ertek} value={f.ertek}>
                  {f.cimke}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <MegerositoDialog
          trigger={
            <Button variant="outline" size="sm" disabled={!cim.includes("@")}>
              <Mail className="size-4" />
              Minta küldése
            </Button>
          }
          cim="Mintalevél küldése"
          kovetkezmeny={
            <span className="flex flex-col gap-1">
              <span>
                Egy valódi levél megy ki erre a címre: <strong>{cim}</strong>.
              </span>
              <span>
                A valódi címzettek nem kapnak semmit, és a küldési előzményük sem
                változik, tehát a szekvenciájuk érintetlen marad — a Google napi
                limitjébe viszont beleszámít.
              </span>
            </span>
          }
          megerositoSzoveg="Elküldöm magamnak"
          onMegerosit={kuld}
        />
      </div>

      {hiba && <p className="text-sm text-destructive">{hiba}</p>}
      {eredmeny && (
        <>
          {!eredmeny.ok && eredmeny.error && (
            <p className="text-sm text-destructive">{eredmeny.error}</p>
          )}
          <pre className="max-h-64 overflow-auto rounded-md border bg-muted/30 p-3 text-xs leading-relaxed whitespace-pre-wrap">
            {eredmeny.sorok.join("\n") || "(nincs kimenet)"}
          </pre>
        </>
      )}
    </div>
  );
}
