"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AdatTabla } from "@/components/adat-tabla";
import { StatusBadge } from "@/components/status-badge";
import { UresAllapot } from "@/components/ures-allapot";
import { useMeta } from "@/lib/use-meta";
import { api, ApiError, type CompanyListItem } from "@/lib/api";
import { formatDatum } from "@/lib/format";
import { ReviewActions } from "./[id]/review-actions";
import { SuppressedLista } from "./suppressed-lista";

// A gazdasagi ertek (LOW/MEDIUM/HIGH) NEM a /api/meta-bol jon: ez egy fix,
// DB CHECK constraint-tel zart halmaz (leadgen/migrations/011_financials.sql
// companies_economic_value_check), nem novekvo uzleti lista, mint a
// statuszok vagy kampanyok -- a Python oldalon sincs ra kozponti nevesitett
// konstans (financials.py es report.py is nyers stringkent hasznalja).
// WEBUI-TESZTELENDO.md: F4, 2026-08-30.
const GAZDASAGI_ERTEKEK = ["LOW", "MEDIUM", "HIGH"] as const;

const MINDEN = "__minden__";

/** A ceg weboldalanak megnyithato cime.
 *
 *  A szerver az EREDETI URL-t adja (`website`), mert a forras tudja a
 *  legjobban, hol el az oldal -- de az nem mindig tartalmaz semat, es
 *  hianyozhat is. Sema nelkul a bongeszo relativ utkent ertelmezne, es a
 *  felulet sajat oldalara navigalna. */
function weboldalUrl(sor: CompanyListItem): string | null {
  const nyers = (sor.website || sor.normalized_domain || "").trim();
  if (!nyers) return null;
  return /^https?:\/\//i.test(nyers) ? nyers : `https://${nyers}`;
}

const OSZLOPOK: ColumnDef<CompanyListItem, unknown>[] = [
  {
    id: "company_name",
    accessorKey: "company_name",
    header: "Név",
    cell: ({ row }) => (
      <Link href={`/cegek/${row.original.id}`} className="font-medium hover:underline">
        {row.original.company_name || row.original.normalized_domain || "(névtelen)"}
      </Link>
    ),
  },
  {
    id: "normalized_domain",
    accessorKey: "normalized_domain",
    header: "Weboldal",
    enableSorting: false,
    cell: ({ row }) => {
      const url = weboldalUrl(row.original);
      if (!url) return "—";
      return (
        // `noopener`: a megnyitott oldal ne ferjen hozza a felulethez.
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 hover:underline"
          // A sor kattintasa a reszletes oldalra vinne -- itt a KULSO
          // oldalra megyunk, tehat a buborekolast megallitjuk.
          onClick={(e) => e.stopPropagation()}
        >
          {row.original.normalized_domain || url}
          <ExternalLink className="size-3 shrink-0 text-muted-foreground" />
        </a>
      );
    },
  },
  {
    id: "status",
    accessorKey: "status",
    header: "Státusz",
    enableSorting: false,
    cell: ({ row }) => <StatusBadge status={row.original.status} />,
  },
  {
    id: "campaign",
    accessorKey: "campaign",
    header: "Kampány",
    enableSorting: false,
    cell: ({ row }) => row.original.campaign || "—",
  },
  {
    id: "signal_score",
    accessorKey: "signal_score",
    header: "Pontszám",
    cell: ({ row }) =>
      row.original.signal_score !== null ? row.original.signal_score.toFixed(0) : "—",
  },
  {
    id: "economic_value",
    accessorKey: "economic_value",
    header: "Gazdasági érték",
    enableSorting: false,
    cell: ({ row }) =>
      row.original.economic_value ? (
        <Badge variant="secondary">{row.original.economic_value}</Badge>
      ) : (
        "—"
      ),
  },
  {
    id: "email",
    accessorKey: "email",
    header: "Email",
    enableSorting: false,
    cell: ({ row }) => row.original.email || "—",
  },
  {
    id: "updated_at",
    accessorKey: "updated_at",
    header: "Frissítve",
    cell: ({ row }) => formatDatum(row.original.updated_at) || "—",
  },
];

interface Szurok {
  status: string;
  campaign: string;
  engine: string;
  economic_value: string;
  label: string;
}

const URES_SZUROK: Szurok = {
  status: MINDEN,
  campaign: MINDEN,
  engine: MINDEN,
  economic_value: MINDEN,
  label: MINDEN,
};

