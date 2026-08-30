"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Betoltes } from "@/components/betoltes";
import { Button } from "@/components/ui/button";
import { HibaAllapot } from "@/components/hiba-allapot";
import { MegerositoDialog } from "@/components/megerosito-dialog";
import { UresAllapot } from "@/components/ures-allapot";
import { api, ApiError, type SuppressedList } from "@/lib/api";

/** Az automatikusan versenytarskent kizart cegek, felulbiralhatoan
 * (WEBUI-TERV.md F5: GET /api/review/suppressed). */
export function SuppressedLista() {
  const [adat, setAdat] = useState<SuppressedList | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .reviewSuppressed()
      .then(setAdat)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  useEffect(betolt, [betolt]);

  if (hiba) return <HibaAllapot uzenet={hiba} ujra={betolt} />;
  if (!adat) return <Betoltes sorok={5} />;
  if (!adat.items.length) {
    return <UresAllapot cim="Nincs automatikusan kizárt cég" />;
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        {adat.items.length} céget a rendszer automatikusan zárt ki versenytársként. Ha
        valamelyiket tévesnek tartod, jóváhagyással visszahozhatod.
      </p>
      {adat.items.map((c) => (
        <SuppressedSor key={c.id} ceg={c} onKesz={betolt} />
      ))}
    </div>
  );
}

function SuppressedSor({
  ceg,
  onKesz,
}: {
  ceg: SuppressedList["items"][number];
  onKesz: () => void;
}) {
  const [hiba, setHiba] = useState<string | null>(null);

  async function jovahagy() {
    setHiba(null);
    try {
      await api.reviewApprove(ceg.id);
      onKesz();
    } catch (err) {
      setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <Link href={`/cegek/${ceg.id}`} className="font-medium hover:underline">
            {ceg.company_name || ceg.normalized_domain || "(névtelen)"}
          </Link>
          {ceg.normalized_domain && (
            <span className="text-sm text-muted-foreground">{ceg.normalized_domain}</span>
          )}
          {ceg.status_note && (
            <span className="text-sm text-muted-foreground">{ceg.status_note}</span>
          )}
          {ceg.title && (
            <span className="text-xs text-muted-foreground">cím: {ceg.title}</span>
          )}
        </div>
        <MegerositoDialog
          trigger={
            <Button size="sm" variant="outline">
              Jóváhagyás
            </Button>
          }
          cim="Biztosan jóváhagyod?"
          kovetkezmeny="A cég felszabadul a versenytárs-kizárás alól, és exportálható vagy minősítésre váró állapotba kerül."
          megerositoSzoveg="Jóváhagyom"
          onMegerosit={jovahagy}
        />
      </div>
      {hiba && <p className="text-sm text-destructive">{hiba}</p>}
    </div>
  );
}
