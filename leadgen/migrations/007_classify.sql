-- 007_classify.sql — AI valasz-osztalyozas (6. szakasz), 2026-08-22
--
-- A `reply_events` tabla mar tudja, MI a besorolas (`classification`) es MIKOR
-- keszult (`classified_at`). Ami hianyzik, az a besorolas SZAMONKERHETOSEGE.
--
-- MIERT KELL EZ A NEGY OSZLOP, ES MIERT NEM ELEG A CIMKE ONMAGABAN:
--
-- Ez az egyetlen AI-dontes a rendszerben, aminek VISSZAFORDITHATATLAN
-- kovetkezmenye van: az `unsubscribe` es a `negative` besorolas suppressionbe
-- teszi a ceget, es onnan a lead nem jon vissza magatol. Ha fel ev mulva
-- kiderul, hogy egy modell rosszul sorolt be 30 valaszt, tudni kell:
--
--   melyik modell csinalta   -> `model`      (modellvaltasnal ez a hatarvonal)
--   mennyire volt biztos     -> `confidence` (a bizonytalanokat at lehet nezni)
--   miert dontott igy        -> `rationale`  (emberi felulvizsgalat)
--   sikerult-e egyaltalan    -> `error`      (kulonben a hibas hivas ugy nezne
--                                             ki, mint egy meg nem dolgozott sor)
--
-- Az `error` oszlop kulon fontos: nelkule egy elszallt LLM-hivas
-- megkulonboztethetetlen lenne attol a sortol, amit meg nem probaltunk
-- feldolgozni -- a kovetkezo futas ujra es ujra nekimenne ugyanannak.

alter table reply_events
  add column if not exists confidence numeric,
  add column if not exists model      text,
  add column if not exists rationale  text,
  add column if not exists error      text;

-- A feldolgozatlan sorok gyors megtalalasa. A classify batch-elve dolgozik
-- (`where classified_at is null limit N`), ugyanugy, ahogy az enrich.
create index if not exists reply_events_unclassified
  on reply_events (created_at)
  where classified_at is null;

-- ─── Az RLS a 006-ban minden tablara bekapcsolt, de a reply_events akkor
--     mar letezett. Ez csak biztositas: ha valaha ujra letrejonne, legyen rajta.
alter table reply_events enable row level security;
