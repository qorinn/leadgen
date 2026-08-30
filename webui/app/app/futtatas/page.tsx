import { NaploNezo } from "./naplo-nezo";
import { ParancsKatalogus } from "./parancs-katalogus";

export default function FuttatasPage() {
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">Futtatás</h1>
        <p className="text-sm text-muted-foreground">
          Egyszerre egy futás mehet. A fizetős parancsok csak megerősítés után indulnak
          el, a becsült költséggel együtt. A kiküldést (<code>sender.py --live</code>)
          nem innen indítod — az a Küldés oldalon, két lépésben megy.
        </p>
      </div>

      <ParancsKatalogus />

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-muted-foreground">Naplók</h2>
        <NaploNezo />
      </section>
    </div>
  );
}
