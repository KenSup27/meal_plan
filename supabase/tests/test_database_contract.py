from pathlib import Path


SUPABASE_DIR = Path(__file__).parents[1]
SCHEMA = (SUPABASE_DIR / "schema.sql").read_text()
SEED = (SUPABASE_DIR / "seed.sql").read_text()


def test_schema_and_seed_are_separate_and_have_a_safe_execution_order() -> None:
    assert "Run this file before supabase/seed.sql." in SCHEMA
    assert "insert into public.ingredients" in SEED
    assert SCHEMA.index("create table if not exists public.ingredients") < SCHEMA.index(
        "create or replace view public.recipe_nutrition"
    )
    assert SCHEMA.index("create or replace view public.recipe_nutrition") < SCHEMA.index(
        "alter table public.profiles enable row level security"
    )


def test_database_contract_has_no_legacy_batch_serving_semantics() -> None:
    recipes_start = SCHEMA.index("create table if not exists public.recipes")
    recipes_end = SCHEMA.index("create table if not exists public.recipe_ingredients")
    recipes = SCHEMA[recipes_start:recipes_end]

    assert "servings" not in recipes
    assert "batch_weight" not in recipes
    assert "yield" not in recipes
    assert "total_kcal" not in recipes


def test_database_contract_exposes_the_required_query_surfaces() -> None:
    for view in (
        "recipe_nutrition",
        "meal_plan_item_nutrition",
        "meal_plan_nutrition",
        "meal_plan_totals",
        "shopping_list_items",
    ):
        assert f"create or replace view public.{view}" in SCHEMA
        assert f"grant select on public.{view} to authenticated" in SCHEMA


def test_database_contract_has_owner_rls_and_anonymous_denial() -> None:
    assert SCHEMA.count("enable row level security") == 6
    assert SCHEMA.count("create policy") == 6
    assert "from public, anon, authenticated;" in SCHEMA
    assert "public.shopping_list_items\nfrom public, anon, authenticated;" in SCHEMA


def test_database_contract_has_seed_data_for_each_picker_category() -> None:
    for category in (
        "meat",
        "seafood",
        "dairy",
        "vegetable",
        "fruit",
        "carb",
        "seasoning",
    ):
        assert f"'{category}'" in SEED
