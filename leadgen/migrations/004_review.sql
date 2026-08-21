-- 004_review.sql — emberi atnezesre varo allapot
--
-- MIERT KELL: a kulcsszo-alapu minosites nem tudja megkulonboztetni, hogy egy
-- kifejezes a ceg SAJAT szolgaltatas-listajaban szerepel-e, vagy csak egy
-- ugyfel-referenciaban. Merve (2026-08-21, elso eles futas): a plus-kreativ.hu
-- azert kapott "versenytars" jelolest, mert egy ugyfel-velemenyben szerepelt a
-- "webfejlesztesi feladatokat" kifejezes -- pedig jo lead lett volna.
--
-- A ket hiba ara NEM szimmetrikus:
--   hamis pozitiv (jo ugynokseget versenytarsnak veszunk) -> elveszett lead,
--       es a celcsoport veges (100-300 ceg Magyarorszagon)
--   hamis negativ (fejleszto ugynoksegnek irunk)          -> nem valaszol, ennyi
--
-- Ezert a gyenge jelek nem zarnak ki automatikusan, hanem sorba allnak
-- emberi dontesre.
alter table companies drop constraint if exists companies_status_check;

alter table companies add constraint companies_status_check check (status in (
  'new', 'enriching', 'enriched', 'scored', 'review', 'ready',
  'queued', 'sent', 'done', 'replied',
  'rejected', 'suppressed', 'error'
));
