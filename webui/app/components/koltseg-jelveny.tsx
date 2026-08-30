import { Badge } from "@/components/ui/badge";

interface KoltsegJelvenyProps {
  /** Becsult koltseg USD-ben, pl. 0.22. */
  usd: number;
}

function formatUsd(usd: number): string {
  // Magyar tizedesvesszo, de a "$" jel marad -- ez penzosszeg, nem
  // lokalizalt penznem-formazas (a rendszer minden ara USD, lasd
  // leadgen/pricing.py).
  const formazott = usd.toLocaleString("hu-HU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `~$${formazott}`;
}

/** "~$0,22" -- fizetos muveletek melle (WEBUI-TERV.md F2). */
export function KoltsegJelveny({ usd }: KoltsegJelvenyProps) {
  return (
    <Badge variant="secondary" title="Becsült költség">
      {formatUsd(usd)}
    </Badge>
  );
}
