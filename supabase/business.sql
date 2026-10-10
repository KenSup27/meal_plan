-- Upgrade after schema.sql. No business tables or ownership policies change.
create or replace function public.save_recipe(
  p_recipe_id uuid, p_name text, p_description text, p_ingredients jsonb
) returns uuid
language plpgsql security invoker set search_path = ''
as $$
declare
  recipe_uuid uuid := p_recipe_id;
begin
  if auth.uid() is null then
    raise exception using errcode = '42501', message = 'authentication required';
  end if;
  if jsonb_typeof(p_ingredients) is distinct from 'array'
    or jsonb_array_length(p_ingredients) not between 1 and 100 then
    raise exception using errcode = '22023', message = 'ingredients required';
  end if;
  if exists (
    select 1 from jsonb_array_elements(p_ingredients) e
    left join public.ingredients i on i.id = (e->>'ingredient_id')::bigint
    where i.id is null or not i.is_active
  ) then
    raise exception using errcode = '22023', message = 'ingredient unavailable';
  end if;
  if recipe_uuid is null then
    insert into public.recipes(user_id, name, description)
    values (auth.uid(), p_name, p_description) returning id into recipe_uuid;
  else
    perform 1 from public.recipes where id = recipe_uuid and user_id = auth.uid()
      and archived_at is null for update;
    if not found then
      raise exception using errcode = 'PT404', message = 'recipe not found';
    end if;
    update public.recipes set name = p_name, description = p_description where id = recipe_uuid;
    delete from public.recipe_ingredients where recipe_id = recipe_uuid;
  end if;
  insert into public.recipe_ingredients(recipe_id, ingredient_id, raw_weight_g)
    select recipe_uuid, (e->>'ingredient_id')::bigint, (e->>'raw_weight_g')::numeric
    from jsonb_array_elements(p_ingredients) e;
  return recipe_uuid;
end;
$$;

create or replace function public.save_plan_items(
  p_plan_id uuid, p_items jsonb, p_expected_revision timestamptz, p_append boolean default false
) returns void
language plpgsql security invoker set search_path = ''
as $$
declare
  current_revision timestamptz;
  entry jsonb;
  item public.meal_plan_items;
  existing jsonb;
begin
  select updated_at into current_revision from public.meal_plans
    where id = p_plan_id and user_id = auth.uid() for update;
  if not found then
    raise exception using errcode = 'PT404', message = 'plan not found';
  end if;
  if p_append is null then
    raise exception using errcode = '22023', message = 'append mode required';
  end if;
  if jsonb_typeof(p_items) is distinct from 'array' or jsonb_array_length(p_items) > 100 then
    raise exception using errcode = '22023', message = 'invalid items';
  end if;
  if not p_append and (p_expected_revision is null or current_revision <> p_expected_revision) then
    raise exception using errcode = 'PT409', message = 'plan has changed';
  end if;
  if p_append and (select count(*) from public.meal_plan_items where meal_plan_id = p_plan_id)
    + jsonb_array_length(p_items) > 100 then
    raise exception using errcode = '22023', message = 'too many items';
  end if;
  if (select count(distinct e->>'id') from jsonb_array_elements(p_items) e) <> jsonb_array_length(p_items) then
    raise exception using errcode = '22023', message = 'distinct item ids required';
  end if;
  if not p_append then
    delete from public.meal_plan_items where meal_plan_id = p_plan_id
      and id not in (select (e->>'id')::uuid from jsonb_array_elements(p_items) e);
  end if;
  for entry in select * from jsonb_array_elements(p_items) loop
    item := jsonb_populate_record(null::public.meal_plan_items,
      entry || jsonb_build_object('meal_plan_id', p_plan_id));
    select to_jsonb(i) - 'created_at' into existing from public.meal_plan_items i
      where i.id = item.id and i.meal_plan_id = p_plan_id;
    if found and p_append then
      raise exception using errcode = '23505', message = 'item already exists';
    end if;
    -- Leave unchanged historical items alone, including archived recipes.
    if existing = to_jsonb(item) - 'created_at' then
      continue;
    end if;
    insert into public.meal_plan_items(
      id, meal_plan_id, planned_date, meal_type, input_mode, recipe_id, meal_name,
      quantity, manual_kcal, manual_protein_g, manual_carbs_g, manual_fat_g, sort_order
    ) values (
      item.id, p_plan_id, item.planned_date, item.meal_type, item.input_mode, item.recipe_id, item.meal_name,
      item.quantity, item.manual_kcal, item.manual_protein_g, item.manual_carbs_g, item.manual_fat_g, item.sort_order
    ) on conflict (id) do update set
      planned_date = excluded.planned_date, meal_type = excluded.meal_type,
      input_mode = excluded.input_mode, recipe_id = excluded.recipe_id, meal_name = excluded.meal_name,
      quantity = excluded.quantity, manual_kcal = excluded.manual_kcal,
      manual_protein_g = excluded.manual_protein_g, manual_carbs_g = excluded.manual_carbs_g,
      manual_fat_g = excluded.manual_fat_g, sort_order = excluded.sort_order
    where public.meal_plan_items.meal_plan_id = p_plan_id;
    if not found then
      raise exception using errcode = 'PT404', message = 'item not found';
    end if;
  end loop;
  update public.meal_plans set updated_at = now() where id = p_plan_id;
