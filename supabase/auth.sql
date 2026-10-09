-- Incremental Auth integration for projects that already have schema.sql.
-- Safe to reapply. Passwords and sessions remain Supabase-managed.
-- Hosted Auth settings are configured separately; see ADR 0004.
begin;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, display_name)
  values (
    new.id,
    case when jsonb_typeof(new.raw_user_meta_data -> 'display_name') = 'string'
      then nullif(btrim(new.raw_user_meta_data ->> 'display_name'), '')
      else null end
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

revoke execute on function public.handle_new_user() from public, anon, authenticated;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

insert into public.profiles (id, display_name)
select u.id,
  case when jsonb_typeof(u.raw_user_meta_data -> 'display_name') = 'string'
    then nullif(btrim(u.raw_user_meta_data ->> 'display_name'), '')
    else null end
from auth.users u
where not exists (select 1 from public.profiles p where p.id = u.id)
on conflict (id) do nothing;

-- Supabase's default grants may include TRUNCATE and food writes; reset them.
revoke all on public.profiles, public.ingredients, public.recipes,
  public.recipe_ingredients, public.meal_plans, public.meal_plan_items
from public, anon, authenticated;
revoke all on public.recipe_nutrition, public.meal_plan_item_nutrition,
  public.meal_plan_nutrition, public.meal_plan_totals, public.shopping_list_items
from public, anon, authenticated;
grant select, insert, update, delete on public.profiles, public.recipes,
  public.recipe_ingredients, public.meal_plans, public.meal_plan_items
to authenticated;
grant select on public.ingredients, public.recipe_nutrition,
  public.meal_plan_item_nutrition, public.meal_plan_nutrition,
  public.meal_plan_totals, public.shopping_list_items to authenticated;

commit;
