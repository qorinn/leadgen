"use client";

import { useEffect, useState } from "react";
import { api, ApiError, type Meta } from "@/lib/api";

// A /api/meta valtozatlan egy futas alatt (statuszok, kampanyok, stb. csak
// migracioval / deploy-jal valtoznak) -- modul-szintu gyorsitotar eleg,
// nem kell minden komponensben ujra lekerni.
let cache: Meta | null = null;
let inFlight: Promise<Meta> | null = null;

function betolt(): Promise<Meta> {
  if (cache) return Promise.resolve(cache);
  if (!inFlight) {
    inFlight = api.meta().then((meta) => {
      cache = meta;
      inFlight = null;
      return meta;
    });
  }
  return inFlight;
}

interface UseMetaResult {
  meta: Meta | null;
  betoltve: boolean;
  hiba: string | null;
}

/** A /api/meta kontraktus kliens-oldali elerese (WEBUI-TERV.md Invariansok
 * #1) -- innen jon minden statusz-, kampany- es suppression-ok-cimke, soha
 * nem bedrotozva egy komponensbe. */
export function useMeta(): UseMetaResult {
  const [meta, setMeta] = useState<Meta | null>(cache);
  const [hiba, setHiba] = useState<string | null>(null);

  useEffect(() => {
    if (cache) return;
    betolt()
      .then(setMeta)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  return { meta, betoltve: meta !== null, hiba };
}
