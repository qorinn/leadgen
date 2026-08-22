-- 008_dead_dev.sql — 8.2 "halott fejleszto" enrichment, 2026-08-22
--
-- MIERT KELL OT OSZLOP EGY IGEN/NEM KERDESHEZ:
--
-- A terv kemeny szabalya erre a signalra: "Ha a footer-kredit nem egyertelmu,
-- a lead inkabb essen ki, mint hogy ROSSZ NEVET IRJ EGY EMAILBE." A levelben
-- ugyanis szo szerint szerepelni fog a fejleszto neve:
--
--     "...feltunt, hogy a weboldalukat annak idejen az XY keszitette.
--      Ugy tunik, ok mar nem mukodnek."
--
-- Ha ez teved, az nem apro pontatlansag, hanem kinos. Ezert nem eleg tudni,
-- hogy DEAD -- azt is tudni kell, MIBOL gondoljuk:
--
--   dev_domain      -- kire mutatott a footer linkje
--   dev_name        -- milyen neven (ez megy majd a levelbe)
--   dev_state       -- DEAD | DORMANT | ALIVE
--   dev_evidence    -- a footer SZO SZERINTI szovege  <-- ezt nezi at az ember
--   dev_checked_at  -- mikor neztuk (batch-eles + ujrafuttathatosag)
--
-- A `dev_evidence` teszi emberileg ellenorizhetove a dontest: a felhasznalo
-- 10 talalatot atnez, es latja a nyers footer-szoveget, nem csak egy cimket.
--
-- A `dev_checked_at` a batch-eles kulcsa: az enrichment `where dev_checked_at
-- is null limit N` szerint dolgozik, ugyanugy, ahogy a tobbi lepes a `status`
-- oszlopbol. Egy megszakadt futas igy folytathato, nem kezdi elolrol.

alter table companies
  add column if not exists dev_domain     text,
  add column if not exists dev_name       text,
  add column if not exists dev_state      text,
  add column if not exists dev_evidence   text,
  add column if not exists dev_checked_at timestamptz;

-- Csak a harom ervenyes allapot (vagy null). Egy elgepelt allapot csendben
-- kiesne a riportbol, es senki nem venne eszre.
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'companies_dev_state_check') then
    alter table companies add constraint companies_dev_state_check
      check (dev_state is null or dev_state in ('DEAD', 'DORMANT', 'ALIVE'));
  end if;
end $$;

-- A meg nem vizsgalt cegek gyors megtalalasa (batch-elt futas).
create index if not exists companies_dev_unchecked
  on companies (first_seen_at)
  where dev_checked_at is null;

-- A DEAD talalatok kilistazasa emberi atnezeshez.
create index if not exists companies_dev_state
  on companies (dev_state) where dev_state is not null;
