from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from backend.app.domain import (
    IngredientRecord,
    MealPlanRecord,
    ProfileRecord,
    RecipeIngredientRecord,
    RecipeRecord,
    NutritionValues,
)


DEFAULT_INGREDIENTS: tuple[IngredientRecord, ...] = (
    IngredientRecord(1, "鸡胸肉", "meat", NutritionValues(Decimal("133"), Decimal("23.3"), Decimal("0"), Decimal("4.7"))),
    IngredientRecord(2, "鸡腿肉", "meat", NutritionValues(Decimal("181"), Decimal("18"), Decimal("0"), Decimal("12"))),
    IngredientRecord(3, "瘦猪肉", "meat", NutritionValues(Decimal("143"), Decimal("20.3"), Decimal("1.5"), Decimal("6.2"))),
    IngredientRecord(4, "牛里脊", "meat", NutritionValues(Decimal("155"), Decimal("22"), Decimal("0"), Decimal("7"))),
    IngredientRecord(5, "牛腱子", "meat", NutritionValues(Decimal("172"), Decimal("31"), Decimal("0"), Decimal("5"))),
    IngredientRecord(6, "虾仁", "seafood", NutritionValues(Decimal("48"), Decimal("10"), Decimal("0"), Decimal("0.7"))),
    IngredientRecord(7, "三文鱼", "seafood", NutritionValues(Decimal("208"), Decimal("20"), Decimal("0"), Decimal("13"))),
    IngredientRecord(8, "鳕鱼", "seafood", NutritionValues(Decimal("82"), Decimal("18"), Decimal("0"), Decimal("0.7"))),
    IngredientRecord(9, "鸡蛋", "dairy", NutritionValues(Decimal("144"), Decimal("12.5"), Decimal("0.7"), Decimal("9.5"))),
    IngredientRecord(10, "低脂牛奶", "dairy", NutritionValues(Decimal("46"), Decimal("3.4"), Decimal("4.8"), Decimal("1.5"))),
    IngredientRecord(11, "北豆腐", "dairy", NutritionValues(Decimal("81"), Decimal("8.1"), Decimal("4.2"), Decimal("4.2"))),
    IngredientRecord(12, "西兰花", "vegetable", NutritionValues(Decimal("34"), Decimal("2.8"), Decimal("4.3"), Decimal("0.4"))),
    IngredientRecord(13, "菠菜", "vegetable", NutritionValues(Decimal("23"), Decimal("2.9"), Decimal("3.6"), Decimal("0.4"))),
    IngredientRecord(14, "胡萝卜", "vegetable", NutritionValues(Decimal("41"), Decimal("0.9"), Decimal("9.6"), Decimal("0.2"))),
    IngredientRecord(15, "番茄", "vegetable", NutritionValues(Decimal("18"), Decimal("0.9"), Decimal("3.9"), Decimal("0.2"))),
    IngredientRecord(16, "黄瓜", "vegetable", NutritionValues(Decimal("15"), Decimal("0.7"), Decimal("3.6"), Decimal("0.1"))),
    IngredientRecord(17, "彩椒", "vegetable", NutritionValues(Decimal("31"), Decimal("1"), Decimal("6"), Decimal("0.3"))),
    IngredientRecord(18, "洋葱", "vegetable", NutritionValues(Decimal("40"), Decimal("1.1"), Decimal("9.3"), Decimal("0.1"))),
    IngredientRecord(19, "蘑菇", "vegetable", NutritionValues(Decimal("22"), Decimal("3.1"), Decimal("3.3"), Decimal("0.3"))),
    IngredientRecord(20, "玉米", "carb", NutritionValues(Decimal("86"), Decimal("3.3"), Decimal("19"), Decimal("1.4"))),
    IngredientRecord(21, "大米", "carb", NutritionValues(Decimal("346"), Decimal("7.4"), Decimal("77.2"), Decimal("0.8"))),
    IngredientRecord(22, "糙米", "carb", NutritionValues(Decimal("348"), Decimal("7.3"), Decimal("72"), Decimal("2.7"))),
    IngredientRecord(23, "燕麦片", "carb", NutritionValues(Decimal("367"), Decimal("15"), Decimal("61"), Decimal("6.7"))),
    IngredientRecord(24, "全麦面包", "carb", NutritionValues(Decimal("246"), Decimal("10.2"), Decimal("43"), Decimal("4.2"))),
    IngredientRecord(25, "意大利面", "carb", NutritionValues(Decimal("350"), Decimal("12.5"), Decimal("72"), Decimal("1.5"))),
    IngredientRecord(26, "红薯", "carb", NutritionValues(Decimal("86"), Decimal("1.6"), Decimal("20.1"), Decimal("0.1"))),
    IngredientRecord(27, "土豆", "carb", NutritionValues(Decimal("77"), Decimal("2"), Decimal("17.5"), Decimal("0.1"))),
    IngredientRecord(28, "香蕉", "fruit", NutritionValues(Decimal("89"), Decimal("1.1"), Decimal("22.8"), Decimal("0.3"))),
    IngredientRecord(29, "苹果", "fruit", NutritionValues(Decimal("52"), Decimal("0.3"), Decimal("13.8"), Decimal("0.2"))),
    IngredientRecord(30, "橄榄油", "seasoning", NutritionValues(Decimal("884"), Decimal("0"), Decimal("0"), Decimal("100"))),
    IngredientRecord(31, "酱油", "seasoning", NutritionValues(Decimal("53"), Decimal("8.1"), Decimal("4.9"), Decimal("0.1"))),
    IngredientRecord(32, "食盐", "seasoning", NutritionValues(Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))),
    IngredientRecord(33, "黑胡椒", "seasoning", NutritionValues(Decimal("251"), Decimal("10.4"), Decimal("63.9"), Decimal("3.3"))),
)


