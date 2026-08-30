"use client";

import { useState, type ReactElement, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface MegerositoDialogProps {
  trigger: ReactElement;
  cim: string;
  /** A muvelet kovetkezmenye -- ezt mindig ki kell irni (WEBUI-TERV.md F2). */
  kovetkezmeny: ReactNode;
  megerositoSzoveg?: string;
  /** Letiltja a megerosito gombot (pl. amig a kovetkezmenyben egy kotelezo
   * mezo -- mint egy elutasitasi ok -- nincs kitoltve). */
  megerositoTiltva?: boolean;
  onMegerosit: () => void | Promise<void>;
}

/** Veszelyes muveletekhez, a kovetkezmeny kiirasaval (WEBUI-TERV.md F2). */
export function MegerositoDialog({
  trigger,
  cim,
  kovetkezmeny,
  megerositoSzoveg = "Megerősítem",
  megerositoTiltva = false,
  onMegerosit,
}: MegerositoDialogProps) {
  const [nyitva, setNyitva] = useState(false);
  const [fut, setFut] = useState(false);

  async function kezeles() {
    setFut(true);
    try {
      await onMegerosit();
      setNyitva(false);
    } finally {
      setFut(false);
    }
  }

  return (
    <Dialog open={nyitva} onOpenChange={setNyitva}>
      <DialogTrigger render={trigger} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{cim}</DialogTitle>
          {/* A DialogDescription alapbol <p>-t renderel, de a `kovetkezmeny`
              barmilyen ReactNode lehet (pl. F5: szoveg + Select egy dobozban)
              -- egy <div> vagy <p> beagyazasa egy <p>-be ervenytelen HTML-t
              es hydration-hibat adna, ezert <div>-re valtjuk a cimket. */}
          <DialogDescription render={<div />}>{kovetkezmeny}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setNyitva(false)} disabled={fut}>
            Mégse
          </Button>
          <Button variant="destructive" onClick={kezeles} disabled={fut || megerositoTiltva}>
            {fut ? "Folyamatban…" : megerositoSzoveg}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
