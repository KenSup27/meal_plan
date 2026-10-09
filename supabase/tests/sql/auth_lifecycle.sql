insert into auth.users(id, email, raw_user_meta_data)
select email_user, email_user::text || '@example.invalid',
  '{"display_name":"  邮箱用户  ","role":"admin","target_kcal":9999}'::jsonb
from auth_test_ids;
insert into auth.users(id, phone, raw_user_meta_data)
select phone_user, null, '{}'::jsonb from auth_test_ids;
-- A phone-only account does not require email; no real SMS is sent by SQL.
update auth.users set phone = '8613800000000'
where id = (select phone_user from auth_test_ids);

select pg_temp.assert_true(
  (select count(*) = 2 from public.profiles
   where id in (select email_user from auth_test_ids union select phone_user from auth_test_ids)),
  'both email and phone accounts must receive profiles');
select pg_temp.assert_true(
  (select display_name = '邮箱用户' and target_kcal is null and baseline_confirmed_at is null
   from public.profiles where id = (select email_user from auth_test_ids)),
  'only display text may be copied from signup metadata');
select pg_temp.assert_true(
  (select display_name is null from public.profiles where id = (select phone_user from auth_test_ids)),
  'missing display_name must not block phone signup');

-- Logging in or editing Auth metadata must not reset the business baseline.
update public.profiles set display_name = '已编辑', target_kcal = 1800
where id = (select email_user from auth_test_ids);
update auth.users set last_sign_in_at = now(), raw_user_meta_data = '{"display_name":"其他名称"}'
where id = (select email_user from auth_test_ids);
select pg_temp.assert_true(
  (select display_name = '已编辑' and target_kcal = 1800 from public.profiles
   where id = (select email_user from auth_test_ids)),
  'subsequent login must preserve profile edits');

-- Re-run the deployment SQL; existing profiles must not be overwritten.
/* APPLY_AUTH_MODULE */
select pg_temp.assert_true(
  (select target_kcal = 1800 from public.profiles where id = (select email_user from auth_test_ids)),
  'backfill must preserve an existing baseline');

-- A pre-trigger account missing its profile is repaired by the same backfill.
delete from public.profiles where id = (select phone_user from auth_test_ids);
/* APPLY_AUTH_MODULE */
select pg_temp.assert_true(
  exists(select 1 from public.profiles where id = (select phone_user from auth_test_ids)),
  'backfill must repair missing profiles');

-- JSON with unexpected types cannot make the signup trigger fail.
insert into auth.users(id, raw_user_meta_data)
values (gen_random_uuid(), '{"display_name":{"unexpected":true}}'),
       (gen_random_uuid(), '{"display_name":"   "}'),
       (gen_random_uuid(), null);
set constraints all immediate;
