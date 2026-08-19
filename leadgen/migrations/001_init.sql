-- 001_init.sql — a scraper alapsemaja
--
-- Forras: SCRAPER-PLAN.md adatbazis-sema fejezet + INTEGRATION-PLAN.md 1. szakasz.
-- Negy dolog van benne, amit a terv szerint SOHA nem aldozunk fel, mert utolag
-- beepiteni napokba kerulne: suppression tabla, platform blocklist (a
-- normalized_domain nullazhatosaga), status oszlop, es a forras-rogzites
-- (contacts.source_url NOT NULL).

-- ─── Segedfuggveny: updated_at karbantartasa ──────────────────────────────
-- A kesobbi webes felulet "mi valtozott" nezetehez kell, es ingyen van.
create or replace function set_updated_at() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;


-- ─── companies ────────────────────────────────────────────────────────────
create table if not exists companies (
  id                  uuid primary key default gen_random_uuid(),

  company_name        text,
  name_key            text,        -- normalizalt cegnev (fallback dedupe kulcs)
  domain              text,        -- ahogy talaltuk, nyersen
  normalized_domain   text,        -- A FO DEDUPE KULCS. NULL, ha platform-domain.
  platform_url        text,        -- facebook/wix/... ha nincs sajat domain
  tax_number          text,
  registration_number text,

  industry            text,
  city                text,
  phone               text,

  website_fit         integer,
  webapp_fit          integer,
  mobile_fit          integer,
  best_offer          text,        -- website | webapp | mobile
  campaign            text,        -- agency_partner | dead_dev | ops_pain | ...
  signal_score        numeric not null default 0,
  economic_value      text,        -- LOW | MEDIUM | HIGH

  status              text not null default 'new',
  status_note         text,
  cooldown_until      timestamptz,

  first_seen_at       timestamptz not null default now(),
  last_seen_at        timestamptz not null default now(),
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),

  constraint companies_status_check check (status in (
    'new', 'enriching', 'enriched', 'scored', 'ready',
    'queued', 'sent', 'done', 'replied',
    'rejected', 'suppressed', 'error'
  )),
  -- Kulcs nelkuli ceg nem letezhet: valamivel azonosithatonak kell lennie.
  constraint companies_has_key check (
    normalized_domain is not null or tax_number is not null or name_key is not null
  )
);

-- A fo dedupe kulcs. Reszleges index: tobb NULL (platform-only ceg) megfer.
create unique index if not exists companies_domain_uniq
  on companies (normalized_domain) where normalized_domain is not null;

create unique index if not exists companies_tax_uniq
  on companies (tax_number) where tax_number is not null;

-- Fallback kulcs: csak akkor ervenyes, ha nincs sajat domain.
create unique index if not exists companies_name_city_uniq
  on companies (name_key, city)
  where normalized_domain is null and name_key is not null and city is not null;

-- A batch-elt futasok ezen a WHERE-en jarnak (SELECT ... WHERE status=... LIMIT 50).
create index if not exists companies_status_idx on companies (status, last_seen_at);
create index if not exists companies_cooldown_idx on companies (cooldown_until)
  where cooldown_until is not null;

drop trigger if exists companies_set_updated_at on companies;
create trigger companies_set_updated_at before update on companies
  for each row execute function set_updated_at();


-- ─── sources ──────────────────────────────────────────────────────────────
-- Egy ceg tobb scraperbol is elokerulhet. Ez NEM negy lead, hanem egy lead
-- negy buying signallal. Az UNIQUE (source_type, source_url) az, ami a napi
-- futast inkrementalissa teszi: a mar latott hirdetes neman kiesik.
create table if not exists sources (
  id           uuid primary key default gen_random_uuid(),
  company_id   uuid not null references companies(id) on delete cascade,

  source_type  text not null,      -- profession_job | meta_ad | agency_seed | ...
  source_url   text not null,
  raw_signal   jsonb not null default '{}'::jsonb,

  detected_at  timestamptz not null default now(),
  created_at   timestamptz not null default now(),

  constraint sources_url_uniq unique (source_type, source_url)
);

create index if not exists sources_company_idx on sources (company_id);
-- A signal_score idofuggo lecsengesehez (SCRAPER-PLAN.md).
create index if not exists sources_detected_idx on sources (detected_at desc);


-- ─── contacts ─────────────────────────────────────────────────────────────
create table if not exists contacts (
  id                 uuid primary key default gen_random_uuid(),
  company_id         uuid not null references companies(id) on delete cascade,

  name               text,
  email              text not null,
  email_type         text,          -- personal | generic | role

  local_check        text,          -- pass | fail   (ingyenes szuro)
  local_check_reason text,
  verify_result      text,          -- valid | invalid | catch_all | unknown (Reoon)
  verified_at        timestamptz,   -- a cache ezen all: 90 napon belul nem hivunk ujra
  bounce_state       text,          -- hard_bounce | soft_bounce

  -- 0.4 JOGI MINIMUM: minden cimnel tudni kell, honnan van. Ezert NOT NULL.
  source_url         text not null,

  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),

  constraint contacts_email_uniq unique (email)
);

