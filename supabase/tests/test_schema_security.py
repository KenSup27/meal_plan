from pathlib import Path


SCHEMA = Path(__file__).parents[1].joinpath("schema.sql").read_text()


def test_timestamp_and_auth_profile_triggers_are_defined() -> None:
    assert "create or replace function public.set_updated_at()" in SCHEMA
    assert "new.updated_at = now();" in SCHEMA
    assert "create or replace function public.handle_new_user()" in SCHEMA
    assert "insert into public.profiles (id, display_name)" in SCHEMA
    assert "on conflict (id) do nothing" in SCHEMA
    assert "create trigger on_auth_user_created" in SCHEMA


def test_recipe_integrity_is_checked_at_transaction_commit() -> None:
    assert "create or replace function public.assert_recipe_has_ingredients()" in SCHEMA
    assert "recipe must contain at least one ingredient" in SCHEMA
    assert "create constraint trigger recipes_require_ingredients" in SCHEMA
    assert "deferrable initially deferred" in SCHEMA
    assert "create constraint trigger recipe_ingredients_require_parent" in SCHEMA


def test_plan_item_trigger_checks_week_ownership_and_archiving() -> None:
    start = SCHEMA.index("create or replace function public.validate_meal_plan_item()")
    end = SCHEMA.index("drop trigger if exists meal_plan_items_validate", start)
    function = SCHEMA[start:end]

    assert "new.planned_date < plan_week_start" in function
    assert "new.planned_date > plan_week_start + 6" in function
    assert "recipe and meal plan must belong to the same user" in function
    assert "archived recipes cannot be added to new plan items" in function


def test_all_persisted_tables_enable_rls() -> None:
    for table in (
        "profiles",
        "ingredients",
        "recipes",
        "recipe_ingredients",
        "meal_plans",
        "meal_plan_items",
    ):
        assert f"alter table public.{table} enable row level security" in SCHEMA


def test_owner_policies_cover_every_personal_table() -> None:
    for policy in (
        "profiles_owner_all",
        "recipes_owner_all",
        "recipe_ingredients_owner_all",
        "meal_plans_owner_all",
        "meal_plan_items_owner_all",
    ):
        assert f"create policy {policy}" in SCHEMA
    assert "using (id = (select auth.uid()))" in SCHEMA
    assert "using (user_id = (select auth.uid()))" in SCHEMA
    assert "with check (user_id = (select auth.uid()))" in SCHEMA


def test_manual_plan_items_are_not_rejected_by_recipe_ownership_policy() -> None:
    policy_start = SCHEMA.index("create policy meal_plan_items_owner_all")
    policy_end = SCHEMA.index("-- Reset Supabase default grants", policy_start)
    policy = SCHEMA[policy_start:policy_end]

    assert "recipe_id is null" in policy
    assert "where p.id = meal_plan_id and p.user_id = (select auth.uid())" in policy
    assert "where r.id = recipe_id and r.user_id = (select auth.uid())" in policy


def test_ingredients_are_read_only_for_authenticated_users_and_anon_is_revoked() -> None:
    assert "create policy ingredients_authenticated_read" in SCHEMA
    assert "for select to authenticated" in SCHEMA
    assert "revoke all on public.profiles," in SCHEMA
    assert "public.meal_plan_items\nfrom public, anon, authenticated" in SCHEMA
    assert "grant select on public.ingredients to authenticated" in SCHEMA
