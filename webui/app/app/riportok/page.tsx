import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { GazdasagiErtek } from "./gazdasagi-ertek";
import { Grounding } from "./grounding";
import { Kampany } from "./kampany";
import { Koltsegek } from "./koltsegek";
import { Merofeszkozok } from "./merofeszkozok";
import { NyersNaplok } from "./nyers-naplok";
import { Tolcser } from "./tolcser";

export default function RiportokPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Riportok</h1>

      <Tabs defaultValue="tolcser">
        <TabsList>
          <TabsTrigger value="tolcser">Tölcsér</TabsTrigger>
          <TabsTrigger value="grounding">Grounding</TabsTrigger>
          <TabsTrigger value="gazdasagi-ertek">Gazdasági érték</TabsTrigger>
          <TabsTrigger value="kampany">Kampány</TabsTrigger>
          <TabsTrigger value="koltsegek">Költségek</TabsTrigger>
          <TabsTrigger value="merofeszkozok">Mérőeszközök</TabsTrigger>
          <TabsTrigger value="nyers-naplok">Nyers naplók</TabsTrigger>
        </TabsList>

        <TabsContent value="tolcser">
          <Tolcser />
        </TabsContent>
        <TabsContent value="grounding">
          <Grounding />
        </TabsContent>
        <TabsContent value="gazdasagi-ertek">
          <GazdasagiErtek />
        </TabsContent>
        <TabsContent value="kampany">
          <Kampany />
        </TabsContent>
        <TabsContent value="koltsegek">
          <Koltsegek />
        </TabsContent>
        <TabsContent value="merofeszkozok">
          <Merofeszkozok />
        </TabsContent>
        <TabsContent value="nyers-naplok">
          <NyersNaplok />
        </TabsContent>
      </Tabs>
    </div>
  );
}
