import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BeallitasokLista } from "./beallitasok-lista";
import { Diagnosztika } from "./diagnosztika";
import { FinancialsWorklist } from "./financials-worklist";
import { Utemezes } from "./utemezes";

export default function BeallitasokPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Beállítások</h1>

      <Tabs defaultValue="utemezes">
        <TabsList>
          <TabsTrigger value="utemezes">Ütemezés</TabsTrigger>
          <TabsTrigger value="beallitasok">Beállítások</TabsTrigger>
          <TabsTrigger value="diagnosztika">Diagnosztika</TabsTrigger>
          <TabsTrigger value="penzugyi">Pénzügyi worklist</TabsTrigger>
        </TabsList>

        <TabsContent value="utemezes">
          <Utemezes />
        </TabsContent>
        <TabsContent value="beallitasok">
          <BeallitasokLista />
        </TabsContent>
        <TabsContent value="diagnosztika">
          <Diagnosztika />
        </TabsContent>
        <TabsContent value="penzugyi">
          <FinancialsWorklist />
        </TabsContent>
      </Tabs>
    </div>
  );
}