class MemoryRepository:
    """Replaceable local adapter used until the database contract is final."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.ingredients: dict[int, IngredientRecord] = {
            ingredient.id: ingredient for ingredient in DEFAULT_INGREDIENTS
        }
        self.recipes: dict[str, RecipeRecord] = {}
        self.profiles: dict[str, ProfileRecord] = {}
        self.meal_plans: dict[str, MealPlanRecord] = {}

    def list_ingredients(self, query: str | None = None, category: str | None = None) -> list[IngredientRecord]:
        normalized = query.casefold() if query else None
        return [
            ingredient
            for ingredient in self.ingredients.values()
            if ingredient.is_active
            and (not normalized or normalized in ingredient.name.casefold())
            and (not category or ingredient.category == category)
        ]

    def get_ingredient(self, ingredient_id: int, include_inactive: bool = False) -> IngredientRecord | None:
        ingredient = self.ingredients.get(ingredient_id)
        return ingredient if ingredient and (ingredient.is_active or include_inactive) else None

    def create_recipe(
        self,
        user_id: str,
        name: str,
        description: str | None,
        ingredients: list[RecipeIngredientRecord],
    ) -> RecipeRecord:
        recipe = RecipeRecord(str(uuid4()), user_id, name, description, ingredients)
        self.recipes[recipe.id] = recipe
        return recipe

    def list_recipes(self, user_id: str, include_archived: bool = False) -> list[RecipeRecord]:
        return [
            recipe
            for recipe in self.recipes.values()
            if recipe.user_id == user_id and (include_archived or recipe.archived_at is None)
        ]

    def get_recipe(self, recipe_id: str) -> RecipeRecord | None:
        return self.recipes.get(recipe_id)

    def update_recipe(
        self,
        recipe: RecipeRecord,
        name: str,
        description: str | None,
        ingredients: list[RecipeIngredientRecord],
    ) -> RecipeRecord:
        recipe.name = name
        recipe.description = description
        recipe.ingredients = ingredients
        recipe.archived_at = None
        return recipe

    def archive_recipe(self, recipe: RecipeRecord) -> RecipeRecord:
        recipe.archived_at = datetime.now(timezone.utc)
        return recipe

    def save_profile(self, profile: ProfileRecord) -> ProfileRecord:
        self.profiles[profile.user_id] = profile
        return profile

    def get_profile(self, user_id: str) -> ProfileRecord | None:
        return self.profiles.get(user_id)

    def create_meal_plan(self, plan: MealPlanRecord) -> MealPlanRecord:
        plan.revision = str(uuid4())
        self.meal_plans[plan.id] = plan
        return plan

    def get_meal_plan(self, user_id: str, week_start) -> MealPlanRecord | None:
        return next(
            (
                plan
                for plan in self.meal_plans.values()
                if plan.user_id == user_id and plan.week_start == week_start
            ),
            None,
        )

    def get_meal_plan_by_id(self, plan_id: str) -> MealPlanRecord | None:
        return self.meal_plans.get(plan_id)


    def add_plan_item(self, plan, item):
        plan.items.append(item)
        plan.revision = str(uuid4())
        return plan

    def replace_plan_items(self, plan, items, expected_revision=None):
        if expected_revision != plan.revision:
            from backend.app.repositories.base import RepositoryError
            raise RepositoryError(409, "计划已被修改，请重新加载后再保存")
        plan.items = items
        plan.revision = str(uuid4())
        return plan


repository = MemoryRepository()


def get_repository() -> MemoryRepository:
    return repository
