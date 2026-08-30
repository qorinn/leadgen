"use client";

import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

interface JsonNezoProps {
  adat: unknown;
  /** Alapertelmezetten nyitva legyen-e. */
  nyitva?: boolean;
}

/** Osszecsukhato JSON (a raw_signal-hoz, WEBUI-TERV.md F2). */
export function JsonNezo({ adat, nyitva = false }: JsonNezoProps) {
  const [kinyitva, setKinyitva] = useState(nyitva);

  return (
    <div className="rounded-md border bg-muted/30">
      <button
        type="button"
        onClick={() => setKinyitva((v) => !v)}
        className="flex w-full items-center gap-1.5 px-3 py-2 text-left text-xs font-medium text-muted-foreground hover:text-foreground"
      >
        <ChevronRight
          className={cn("size-3.5 transition-transform", kinyitva && "rotate-90")}
        />
        Nyers JSON
      </button>
      {kinyitva && (
        <pre className="overflow-x-auto border-t px-3 py-2 text-xs">
          {JSON.stringify(adat, null, 2)}
        </pre>
      )}
    </div>
  );
}
