import type { ReactNode } from "react";

interface UresAllapotProps {
  cim: string;
  /** A kovetkezo lepes leirasa, pl. egy futtatando parancs. */
  lepes?: ReactNode;
}

/** "Nincs atnezendo ceg" + a kovetkezo lepes parancsa (WEBUI-TERV.md F2). */
export function UresAllapot({ cim, lepes }: UresAllapotProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-16 text-center">
      <p className="text-sm font-medium">{cim}</p>
      {lepes && <p className="text-sm text-muted-foreground">{lepes}</p>}
    </div>
  );
}
