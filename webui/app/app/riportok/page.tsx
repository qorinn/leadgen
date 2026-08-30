import { BarChart } from "@/components/charts/bar-chart";
import { Bar } from "@/components/charts/bar";

// Teszt-adat -- csak az F2 ellenorzeshez (a Bklit chart-huzalozas mukodik).
// Szandekosan NEM valodi statusz-kulcsok (WEBUI-TERV.md Invariansok #1: a
// frontend nem drotozhat be uzleti listat) -- a valodi nezetek (tolcser,
// koltsegek) az F9 fazisban cerulnek le a /api/report/funnel es /api/costs
// vegpontokat.
const TESZT_ADAT = [
  { nev: "1. hét", ertek: 12 },
  { nev: "2. hét", ertek: 34 },
  { nev: "3. hét", ertek: 21 },
  { nev: "4. hét", ertek: 9 },
];

export default function RiportokPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Riportok</h1>
      <p className="text-sm text-muted-foreground">
        A tényleges nézetek (tölcsér, gazdasági érték, kampányok, költségek)
        az F9 fázisban készülnek el. Az alábbi chart teszt-adaton fut — csak
        azt igazolja, hogy a Bklit huzalozás működik.
      </p>
      <div className="max-w-2xl rounded-lg border p-4">
        <BarChart data={TESZT_ADAT} xDataKey="nev">
          <Bar dataKey="ertek" />
        </BarChart>
      </div>
    </div>
  );
}
