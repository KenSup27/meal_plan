insert into auth.users(id, email, raw_user_meta_data)
select email_user, email_user::text || '@example.invalid', '{"role":"admin"}'::jsonb
from auth_test_ids;
insert into auth.users(id, email)
select phone_user, phone_user::text || '@example.invalid' from auth_test_ids;

-- Anonymous API access must fail by privilege, including all derived views.
set local role anon;
select pg_temp.expect_error('select * from public.profiles', '42501');
select pg_temp.expect_error('select * from public.ingredients', '42501');
select pg_temp.expect_error('select * from public.recipes', '42501');
select pg_temp.expect_error('select * from public.recipe_ingredients', '42501');
select pg_temp.expect_error('select * from public.meal_plans', '42501');
select pg_temp.expect_error('select * from public.meal_plan_items', '42501');
select pg_temp.expect_error('select * from public.recipe_nutrition', '42501');
select pg_temp.expect_error('select * from public.meal_plan_item_nutrition', '42501');
select pg_temp.expect_error('select * from public.meal_plan_nutrition', '42501');
select pg_temp.expect_error('select * from public.meal_plan_totals', '42501');
select pg_temp.expect_error('select * from public.shopping_list_items', '42501');
select pg_temp.expect_error('select public.handle_new_user()', '42501');

-- Inspect effective ACLs: TRUNCATE bypasses RLS, so testing RLS alone is insufficient.
select pg_temp.assert_true(
  not exists (
    select 1 from unnest(array['profiles','ingredients','recipes','recipe_ingredients','meal_plans','meal_plan_items']) t(name)
    where has_table_privilege('authenticated', 'public.' || t.name, 'TRUNCATE')
      or has_table_privilege('anon', 'public.' || t.name, 'TRUNCATE')
  ), 'client roles must not have TRUNCATE');

set local role authenticated;
-- No JWT user context: TO authenticated alone must not expose personal data.
select set_config('request.jwt.claim.sub', '', true);
select set_config('request.jwt.claims', '{}', true);
select pg_temp.assert_true((select count(*) = 0 from public.profiles), 'missing JWT subject leaked profiles');

select set_config('request.jwt.claim.sub', (select email_user::text from auth_test_ids), true);
select pg_temp.assert_true(
  (select count(*) = 1 from public.profiles), 'owner must see exactly their profile');
update public.profiles set display_name = '自己的昵称', target_kcal = 2000
where id = (select email_user from auth_test_ids);
select pg_temp.assert_true(
  (select target_kcal = 2000 from public.profiles where id = (select email_user from auth_test_ids)),
  'owner profile update failed');

with changed as (
  update public.profiles set display_name = '被篡改'
  where id = (select phone_user from auth_test_ids) returning id
) select pg_temp.assert_true((select count(*) = 0 from changed), 'cross-user UPDATE succeeded');
with removed as (
  delete from public.profiles where id = (select phone_user from auth_test_ids) returning id
) select pg_temp.assert_true((select count(*) = 0 from removed), 'cross-user DELETE succeeded');

select pg_temp.expect_error(
  'insert into public.profiles(id) select phone_user from auth_test_ids', '42501');
select pg_temp.expect_error(
  'update public.profiles set id = (select phone_user from auth_test_ids)', '42501');
select pg_temp.expect_error('update public.ingredients set is_active = false', '42501');
select pg_temp.expect_error('select public.handle_new_user()', '42501');

-- Simulate an identity switch to another valid user's subject.
select set_config('request.jwt.claim.sub', (select phone_user::text from auth_test_ids), true);
select pg_temp.assert_true(
  (select count(*) = 1 from public.profiles), 'second user profile missing');
select pg_temp.assert_true(
  not exists(select 1 from public.profiles where id = (select email_user from auth_test_ids)),
  'second user can see first user profile');

-- Sign-out removes JWT context. Actual token revocation is Auth-server behavior.
select set_config('request.jwt.claim.sub', '', true);
select pg_temp.assert_true((select count(*) = 0 from public.profiles), 'signed-out context leaked profiles');
reset role;
