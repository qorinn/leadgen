-- 010_retention_and_angles.sql — adatmegorzes es kampanytol fuggetlen minosites
--
-- A forrasbol visszakapott rekord elobb adat, es csak utana lead. Emiatt egy
-- meg nem azonosithato Maps-talalat vagy hirdetes is bekerul a `sources`
-- tablaba. A kampanyalkalmassagot kulon cimkek es opportunity angle sorok
-- irjak le; egyik sem torli vagy rejti el a nyers adatot.

-- A `hold` nem tiltas. A ceg bent marad es kesobb ujraertekelheto, de addig
-- nem exportalhato (az export tovabbra is csak `ready` statuszt olvas).
alter table companies drop constraint if exists companies_status_check;
alter table companies add constraint companies_status_check check (status in (
  'new', 'enriching', 'enriched', 'scored', 'review', 'hold', 'ready',
  'queued', 'sent', 'done', 'replied',
  'rejected', 'suppressed', 'error'
));

-- A nyers forraselem cegazonositas elott is elmentheto. Ha valaha egy cegsort
-- kezzel torolnenek, a bizonyitek akkor sem tunik el vele.
alter table sources
  add column if not exists processing_status text not null default 'linked',
  add column if not exists processing_note text;

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conname = 'sources_processing_status_check'
       and conrelid = 'public.sources'::regclass
  ) then
    alter table sources add constraint sources_processing_status_check
      check (processing_status in ('discovered', 'linked', 'unmatched', 'error'));
  end if;
end $$;

alter table sources alter column company_id drop not null;
alter table sources drop constraint if exists sources_company_id_fkey;
alter table sources add constraint sources_company_id_fkey
  foreign key (company_id) references companies(id) on delete set null;

create index if not exists sources_unmatched_idx
  on sources (detected_at)
  where company_id is null;

-- Aktualis, ujraszamolhato cimkek. A details a bizonyitekot/okot tarolja, a
-- source_id pedig visszavezet a konkret hirdeteshez vagy scraper-talalathoz.
create table if not exists company_labels (
  company_id uuid not null references companies(id) on delete cascade,
  label      text not null,
  details    jsonb not null default '{}'::jsonb,
  source_id  uuid references sources(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (company_id, label)
);

create index if not exists company_labels_label_idx
  on company_labels (label, company_id);
create index if not exists company_labels_source_idx
  on company_labels (source_id) where source_id is not null;

drop trigger if exists company_labels_set_updated_at on company_labels;
create trigger company_labels_set_updated_at before update on company_labels
  for each row execute function set_updated_at();

-- Egy AI-futas tobb, egymast nem kizaro lehetoseget tarolhat. A `rank` csak
-- a jelenlegi sorrend; a kivalsztott kampanyt a selected=true jeloli.
create table if not exists opportunity_angles (
  id           uuid primary key default gen_random_uuid(),
  company_id   uuid not null references companies(id) on delete cascade,
  source_id    uuid references sources(id) on delete set null,
  rank         smallint not null,
  angle_type   text not null,
  pain         text,
  claim        text,
  quote        text,
  score        numeric not null default 0,
  confidence   numeric,
  selected     boolean not null default false,
  model        text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  constraint opportunity_angles_rank_check check (rank > 0),
  constraint opportunity_angles_score_check check (score >= 0 and score <= 100),
  constraint opportunity_angles_confidence_check check (
    confidence is null or (confidence >= 0 and confidence <= 1)
  ),
  constraint opportunity_angles_company_rank_uniq unique (company_id, rank)
);

create index if not exists opportunity_angles_company_idx
  on opportunity_angles (company_id, selected desc, rank);
create index if not exists opportunity_angles_type_idx
  on opportunity_angles (angle_type, score desc);

drop trigger if exists opportunity_angles_set_updated_at on opportunity_angles;
create trigger opportunity_angles_set_updated_at before update on opportunity_angles
  for each row execute function set_updated_at();

-- A public semaban levo uj tablak az anon/authenticated szerep szamara policy
-- nelkul elerhetetlenek. A scraper tulajdonosi adatbazis-kapcsolata tovabbra
-- is hasznalhatja oket.
alter table company_labels enable row level security;
alter table opportunity_angles enable row level security;

-- Visszamenoleges cimkezes adatvesztes nelkul.
insert into company_labels (company_id, label, details)
select id, 'domain_missing', jsonb_build_object('backfilled', true)
  from companies
 where normalized_domain is null
on conflict (company_id, label) do nothing;

insert into company_labels (company_id, label, details)
select c.id, 'contact_missing', jsonb_build_object('backfilled', true)
  from companies c
 where not exists (select 1 from contacts ct where ct.company_id = c.id)
on conflict (company_id, label) do nothing;

insert into company_labels (company_id, label, details)
select id, 'manual_review', jsonb_build_object('backfilled', true)
  from companies where status = 'review'
on conflict (company_id, label) do nothing;

-- A korabbi automatikus `rejected` nem vegleges kizaras. Ha nincs hozza
-- suppression, visszakerul ujraertekelheto `scored` allapotba; a regi ok
-- cimkekent es status_note-kent is megmarad.
insert into company_labels (company_id, label, details)
select c.id, 'legacy_rejected',
       jsonb_build_object('previous_status_note', c.status_note, 'backfilled', true)
  from companies c
 where c.status = 'rejected'
   and not exists (
     select 1 from suppression sp
      where (sp.normalized_domain is not null
             and sp.normalized_domain = c.normalized_domain)
         or (sp.email is not null and exists (
               select 1 from contacts ct
                where ct.company_id = c.id and ct.email = sp.email))
   )
on conflict (company_id, label) do nothing;

update companies c
   set status = 'scored'
 where c.status = 'rejected'
   and not exists (
     select 1 from suppression sp
      where (sp.normalized_domain is not null
             and sp.normalized_domain = c.normalized_domain)
         or (sp.email is not null and exists (
               select 1 from contacts ct
                where ct.company_id = c.id and ct.email = sp.email))
   );
