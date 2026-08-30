import { FinancialsWorklist } from "./financials-worklist";

export default function BeallitasokPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Beállítások</h1>
      <p className="text-sm text-muted-foreground">
        Az ütemezés- és a maszkolt beállítás-nézet az F10 fázisban készül el.
      </p>

      <FinancialsWorklist />
    </div>
  );
}