function CegLista() {
  const searchParams = useSearchParams();
  const { meta } = useMeta();

  const [szurok, setSzurok] = useState<Szurok>(URES_SZUROK);
  const [kezdoSzurokBetoltve, setKezdoSzurokBetoltve] = useState(false);
  const [qNyers, setQNyers] = useState("");
  const [q, setQ] = useState("");
  const [oldal, setOldal] = useState(1);
  const [rendezes, setRendezes] = useState<SortingState>([
    { id: "signal_score", desc: true },
  ]);

  const [items, setItems] = useState<CompanyListItem[]>([]);
  const [osszesen, setOsszesen] = useState(0);
  const [betoltes, setBetoltes] = useState(true);
  const [hiba, setHiba] = useState<string | null>(null);
  // Ujratoltes-szamlalo. NEM a szurot piszkaljuk egy dontes utan: az
  // visszaugrana az elso oldalra, es egy hosszu atnezes kozben elveszne,
  // hol tartottal.
  const [frissites, setFrissites] = useState(0);
  const frissit = useCallback(() => setFrissites((n) => n + 1), []);

  // MELYIK statusznal van hatra emberi dontes, azt a SZERVER mondja meg
  // (`/api/meta` -> `dontesre_var`, forrasa a leadgen/review.py
  // DONTESRE_VARO_STATUSZOK). Itt nincs bedrotozott statuszlista
  // (WEBUI-TERV.md Invariansok #1).
  const reviewMod = useMemo(
    () =>
      (meta?.statuszok ?? []).some(
        (s) => s.dontesre_var && s.kulcs === szurok.status
      ),
    [meta, szurok.status]
  );

  // A dontesi oszlopok CSAK az emberi dontesre varo listaban jelennek meg:
  // mashol a `status_note` nem kizaro ok, a gombok pedig ertelmetlenek
  // lennenek (a szerver ugyis 409-cel utasitana el).
  const oszlopok = useMemo<ColumnDef<CompanyListItem, unknown>[]>(() => {
    if (!reviewMod) return OSZLOPOK;
    return [
      ...OSZLOPOK,
      {
        id: "status_note",
        accessorKey: "status_note",
        header: "Kizáró ok",
        enableSorting: false,
        cell: ({ row }) => (
          <span className="text-xs text-muted-foreground">
            {row.original.status_note || "—"}
          </span>
        ),
      },
      {
        id: "dontes",
        header: "Döntés",
        enableSorting: false,
        cell: ({ row }) => (
          <div onClick={(e) => e.stopPropagation()}>
            <ReviewActions companyId={String(row.original.id)} onKesz={frissit} />
          </div>
        ),
      },
    ];
  }, [reviewMod, frissit]);

  // A /cegek?status=review linket (Irányítópult "Rád vár") csak EGYSZER,
  // induláskor olvassuk be -- utána a felhasználó szűrése az igazság.
  useEffect(() => {
    const urlStatus = searchParams.get("status");
    if (urlStatus) {
      setSzurok((s) => ({ ...s, status: urlStatus }));
    }
    setKezdoSzurokBetoltve(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Kereses debounce-szal: ne kuldjunk kerest minden lenyomott billentyure.
  useEffect(() => {
    const id = setTimeout(() => setQ(qNyers), 300);
    return () => clearTimeout(id);
  }, [qNyers]);

  useEffect(() => setOldal(1), [szurok, q]);

  const lekerdezes = useMemo(
    () => ({
      status: szurok.status === MINDEN ? undefined : szurok.status,
      campaign: szurok.campaign === MINDEN ? undefined : szurok.campaign,
      engine: szurok.engine === MINDEN ? undefined : szurok.engine,
      economic_value: szurok.economic_value === MINDEN ? undefined : szurok.economic_value,
      label: szurok.label === MINDEN ? undefined : szurok.label,
      q: q || undefined,
      sort: (rendezes[0]?.id ?? "signal_score") as
        | "signal_score"
        | "company_name"
        | "updated_at",
      order: rendezes[0]?.desc === false ? ("asc" as const) : ("desc" as const),
      page: oldal,
      per_page: 50,
    }),
    [szurok, q, rendezes, oldal]
  );

  useEffect(() => {
    if (!kezdoSzurokBetoltve) return;
    setBetoltes(true);
    setHiba(null);
    api
      .companies(lekerdezes)
      .then((res) => {
        setItems(res.items);
        setOsszesen(res.total);
      })
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      })
      .finally(() => setBetoltes(false));
  }, [lekerdezes, kezdoSzurokBetoltve, frissites]);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Cégek</h1>

      <Tabs defaultValue="cegek">
        <TabsList>
          <TabsTrigger value="cegek">Cégek</TabsTrigger>
          <TabsTrigger value="auto-versenytars">Automatikusan kizárt versenytársak</TabsTrigger>
        </TabsList>

        <TabsContent value="cegek">
          <AdatTabla
            oszlopok={oszlopok}
            adat={items}
            oldal={oldal}
            oldalMeret={50}
            osszesen={osszesen}
            onOldalValtas={setOldal}
            rendezes={rendezes}
            onRendezesValtas={setRendezes}
            betoltes={betoltes}
            hiba={hiba}
            ujra={() => setSzurok((s) => ({ ...s }))}
            ures={<UresAllapot cim="Nincs a szűrésnek megfelelő cég" />}
            toolbar={
              <div className="flex flex-wrap items-end gap-3">
                <div className="flex flex-col gap-1">
                  <Label htmlFor="q">Keresés</Label>
                  <Input
                    id="q"
                    placeholder="Név vagy domain…"
                    value={qNyers}
                    onChange={(e) => setQNyers(e.target.value)}
                    className="w-48"
                  />
                </div>

                <SzuroValaszto
                  cimke="Státusz"
                  ertek={szurok.status}
                  onValtoz={(v) => setSzurok((s) => ({ ...s, status: v }))}
                  opciok={(meta?.statuszok ?? []).map((s) => ({
                    ertek: s.kulcs,
                    cimke: s.cimke,
                  }))}
                />
                <SzuroValaszto
                  cimke="Kampány"
                  ertek={szurok.campaign}
                  onValtoz={(v) => setSzurok((s) => ({ ...s, campaign: v }))}
                  opciok={(meta?.kampanyok ?? []).map((k) => ({
                    ertek: k.kulcs,
                    cimke: k.jovahagyott ? k.kulcs : `${k.kulcs} (vázlat)`,
                  }))}
                />
                <SzuroValaszto
                  cimke="Engine"
                  ertek={szurok.engine}
                  onValtoz={(v) => setSzurok((s) => ({ ...s, engine: v }))}
                  opciok={(meta?.engine_ek ?? []).map((e) => ({
                    ertek: e.kulcs,
                    cimke: e.cimke,
                  }))}
                />
                <SzuroValaszto
                  cimke="Gazdasági érték"
                  ertek={szurok.economic_value}
                  onValtoz={(v) => setSzurok((s) => ({ ...s, economic_value: v }))}
                  opciok={GAZDASAGI_ERTEKEK.map((e) => ({ ertek: e, cimke: e }))}
                />
                <SzuroValaszto
                  cimke="Címke"
                  ertek={szurok.label}
                  onValtoz={(v) => setSzurok((s) => ({ ...s, label: v }))}
                  opciok={(meta?.cimkek ?? []).map((c) => ({ ertek: c, cimke: c }))}
                />
              </div>
            }
          />
        </TabsContent>

        <TabsContent value="auto-versenytars">
          <SuppressedLista />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function SzuroValaszto({
  cimke,
  ertek,
  onValtoz,
  opciok,
}: {
  cimke: string;
  ertek: string;
  onValtoz: (ertek: string) => void;
  opciok: { ertek: string; cimke: string }[];
}) {
  return (
    <div className="flex flex-col gap-1">
      <Label>{cimke}</Label>
      <Select value={ertek} onValueChange={(v) => onValtoz(v ?? MINDEN)}>
        <SelectTrigger className="w-40">
          {/* Base UI a Select.Value-ban alapertelmezetten a NYERS erteket
              mutatja, nem a SelectItem cimkejet (csak az `items` prop
              megadasaval tenne, azt viszont nem hasznaljuk) -- ezert kell
              itt kezzel visszakeresni a cimket. */}
          <SelectValue>
            {(v: string | null) =>
              !v || v === MINDEN ? "Összes" : (opciok.find((o) => o.ertek === v)?.cimke ?? v)
            }
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={MINDEN}>Összes</SelectItem>
          {opciok.map((o) => (
            <SelectItem key={o.ertek} value={o.ertek}>
              {o.cimke}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

export default function CegekPage() {
  return (
    <Suspense>
      <CegLista />
    </Suspense>
  );
}