end;
$$;

revoke all on function public.save_recipe(uuid, text, text, jsonb) from public, anon;
revoke all on function public.save_plan_items(uuid, jsonb, timestamptz, boolean) from public, anon;
grant execute on function public.save_recipe(uuid, text, text, jsonb) to authenticated;
grant execute on function public.save_plan_items(uuid, jsonb, timestamptz, boolean) to authenticated;

-- Raw intermediates are separate from the stable one-decimal display views.
create or replace view public.recipe_nutrition_raw with (security_invoker = true) as
select r.id as recipe_id, r.user_id,
  coalesce(sum(i.kcal_per_100g * ri.raw_weight_g / 100), 0) as kcal,
  coalesce(sum(i.protein_per_100g * ri.raw_weight_g / 100), 0) as protein_g,
  coalesce(sum(i.carbs_per_100g * ri.raw_weight_g / 100), 0) as carbs_g,
  coalesce(sum(i.fat_per_100g * ri.raw_weight_g / 100), 0) as fat_g
from public.recipes r
left join public.recipe_ingredients ri on ri.recipe_id = r.id
left join public.ingredients i on i.id = ri.ingredient_id
group by r.id, r.user_id;

create or replace view public.meal_plan_item_nutrition_raw with (security_invoker = true) as
select mpi.id as meal_plan_item_id, mpi.meal_plan_id, mpi.planned_date, mpi.meal_type,
  case when mpi.input_mode = 'recipe' then rn.kcal * mpi.quantity else mpi.manual_kcal end as kcal,
  case when mpi.input_mode = 'recipe' then rn.protein_g * mpi.quantity else mpi.manual_protein_g end as protein_g,
  case when mpi.input_mode = 'recipe' then rn.carbs_g * mpi.quantity else mpi.manual_carbs_g end as carbs_g,
  case when mpi.input_mode = 'recipe' then rn.fat_g * mpi.quantity else mpi.manual_fat_g end as fat_g
from public.meal_plan_items mpi
left join public.recipe_nutrition_raw rn on rn.recipe_id = mpi.recipe_id;

create or replace view public.meal_plan_item_nutrition with (security_invoker = true) as
select mpi.id as meal_plan_item_id, mpi.meal_plan_id, mpi.planned_date, mpi.meal_type,
  mpi.input_mode, mpi.recipe_id, coalesce(mpi.meal_name, r.name) as meal_name, mpi.quantity,
  n.kcal::numeric(12, 1) as total_kcal, n.protein_g::numeric(10, 1) as total_protein_g,
  n.carbs_g::numeric(10, 1) as total_carbs_g, n.fat_g::numeric(10, 1) as total_fat_g
from public.meal_plan_items mpi
left join public.recipes r on r.id = mpi.recipe_id
join public.meal_plan_item_nutrition_raw n on n.meal_plan_item_id = mpi.id;

create or replace view public.meal_plan_nutrition with (security_invoker = true) as
select meal_plan_id, planned_date, meal_type,
  sum(kcal)::numeric(12, 1) as total_kcal, sum(protein_g)::numeric(10, 1) as total_protein_g,
  sum(carbs_g)::numeric(10, 1) as total_carbs_g, sum(fat_g)::numeric(10, 1) as total_fat_g,
  count(*)::integer as item_count
from public.meal_plan_item_nutrition_raw group by meal_plan_id, planned_date, meal_type;

create or replace view public.meal_plan_totals with (security_invoker = true) as
select p.id as meal_plan_id, p.user_id, p.week_start,
  p.target_kcal, p.target_protein_g, p.target_carbs_g, p.target_fat_g,
  coalesce(sum(n.kcal), 0)::numeric(12, 1) as planned_kcal,
  coalesce(sum(n.protein_g), 0)::numeric(10, 1) as planned_protein_g,
  coalesce(sum(n.carbs_g), 0)::numeric(10, 1) as planned_carbs_g,
  coalesce(sum(n.fat_g), 0)::numeric(10, 1) as planned_fat_g,
  count(n.meal_plan_item_id)::integer as planned_item_count
from public.meal_plans p left join public.meal_plan_item_nutrition_raw n on n.meal_plan_id = p.id
group by p.id, p.user_id, p.week_start, p.target_kcal, p.target_protein_g, p.target_carbs_g, p.target_fat_g;

revoke all on public.recipe_nutrition_raw, public.meal_plan_item_nutrition_raw from public, anon;
grant select on public.recipe_nutrition_raw, public.meal_plan_item_nutrition_raw to authenticated;
