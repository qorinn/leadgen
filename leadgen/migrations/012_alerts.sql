-- 012_alerts.sql — riasztasok allapota (12. szakasz), 2026-08-27
--
-- MIERT KELL EHHEZ TABLA, HA A RIASZTAS UGYIS FAJLBA IR:
--
-- A riasztas fajlba irasa naplo, nem allapot. A 12. szakasz utan a lanc
-- NAPONTA fut magatol, es a riasztasi feltetelek tobbnaposak:
--
--   "3 napja nincs `ready` lead"
--   "egy `interested` valasz 24 oraja megvalaszolatlan"
--
-- Ezek nem egy pillanat esemenyei, hanem allapotok, amik NAPOKIG fennallnak.
-- Allapot-tarolas nelkul ugyanaz a riasztas minden reggel ujra kimenne
-- emailben, valtozatlan szoveggel. Harom nap utan a felhasznalo szurot tesz
-- ra a postafiokjaban -- es onnantol a VALODI riasztast sem latja. A
-- riasztas akkor er valamit, ha ritka; ez a tabla teszi ritkava.
--
-- ─────────────────────────────────────────────────────────────────────────
-- A `kulcs` A DEDUP EGYSEGE, es szandekosan tartalmazza a riasztas TARGYAT,
-- nem csak a tipusat:
--
--   'no_ready_leads'                     -- egy globalis allapot: egy sor
--   'unanswered_interested:<email>'      -- cimzettenkent kulon sor
--
-- Ha a masodik csak 'unanswered_interested' lenne, akkor a MASODIK
-- erdeklodo valasza elnyomva maradna, amig az elso nincs megvalaszolva --
-- vagyis pont a legertekesebb jelzest veszitenenk el.
--
-- ─────────────────────────────────────────────────────────────────────────
-- A `first_seen` / `last_seen` / `last_notified` HARMAS:
--
--   first_seen    -- mikor allt elo eloszor (ez adja a "3 napja tart" szamot)
--   last_seen     -- mikor lattuk utoljara (ha regi, az allapot megszunt)
--   last_notified -- mikor ertesitettunk rola (ez fekezi az ismetlest)
--
-- Harom kulon oszlop kell: a "mennyi ideje all fenn" es a "mikor szoltunk
-- rola utoljara" ket fuggetlen kerdes. Egyetlen idobelyeggel az egyiket
-- mindig elveszitenenk.
--
-- A `resolved_at` nem torol: a megszunt riasztas TORTENET marad. Ha egy
-- riasztas hetente visszater, azt latni kell -- egy torolt sorbol nem latszana.

create table if not exists alerts (
  kulcs         text primary key,
  tipus         text not null,          -- deliverability | no_ready_leads | unanswered_interested
  uzenet        text not null,          -- ember-olvashato szoveg (ez megy emailbe is)
  reszletek     jsonb not null default '{}'::jsonb,
  first_seen    timestamptz not null default now(),
  last_seen     timestamptz not null default now(),
  last_notified timestamptz,            -- null = meg nem ertesitettunk rola
  resolved_at   timestamptz,            -- null = meg fennall
  created_at    timestamptz not null default now()
);

-- A meg fennallo riasztasok gyors kiolvasasa (`report --daily` minden
-- futasnal ezt kerdezi, a lezartak viszont csak tortenet).
create index if not exists alerts_aktiv_idx on alerts (last_seen desc)
  where resolved_at is null;

-- ─── RLS ───────────────────────────────────────────────────────────────────
-- Ugyanaz a szabaly, mint a 006 ota minden tablan: RLS bekapcsolva, NULLA
-- policy. A Supabase `anon` szerepe igy semmit nem lat belole -- a riasztas
-- szovege ugyanis cegneveket es email-cimeket tartalmaz. A scraper
-- `postgres` szerepkorrel csatlakozik (a tabla tulajdonosa), ot ez nem
-- erinti.
alter table alerts enable row level security;
