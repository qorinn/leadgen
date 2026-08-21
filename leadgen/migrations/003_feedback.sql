-- 003_feedback.sql — a feedback-importhoz
--
-- A reply_events eddigi egyedi kulcsa (email, received_at, subject) gyenge:
-- a `received_at` a FELDOLGOZAS ideje volt (a guards akkor irja, amikor
-- eszreveszi), nem a level erkezese. Ket ugyanolyan targyu valasz ugyanattol
-- a feladotol ugyanabban a masodpercben utkozott volna, mig ket kulonbozo
-- feldolgozasi idovel ugyanaz a level duplikalodott volna.
--
-- A Message-ID viszont a levelhez tartozik es globalisan egyedi -- ez a
-- helyes kulcs. A guards.py mostantol ezt naplozza a replies.csv-be.
alter table reply_events add column if not exists msg_id text;

alter table reply_events drop constraint if exists reply_events_uniq;

create unique index if not exists reply_events_msg_id_uniq
  on reply_events (msg_id) where msg_id is not null;

-- A feedback-import sokat kerdez cim szerint (sent.csv / DNC / bounce sorok
-- mind email-lel joinolnak vissza).
create index if not exists contacts_email_lookup_idx on contacts (email);
