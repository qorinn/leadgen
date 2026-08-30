"use client";

import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** Egy riport-szekcio kartya. Ugyanaz a minta, mint a cegek/[id]/sections.tsx
 * `Szekcio`-ja -- kulon peldany, mert a ket route egymastol fuggetlen marad. */
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

/** Szo szerinti idezet kiemelt megjelenitese (ugyanaz a stilus, mint a
 * cegek/[id] reszletnezetben -- grounding: a mondat es az idezet EGYUTT). */
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
