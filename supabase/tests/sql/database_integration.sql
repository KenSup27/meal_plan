insert into auth.users(id, email, raw_user_meta_data)
select email_user, email_user::text || '@example.invalid', '{"role":"admin"}'::jsonb
from auth_test_ids;
insert into auth.users(id, email)
select phone_user, phone_user::text || '@example.invalid' from auth_test_ids;

create temporary table business_test_ids (recipe_id uuid, plan_id uuid, other_recipe_id uuid);
insert into business_test_ids values (gen_random_uuid(), gen_random_uuid(), gen_random_uuid());
grant select on business_test_ids to authenticated;

-- Another user's private recipe must never appear in this user's views.
insert into public.recipes(id, user_id, name)
select b.other_recipe_id, a.phone_user, '另一用户的菜谱'
from business_test_ids b cross join auth_test_ids a;
insert into public.recipe_ingredients(recipe_id, ingredient_id, raw_weight_g)
select b.other_recipe_id, i.id, 100
from business_test_ids b cross join public.ingredients i where i.name = '鸡胸肉';
set constraints all immediate;
set constraints all deferred;

set local role authenticated;
select set_config('request.jwt.claim.sub', (select email_user::text from auth_test_ids), true);
update public.profiles set target_kcal = 2000, protein_g = 150, carbs_g = 220,
  fat_g = 60, baseline_confirmed_at = now(), updated_at = '2000-01-01'
where id = (select email_user from auth_test_ids);
select pg_temp.assert_true(
  (select updated_at = transaction_timestamp() from public.profiles
   where id = (select email_user from auth_test_ids)), 'profile updated_at trigger failed');

insert into public.recipes(id, user_id, name)
select b.recipe_id, a.email_user, '邮箱登录验收鸡肉饭'
from business_test_ids b cross join auth_test_ids a;
insert into public.recipe_ingredients(recipe_id, ingredient_id, raw_weight_g)
select b.recipe_id, i.id, case when i.name = '鸡胸肉' then 200 else 100 end
from business_test_ids b cross join public.ingredients i where i.name in ('鸡胸肉', '大米');
set constraints all immediate;
set constraints all deferred;

select pg_temp.assert_true(
  (select ingredient_count = 2 and total_kcal = 612 and total_protein_g = 54
      and total_carbs_g = 77.2 and total_fat_g = 10.2
   from public.recipe_nutrition where recipe_id = (select recipe_id from business_test_ids)),
  'recipe nutrition mismatch');
select pg_temp.assert_true(
  (select count(*) = 1 from public.recipe_nutrition), 'recipe nutrition view leaked another user');

insert into public.meal_plans(
  id, user_id, week_start, target_kcal, target_protein_g, target_carbs_g, target_fat_g
)
select b.plan_id, a.email_user, '2026-10-05', 2000, 150, 220, 60
from business_test_ids b cross join auth_test_ids a;
insert into public.meal_plan_items(meal_plan_id, planned_date, meal_type, input_mode, recipe_id, quantity)
select plan_id, '2026-10-05', 'lunch', 'recipe', recipe_id, 1.5 from business_test_ids;
-- Same day and same meal can have several dishes; manual dishes are not shopping items.
insert into public.meal_plan_items(
  meal_plan_id, planned_date, meal_type, input_mode, meal_name,
  manual_kcal, manual_protein_g, manual_carbs_g, manual_fat_g
)
select plan_id, '2026-10-05', 'lunch', 'manual', '人工补充餐', 500, 30, 40, 20 from business_test_ids;

select pg_temp.assert_true(
  (select planned_kcal = 1418 and planned_item_count = 2 and planned_protein_g = 111
   from public.meal_plan_totals where meal_plan_id = (select plan_id from business_test_ids)),
  'whole-plan nutrition mismatch');
select pg_temp.assert_true(
  (select item_count = 2 and total_kcal = 1418 from public.meal_plan_nutrition
   where meal_plan_id = (select plan_id from business_test_ids)), 'same-meal aggregation mismatch');
select pg_temp.assert_true(
  (select count(*) = 2 and sum(total_raw_weight_g) = 450 from public.shopping_list_items
   where meal_plan_id = (select plan_id from business_test_ids)), 'shopping quantities or manual exclusion failed');

update public.profiles set target_kcal = 1900 where id = (select email_user from auth_test_ids);
select pg_temp.assert_true(
  (select target_kcal = 2000 from public.meal_plans where id = (select plan_id from business_test_ids)),
  'profile update changed the historical plan target');

select pg_temp.expect_error(
  'insert into public.meal_plan_items(meal_plan_id,planned_date,meal_type,input_mode,manual_kcal,manual_protein_g,manual_carbs_g,manual_fat_g)
   select plan_id, ''2026-10-12'', ''lunch'', ''manual'', 100, 10, 10, 1 from business_test_ids', '23514');
select pg_temp.expect_error(
  'insert into public.meal_plan_items(meal_plan_id,planned_date,meal_type,input_mode,recipe_id,quantity)
   select plan_id, ''2026-10-05'', ''lunch'', ''recipe'', recipe_id, null from business_test_ids', '23514');
select pg_temp.expect_error(
  'insert into public.meal_plan_items(meal_plan_id,planned_date,meal_type,input_mode,manual_kcal)
   select plan_id, ''2026-10-05'', ''lunch'', ''manual'', 100 from business_test_ids', '23514');
select pg_temp.expect_error(
  'insert into public.recipes(user_id,name) select phone_user, ''越权菜谱'' from auth_test_ids', '42501');
select pg_temp.expect_error(
  'insert into public.recipe_ingredients(recipe_id,ingredient_id,raw_weight_g)
   select other_recipe_id, (select id from public.ingredients where name=''大米''), 100 from business_test_ids', '42501');
select pg_temp.expect_error(
  'insert into public.recipes(user_id,name) select email_user, ''空菜谱'' from auth_test_ids;
   set constraints all immediate', '23514');

update public.recipes set archived_at = now() where id = (select recipe_id from business_test_ids);
select pg_temp.expect_error(
  'insert into public.meal_plan_items(meal_plan_id,planned_date,meal_type,input_mode,recipe_id,quantity)
   select plan_id, ''2026-10-05'', ''dinner'', ''recipe'', recipe_id, 1 from business_test_ids', '23514');
select pg_temp.assert_true(
  (select planned_kcal = 1418 from public.meal_plan_totals where meal_plan_id = (select plan_id from business_test_ids)),
  'archiving recipe changed historical nutrition');

-- Flush this user's deferred writes before simulating another HTTP request.
set constraints all immediate;
set constraints all deferred;

select set_config('request.jwt.claim.sub', (select phone_user::text from auth_test_ids), true);
select pg_temp.assert_true((select count(*) = 1 from public.recipes), 'other owner recipe invisible');
select pg_temp.assert_true((select count(*) = 1 from public.recipe_nutrition), 'recipe view leaked a foreign recipe');
select pg_temp.assert_true((select count(*) = 0 from public.meal_plans), 'meal plan RLS leak');
select pg_temp.assert_true((select count(*) = 0 from public.meal_plan_items), 'meal items RLS leak');
select pg_temp.assert_true((select count(*) = 0 from public.meal_plan_item_nutrition), 'item view RLS leak');
select pg_temp.assert_true((select count(*) = 0 from public.meal_plan_nutrition), 'meal view RLS leak');
select pg_temp.assert_true((select count(*) = 0 from public.meal_plan_totals), 'plan totals RLS leak');
select pg_temp.assert_true((select count(*) = 0 from public.shopping_list_items), 'shopping view RLS leak');
reset role;
