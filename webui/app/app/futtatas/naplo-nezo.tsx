"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { RotateCw } from "lucide-react";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, ApiError, type LogTail } from "@/lib/api";

// A HAROM NAPLOFAJL neve -- ezek FAJLNEVEK, nem uzleti ertekek: ugyanez a
// harom kulcs all a `webui/api/routers/logs.py` `_LOG_PATHS`-aban es az
// `api.log()` tipusaban is (WEBUI-TERV.md F6: "sender.log · alerts.log ·
// leadgen_daily.log").
const NAPLOK = [
  { kulcs: "daily" as const, cimke: "Napi lánc" },
  { kulcs: "sender" as const, cimke: "Küldés" },
  { kulcs: "alerts" as const, cimke: "Riasztások" },
];

// Ilyen surun toltjuk ujra, ha a kovetes be van kapcsolva. A naplokat nem
// mi irjuk (a launchd lanca es a kuldo teszi), ezert itt nincs mit
// streamelni -- a periodikus ujraolvasas a helyes eszkoz.
const KOVETES_MP = 3000;

/** A harom naplofajl megtekintese, kovetese es szurese (WEBUI-TERV.md F6). */
export function NaploNezo() {
  return (
    <Tabs defaultValue={NAPLOK[0].kulcs}>
      <TabsList>
        {NAPLOK.map((n) => (
          <TabsTrigger key={n.kulcs} value={n.kulcs}>
            {n.cimke}
          </TabsTrigger>
        ))}
      </TabsList>
      {NAPLOK.map((n) => (
        <TabsContent key={n.kulcs} value={n.kulcs}>
          <NaploTartalom nev={n.kulcs} />
        </TabsContent>
      ))}
    </Tabs>
  );
}

function NaploTartalom({ nev }: { nev: "sender" | "alerts" | "daily" }) {
  const [adat, setAdat] = useState<LogTail | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [szuro, setSzuro] = useState("");
  const [kovet, setKovet] = useState(false);
  const dobozRef = useRef<HTMLPreElement>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .log(nev, 2000)
      .then(setAdat)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, [nev]);

  useEffect(betolt, [betolt]);

  useEffect(() => {
    if (!kovet) return;
    const id = setInterval(betolt, KOVETES_MP);
    return () => clearInterval(id);
  }, [kovet, betolt]);

  // Kovetes kozben mindig a vegen allunk: a naplo alja az erdekes.
  useEffect(() => {
    const doboz = dobozRef.current;
    if (doboz && kovet) doboz.scrollTop = doboz.scrollHeight;
  }, [adat, kovet]);

  if (hiba) return <HibaAllapot uzenet={hiba} ujra={betolt} />;
  if (!adat) return <Betoltes sorok={6} />;

  // A SZURES A BETOLTOTT VEGERE (utolso 2000 sor) vonatkozik, nem a teljes
  // fajlra. Ezt ki is irjuk, hogy egy ures talalat ne tunjon ugy, mintha a
  // keresett sor sehol nem lenne a naploban.
  const sorok = szuro
    ? adat.lines.filter((s) => s.toLowerCase().includes(szuro.toLowerCase()))
    : adat.lines;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-3">
        <Input
          placeholder="Szűrés a betöltött sorokra…"
          value={szuro}
          onChange={(e) => setSzuro(e.target.value)}
          className="h-8 max-w-xs"
        />
        <div className="flex items-center gap-2">
          <Switch id={`kovet-${nev}`} checked={kovet} onCheckedChange={setKovet} />
          <Label htmlFor={`kovet-${nev}`} className="text-sm">
            Követés
          </Label>
        </div>
        <Button size="sm" variant="outline" onClick={betolt}>
          <RotateCw className="size-3.5" />
          Frissítés
        </Button>
        <code className="ml-auto text-xs text-muted-foreground">{adat.path}</code>
      </div>

      {!adat.exists ? (
        <p className="text-sm text-muted-foreground">
          Ez a napló még nem létezik — még nem futott, ami írná.
        </p>
      ) : (
        <>
          <p className="text-xs text-muted-foreground">
            {szuro
              ? `${sorok.length} találat a betöltött ${adat.lines.length} sorban`
              : `a napló utolsó ${adat.lines.length} sora`}
          </p>
          <pre
            ref={dobozRef}
            className="h-96 overflow-auto rounded-md border bg-muted/30 p-3 text-xs leading-relaxed whitespace-pre-wrap"
          >
            {sorok.length ? sorok.join("\n") : "(nincs találat)"}
          </pre>
        </>
      )}
    </div>
  );
}