create index if not exists contacts_company_idx on contacts (company_id);
create index if not exists contacts_verify_idx on contacts (verify_result, verified_at);

drop trigger if exists contacts_set_updated_at on contacts;
create trigger contacts_set_updated_at before update on contacts
  for each row execute function set_updated_at();


-- ─── suppression ──────────────────────────────────────────────────────────
-- HASZNALATI SZABALY: a lead kiadasanak LEGELSO lepese egy ellenorzes erre a
-- tablara, nem az utolso. Aki itt szerepel, az sehol nem jelenik meg, akarhany
-- uj source-bol kerul elo kesobb.
-- A kuldo do-not-contact.csv-je ennek a RESZHALMAZA (csak email-szintu).
create table if not exists suppression (
  id                uuid primary key default gen_random_uuid(),

  normalized_domain text,           -- domain-szintu tiltas
  email             text,           -- vagy csak egy konkret cim
  reason            text not null,
  note              text,
  created_at        timestamptz not null default now(),

  constraint suppression_target check (normalized_domain is not null or email is not null),
  constraint suppression_reason_check check (reason in (
    'unsubscribe', 'negative_reply', 'manual_block',
    'competitor', 'existing_client', 'hard_bounce'
  ))
);

create unique index if not exists suppression_email_uniq
  on suppression (email) where email is not null;
create unique index if not exists suppression_domain_uniq
  on suppression (normalized_domain) where normalized_domain is not null and email is null;


-- ─── outreach ─────────────────────────────────────────────────────────────
create table if not exists outreach (
  id             uuid primary key default gen_random_uuid(),
  company_id     uuid not null references companies(id) on delete cascade,
  contact_id     uuid not null references contacts(id) on delete cascade,

  campaign       text not null,
  offer          text,
  status         text not null default 'queued',  -- queued|sent|done|replied|stopped
  stage          text,                            -- cold|follow_up_1|follow_up_2

  queued_at      timestamptz not null default now(),
  sent_at        timestamptz,
  replied_at     timestamptz,
  sender_account text,

  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),

  constraint outreach_status_check check (status in ('queued','sent','done','replied','stopped'))
);

-- ═══ AZ ARANYSZABALY, ADATBAZIS-SZINTEN ═══════════════════════════════════
-- "Egy domain = egy aktiv sequence." A kuldo ezt NEM tudja kifejezni: a
-- sender.build_plan dict[email] -> lead terkepet epit, a domain fogalmat nem
-- ismeri. Ezert itt kenyszeritjuk ki: egy cegnek egyszerre legfeljebb egy
-- aktiv (queued vagy sent) outreach sora lehet. Az exportalo kod is szurni
-- fog ra, de ez az a halo, amit egy kodhiba sem tud atlepni.
create unique index if not exists outreach_active_company_uniq
  on outreach (company_id) where status in ('queued', 'sent');

create index if not exists outreach_contact_idx on outreach (contact_id);
create index if not exists outreach_status_idx on outreach (status, sent_at);

drop trigger if exists outreach_set_updated_at on outreach;
create trigger outreach_set_updated_at before update on outreach
  for each row execute function set_updated_at();


-- ─── feedback_watermark ───────────────────────────────────────────────────
-- A kuldo CSV-inek inkrementalis olvasasahoz. Ettol lesz a feedback-import
-- idempotens: barmennyiszer ujrafuttathato, mindig csak az uj sorokat nezi.
create table if not exists feedback_watermark (
  file       text primary key,      -- sent.csv | do-not-contact.csv | ...
  last_ts    text,
  last_row   integer not null default 0,
  updated_at timestamptz not null default now()
);


-- ─── reply_events ─────────────────────────────────────────────────────────
-- A beerkezo valaszok szovege. A kuldo guards.py-ja eddig ELDOBTA ezt (csak
-- egy DNC-sor maradt), tehat az AI valasz-osztalyozasnak nem volt bemenete.
-- A 3. szakasz vezeti be a replies.csv-t, ez a tabla annak a celja.
create table if not exists reply_events (
  id             uuid primary key default gen_random_uuid(),
  email          text not null,
  received_at    timestamptz,
  subject        text,
  body           text,
  classification text,              -- interested|not_now|negative|unsubscribe|auto_reply|other
  classified_at  timestamptz,
  created_at     timestamptz not null default now(),

  constraint reply_events_uniq unique (email, received_at, subject)
);

create index if not exists reply_events_unclassified_idx on reply_events (created_at)
  where classification is null;
