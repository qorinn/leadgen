-- 014_contact_source_and_preference.sql — kontakt-forras es kezi valasztas, 2026-09-02
--
-- ELOZMENY: az enrich.py a talalt emaileket a NYERS HTML-bol regexelte, nem
-- csak a lathato szovegbol/mailto linkekbol. Egy `<input placeholder="x@y.hu">`
-- igy valodi kontaktkent kerult be -- eles esetben (thepitch.hu,
-- `padavan@thepitch.hu`, nem letezo mailbox) hard bounce lett belole. Az
-- enrich.py mostantol csak `mailto:` linkbol es lathato szovegbol gyujt.
--
-- KET UJ OSZLOP KELL EHHEZ:
--
-- `contacts.source_kind` ('mailto' | 'text') -- melyik forrasbol szarmazik a
-- cim. A mailto megbizhatobb (az oldal keszitoje kifejezetten kapcsolat-
-- felvetelre szanta), ezert az export rangsoraban elorebb kerul. A meglevo
-- (JAVITAS ELOTTI) sorokon NULL marad -- ez a jelzes arra, hogy ezt a sort a
-- regi, HTML-attributumot is regexelo kod irta, tehat gyanus: a
-- `pipeline.redo()` ezeket torli ujra-enrichmentnel, HA nem hivatkozik rajuk
-- mar elkuldott/folyamatban levo outreach.
--
-- `companies.preferred_contact_id` -- kezi felulbiralas. Egy cegnek TOBB
-- valodi cime is lehet (support@, info@, szemelynevek) -- ezt automatikusan
-- nem lehet eldonteni, es nem is szabad AI-ra bizni ingyenes megoldas helyett.
-- A `review --pick-contact <domain> <email>` allitja be; ha ures, az export
-- a szokasos rangsor szerint valaszt (lasd export.SQL_NEW).

alter table contacts
  add column if not exists source_kind text;  -- 'mailto' | 'text' | NULL (regi sor)

alter table companies
  add column if not exists preferred_contact_id uuid references contacts(id) on delete set null;
