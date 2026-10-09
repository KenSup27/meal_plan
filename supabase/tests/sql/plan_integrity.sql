insert into auth.users(id, email)
select email_user, email_user::text || '@example.invalid' from auth_test_ids;
create temporary table business_test_ids (plan_id uuid);
insert into business_test_ids values (gen_random_uuid());
grant select on business_test_ids to authenticated;
set local role authenticated;
select set_config('request.jwt.claim.sub', (select email_user::text from auth_test_ids), true);
insert into public.meal_plans(
  id, user_id, week_start, target_kcal, target_protein_g, target_carbs_g, target_fat_g
)
select b.plan_id, a.email_user, '2026-10-05', 2000, 150, 220, 60
from business_test_ids b cross join auth_test_ids a;

-- An empty plan can move to another Monday.
update public.meal_plans set week_start = '2026-10-12'
where id = (select plan_id from business_test_ids);
insert into public.meal_plan_items(
  meal_plan_id, planned_date, meal_type, input_mode,
  manual_kcal, manual_protein_g, manual_carbs_g, manual_fat_g
)
select plan_id, '2026-10-12', 'lunch', 'manual', 500, 30, 40, 20 from business_test_ids;

-- Updating the parent must not bypass the child date constraint.
select pg_temp.expect_error(
  'update public.meal_plans set week_start = ''2026-10-19''
   where id = (select plan_id from business_test_ids)', '23514');
update public.meal_plans set status = 'confirmed'
where id = (select plan_id from business_test_ids);
select pg_temp.assert_true(
  (select week_start = '2026-10-12' and status = 'confirmed'
   from public.meal_plans where id = (select plan_id from business_test_ids)),
  'valid plan update was rejected or week changed despite existing items');
reset role;
