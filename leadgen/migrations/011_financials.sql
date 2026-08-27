-- 011_financials.sql — 7.1 e-beszamolo (penzugyi adat) + 8.3 webshop kinoves
--
-- KET DOLOG KERUL BE, ES MINDKETTO TENY, NEM AI-TIPP:
--
--   1. penzugyi adat  -- arbevetel, letszam, merlegfoosszeg, eredmeny
--   2. webshop platform -- a sajat weboldal HTML-jebol, bizonyitekkal
--
-- MIERT NEM ELEG AZ `economic_value` OSZLOP ONMAGABAN (az mar 001 ota megvan):
-- mert egy cimke nem szamonkerheto. Ha fel ev mulva kiderul, hogy egy ceget
-- rosszul soroltunk HIGH-ba, tudni kell, MIBOL:
--
--   revenue / headcount / balance_total / profit -- a nyers szamok
--   financial_year                              -- MELYIK EV beszamoloja
--   financial_source                            -- honnan van (kezi? import?)
--   financials_checked_at                       -- mikor neztuk meg
--
-- A `financial_year` kulon fontos: egy 2019-es beszamolobol szarmazo
-- "magas arbevetel" 2026-ban mar nem bizonyit semmit, es enelkul az oszlop
-- nelkul ez a kulonbseg lathatatlan lenne.
--
-- ─────────────────────────────────────────────────────────────────────────
-- A `financial_bonus` AZ IDEMPOTENCIA MIATT VAN, NEM RIPORTOLASI CELBOL.
--
-- A `signal_score` kumulativ oszlop: a pipeline `signal_score + 15` alakban
-- ir bele. Ha a penzugyi bonuszt is igy adnank hozza, MINDEN ujrafuttatas
-- ujra hozzaadna -- ugyanaz a ceg ket import utan 30 pontot kapna 15 helyett,
-- es a rangsor csendben elromlana. Ezert a mar alkalmazott bonuszt taroljuk,
-- es minden ujraszamolas `signal_score - regi_bonusz + uj_bonusz` alakban ir.
--
-- ─────────────────────────────────────────────────────────────────────────
-- A `webshop_evidence` UGYANAZ A SZEREP, MINT A `dev_evidence` A 8.2-BEN:
-- a nyers, szo szerinti bizonyitek, amit EMBER nez at. A 8.3 talalat ugyanis
-- bekerul a levelbe ("lattam, hogy a webshopotok Shoprenteren fut") -- ha ez
-- teved, az nem apro pontatlansag, hanem azonnal hiteltelen.

alter table companies
  add column if not exists revenue               numeric,      -- ertekesites netto arbevetele, FORINTBAN
  add column if not exists headcount             integer,      -- atlagos statisztikai allomanyi letszam
  add column if not exists balance_total         numeric,      -- merlegfoosszeg, forintban
  add column if not exists profit                numeric,      -- adozott eredmeny, forintban
  add column if not exists financial_year        integer,      -- melyik uzleti ev beszamoloja
  add column if not exists financial_source      text,         -- manual | csv_import | api:<nev>
  add column if not exists financials_checked_at timestamptz,
  add column if not exists financial_bonus       numeric not null default 0,
  add column if not exists webshop_platform      text,         -- Shoprenter | Unas | Shopify | ...
  add column if not exists webshop_evidence      text,         -- a SZO SZERINTI markerek a HTML-bol
  add column if not exists webshop_checked_at    timestamptz;

-- Az `economic_value` 001 ota letezik, de eddig barmit el lehetett volna benne
-- tarolni. Egy elgepelt ertek csendben kiesne minden riportbol.
do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conname = 'companies_economic_value_check'
       and conrelid = 'public.companies'::regclass
  ) then
    alter table companies add constraint companies_economic_value_check
      check (economic_value is null or economic_value in ('LOW', 'MEDIUM', 'HIGH'));
  end if;
end $$;

-- Az arbevetel FORINTBAN ertendo, nem ezer forintban. A beszamolo urlapjai
-- "adatok E Ft-ban" formaban jelennek meg, tehat ez a leggyakoribb elirasi
-- hiba -- ezret ir be valaki millio helyett, es a ceg csendben LOW lesz.
-- Az importer figyelmeztet ra; itt csak a nyilvanvalo keptelenseget zarjuk ki.
do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conname = 'companies_revenue_check'
       and conrelid = 'public.companies'::regclass
  ) then
    alter table companies add constraint companies_revenue_check
      check (revenue is null or revenue >= 0);
  end if;
end $$;

-- A batch-elt futas ezen jar: "a legjobb N lead, amit meg nem neztunk meg".
create index if not exists companies_financials_unchecked
  on companies (signal_score desc)
  where financials_checked_at is null;

create index if not exists companies_economic_idx
  on companies (economic_value) where economic_value is not null;

-- A 8.3 metszet lekerdezese (dobozos platform + arbevetel).
create index if not exists companies_webshop_idx
  on companies (webshop_platform) where webshop_platform is not null;
