"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { MegerositoDialog } from "@/components/megerosito-dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useMeta } from "@/lib/use-meta";
import { api, ApiError } from "@/lib/api";

interface ReviewActionsProps {
  companyId: string;
  /** Iras utan ujratoltes -- nincs optimista frissites (WEBUI-TERV.md F5). */
  onKesz: () => void;
}

// Szandekosan NEM szurjuk statusz szerint, melyik gomb jelenjen meg: a
// statusz-atmenet szabalyai a leadgen/review.py-ban (Pythonban) maradnak
// (WEBUI-TERV.md Invariansok #1). Ha egy muvelet nem ervenyes az adott
// cegre, a szerver 409-et ad, es azt mutatjuk -- nem probaljuk megjosolni.
export function ReviewActions({ companyId, onKesz }: ReviewActionsProps) {
  const { meta } = useMeta();
  // Szandekosan nincs elore kivalasztott alapertek: az elutasitas oka
  // felhasznaloi dontes, ne csusszon at csendben egy alapertelmezesen.
  const [elutasitasOk, setElutasitasOk] = useState("");
  const [hiba, setHiba] = useState<string | null>(null);

  async function jovahagy() {
    setHiba(null);
    try {
      await api.reviewApprove(companyId);
      onKesz();
    } catch (err) {
      setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
    }
  }

  async function elutasit() {
    setHiba(null);
    try {
      await api.reviewReject(companyId, elutasitasOk);
      onKesz();
    } catch (err) {
      setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <MegerositoDialog
          trigger={<Button size="sm">Jóváhagyás</Button>}
          cim="Biztosan jóváhagyod?"
          kovetkezmeny="A cég felszabadul a jelenlegi tiltás vagy visszatartás alól (akár emberi, akár automatikus döntés volt), és exportálható vagy minősítésre váró állapotba kerül."
          megerositoSzoveg="Jóváhagyom"
          onMegerosit={jovahagy}
        />
        <MegerositoDialog
          trigger={
            <Button variant="destructive" size="sm">
              Elutasítás
            </Button>
          }
          cim="Biztosan elutasítod?"
          kovetkezmeny={
            <div className="flex flex-col gap-3">
              <p>
                A cég tiltólistára kerül, és a következő exportnál kiesik a{" "}
                <code>leads.csv</code>-ből. Ha már folyamatban van a megkeresés
                (kiküldve vagy sorban áll), a hátralévő follow-upok leállnak.
              </p>
              <Select value={elutasitasOk} onValueChange={(v) => setElutasitasOk(v ?? "")}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Válassz okot…" />
                </SelectTrigger>
                <SelectContent>
                  {(meta?.suppression_okok ?? []).map((ok) => (
                    <SelectItem key={ok} value={ok}>
                      {ok}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          }
          megerositoSzoveg="Elutasítom"
          megerositoTiltva={!elutasitasOk}
          onMegerosit={elutasit}
        />
      </div>
      {hiba && <p className="text-sm text-destructive">{hiba}</p>}
    </div>
  );
}
