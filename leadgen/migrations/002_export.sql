-- 002_export.sql — a leads.csv exporthoz hianyzo mezok
--
-- Miert kulon fajl es nem a 001 atirasa: a 001 mar lefutott, es a db.migrate()
-- checksummal vedi. Egy alkalmazott migracio atirasa azt jelentene, hogy a te
-- gepeden mas a sema, mint barhol masutt -- ezert inkabb uj fajl.

-- A personalization KET helyen el, szandekosan:
--
--   companies.personalization -> a MUNKAVERZIO. A scoring (10. szakasz) irja,
--                                ujraszamolaskor felulirodik.
--   outreach.personalization  -> BEFAGYASZTVA a sorba allitas pillanataban.
--
-- Miert kell a befagyasztas: ha egy ceget kesobb ujra pontozunk es a mondat
-- megvaltozik, a mar futo szekvencia follow-upja mar MAS bizonyitekra
-- hivatkozna, mint a cold email, amit a cimzett kapott. Az outreach sor a
-- kikuldott uzenet allapota, tehat ott a pillanatnyi ertek a helyes.
alter table companies add column if not exists personalization text;

-- Az evidence grounding (10. szakasz) ehhez a mondathoz tartozo szo szerinti
-- idezet. Ha ez nem talalhato meg a scrapelt szovegben, a lead sablon-emailre
-- esik vissza personalization nelkul -- nem esik ki, csak nem lesz szemelyre szabva.
alter table companies add column if not exists personalization_quote text;

-- Emberi atnezesre szant osszefoglalo. Ez megy a leads.csv `notes` oszlopaba.
alter table companies add column if not exists signal_summary text;

alter table outreach add column if not exists personalization text;

-- Az exportalo a legfrissebb signal datumat irja a leads.csv `scraped_at`
-- oszlopaba. Ez a lekerdezes cegenkent egy max() a sources tablan.
create index if not exists sources_company_detected_idx
  on sources (company_id, detected_at desc);
