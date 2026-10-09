from pathlib import Path
import re


SCHEMA = Path(__file__).parents[1].joinpath("schema.sql").read_text()


def table_definition(name: str) -> str:
    match = re.search(
        rf"create table if not exists public\.{name} \((.*?)\n\);",
        SCHEMA,
        flags=re.DOTALL,
    )
    assert match, f"missing table definition: {name}"
    return match.group(1)


def test_schema_creates_the_six_planned_tables() -> None:
    for table in (
        "profiles",
        "ingredients",
        "recipes",
        "recipe_ingredients",
        "meal_plans",
        "meal_plan_items",
    ):
        assert f"create table if not exists public.{table}" in SCHEMA


def test_recipe_is_a_single_plate_without_batch_serving_fields() -> None:
    recipes = table_definition("recipes")

    assert "archived_at timestamptz" in recipes
    assert "servings" not in recipes
    assert "total_kcal" not in recipes
    assert "total_protein_g" not in recipes
    assert "total_carbs_g" not in recipes
    assert "total_fat_g" not in recipes


def test_recipe_ingredients_use_positive_raw_weights_and_safe_foreign_keys() -> None:
    recipe_ingredients = table_definition("recipe_ingredients")

    assert "raw_weight_g numeric(8, 1) not null check (raw_weight_g > 0)" in recipe_ingredients
    assert "references public.recipes(id) on delete cascade" in recipe_ingredients
    assert "references public.ingredients(id) on delete restrict" in recipe_ingredients
    assert "primary key (recipe_id, ingredient_id)" in recipe_ingredients


def test_meal_plans_store_a_monday_target_snapshot() -> None:
    plans = table_definition("meal_plans")

    for column in (
        "target_kcal",
        "target_protein_g",
        "target_carbs_g",
        "target_fat_g",
    ):
        assert f"{column} " in plans
    assert "check (extract(isodow from week_start) = 1)" in plans
    assert "unique (user_id, week_start)" in plans


def test_meal_plan_items_support_multiple_items_per_meal() -> None:
    items = table_definition("meal_plan_items")

    assert "meal_type text not null check (meal_type in ('breakfast', 'lunch', 'dinner'))" in items
    assert "input_mode text not null check (input_mode in ('recipe', 'manual'))" in items
    assert "quantity numeric(6, 2)" in items
    assert "manual_kcal numeric(8, 1)" in items
    assert "unique (meal_plan_id, planned_date, meal_type)" not in SCHEMA


def test_meal_plan_item_mode_check_separates_recipe_and_manual_inputs() -> None:
    items = table_definition("meal_plan_items")

    assert "input_mode = 'recipe'" in items
    assert "recipe_id is not null" in items
    assert "quantity is not null" in items
    assert "quantity > 0" in items
    assert "input_mode = 'manual'" in items
    assert "recipe_id is null" in items
    assert "manual_kcal is not null" in items
    assert "manual_fat_g is not null" in items


def test_required_indexes_cover_owner_lookup_and_plan_queries() -> None:
    for index in (
        "recipes_user_id_idx",
        "recipes_active_user_idx",
        "recipe_ingredients_ingredient_id_idx",
        "meal_plans_user_week_idx",
        "meal_plan_items_plan_date_idx",
        "meal_plan_items_recipe_idx",
    ):
        assert f"create index if not exists {index}" in SCHEMA
