import { KuldesFolyamat } from "./kuldes-folyamat";
import { Mintalevel } from "./mintalevel";

export default function KuldesPage() {
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">Küldés</h1>
        <p className="text-sm text-muted-foreground">
          Két lépésben megy: előbb kérsz egy előnézetet a mai tervről, és
          elolvasod a <strong>teljes</strong> leveleket, utána indul a kiküldés.
          Ha közben bármi változik a terven — lefut egy export, elutasítasz egy
          leadet, átírsz egy sablont —, a szerver elutasítja a küldést, és új
          előnézetet kér.
        </p>
      </div>

      <KuldesFolyamat />
      <Mintalevel />
    </div>
  );
}
