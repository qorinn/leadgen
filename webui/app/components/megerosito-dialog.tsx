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
  onMegerosit: () => void | Promise<void>;
}

/** Veszelyes muveletekhez, a kovetkezmeny kiirasaval (WEBUI-TERV.md F2). */
export function MegerositoDialog({
  trigger,
  cim,
  kovetkezmeny,
  megerositoSzoveg = "Megerősítem",
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
          <DialogDescription>{kovetkezmeny}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setNyitva(false)} disabled={fut}>
            Mégse
          </Button>
          <Button variant="destructive" onClick={kezeles} disabled={fut}>
            {fut ? "Folyamatban…" : megerositoSzoveg}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
