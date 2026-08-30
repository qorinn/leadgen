"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";
import { StatusBadge } from "@/components/status-badge";
import { UresAllapot } from "@/components/ures-allapot";
import { api, ApiError, type Grounding as GroundingAdat } from "@/lib/api";
import { asNum, asStr, formatSzam } from "@/lib/format";
import { Idezet, Szekcio } from "./szekcio";

type GroundingCompany = GroundingAdat["companies"][number];

function AngleSor({ e, legacy }: { e: Record<string, unknown>; legacy: boolean }) {
  const tipus = asStr(e.angle_type) ?? asStr(e.type);
  const score = asNum(e.score);
  const claim = asStr(e.claim);
  const quote = asStr(e.quote);
  const pain = asStr(e.pain);
  const kivalasztva = e.selected === true;
  return (
    <div className="rounded-md border p-3">
      <div className="flex flex-wrap items-center gap-2">
        {tipus && <Badge variant={kivalasztva ? "default" : "outline"}>{tipus}</Badge>}
        {score !== null && <Badge variant="secondary">pontszám: {formatSzam(score)}</Badge>}
        {legacy && <span className="text-xs text-muted-foreground">régi futás</span>}
      </div>
      {pain && <p className="mt-2 text-sm text-muted-foreground">pain: {pain}</p>}
      {claim && <p className="mt-1 text-sm">{claim}</p>}
      {quote && (
        <div className="mt-2">
          <Idezet>{quote}</Idezet>
        </div>
      )}
    </div>
  );
}

function GroundingKartya({ c }: { c: GroundingCompany }) {
  return (
    <div className="flex flex-col gap-3 rounded-md border p-4">
      <div className="flex flex-wrap items-center gap-2">
        {c.id ? (
          <Link href={`/cegek/${c.id}`} className="font-medium hover:underline">
            {c.company_name || c.normalized_domain || "(névtelen)"}
          </Link>
        ) : (
          <span className="font-medium">{c.company_name || "(névtelen)"}</span>
        )}
        <StatusBadge status={c.status} />
        {c.best_offer && <Badge variant="secondary">kiemelt: {c.best_offer}</Badge>}
      </div>

      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
        <span>webapp: {formatSzam(c.scores.webapp)}</span>
        <span>website: {formatSzam(c.scores.website)}</span>
        <span>mobile: {formatSzam(c.scores.mobile)}</span>
        <span>landing_page: {formatSzam(c.scores.landing_page)}</span>
      </div>

      {c.personalization && (
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">A levélbe menő mondat</p>
          <p className="text-sm">{c.personalization}</p>
        </div>
      )}

      {c.kept.length > 0 && (
        <div className="flex flex-col gap-2">
          {c.kept.map((e, i) => (
            <AngleSor key={i} e={e} legacy={c.legacy} />
          ))}
        </div>
      )}

      {c.dropped.length > 0 && (
        <div className="flex flex-col gap-1">
          {c.dropped.map((e, i) => (
            <p key={i} className="text-xs text-muted-foreground">
              ✗ eldobva ({asStr(e.indok) ?? "?"}): „{asStr(e.quote) ?? ""}”
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

export function Grounding() {
  const [adat, setAdat] = useState<GroundingAdat | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .reportGrounding()
      .then(setAdat)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, []);

  useEffect(betolt, [betolt]);

  if (hiba) return <HibaAllapot uzenet={hiba} ujra={betolt} />;
  if (!adat) return <Betoltes sorok={8} />;

  if (!adat.total) {
    return (
      <UresAllapot
        cim="Még nem futott AI-minősítés"
        lepes="Indítsd: ./leadgen.sh score --dry"
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Szekcio cim={`Minősített cégek (${adat.total})`}>
        <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
          <span>
            kész (exportálható): <strong>{adat.ready}</strong>
          </span>
          <span>
            eldobott irány: <strong>{adat.dropped_directions}</strong>
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          Amelyik mondatot NEM küldenéd ki a saját neveddel, az bukott — akkor nem a
          modell hibás, hanem a prompt (leadgen/prompts.py).
        </p>
      </Szekcio>

      <div className="flex flex-col gap-3">
        {adat.companies.map((c) => (
          <GroundingKartya key={c.id} c={c} />
        ))}
      </div>
    </div>
  );
}
