"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Betoltes } from "@/components/betoltes";
import { HibaAllapot } from "@/components/hiba-allapot";
import { JsonNezo } from "@/components/json-nezo";
import { StatusBadge } from "@/components/status-badge";
import { useMeta } from "@/lib/use-meta";
import { api, ApiError, type CompanyDetail } from "@/lib/api";
import { asBool, asNum, asStr, formatDatum, formatForint, formatSzam } from "@/lib/format";
import { Idezet, ListaUres, MezoGrid, Szekcio } from "./sections";

export default function CegReszletPage() {
  const { id } = useParams<{ id: string }>();
  const { meta } = useMeta();
  const [adat, setAdat] = useState<CompanyDetail | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(() => {
    setHiba(null);
    api
      .company(id)
      .then(setAdat)
      .catch((err: unknown) => {
        setHiba(err instanceof ApiError ? err.message : "Ismeretlen hiba");
      });
  }, [id]);

  useEffect(betolt, [betolt]);

  if (hiba) return <HibaAllapot uzenet={hiba} ujra={betolt} />;
  if (!adat) return <Betoltes sorok={10} />;

  const c = adat.company;
  const domain = asStr(c.normalized_domain) ?? asStr(c.domain);
  const kampanyMeta = meta?.kampanyok.find((k) => k.kulcs === c.campaign);
  const angles = adat.opportunity_angles;
  const legacyScoreVanEs =
    !angles.length &&
    (asNum(c.webapp_fit) !== null || asNum(c.website_fit) !== null || asNum(c.mobile_fit) !== null);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold">
            {asStr(c.company_name) ?? domain ?? "(névtelen cég)"}
          </h1>
          <StatusBadge status={String(c.status)} />
          {asStr(c.campaign) && (
            <Badge variant={kampanyMeta?.jovahagyott ? "default" : "outline"}>
              {asStr(c.campaign)}
              {kampanyMeta && !kampanyMeta.jovahagyott && " (vázlat)"}
            </Badge>
          )}
          {asNum(c.signal_score) !== null && (
            <Badge variant="secondary">pontszám: {formatSzam(c.signal_score)}</Badge>
          )}
        </div>
        {domain && (
          <a
            href={`https://${domain}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground hover:underline"
          >
            {domain}
            <ExternalLink className="size-3.5" />
          </a>
        )}
        {asStr(c.status_note) && (
          <p className="text-sm text-muted-foreground">{asStr(c.status_note)}</p>
        )}
      </div>

      <Szekcio cim="Alapadatok">
        <MezoGrid
          mezok={[
            { cimke: "Iparág", ertek: asStr(c.industry) },
            { cimke: "Település", ertek: asStr(c.city) },
            { cimke: "Telefon", ertek: asStr(c.phone) },
            { cimke: "Adószám", ertek: asStr(c.tax_number) },
            { cimke: "Cégjegyzékszám", ertek: asStr(c.registration_number) },
            { cimke: "Platform URL", ertek: asStr(c.platform_url) },
            { cimke: "Első látás", ertek: formatDatum(c.first_seen_at) },
            { cimke: "Utolsó látás", ertek: formatDatum(c.last_seen_at) },
            { cimke: "Cooldown eddig", ertek: formatDatum(c.cooldown_until) },
            { cimke: "Létrehozva", ertek: formatDatum(c.created_at) },
            { cimke: "Frissítve", ertek: formatDatum(c.updated_at) },
            { cimke: "Azonosító", ertek: <span className="font-mono text-xs">{String(c.id)}</span> },
          ]}
        />
      </Szekcio>

      <Szekcio cim="A levélbe menő mondat" ures={!c.personalization && !c.personalization_quote}>
        {asStr(c.personalization) && <p className="text-sm">{asStr(c.personalization)}</p>}
        {asStr(c.personalization_quote) && <Idezet>{asStr(c.personalization_quote)}</Idezet>}
      </Szekcio>

      <Szekcio
        cim="AI-szögek"
        ures={!angles.length && !legacyScoreVanEs && !asStr(c.signal_summary) && !c.evidence}
      >
        {asStr(c.signal_summary) && <p className="text-sm">{asStr(c.signal_summary)}</p>}

        {angles.length > 0 ? (
          <div className="flex flex-col gap-3">
            {angles.map((a, i) => (
              <div key={String(a.id ?? i)} className="rounded-md border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{String(a.angle_type)}</span>
                  {asNum(a.score) !== null && (
                    <Badge variant="secondary">pontszám: {formatSzam(a.score)}</Badge>
                  )}
                  {asNum(a.confidence) !== null && (
                    <Badge variant="outline">bizonyosság: {formatSzam(a.confidence, 2)}</Badge>
                  )}
                  {asBool(a.selected) && <Badge>kiválasztva</Badge>}
                  {asStr(a.model) && (
                    <span className="text-xs text-muted-foreground">{asStr(a.model)}</span>
                  )}
                </div>
                {asStr(a.pain) && <p className="mt-2 text-sm">{asStr(a.pain)}</p>}
                {asStr(a.claim) && <p className="mt-1 text-sm text-muted-foreground">{asStr(a.claim)}</p>}
                {asStr(a.quote) && (
                  <div className="mt-2">
                    <Idezet>{asStr(a.quote)}</Idezet>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : legacyScoreVanEs ? (
          <MezoGrid
            mezok={[
              { cimke: "webapp", ertek: formatSzam(c.webapp_fit) },
              { cimke: "website", ertek: formatSzam(c.website_fit) },
              { cimke: "mobile", ertek: formatSzam(c.mobile_fit) },
            ]}
          />
        ) : (
          <ListaUres szoveg="Még nincs AI-minősítés." />
        )}

        {asStr(c.score_model) && (
          <p className="text-xs text-muted-foreground">
            Modell: {asStr(c.score_model)} · minősítve: {formatDatum(c.scored_at) ?? "—"}
            {asNum(c.grounding_dropped) ? ` · eldobott irány: ${c.grounding_dropped}` : ""}
          </p>
        )}
        {!angles.length && c.evidence != null && (
          <div>
            <p className="mb-1 text-xs text-muted-foreground">
              Korábbi (legacy) evidence-adat:
            </p>
            <JsonNezo adat={c.evidence} />
          </div>
        )}
      </Szekcio>

      <Szekcio cim="Kapcsolatok">
        {adat.contacts.length ? (
          <div className="flex flex-col gap-3">
            {adat.contacts.map((k, i) => (
              <div key={String(k.id ?? i)} className="rounded-md border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{asStr(k.email) ?? "(email nélkül)"}</span>
                  {asStr(k.email_type) && <Badge variant="outline">{asStr(k.email_type)}</Badge>}
                  {asStr(k.local_check) && (
                    <Badge variant="secondary">helyi ellenőrzés: {asStr(k.local_check)}</Badge>
                  )}
                  {asStr(k.verify_result) && (
                    <Badge variant="secondary">validáció: {asStr(k.verify_result)}</Badge>
                  )}
                  {asStr(k.bounce_state) && (
                    <Badge variant="destructive">bounce: {asStr(k.bounce_state)}</Badge>
                  )}
                </div>
                <MezoGrid
                  mezok={[
                    { cimke: "Név", ertek: asStr(k.name) },
                    { cimke: "Helyi ellenőrzés oka", ertek: asStr(k.local_check_reason) },
                    { cimke: "Validálva", ertek: formatDatum(k.verified_at) },
                    { cimke: "Küldési elutasítás száma", ertek: asNum(k.send_reject_count) },
                    { cimke: "Küldési hiba", ertek: asStr(k.send_error) },
                    { cimke: "Elutasítva", ertek: formatDatum(k.send_rejected_at) },
                    {
                      cimke: "Forrás",
                      ertek: asStr(k.source_url) ? (
                        <a
                          href={asStr(k.source_url)!}
                          target="_blank"
                          rel="noreferrer"
                          className="hover:underline"
                        >
                          {asStr(k.source_url)}
                        </a>
                      ) : null,
                    },
                    { cimke: "Létrehozva", ertek: formatDatum(k.created_at) },
                  ]}
                />
              </div>
            ))}
          </div>
        ) : (
          <ListaUres szoveg="Nincs kapcsolattartó." />
        )}
      </Szekcio>

      <Szekcio
        cim="Pénzügy"
        ures={
          asNum(c.revenue) === null &&
          asNum(c.headcount) === null &&
          asNum(c.balance_total) === null &&
          asNum(c.profit) === null &&
          asNum(c.financial_year) === null &&
          asStr(c.financial_source) === null &&
          asStr(c.economic_value) === null &&
          asNum(c.financial_bonus) === null
        }
      >
        <MezoGrid
          mezok={[
            { cimke: "Árbevétel", ertek: formatForint(c.revenue) },
            { cimke: "Létszám", ertek: formatSzam(c.headcount) },
            { cimke: "Mérlegfőösszeg", ertek: formatForint(c.balance_total) },
            { cimke: "Adózott eredmény", ertek: formatForint(c.profit) },
            { cimke: "Pénzügyi év", ertek: formatSzam(c.financial_year) },
            { cimke: "Forrás", ertek: asStr(c.financial_source) },
            { cimke: "Gazdasági érték", ertek: asStr(c.economic_value) },
            { cimke: "Bónusz (signal_score-hoz)", ertek: formatSzam(c.financial_bonus) },
            { cimke: "Ellenőrizve", ertek: formatDatum(c.financials_checked_at) },
          ]}
        />
      </Szekcio>

      <Szekcio cim="Fejlesztő (8.2)" ures={!c.dev_name && !c.dev_domain && !c.dev_state}>
        <MezoGrid
          mezok={[
            { cimke: "Fejlesztő neve", ertek: asStr(c.dev_name) },
            { cimke: "Fejlesztő domainje", ertek: asStr(c.dev_domain) },
            { cimke: "Állapot", ertek: asStr(c.dev_state) },
            { cimke: "Ellenőrizve", ertek: formatDatum(c.dev_checked_at) },
          ]}
        />
        {asStr(c.dev_evidence) && <Idezet>{asStr(c.dev_evidence)}</Idezet>}
      </Szekcio>

      <Szekcio cim="Webshop (8.3)" ures={!c.webshop_platform}>
        <MezoGrid
          mezok={[
            { cimke: "Platform", ertek: asStr(c.webshop_platform) },
            { cimke: "Ellenőrizve", ertek: formatDatum(c.webshop_checked_at) },
          ]}
        />
        {asStr(c.webshop_evidence) && <Idezet>{asStr(c.webshop_evidence)}</Idezet>}
      </Szekcio>

      <Szekcio cim="Címkék">
        {adat.company_labels.length ? (
          <div className="flex flex-col gap-3">
            {adat.company_labels.map((l, i) => (
              <div key={String(l.label) + i} className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <Badge variant="outline">{String(l.label)}</Badge>
                  <span className="text-xs text-muted-foreground">
                    {formatDatum(l.created_at)}
                  </span>
                </div>
                {l.details != null && <JsonNezo adat={l.details} />}
              </div>
            ))}
          </div>
        ) : (
          <ListaUres szoveg="Nincs címke." />
        )}
      </Szekcio>

      <Szekcio cim="Outreach">
        {!adat.outreach.length && <ListaUres szoveg="Még nem indult outreach." />}
        <div className="flex flex-col gap-3">
          {adat.outreach.map((o, i) => (
            <div key={String(o.id ?? i)} className="rounded-md border p-3">
              <div className="flex flex-wrap items-center gap-2">
                {asStr(o.campaign) && <Badge variant="outline">{asStr(o.campaign)}</Badge>}
                {asStr(o.status) && <Badge variant="secondary">{asStr(o.status)}</Badge>}
                {asStr(o.stage) && <span className="text-sm">{asStr(o.stage)}</span>}
              </div>
              <MezoGrid
                mezok={[
                  { cimke: "Ajánlat", ertek: asStr(o.offer) },
                  { cimke: "Feladó fiók", ertek: asStr(o.sender_account) },
                  { cimke: "Sorba állítva", ertek: formatDatum(o.queued_at) },
                  { cimke: "Kiküldve", ertek: formatDatum(o.sent_at) },
                  { cimke: "Válasz érkezett", ertek: formatDatum(o.replied_at) },
                ]}
              />
            </div>
          ))}
        </div>
      </Szekcio>

      <Szekcio cim="Suppression" ures={!adat.suppression.length}>
        <div className="flex flex-col gap-3">
          {adat.suppression.map((s, i) => (
            <div key={String(s.id ?? i)} className="rounded-md border border-destructive/40 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="destructive">{asStr(s.reason)}</Badge>
                <span className="text-xs text-muted-foreground">
                  {formatDatum(s.created_at)}
                </span>
              </div>
              <MezoGrid
                mezok={[
                  { cimke: "Domain", ertek: asStr(s.normalized_domain) },
                  { cimke: "Email", ertek: asStr(s.email) },
                  { cimke: "Megjegyzés", ertek: asStr(s.note) },
                ]}
              />
            </div>
          ))}
        </div>
      </Szekcio>

      <Szekcio cim="Nyers források">
        {!adat.sources.length && <ListaUres szoveg="Nincs rögzített forrás." />}
        <div className="flex flex-col gap-3">
          {adat.sources.map((s, i) => (
            <div key={String(s.id ?? i)} className="flex flex-col gap-2 rounded-md border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{asStr(s.source_type)}</Badge>
                {asStr(s.processing_status) && (
                  <Badge variant="secondary">{asStr(s.processing_status)}</Badge>
                )}
                <span className="text-xs text-muted-foreground">
                  {formatDatum(s.detected_at)}
                </span>
              </div>
              {asStr(s.source_url) && (
                <a
                  href={asStr(s.source_url)!}
                  target="_blank"
                  rel="noreferrer"
                  className="w-fit text-sm hover:underline"
                >
                  {asStr(s.source_url)}
                </a>
              )}
              {asStr(s.processing_note) && (
                <p className="text-sm text-muted-foreground">{asStr(s.processing_note)}</p>
              )}
              {s.raw_signal != null && <JsonNezo adat={s.raw_signal} />}
            </div>
          ))}
        </div>
      </Szekcio>

      <Link href="/cegek" className="w-fit text-sm text-muted-foreground hover:text-foreground">
        ← Vissza a listához
      </Link>
    </div>
  );
}
