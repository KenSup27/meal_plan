from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from backend.app.domain import IngredientRecord, MealPlanRecord, NutritionValues
from backend.app.repositories.base import Repository
from backend.app.schemas.meal_plans import (
    MealPlanNutritionResponse,
    MealPlanTargetResponse,
    NutritionDayResponse,
    ShoppingListItemResponse,
    ShoppingListResponse,
)
from backend.app.services.recipes import calculate_recipe_nutrition, nutrition_response


MEAL_TYPES = ("breakfast", "lunch", "dinner")
CATEGORY_ORDER = ("meat", "seafood", "dairy", "vegetable", "fruit", "carb", "seasoning", "other")


def get_plan_for_derived_data(
    repository: Repository,
    user_id: str,
    week_start: date,
) -> MealPlanRecord:
    plan = repository.get_meal_plan(user_id, week_start)
    if plan is None:
        raise LookupError("周计划不存在")
    return plan


def item_nutrition(repository: Repository, user_id: str, item) -> NutritionValues:
    if item.input_mode == "manual":
        return item.manual_nutrition
    recipe = repository.get_recipe(item.recipe_id)
    if recipe is None or recipe.user_id != user_id:
        raise RuntimeError("计划中包含已删除或不可访问的菜谱")
    return calculate_recipe_nutrition(repository, recipe).scale(item.quantity)


def summarize_nutrition(
    repository: Repository,
    user_id: str,
    week_start: date,
) -> MealPlanNutritionResponse:
    plan = get_plan_for_derived_data(repository, user_id, week_start)
    by_day: dict[date, NutritionValues] = defaultdict(NutritionValues)
    meal_types_by_day: dict[date, set[str]] = defaultdict(set)
    total = NutritionValues()
    for item in plan.items:
        nutrition = item_nutrition(repository, user_id, item)
        by_day[item.planned_date] += nutrition
        meal_types_by_day[item.planned_date].add(item.meal_type)
        total += nutrition

    days = []
    for offset in range(7):
        planned_date = week_start + timedelta(days=offset)
        planned_types = [meal_type for meal_type in MEAL_TYPES if meal_type in meal_types_by_day[planned_date]]
        missing_types = [meal_type for meal_type in MEAL_TYPES if meal_type not in meal_types_by_day[planned_date]]
        days.append(
            NutritionDayResponse(
                planned_date=planned_date,
                nutrition=nutrition_response(by_day[planned_date]),
                planned_meal_types=planned_types,
                missing_meal_types=missing_types,
            )
        )
    return MealPlanNutritionResponse(
        week_start=week_start,
        target=MealPlanTargetResponse(
            kcal=float(plan.target.kcal),
            protein_g=float(plan.target.protein_g),
            carbs_g=float(plan.target.carbs_g),
            fat_g=float(plan.target.fat_g),
        ),
        total=nutrition_response(total),
        days=days,
    )


def shopping_list(
    repository: Repository,
    user_id: str,
    week_start: date,
) -> ShoppingListResponse:
    plan = get_plan_for_derived_data(repository, user_id, week_start)
    totals: dict[int, Decimal] = defaultdict(Decimal)
    for item in plan.items:
        if item.input_mode != "recipe":
            continue
        recipe = repository.get_recipe(item.recipe_id)
        if recipe is None or recipe.user_id != user_id:
            raise RuntimeError("计划中包含已删除或不可访问的菜谱")
        for recipe_ingredient in recipe.ingredients:
            totals[recipe_ingredient.ingredient_id] += recipe_ingredient.raw_weight_g * item.quantity

    ingredients: list[IngredientRecord] = []
    for ingredient_id in totals:
        ingredient = repository.get_ingredient(ingredient_id, include_inactive=True)
        if ingredient is None:
            raise RuntimeError("采购清单引用的食材不可用")
        ingredients.append(ingredient)
    ingredients.sort(key=lambda item: (CATEGORY_ORDER.index(item.category), item.name))
    return ShoppingListResponse(
        week_start=week_start,
        items=[
            ShoppingListItemResponse(
                ingredient_id=ingredient.id,
                ingredient_name=ingredient.name,
                category=ingredient.category,
                total_raw_weight_g=float(totals[ingredient.id].quantize(Decimal("0.1"))),
            )
            for ingredient in ingredients
        ],
    )
