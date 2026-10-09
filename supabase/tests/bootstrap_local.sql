-- LOCAL TEST DATABASE ONLY. This is a minimal Auth contract, not an Auth server.
do $$
begin
  if current_database() <> 'meal_plan_auth_test' then
    raise exception 'bootstrap_local.sql requires meal_plan_auth_test';
  end if;
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin;
  end if;
end $$;

create schema if not exists auth;
create table if not exists auth.users (
  id uuid primary key,
  email text,
  phone text,
  raw_user_meta_data jsonb,
  last_sign_in_at timestamptz
);
create or replace function auth.uid()
returns uuid language sql stable set search_path = ''
as $$ select coalesce(
  nullif(current_setting('request.jwt.claim.sub', true), ''),
  nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub'
)::uuid $$;
grant usage on schema auth, public to anon, authenticated;
grant execute on function auth.uid() to anon, authenticated;
