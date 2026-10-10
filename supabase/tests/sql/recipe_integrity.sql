/* APPLY_INTEGRITY_MODULE */
insert into auth.users(id, email)
select email_user, email_user::text || '@example.invalid' from auth_test_ids;
create temporary table business_test_ids (recipe_id uuid, plan_id uuid);
insert into business_test_ids values (gen_random_uuid(), gen_random_uuid());
grant select on business_test_ids to authenticated;
set local role authenticated;
select set_config('request.jwt.claim.sub', (select email_user::text from auth_test_ids), true);

-- A committed recipe can be deleted together with its ingredient rows.
insert into public.recipes(id, user_id, name)
select b.recipe_id, a.email_user, 'Deletion regression'
from business_test_ids b cross join auth_test_ids a;
insert into public.recipe_ingredients(recipe_id, ingredient_id, raw_weight_g)
select b.recipe_id, i.id, 100
from business_test_ids b cross join public.ingredients i where i.name = '鸡胸肉';
set constraints all immediate;
set constraints all deferred;
delete from public.recipes where id = (select recipe_id from business_test_ids);
set constraints all immediate;
set constraints all deferred;
select pg_temp.assert_true(
  not exists (select 1 from public.recipe_ingredients
              where recipe_id = (select recipe_id from business_test_ids)),
  'recipe deletion did not cascade to ingredients');

-- A recipe created and deleted in one transaction is not an empty survivor.
insert into public.recipes(id, user_id, name)
select b.recipe_id, a.email_user, 'Transient recipe'
from business_test_ids b cross join auth_test_ids a;
delete from public.recipes where id = (select recipe_id from business_test_ids);
set constraints all immediate;
set constraints all deferred;

insert into public.recipes(id, user_id, name)
select b.recipe_id, a.email_user, 'Ingredient source'
from business_test_ids b cross join auth_test_ids a;
insert into public.recipes(id, user_id, name)
select b.plan_id, a.email_user, 'Ingredient destination'
from business_test_ids b cross join auth_test_ids a;
insert into public.recipe_ingredients(recipe_id, ingredient_id, raw_weight_g)
select b.recipe_id, i.id, 100
from business_test_ids b cross join public.ingredients i where i.name = '鸡胸肉';
insert into public.recipe_ingredients(recipe_id, ingredient_id, raw_weight_g)
select b.plan_id, i.id, 100
from business_test_ids b cross join public.ingredients i where i.name = '大米';
set constraints all immediate;
set constraints all deferred;

select pg_temp.expect_error(
  'update public.recipe_ingredients set recipe_id = (select plan_id from business_test_ids)
   where recipe_id = (select recipe_id from business_test_ids);
   set constraints all immediate', '23514');
select pg_temp.expect_error(
  'delete from public.recipe_ingredients where recipe_id = (select recipe_id from business_test_ids);
   set constraints all immediate', '23514');

-- Replacing all ingredients atomically remains valid.
delete from public.recipe_ingredients where recipe_id = (select recipe_id from business_test_ids);
insert into public.recipe_ingredients(recipe_id, ingredient_id, raw_weight_g)
select b.recipe_id, i.id, 150
from business_test_ids b cross join public.ingredients i where i.name = '大米';
set constraints all immediate;
set constraints all deferred;
reset role;

-- Account removal must also cascade through recipes without a false failure.
delete from auth.users where id = (select email_user from auth_test_ids);
set constraints all immediate;
select pg_temp.assert_true(
  not exists (select 1 from public.recipes where user_id = (select email_user from auth_test_ids)),
  'account deletion did not cascade to recipes');
