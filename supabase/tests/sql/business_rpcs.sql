/* APPLY_BUSINESS_MODULE */
insert into auth.users(id,email)
select email_user,email_user::text || '@example.invalid' from auth_test_ids;
insert into auth.users(id,email)
select phone_user,phone_user::text || '@example.invalid' from auth_test_ids;
create temporary table business_rpc_ids (recipe_id uuid, plan_id uuid, item_a uuid, item_b uuid);
insert into business_rpc_ids values (null, gen_random_uuid(), gen_random_uuid(), gen_random_uuid());
grant select, update on business_rpc_ids to authenticated;
set local role authenticated;
select set_config('request.jwt.claim.sub', (select email_user::text from auth_test_ids), true);
update business_rpc_ids set recipe_id = public.save_recipe(null, 'RPC三盘菜', null,
  (select jsonb_agg(jsonb_build_object('ingredient_id', id, 'raw_weight_g',
    case name when '鸡胸肉' then 150 when '西兰花' then 200 else 5 end))
   from public.ingredients where name in ('鸡胸肉', '西兰花', '橄榄油')));
set constraints all immediate;
set constraints all deferred;
select pg_temp.assert_true((select count(*) = 3 from public.recipe_ingredients), 'recipe detail not atomic');
select pg_temp.expect_error(
  $$select public.save_recipe(null, '非法菜谱', null, '[{"ingredient_id": -1,"raw_weight_g":100}]')$$, '22023');
select pg_temp.assert_true((select count(*) = 1 from public.recipes), 'failed create left parent');
select pg_temp.expect_error(
  $$select public.save_recipe((select recipe_id from business_rpc_ids), '坏更新', null,
    (select jsonb_agg(jsonb_build_object('ingredient_id',id,'raw_weight_g',-1)) from public.ingredients where name='鸡胸肉'))$$, '23514');
select pg_temp.assert_true((select name = 'RPC三盘菜' from public.recipes), 'failed update changed name');
select pg_temp.assert_true((select count(*) = 3 from public.recipe_ingredients), 'failed update destroyed ingredients');
insert into public.meal_plans(id,user_id,week_start,target_kcal,target_protein_g,target_carbs_g,target_fat_g)
select plan_id, auth.uid(), '2026-09-28',1800,120,200,60 from business_rpc_ids;
select public.save_plan_items(plan_id,
  jsonb_build_array(
    jsonb_build_object('id',item_a,'planned_date','2026-09-28','meal_type','lunch','input_mode','recipe','recipe_id',recipe_id,'quantity',2,'sort_order',0),
    jsonb_build_object('id',item_b,'planned_date','2026-10-04','meal_type','dinner','input_mode','recipe','recipe_id',recipe_id,'quantity',1,'sort_order',0)
  ),null,true) from business_rpc_ids;
select pg_temp.assert_true(
  (select planned_kcal = 935.1 and planned_protein_g = 121.7 and planned_carbs_g = 25.8 and planned_fat_g = 38.6
   from public.meal_plan_totals), 'raw precision differs from backend');
select pg_temp.assert_true((select sum(total_raw_weight_g) = 1065 from public.shopping_list_items), 'shopping quantity mismatch');
select pg_temp.expect_error(
  $$select public.save_plan_items((select plan_id from business_rpc_ids),'[]','2000-01-01',false)$$,'PT409');
select pg_temp.assert_true((select count(*) = 2 from public.meal_plan_items), 'stale write deleted data');
select pg_temp.expect_error(
  $$select public.save_plan_items((select plan_id from business_rpc_ids),
     jsonb_build_array(jsonb_build_object('id',gen_random_uuid(),'planned_date','2026-10-05','meal_type','lunch','input_mode','recipe','recipe_id',(select recipe_id from business_rpc_ids),'quantity',1,'sort_order',0)),
     (select updated_at from public.meal_plans),false)$$,'23514');
select pg_temp.assert_true((select count(*) = 2 from public.meal_plan_items), 'invalid replacement lost previous items');
update public.recipes set archived_at=now() where id=(select recipe_id from business_rpc_ids);
-- Unchanged archived items can survive editing another part of the plan.
select public.save_plan_items((select plan_id from business_rpc_ids),
  (select jsonb_agg(to_jsonb(i)) from public.meal_plan_items i),
  (select updated_at from public.meal_plans),false);
set constraints all immediate;
set constraints all deferred;
select set_config('request.jwt.claim.sub', (select phone_user::text from auth_test_ids), true);
select pg_temp.assert_true((select count(*)=0 from public.meal_plan_totals), 'raw view RLS leak');
select pg_temp.assert_true((select count(*)=0 from public.recipe_nutrition_raw), 'raw recipe view RLS leak');
select pg_temp.expect_error(
  $$select public.save_recipe((select recipe_id from business_rpc_ids),'越权',null,'[]')$$,'22023');
select pg_temp.expect_error(
  $$select public.save_plan_items((select plan_id from business_rpc_ids),'[]',null,true)$$,'PT404');
reset role;
set local role anon;
select pg_temp.expect_error($$select public.save_recipe(null,'匿名',null,'[]')$$,'42501');
reset role;
