-- 006_unsubscribe.sql — leiratkozo link (2026-08-21)
--
-- HAROM DOLGOT CSINAL, ES MINDHAROM KELL AHHOZ, HOGY A LINK BIZTONSAGOS LEGYEN:
--
--   1. `contacts.unsub_token` -- a link azonositoja
--   2. RLS bekapcsolasa MINDEN tablan  <-- ez egy MEGLEVO LYUKAT zar be
--   3. ket `security definer` fuggveny, amit kivulrol hivni lehet
--
--
-- 1. MIERT A `contacts`-ON VAN A TOKEN, ES NEM AZ `outreach`-EN
--
-- A leiratkozas SZEMELYHEZ szol, nem kampanyhoz: aki egyszer nemet mondott,
-- annak egy fel ev mulva indulo masodik sequence-bol is ki kell maradnia.
-- Ha a token az outreach soron ulne, minden uj sequence uj tokent adna, es a
-- regi levelben levo link elavulna. Igy viszont a token a cimhez tartozik,
-- es orokre el.
--
-- Miert UUID es nem rovidebb, szebb azonosito: 122 bit veletlen -- nem
-- kitalalhato es nem vegigprobalhato. Egy rovid, olvashato kod (pl. 6 karakter)
-- eleg lenne a kenyelemhez, de barki vegigprobalhatna, es tomegesen
-- leiratkoztathatna olyanokat, akik erre nem kertek.
--
--
-- 2. RLS: EZ NEM UJ VEDELEM, HANEM EGY MEGLEVO LYUK BEZARASA
--
-- Merve 2026-08-21-en: a tablakon NEM volt bekapcsolva a row level security,
-- viszont az `anon` es `authenticated` szerepnek SELECT/INSERT/UPDATE/DELETE
-- joga volt MINDEN tablara. A Supabase ezeket a jogokat alapertelmezesben adja,
-- es RLS nelkul nincs mogottuk semmi.
--
-- Ez azt jelenti, hogy a projekt ANON KULCSAVAL barki kiolvashatta volna a
-- teljes lead-adatbazist a PostgREST API-n keresztul -- es torolhette volna.
-- Az anon kulcs pedig SZANDEKOSAN publikus: bongeszobe valo, minden Supabase
-- frontend tartalmazza. Eddig ez csak latens kockazat volt (a kulcs sehol nem
-- szerepelt), de a leiratkozo oldal pontosan egy ilyen kulcsot allitana
-- munkaba -- vagyis ez a migracio nelkul a funkcio ELESITENE a lyukat.
--
-- RLS bekapcsolva + NULLA policy = teljes tiltas az `anon`/`authenticated`
-- szerepnek. A scrapert ez NEM erinti: `postgres` szerepkorrel csatlakozik,
-- ami a tablak TULAJDONOSA, a tulajdonos pedig megkeruli az RLS-t (nincs
-- `force row level security`).
--
--
-- 3. MIERT `security definer` FUGGVENY, ES NEM KOZVETLEN TABLA-HOZZAFERES
--
-- A leiratkozo oldalnak pontosan ket dolgot kell tudnia: megnezni egy tokent,
-- es leiratkoztatni. Nem kell latnia a cegeket, a kapcsolatokat, a
-- megkereseseket. Ha tabla-jogot adnank neki, mindezt latna.
--
-- A `security definer` fuggveny a TULAJDONOS jogaival fut, tehat atlat az
-- RLS-en -- de csak azt teszi, ami bele van irva. Igy a weboldal oldalan levo
-- kulcs a legrosszabb esetben is csak annyit tud: leiratkoztatni valakit, aki
-- ervenyes tokennel rendelkezik. A teljes adatbazis nem szivarog ki vele.
--
-- A `set search_path = ''` es a teljesen minositett tablanevek (public.x) a
-- security definer fuggvenyek kotelezo ovintezkedese: e nelkul egy tamado a
-- sajat semajat a search_path elejere teve sajat `contacts` tablat tolthatna
-- a fuggveny ala.

-- ─── 1. A token ────────────────────────────────────────────────────────────
alter table contacts
  add column if not exists unsub_token uuid not null default gen_random_uuid();

