"use client";

import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface MezoDef {
  cimke: string;
  ertek: ReactNode;
}

function vanErteke(ertek: ReactNode): boolean {
  return ertek !== null && ertek !== undefined && ertek !== "";
}

/** Egy szekcio-kartya. Ha nincs egyetlen megjelenitheto gyereke sem (pl. az
 * osszes mezo null), ne foglaljon helyet -- a WEBUI-TERV.md F4 "minden
 * mezo, ami nem null" kovetelmenye nem azt jelenti, hogy ures dobozokat is
 * mutassunk. */
export function Szekcio({
  cim,
  ures,
  children,
}: {
  cim: string;
  ures?: boolean;
  children: ReactNode;
}) {
  if (ures) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{cim}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">{children}</CardContent>
    </Card>
  );
}

/** Mezo-racs: csak a NEM-URES ertekeket rendereli (WEBUI-TERV.md F4
 * ellenorzese: "minden mezo, ami a DB-ben nem null, jelenjen meg valahol"
 * -- a null mezok viszont nem torlodnek fel feleslegesen). */
export function MezoGrid({ mezok }: { mezok: MezoDef[] }) {
  const lathatok = mezok.filter((m) => vanErteke(m.ertek));
  if (!lathatok.length) return null;
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
      {lathatok.map((m) => (
        <div key={m.cimke} className="flex flex-col gap-0.5">
          <dt className="text-xs text-muted-foreground">{m.cimke}</dt>
          <dd className="text-sm break-words">{m.ertek}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Szo szerinti idezet kiemelt megjelenitese (WEBUI-TERV.md F4: "a szo
 * szerinti idezetek kiemelten jelenjenek meg... ne roviditsd le oket"). */
export function Idezet({ children }: { children: ReactNode }) {
  return (
    <blockquote className="border-l-2 border-l-amber-500 bg-muted/40 py-1 pl-3 text-sm italic">
      „{children}”
    </blockquote>
  );
}

export function ListaUres({ szoveg }: { szoveg: string }) {
  return <p className="text-sm text-muted-foreground">{szoveg}</p>;
}
