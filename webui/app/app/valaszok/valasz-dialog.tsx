"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useMeta } from "@/lib/use-meta";
import type { Replies } from "@/lib/api";
import { formatDatum, formatSzam } from "@/lib/format";

type ReplyItem = Replies["items"][number];

/** Egy valasz teljes szovege + az AI indoklasa (WEBUI-TERV.md F8: "Reszletek:
 * a teljes szoveg es az AI indoklasa"). Kulon dialog, mert a lista-sorban
 * (subject) nincs hely a teljes levelnek. */
export function ValaszDialog({
  valasz,
  nyitva,
  onNyitvaValtoz,
}: {
  valasz: ReplyItem | null;
  nyitva: boolean;
  onNyitvaValtoz: (nyitva: boolean) => void;
}) {
  const { meta } = useMeta();
  const cimke = valasz
    ? (meta?.valasz_osztalyok.find((o) => o.kulcs === valasz.classification)?.cimke ??
      valasz.classification)
    : null;

  return (
    <Dialog open={nyitva} onOpenChange={onNyitvaValtoz}>
      <DialogContent className="max-w-lg">
        {valasz && (
          <>
            <DialogHeader>
              <DialogTitle>{valasz.subject || "(tárgy nélkül)"}</DialogTitle>
            </DialogHeader>

            <div className="flex flex-wrap items-center gap-2 text-sm">
              {valasz.company_id ? (
                <Link href={`/cegek/${valasz.company_id}`} className="font-medium hover:underline">
                  {valasz.company_name || valasz.normalized_domain}
                </Link>
              ) : (
                <span className="font-medium">{valasz.company_name || "(ismeretlen cég)"}</span>
              )}
              <span className="text-muted-foreground">{valasz.email}</span>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {cimke && <Badge variant="outline">{cimke}</Badge>}
              {valasz.confidence !== null && (
                <Badge variant="secondary">
                  bizonyosság: {formatSzam(valasz.confidence * 100, 0)}%
                </Badge>
              )}
              {valasz.error && <Badge variant="destructive">osztályozási hiba</Badge>}
              <span className="text-xs text-muted-foreground">
                {formatDatum(valasz.received_at) ?? "—"}
              </span>
            </div>

            <div className="flex flex-col gap-1">
              <p className="text-xs font-medium text-muted-foreground">Teljes szöveg</p>
              <pre className="max-h-72 overflow-auto rounded-md border bg-muted/30 p-3 text-xs whitespace-pre-wrap">
                {valasz.body || "(nincs elmentett szöveg)"}
              </pre>
            </div>

            {valasz.error ? (
              <div className="flex flex-col gap-1">
                <p className="text-xs font-medium text-muted-foreground">Hiba</p>
                <p className="text-sm text-destructive">{valasz.error}</p>
              </div>
            ) : valasz.rationale ? (
              <div className="flex flex-col gap-1">
                <p className="text-xs font-medium text-muted-foreground">
                  AI indoklása{valasz.model ? ` (${valasz.model})` : ""}
                </p>
                <p className="text-sm">{valasz.rationale}</p>
              </div>
            ) : null}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