create unique index if not exists contacts_unsub_token_uniq
  on contacts (unsub_token);


-- ─── 2. RLS minden tablan ──────────────────────────────────────────────────
alter table companies          enable row level security;
alter table sources            enable row level security;
alter table contacts           enable row level security;
alter table suppression        enable row level security;
alter table outreach           enable row level security;
alter table reply_events       enable row level security;
alter table feedback_watermark enable row level security;
alter table source_runs        enable row level security;
alter table schema_migrations  enable row level security;


-- ─── 3. A ket fuggveny ─────────────────────────────────────────────────────

-- OLVASAS. A megerosito oldal ezt hivja. NEM ir semmit -- ez a lenyege:
-- a level-szkennerek (Gmail, Outlook ATP, ceges proxy) automatikusan
-- LETOLTIK a linkeket. Ha a megnyitas onmagaban leiratkoztatna, a cimzettek
-- egy reszet egy robot iratna le, nemán, es soha nem derulne ki.
--
-- A cimet MASZKOLVA adja vissza (`i***@ceg.hu`): a cimzett felismeri a sajat
-- cimet, de a token -- ami naplokba, proxykba, szkennerekbe kerul -- nem
-- szivarogtat teljes email cimet annak, aki csak megtalalja.
create or replace function public.unsub_lookup(p_token uuid)
returns table (found boolean, masked_email text, company_name text, already boolean)
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  v_email   text;
  v_company text;
  v_already boolean;
begin
  select ct.email, c.company_name
    into v_email, v_company
    from public.contacts ct
    join public.companies c on c.id = ct.company_id
   where ct.unsub_token = p_token;

  if v_email is null then
    return query select false, null::text, null::text, false;
    return;
  end if;

  select exists (
    select 1 from public.suppression s
     where s.email = v_email and s.reason = 'unsubscribe'
  ) into v_already;

  return query select
    true,
    left(v_email, 1) || '***' || substring(v_email from position('@' in v_email)),
    v_company,
    v_already;
end;
$$;


-- IRAS. Csak a megerosito gomb (POST) hivja.
--
-- IDEMPOTENS: ketszer kattintva ugyanaz az eredmeny, nem hiba. A `do nothing`
-- es a statusz-feltetelek miatt a masodik hivas egyszeruen nem valtoztat semmit.
create or replace function public.unsub_confirm(p_token uuid)
returns table (found boolean, masked_email text)
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
  v_contact uuid;
  v_company uuid;
  v_email   text;
begin
  select ct.id, ct.company_id, ct.email
    into v_contact, v_company, v_email
    from public.contacts ct
   where ct.unsub_token = p_token;

  if v_contact is null then
    return query select false, null::text;
    return;
  end if;

  insert into public.suppression (email, reason, note)
       values (v_email, 'unsubscribe', 'leiratkozo link')
  on conflict (email) where email is not null do nothing;

  -- A FOLYAMATBAN LEVO MEGKERESEST LE KELL ZARNI. Enelkul a domain lock
  -- reszleges indexe (`outreach (company_id) where status in ('queued','sent')`)
  -- szerint a sequence orokre "aktiv" marad, es a ceg soha tobbe nem kaphatna
  -- uj outreach sort. Ezt a hibat a 3. szakasz eletciklus-tesztje talalta meg,
  -- es a feedback-import ugyanigy kezeli.
  update public.outreach
     set status = 'stopped'
   where contact_id = v_contact and status in ('queued', 'sent');

  update public.companies
     set status = 'suppressed',
         status_note = 'leiratkozott a linken keresztul'
   where id = v_company;

  return query select
    true,
    left(v_email, 1) || '***' || substring(v_email from position('@' in v_email));
end;
$$;


-- A `public` szerep (= barki) alol elvesszuk, es CSAK az anon/authenticated
-- kapja meg. Igy a weboldal hivhatja, de semmi mast nem er el.
revoke all on function public.unsub_lookup(uuid)  from public;
revoke all on function public.unsub_confirm(uuid) from public;
grant execute on function public.unsub_lookup(uuid)  to anon, authenticated;
grant execute on function public.unsub_confirm(uuid) to anon, authenticated;
