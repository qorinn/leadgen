"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";
import { api, ApiError, type Daily } from "@/lib/api";

// A `Daily` tipus a lib/api-types.ts-bol jon (npm run types) -- itt kezzel
// NEM definialunk API-tipust (WEBUI-TERV.md Invariansok #1/#7).

// Csak MEGJELENITESI hangsuly a riasztas-savhoz (WEBUI-TERV.md F3: "a
// megvalaszolatlan erdeklodo a legerosebb") -- a TENYLEGES dontes, hogy mi
// szamit riasztasnak, a Python `alerts.py`-ban marad. Ismeretlen tipus a
// legenyhebb (alap) hangsulyt kapja, nem tunik el.
const TIPUS_VARIANT: Record<string, "destructive" | "default"> = {
  unanswered_interested: "destructive",
};
const TIPUS_HANGSULY_OSZTALY: Record<string, string> = {
  deliverability: "border-l-4 border-l-amber-500",
};

function riasztasKora(elso: string | null | undefined): string {
  if (!elso) return "";
  const napok = Math.floor((Date.now() - new Date(elso).getTime()) / 86_400_000);
  return napok > 0 ? `  (${napok} napja)` : "  (ma)";
}

function RiasztasSav({ riasztasok }: { riasztasok: Daily["riasztasok"] }) {
  if (!riasztasok.ok) {
    return (
      <Alert variant="destructive">
        <AlertTriangle />
        <AlertTitle>Riasztások nem olvashatók</AlertTitle>
        <AlertDescription>
          {riasztasok.error} — futott már a <code>db migrate</code>?
        </AlertDescription>
      </Alert>
    );
  }
  if (riasztasok.aktiv.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      {riasztasok.aktiv.map((r) => (
        <Alert
          key={r.kulcs}
          variant={TIPUS_VARIANT[r.tipus] ?? "default"}
          className={TIPUS_HANGSULY_OSZTALY[r.tipus]}
        >
          <AlertTriangle />
          <AlertTitle>
            [{r.tipus}]{riasztasKora(r.first_seen)}
          </AlertTitle>
          <AlertDescription className="whitespace-pre-line">{r.uzenet}</AlertDescription>
        </Alert>
      ))}
      <Link href="/riasztasok" className="text-sm text-muted-foreground hover:text-foreground">
        Összes riasztás →
      </Link>
    </div>
  );
}

function MaSzekcio({ sender }: { sender: Daily["sender"] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Ma</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 text-sm">
        {sender.ok ? (
          <>
            <Sor cimke="Napi keret" ertek={sender.cap} />
            <Sor cimke="Ma már kiküldve" ertek={sender.sent_today} />
            <Sor cimke="Ma még kiküldhető" ertek={sender.remaining} />
            <Sor cimke="leads.csv sorai" ertek={sender.leads_rows} />
            {/* A bounce/reject csak nem-nulla ertekre jelenik meg -- egy
                allando "0" harom nap alatt lathatatlanna valna (report.py). */}
            {sender.bounces_today > 0 && (
              <Sor cimke="Bounce ma" ertek={sender.bounces_today} kiemelt />
            )}
            {sender.rejects_today > 0 && (
              <Sor cimke="SMTP-elutasítás ma" ertek={sender.rejects_today} kiemelt />
            )}
          </>
        ) : (
          <p className="text-sm text-destructive">
            A küldő állapota NEM OLVASHATÓ: {sender.error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function Sor({
  cimke,
  ertek,
  kiemelt,
}: {
  cimke: string;
  ertek: number;
  kiemelt?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className={kiemelt ? "text-destructive" : undefined}>{cimke}</span>
      <span className={kiemelt ? "font-medium text-destructive" : "font-medium"}>{ertek}</span>
    </div>
  );
}

function SorbanallasSzekcio({ daily }: { daily: Daily }) {
  const napok = daily.days_of_backlog;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Sorbanállás</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 text-sm">
        <Sor cimke="Sorban áll (kiment már a leads.csv-be)" ertek={daily.queued} />
        <Sor cimke="Kész, még nincs exportálva" ertek={daily.ready} />
        {napok !== null && (
          <div className="pt-2 text-sm">
            <p>
              A jelenlegi sor <strong>~{napok.toFixed(1)} napra</strong> elég (napi{" "}
              {daily.sender.ok ? daily.sender.cap : "?"} keret mellett).
            </p>
            {napok > 5 && (
              <p className="mt-1 text-muted-foreground">
                Adagolj: <code>./leadgen.sh export --limit 20</code> — a follow-up mindig
                veri a friss cold-ot ugyanabban a keretben, tehát egy nagy export nem
                gyorsít, csak várakozó sort épít.
              </p>
            )}
            {napok < 1 && (
              <p className="mt-1 text-muted-foreground">
                Fogy a sor. Új cégek:{" "}
                <code>./leadgen.sh ingest maps --max-results 100</code>
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RadVarSzekcio({ daily }: { daily: Daily }) {
  if (!daily.replied && !daily.review) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Rád vár</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 text-sm">
        {daily.replied > 0 && (
          <Link
            href="/valaszok"
            className="flex items-center justify-between rounded-md p-2 hover:bg-muted"
          >
            <span>{daily.replied} cég VÁLASZOLT — személyes válasz kell, 24 órán belül</span>
            <Badge variant="destructive">{daily.replied}</Badge>
          </Link>
        )}
        {daily.review > 0 && (
          <Link
            href="/cegek?status=review"
            className="flex items-center justify-between rounded-md p-2 hover:bg-muted"
          >
            <span>{daily.review} cég emberi döntésre vár</span>
            <Badge variant="secondary">{daily.review}</Badge>
          </Link>
        )}
      </CardContent>
    </Card>
  );
}

// F6-ig letiltva (WEBUI-TERV.md F3): a job-inditas es az elo naplo csak
// akkor jon, es addig egy aktiv gomb felrevezetne, hogy mar mukodik.
function Gyorsgombok() {
  const GOMBOK = ["Napi lánc", "Export", "Feedback", "Küldés-előnézet"];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Gyorsgombok</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        {GOMBOK.map((nev) => (
          <Button key={nev} variant="outline" size="sm" disabled title="Hamarosan (F6)">
            {nev}
            <Badge variant="secondary" className="ml-1">
              hamarosan
            </Badge>
          </Button>
        ))}
      </CardContent>
    </Card>
  );
}

export default function Home() {
  const [daily, setDaily] = useState<Daily | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .reportDaily()
      .then(setDaily)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  useEffect(betolt, [betolt]);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Irányítópult</h1>

      {hiba && <HibaAllapot uzenet={hiba} ujra={betolt} />}
      {!hiba && !daily && <Betoltes sorok={5} />}

      {daily && (
        <div className="flex flex-col gap-4">
          <RiasztasSav riasztasok={daily.riasztasok} />
          <div className="grid gap-4 md:grid-cols-2">
            <MaSzekcio sender={daily.sender} />
            <SorbanallasSzekcio daily={daily} />
          </div>
          <RadVarSzekcio daily={daily} />
          <Gyorsgombok />
        </div>
      )}
    </div>
  );
}
