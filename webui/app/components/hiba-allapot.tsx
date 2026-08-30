import { RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface HibaAllapotProps {
  uzenet: string;
  ujra?: () => void;
}

/** A hiba szovege + "Ujra" gomb (WEBUI-TERV.md F2). */
export function HibaAllapot({ uzenet, ujra }: HibaAllapotProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-destructive/50 bg-destructive/5 py-16 text-center">
      <p className="text-sm text-destructive">{uzenet}</p>
      {ujra && (
        <Button variant="outline" size="sm" onClick={ujra}>
          <RotateCw className="size-4" />
          Újra
        </Button>
      )}
    </div>
  );
}
