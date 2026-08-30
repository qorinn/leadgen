"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Eye, Send } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";
import { MegerositoDialog } from "@/components/megerosito-dialog";
import { UresAllapot } from "@/components/ures-allapot";
import { EloNaplo } from "@/app/futtatas/elo-naplo";
import { api, ApiError, type JobItem, type SendLevel, type SendPreview } from "@/lib/api";

/**
 * A ketlepcsos kuldes (WEBUI-TERV.md F7).
 *
 * ITT NINCS VEDELMI LOGIKA. A gomb letiltasa, a token elrejtese, a lejarat
 * visszaszamlalasa mind KENYELEM -- a tenyleges kaput a szerver
 * kenyszeriti ki: az eles kuldes elott ujra lekerdezi a tervet, ujra
 * hasheli, es elutasitja, ha barmi valtozott az elonezet ota
 * (Invariansok #2). Ha ez a komponens hibas lenne, attol meg nem menne ki
 * egyetlen level sem, amit az ember nem hagyott jova.
 */
export function KuldesFolyamat() {
  const [elonezet, setElonezet] = useState<SendPreview | null>(null);
  const [job, setJob] = useState<JobItem | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [betoltes, setBetoltes] = useState(false);

  // Ha epp fut valami (pl. egy korabban inditott kuldes), azt mutatjuk.
  useEffect(() => {
    api
      .jobCurrent()
      .then((v) => setJob(v.job))
      .catch(() => {
        // A kuldes kepernyo enelkul is hasznalhato: az elonezet sajat
        // hibauzenetet ad, ha az API nem elerheto.
      });
  }, []);

  async function elonezetKer() {
    setBetoltes(true);
    setHiba(null);
    try {
      setElonezet(await api.sendPreview());
    } catch (err) {
      setElonezet(null);
      setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
    } finally {
      setBetoltes(false);
    }
  }

  async function kuld() {
    if (!elonezet) return;
    setHiba(null);
    try {
      const valasz = await api.sendLive(elonezet.token);
      setJob(valasz.job);
      // A token EGYSZER hasznalatos -- a szerver mar elhasznalta. Az
      // elonezetet eldobjuk, hogy a kepernyo se sugallja az ellenkezojet.
      setElonezet(null);
    } catch (err) {
      setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      setElonezet(null);
    }
  }

  const jobValtozas = useCallback((frissitett: JobItem) => setJob(frissitett), []);

  return (
    <div className="flex flex-col gap-6">
      {job && (
        <section className="flex flex-col gap-2 rounded-lg border p-4">
          <h2 className="text-sm font-semibold text-muted-foreground">
            {job.fut ? "Most fut" : "Legutóbbi futás"}
          </h2>
          <EloNaplo job={job} onValtozas={jobValtozas} />
        </section>
      )}

      {hiba && (
        <Alert variant="destructive">
          <AlertTriangle />
          <AlertTitle>A küldés nem indult el</AlertTitle>
          <AlertDescription>{hiba}</AlertDescription>
        </Alert>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={elonezetKer} disabled={betoltes || (job?.fut ?? false)}>
          <Eye className="size-4" />
          {elonezet ? "Előnézet frissítése" : "Előnézet kérése"}
        </Button>
        <p className="text-sm text-muted-foreground">
          Előnézet nélkül nincs küldés — és az előnézet 10 percig érvényes.
        </p>
      </div>

      {betoltes && <Betoltes sorok={4} />}
      {elonezet && (
        <Elonezet adat={elonezet} tiltva={job?.fut ?? false} onKuld={kuld} />
      )}
    </div>
  );
}

function Elonezet({
  adat,
  tiltva,
  onKuld,
}: {
  adat: SendPreview;
  tiltva: boolean;
  onKuld: () => void | Promise<void>;
}) {
  if (adat.terv_meret === 0) {
    return (
      <UresAllapot
        cim="Ma nincs kiküldhető levél"
        lepes={
          <>
            Vagy elfogyott a mai keret ({adat.mai_keret}), vagy nincs sorban álló
            lead. Futtass egy <code>export</code>ot a Futtatás oldalon.
          </>
        }
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">Mai keret: {adat.mai_keret}</Badge>
        <Badge variant="secondary">Terv mérete: {adat.terv_meret} levél</Badge>
        <span className="text-xs text-muted-foreground">
          az előnézet érvényes eddig: {new Date(adat.lejar).toLocaleTimeString("hu-HU")}
        </span>
      </div>

      {!adat.ablak_nyitva && (
        <Alert variant="destructive">
          <AlertTriangle />
          <AlertTitle>A küldési ablak most zárva ({adat.ablak_ok})</AlertTitle>
          <AlertDescription>
            Ha most indítod, a küldő kilép anélkül, hogy bármit kiküldene. Nem
            történik baj — de nem is megy ki levél.
          </AlertDescription>
        </Alert>
      )}

      <Alert>
        <AlertTriangle />
        <AlertTitle>A védelmi kör (guards) még nem futott le</AlertTitle>
        <AlertDescription>
          Az előnézet a postafiókok olvasása nélkül készült — az írna a
          tiltólistába, egy előnézetnek pedig nem szabad írnia. Küldéskor a
          guards lefut, és <strong>szűkítheti</strong> ezt a listát: aki közben
          válaszolt, leiratkozott vagy visszapattant, kimarad.
        </AlertDescription>
      </Alert>

      <div className="flex flex-col gap-4">
        {adat.levelek.map((lv, i) => (
          <LevelKartya key={`${lv.cimzett}-${i}`} level={lv} sorszam={i + 1} />
        ))}
      </div>

      <MegerositoDialog
        trigger={
          <Button disabled={tiltva} className="self-start">
            <Send className="size-4" />
            Éles küldés ({adat.terv_meret} levél)
          </Button>
        }
        cim="Biztosan kiküldöd?"
        kovetkezmeny={
          <span className="flex flex-col gap-1">
            <span>
              <strong>{adat.terv_meret} valódi levél</strong> megy ki a fenti
              címzetteknek, a te nevedben. Ez visszafordíthatatlan.
            </span>
            <span>
              Előbb lefut a védelmi kör, ami szűkítheti a listát. A mai keret{" "}
              {adat.mai_keret} levél.
            </span>
            {!adat.ablak_nyitva && (
              <span>
                Figyelem: a küldési ablak zárva ({adat.ablak_ok}) — most nem menne
                ki semmi.
              </span>
            )}
          </span>
        }
        megerositoSzoveg="Kiküldöm"
        onMegerosit={onKuld}
      />
    </div>
  );
}

function LevelKartya({ level, sorszam }: { level: SendLevel; sorszam: number }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-muted-foreground">{sorszam}.</span>
        <span className="font-medium">{level.ceg || level.cimzett}</span>
        <code className="text-xs text-muted-foreground">{level.cimzett}</code>
        {/* A fok a szervertol jon (`sender._stage_of`) -- itt nincs
            bedrotozott lista arrol, milyen fokok leteznek. */}
        <Badge variant="outline">{level.fok}</Badge>
      </div>
      <div className="text-sm">
        <span className="text-muted-foreground">Tárgy: </span>
        <strong>{level.targy}</strong>
      </div>
      {/* A TELJES torzs, nem az elso 400 karakter (WEBUI-TERV.md F7): ez az
          utolso visszafordithato pont, itt mindent latni kell. */}
      <pre className="overflow-x-auto rounded-md border bg-muted/30 p-3 text-xs leading-relaxed whitespace-pre-wrap">
        {level.torzs}
      </pre>
    </div>
  );
}
