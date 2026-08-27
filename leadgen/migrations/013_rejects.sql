-- 013_rejects.sql — SMTP-elutasitasok a scraper oldalan (12. szakasz), 2026-08-27
--
-- A kuldo mar naplozza az elutasitasokat (`data/rejects.csv`), es a ramp mar
-- tanul beloluk. Ami hianyzott: a SCRAPER nem latta oket.
--
-- MIERT KELL EZ A SCRAPERNEK, HA A RAMP MAR KEZELI:
--
-- A ramp a VOLUMENT szabalyozza -- osszesitve, cimzettektol fuggetlenul. A
-- scraper viszont CEGENKENT dolgozik, es egeszen mas kerdesre kell valaszolnia:
-- "ezt a cimet erdemes-e meg egyszer megprobalni?"
--
-- Egy elutasitas ket teljesen kulonbozo dolgot jelenthet:
--
--   atmeneti  -- rate limit, halozati hiba, lejart token. A cim JO, csak
--                most nem sikerult. Holnap ujra kell probalni.
--   vegleges  -- a fogado MTA policy alapjan utasitja el. Ez a cimrol szol.
--
-- Ezert taroljuk a NYERS HIBASZOVEGET is (`send_error`), nem csak a tenyt:
-- e nelkul a ket eset megkulonboztethetetlen lenne, es vagy elveszitenenk jo
-- leadeket, vagy vegtelenul probalkoznank egy halott cimen.
--
-- ─────────────────────────────────────────────────────────────────────────
-- A `send_reject_count` KUMULATIV, ES EZ SZANDEKOS.
--
-- Egyetlen elutasitas semmit nem bizonyit (a Google barmikor dobhat egy
-- atmeneti hibat). Az ISMETLODES bizonyit. A szamlalo teszi lathatova azt a
-- cimet, amelyik mar otodszor utasittatik el -- azt mar ember nezze meg.
--
-- FONTOS: a `feedback` watermarkkal dolgozik, tehat minden CSV-sort pontosan
-- egyszer olvas be. Ha a fajl megrovidul, a watermark nullazodik es ujra
-- feldolgozunk mindent -- ilyenkor a szamlalo felfele torzulna. Ezert a
-- `feedback` a szamlalot NEM inkrementalja vakon: a rejects.csv-bol szamolt
-- OSSZESITETT erteket irja be (`= %s`), nem `+ 1`-et. Ugyanaz a logika, mint
-- a `financial_bonus`-nal a 011-ben: kumulativ oszlopot sosem irunk
-- `oszlop + x` alakban, ha a forras ujraolvashato.
--
-- ─────────────────────────────────────────────────────────────────────────
-- AMI SZANDEKOSAN NINCS ITT: automatikus suppression.
--
-- Az elutasitas NEM zar ki senkit. A megorzo leadmodell (2026-08-25) szerint
-- valodi tiltas csak leiratkozas, negativ valasz, hard bounce, meglevo
-- ugyfel, kezi tiltas vagy bizonyithato versenytars lehet. Egy SMTP-hiba a
-- KULDO oldalarol szol, nem a cegrol -- suppressionbe tenni egy leadet azert,
-- mert a mi szerverunk epp limitbe utkozott, csendben megsemmisitene a listat.
-- A `send_reject_count` RANGSOROL es LATHATOVA TESZ, nem szur.

alter table contacts
  add column if not exists send_reject_count integer not null default 0,
  add column if not exists send_error        text,        -- a nyers SMTP hibauzenet
  add column if not exists send_rejected_at  timestamptz; -- az utolso elutasitas ideje

-- Az ismetelten elutasitott cimek gyors megtalalasa (`report` / kezi atnezes).
create index if not exists contacts_reject_idx on contacts (send_reject_count desc)
  where send_reject_count > 0;
