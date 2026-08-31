"use client";

import { useCallback, useEffect, useState } from "react";
import { RotateCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";
import { MegerositoDialog } from "@/components/megerosito-dialog";
import { api, ApiError, type LogTail, type ScheduleStatus } from "@/lib/api";
import { formatDatum } from "@/lib/format";

/** Az utemezett napi lanc allapota + telepites/eltavolitas (WEBUI-TERV.md
 * F10). A tenyleges launchd-muveletet a szerver vegzi (`leadgen.schedule`),
 * a gomb csak a POST-ot inditja -- ugyanaz a fuggveny all mogotte, mint a
 * CLI `schedule install`/`uninstall` mogott. */
export function Utemezes() {
  const [adat, setAdat] = useState<ScheduleStatus | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [muveletHiba, setMuveletHiba] = useState<string | null>(null);
  const [naplo, setNaplo] = useState<LogTail | null>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .scheduleStatus()
      .then(setAdat)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
    api.log("daily", 200).then(setNaplo).catch(() => undefined);
  }, []);

  useEffect(betolt, [betolt]);

  async function telepit() {
    setMuveletHiba(null);
    try {
      const eredmeny = await api.scheduleInstall();
      if (!eredmeny.ok) {
        setMuveletHiba(eredmeny.hiba ?? "A telepítés nem sikerült.");
      }
    } catch (err) {
      setMuveletHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
    } finally {
      betolt();
    }
  }

  async function eltavolit() {
    setMuveletHiba(null);
    try {
      await api.scheduleUninstall();
    } catch (err) {
      setMuveletHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
    } finally {
      betolt();
    }
  }

  if (hiba) return <HibaAllapot uzenet={hiba} ujra={betolt} />;
  if (!adat) return <Betoltes sorok={5} />;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Ütemezés — a napi lánc</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={adat.installed ? "default" : "outline"}>
            {adat.installed ? "telepítve" : "nincs telepítve"}
          </Badge>
          {adat.installed && (
            <Badge variant={adat.loaded ? "secondary" : "destructive"}>
              {adat.loaded ? "betöltve" : "nincs betöltve"}
            </Badge>
          )}
          <span className="text-sm text-muted-foreground">
            indulás: minden nap {adat.start_time}
          </span>
        </div>

        {adat.launchctl_lines.length > 0 && (
          <div className="flex flex-col gap-1 text-xs text-muted-foreground">
            {adat.launchctl_lines.map((sor) => (
              <code key={sor}>{sor}</code>
            ))}
          </div>
        )}

        <div className="flex items-center gap-2">
          {!adat.installed ? (
            <MegerositoDialog
              trigger={<Button size="sm">Telepítés</Button>}
              cim="Biztosan telepíted az ütemezést?"
              kovetkezmeny="A napi lánc (gyűjtés, feldolgozás, átadás) minden nap 07:30-kor magától elindul, launchd-bejegyzésként. A küldés (sender.py --live) és az esti jelentés (deliverability.py) ettől függetlenül kézi marad."
              megerositoSzoveg="Telepítem"
              onMegerosit={telepit}
            />
          ) : (
            <MegerositoDialog
              trigger={
                <Button size="sm" variant="destructive">
                  Eltávolítás
                </Button>
              }
              cim="Biztosan eltávolítod az ütemezést?"
              kovetkezmeny="A napi lánc többé nem indul el magától. Kézzel továbbra is futtatható: ./leadgen.sh daily."
              megerositoSzoveg="Eltávolítom"
              onMegerosit={eltavolit}
            />
          )}
          <Button size="sm" variant="outline" onClick={betolt}>
            <RotateCw className="size-3.5" />
            Frissítés
          </Button>
        </div>

        {muveletHiba && <p className="text-sm text-destructive">{muveletHiba}</p>}

        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium text-muted-foreground">
            leadgen_daily.log{" "}
            {naplo?.exists && formatDatum(adat.log_last_written)
              ? `— utoljára írva: ${formatDatum(adat.log_last_written)}`
              : ""}
          </p>
          {naplo && naplo.exists ? (
            <pre className="h-48 overflow-auto rounded-md border bg-muted/30 p-3 text-xs leading-relaxed whitespace-pre-wrap">
              {naplo.lines.length ? naplo.lines.join("\n") : "(üres napló)"}
            </pre>
          ) : (
            <p className="text-sm text-muted-foreground">
              Ez a napló még nem létezik — a lánc még nem futott.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
