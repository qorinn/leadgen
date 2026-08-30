"use client";

import { Badge } from "@/components/ui/badge";
import { useMeta } from "@/lib/use-meta";

// Ciklikus szinsor a status "sorrend" mezojebol -- NEM statusz-kulcs szerint
// van drotozva (pl. egy adott statuszhoz mindig ugyanaz a zold), mert az mar
// uzleti jelentes lenne a frontendben. A sorrend csak a megjeleniteshez
// szamit, hogy a tolcser egymast koveto fokai vizualisan is kulonbozzenek.
const SZIN_CIKLUS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

interface StatusBadgeProps {
  /** A companies.status erteke (statuszok.kulcs a /api/meta-ban). */
  status: string;
}

/** A cimke es a szin a /api/meta "statuszok" listajabol jon -- soha nem
 * bedrotozva (WEBUI-TERV.md Invariansok #1). Ha egy statusz nincs a
 * listaban (pl. ismeretlen/hibas adat), a nyers kulcsot mutatja szin
 * nelkul. */
export function StatusBadge({ status }: StatusBadgeProps) {
  const { meta } = useMeta();
  const bejegyzes = meta?.statuszok.find((s) => s.kulcs === status);

  if (!bejegyzes) {
    return <Badge variant="outline">{status}</Badge>;
  }

  const szin = SZIN_CIKLUS[bejegyzes.sorrend % SZIN_CIKLUS.length];

  return (
    <Badge variant="outline" className="gap-1.5">
      <span
        className="size-1.5 rounded-full"
        style={{ backgroundColor: szin }}
        aria-hidden
      />
      {bejegyzes.cimke}
    </Badge>
  );
}
