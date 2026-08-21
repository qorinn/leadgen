-- 005_source_runs.sql — melyik lekerdezes futott mar le
--
-- MIERT KELL: minden `ingest maps` futas ujra elolrol kezdte a lekerdezeseket,
-- es a Google Maps ugyanarra a keresesre ugyanazt adja vissza. Vagyis
-- ugyanazokert a cegekert fizettunk volna ujra (~$0.005/talalat), miközben a
-- DB amugy is kiszurte oket duplikatumkent -- tehat a penz tisztan elveszett.
--
-- A `sources` tabla REKORD-szintu ismetlodest akadalyoz meg (ugyanaz a ceg
-- nem kerul be ketszer). Ez a tabla LEKERDEZES-szintu: ugyanaz a kereses nem
-- FUT LE ketszer. A ketto kulonbozo, es mindketto kell.
create table if not exists source_runs (
  id            uuid primary key default gen_random_uuid(),
  engine_key    text not null,
  actor         text not null,
  term          text not null,
  location      text not null,
  results       integer not null default 0,
  new_companies integer not null default 0,
  cost_usd      numeric,
  run_at        timestamptz not null default now(),

  constraint source_runs_uniq unique (engine_key, actor, term, location)
);

create index if not exists source_runs_engine_idx on source_runs (engine_key, run_at desc);
