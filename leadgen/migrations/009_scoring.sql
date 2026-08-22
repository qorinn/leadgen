-- 009_scoring.sql — AI-minosites + evidence grounding (10. szakasz), 2026-08-22
--
-- HAROM FIT-PONTSZAM, MERT EGY CEG EGY KAMPANYBA KERUL (offer arbitration).
-- A terv pelda: website_fit=75, webapp_fit=92, mobile_fit=38 -> a ceg a
-- WEBAPP kampanyba kerul, es NEM kap masnap "weboldalt keszitek" levelet is.
-- Ehhez mindharom erteket kulon kell tarolni, kulonben nem lehet donteni.
--
-- AZ `evidence` OSZLOP A HITELESSEGI NYOMVONAL. Nem diszites: ebben marad
-- meg, hogy az AI MIBOL kovetkeztetett, szo szerinti idezettel. Ha valaha
-- kiderul, hogy egy level teves allitast tartalmazott, ebbol lehet
-- visszakovetni, hol romlott el -- a modellnel, a promptnal, vagy a
-- forrasszovegnel.
--
-- A `grounding_dropped` azt szamolja, hany allitast DOBTUNK EL, mert az
-- idezete nem volt megtalalhato a forrasban. Ez a hallucinacio-merooszam:
-- ha az aranya 20% fole megy, a modell talal ki dolgokat, es vissza kell
-- terni a bake-offhoz.

alter table companies
  add column if not exists webapp_fit        numeric,
  add column if not exists website_fit       numeric,
  add column if not exists mobile_fit        numeric,
  add column if not exists evidence          jsonb,
  add column if not exists scored_at         timestamptz,
  add column if not exists score_model       text,
  add column if not exists grounding_dropped integer not null default 0;

-- A meg nem pontozott cegek gyors megtalalasa (batch-elt futas).
create index if not exists companies_unscored
  on companies (first_seen_at) where scored_at is null;
