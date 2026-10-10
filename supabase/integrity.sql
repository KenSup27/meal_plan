-- Bring existing deployments up to the integrity rules already in schema.sql.
-- No tables, RLS policies or user rows change.

create or replace function public.assert_recipe_has_ingredients()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if exists (select 1 from public.recipes r where r.id = new.id)
  and not exists (
    select 1
    from public.recipe_ingredients ri
    where ri.recipe_id = new.id
  ) then
    raise exception using
      errcode = '23514',
      message = 'recipe must contain at least one ingredient';
  end if;
  return null;
end;
$$;

create or replace function public.assert_recipe_ingredient_parent()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  recipe_uuid uuid;
  recipe_ids uuid[];
begin
  if tg_op = 'INSERT' then
    recipe_ids := array[new.recipe_id];
  elsif tg_op = 'DELETE' then
    recipe_ids := array[old.recipe_id];
  else
    recipe_ids := array[old.recipe_id, new.recipe_id];
  end if;
  foreach recipe_uuid in array recipe_ids loop
    -- Deleted parents (including account cascades) need no ingredients.
    -- Reassignment must validate both the old and the new surviving parent.
    if exists (select 1 from public.recipes r where r.id = recipe_uuid)
    and not exists (
      select 1 from public.recipe_ingredients ri where ri.recipe_id = recipe_uuid
    ) then
      raise exception using
        errcode = '23514',
        message = 'recipe must contain at least one ingredient';
    end if;
  end loop;
  return null;
end;
$$;

create or replace function public.validate_meal_plan_week()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.week_start is distinct from old.week_start and exists (
    select 1 from public.meal_plan_items mpi
    where mpi.meal_plan_id = old.id
      and (mpi.planned_date < new.week_start or mpi.planned_date > new.week_start + 6)
  ) then
    raise exception using
      errcode = '23514',
      message = 'existing meal items must remain within the plan week';
  end if;
  return new;
end;
$$;

drop trigger if exists meal_plans_validate_week on public.meal_plans;
create trigger meal_plans_validate_week
  before update of week_start on public.meal_plans
  for each row execute function public.validate_meal_plan_week();

revoke execute on function public.assert_recipe_has_ingredients(), public.assert_recipe_ingredient_parent(), public.validate_meal_plan_week() from public, anon, authenticated;
