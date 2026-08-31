"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Meta } from "@/lib/api";

// A /api/meta valtozatlan egy futas alatt (statuszok, kampanyok, stb. csak
// migracioval / deploy-jal valtoznak) -- modul-szintu gyorsitotar eleg,
// nem kell minden komponensben ujra lekerni.
let cache: Meta | null = null;
let inFlight: Promise<Meta> | null = null;

function betolt(kenyszeritett = false): Promise<Meta> {
  if (cache && !kenyszeritett) return Promise.resolve(cache);
  if (kenyszeritett) inFlight = null;
  if (!inFlight) {
    inFlight = api
      .meta()
      .then((meta) => {
        cache = meta;
        inFlight = null;
        return meta;
      })
      .catch((err: unknown) => {
        // Ha itt `inFlight` benne maradna egy ELUTASITOTT Promise-kent, a
        // KOVETKEZO betolt() -- akar egy kesobb csatlakozo komponensbol,
        // akar egy "Ujra" gombbol -- ugyanazt a regi hibat kapna vissza UJ
        // HTTP-hivas nelkul: az /api/meta kiesese igy a teljes session
        // vegeig "ragadna", meg akkor is, ha a szerver kozben visszajott.
        inFlight = null;
        throw err;
      });
  }
  return inFlight;
}

interface UseMetaResult {
  meta: Meta | null;
  betoltve: boolean;
  hiba: string | null;
  /** Ujra probalkozas /api/meta hiba utan -- MINDEN `useMeta()`-t hasznalo
   *  komponensre hat, mert a gyorsitotar modul-szintu. */
  ujra: () => void;
}

/** A /api/meta kontraktus kliens-oldali elerese (WEBUI-TERV.md Invariansok
 * #1) -- innen jon minden statusz-, kampany- es suppression-ok-cimke, soha
 * nem bedrotozva egy komponensbe. */
export function useMeta(): UseMetaResult {
  const [meta, setMeta] = useState<Meta | null>(cache);
  const [hiba, setHiba] = useState<string | null>(null);

  const probalkozik = useCallback((kenyszeritett: boolean) => {
    setHiba(null);
    betolt(kenyszeritett)
      .then(setMeta)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  useEffect(() => {
    if (cache) return;
    probalkozik(false);
  }, [probalkozik]);

  return { meta, betoltve: meta !== null, hiba, ujra: () => probalkozik(true) };
}
