"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type Health } from "@/lib/api";

// A `Health` tipus a lib/api-types.ts-bol jon, amit az `npm run types`
// general az OpenAPI semabol -- itt kezzel NEM definialunk API-tipust.

function Allapot({ ok }: { ok: boolean }) {
  return (
    <Badge variant={ok ? "default" : "destructive"}>{ok ? "OK" : "HIBA"}</Badge>
  );
}

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((err) => setHiba(err.message));
  }, []);

  return (
    <div className="flex min-h-screen flex-col items-center gap-6 bg-zinc-50 p-16 dark:bg-black">
      <h1 className="text-2xl font-semibold">leadgen — irányítópult</h1>

      {hiba && (
        <Card className="w-full max-w-md border-destructive">
          <CardHeader>
            <CardTitle>Nem sikerült elérni az API-t</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            {hiba}
          </CardContent>
        </Card>
      )}

      {health && (
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Rendszerállapot</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            <div className="flex items-center justify-between">
              <span>Adatbázis ({health.db.tablak} tábla)</span>
              <Allapot ok={health.db.ok} />
            </div>
            <div className="flex items-center justify-between">
              <span>Küldő könyvtár</span>
              <Allapot ok={health.sender_dir.ok} />
            </div>
            <div className="flex items-center justify-between">
              <span>
                Migrációk ({health.migraciok.alkalmazott}, utolsó:{" "}
                {health.migraciok.utolso ?? "—"})
              </span>
              <Allapot ok={health.migraciok.alkalmazott > 0} />
            </div>
            <div className="pt-2 text-xs text-muted-foreground">
              API verzió: {health.verzio}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
