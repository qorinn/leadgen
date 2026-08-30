import { Skeleton } from "@/components/ui/skeleton";

interface BetoltesProps {
  sorok?: number;
}

/** Skeleton, nem porgo ikon (WEBUI-TERV.md F2). */
export function Betoltes({ sorok = 3 }: BetoltesProps) {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: sorok }).map((_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  );
}
