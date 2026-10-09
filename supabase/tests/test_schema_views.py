from pathlib import Path


SCHEMA = Path(__file__).parents[1].joinpath("schema.sql").read_text()


def view_definition(name: str) -> str:
    marker = f"create or replace view public.{name}"
    start = SCHEMA.index(marker)
    end = SCHEMA.find(";", start)
    assert end != -1, f"unterminated view definition: {name}"
    return SCHEMA[start : end + 1]


def test_all_public_nutrition_views_are_security_invoker_views() -> None:
    for view in (
        "recipe_nutrition",
        "meal_plan_item_nutrition",
        "meal_plan_nutrition",
        "meal_plan_totals",
        "shopping_list_items",
    ):
        definition = view_definition(view)
        assert "with (security_invoker = true)" in definition
        assert f"grant select on public.{view} to authenticated" in SCHEMA


def test_recipe_nutrition_is_aggregated_from_raw_ingredient_detail() -> None:
    view = view_definition("recipe_nutrition")

    assert "public.recipe_ingredients ri" in view
    assert "public.ingredients i" in view
    assert "i.kcal_per_100g * ri.raw_weight_g / 100" in view
    assert "i.protein_per_100g * ri.raw_weight_g / 100" in view
    assert "i.carbs_per_100g * ri.raw_weight_g / 100" in view
    assert "i.fat_per_100g * ri.raw_weight_g / 100" in view
    assert "group by r.id, r.user_id" in view


def test_item_nutrition_supports_recipe_quantity_and_manual_values() -> None:
    view = view_definition("meal_plan_item_nutrition")

    assert "rn.total_kcal * mpi.quantity" in view
    assert "else mpi.manual_kcal" in view
    assert "rn.total_protein_g * mpi.quantity" in view
    assert "else mpi.manual_protein_g" in view
    assert "rn.total_carbs_g * mpi.quantity" in view
    assert "else mpi.manual_carbs_g" in view
    assert "rn.total_fat_g * mpi.quantity" in view
    assert "else mpi.manual_fat_g" in view


def test_daily_and_weekly_views_aggregate_multiple_plan_items() -> None:
    daily = view_definition("meal_plan_nutrition")
    totals = view_definition("meal_plan_totals")

    assert "group by meal_plan_id, planned_date, meal_type" in daily
    assert "count(*)::integer as item_count" in daily
    assert "left join public.meal_plan_item_nutrition n" in totals
    assert "sum(n.total_kcal)" in totals
    assert "sum(n.total_protein_g)" in totals
    assert "sum(n.total_carbs_g)" in totals
    assert "sum(n.total_fat_g)" in totals


def test_shopping_list_merges_raw_weights_and_excludes_manual_items() -> None:
    view = view_definition("shopping_list_items")

    assert "sum(ri.raw_weight_g * mpi.quantity)" in view
    assert "group by mpi.meal_plan_id, i.id, i.name, i.category" in view
    assert "where mpi.input_mode = 'recipe'" in view
    assert "manual_" not in view
