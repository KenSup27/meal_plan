from decimal import Decimal, ROUND_HALF_UP

from backend.app.domain import NutritionValues, RecipeIngredientRecord, RecipeRecord
from backend.app.repositories.base import Repository
from backend.app.schemas.recipes import (
    NutritionResponse,
    RecipeCreate,
    RecipeIngredientResponse,
    RecipeResponse,
    RecipeUpdate,
)


def round_one(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def nutrition_response(nutrition: NutritionValues) -> NutritionResponse:
    return NutritionResponse(
        kcal=round_one(nutrition.kcal),
        protein_g=round_one(nutrition.protein_g),
        carbs_g=round_one(nutrition.carbs_g),
        fat_g=round_one(nutrition.fat_g),
    )


def resolve_ingredients(
    repository: Repository,
    inputs,
) -> list[RecipeIngredientRecord]:
    seen: set[int] = set()
    records: list[RecipeIngredientRecord] = []
    for item in inputs:
        if item.ingredient_id in seen:
            raise ValueError(f"食材不能重复添加: {item.ingredient_id}")
        ingredient = repository.get_ingredient(item.ingredient_id)
        if ingredient is None:
            raise ValueError(f"食材不存在或已停用: {item.ingredient_id}")
        seen.add(item.ingredient_id)
        records.append(
            RecipeIngredientRecord(
                ingredient_id=item.ingredient_id,
                raw_weight_g=item.raw_weight_g,
            )
        )
    return records


def calculate_recipe_nutrition(
    repository: Repository,
    recipe: RecipeRecord,
) -> NutritionValues:
    total = NutritionValues()
    for item in recipe.ingredients:
        ingredient = repository.get_ingredient(item.ingredient_id, include_inactive=True)
        if ingredient is None:
            raise ValueError(f"菜谱引用的食材不可用: {item.ingredient_id}")
        total += ingredient.nutrition.scale(item.raw_weight_g / Decimal("100"))
    return total


def to_recipe_response(repository: Repository, recipe: RecipeRecord) -> RecipeResponse:
    ingredient_responses: list[RecipeIngredientResponse] = []
    for item in recipe.ingredients:
        ingredient = repository.get_ingredient(item.ingredient_id, include_inactive=True)
        if ingredient is None:
            raise ValueError(f"菜谱引用的食材不可用: {item.ingredient_id}")
        contribution = ingredient.nutrition.scale(item.raw_weight_g / Decimal("100"))
        ingredient_responses.append(
            RecipeIngredientResponse(
                ingredient_id=ingredient.id,
                ingredient_name=ingredient.name,
                category=ingredient.category,
                raw_weight_g=round_one(item.raw_weight_g),
                nutrition=nutrition_response(contribution),
            )
        )
    return RecipeResponse(
        id=recipe.id,
        name=recipe.name,
        description=recipe.description,
        ingredients=ingredient_responses,
        nutrition=nutrition_response(calculate_recipe_nutrition(repository, recipe)),
        archived_at=recipe.archived_at,
    )


def create_recipe(repository: Repository, user_id: str, request: RecipeCreate) -> RecipeResponse:
    recipe = repository.create_recipe(
        user_id=user_id,
        name=request.name,
        description=request.description,
        ingredients=resolve_ingredients(repository, request.ingredients),
    )
    return to_recipe_response(repository, recipe)


def list_recipes(repository: Repository, user_id: str) -> list[RecipeResponse]:
    return [
        to_recipe_response(repository, recipe)
        for recipe in repository.list_recipes(user_id)
    ]


def get_owned_recipe(repository: Repository, user_id: str, recipe_id: str, allow_archived: bool = False) -> RecipeRecord:
    recipe = repository.get_recipe(recipe_id)
    if recipe is None or recipe.user_id != user_id or (recipe.archived_at is not None and not allow_archived):
        raise LookupError("菜谱不存在")
    return recipe


def update_recipe(
    repository: Repository,
    user_id: str,
    recipe_id: str,
    request: RecipeUpdate,
) -> RecipeResponse:
    recipe = get_owned_recipe(repository, user_id, recipe_id)
    name = request.name if request.name is not None else recipe.name
    description = request.description if request.description is not None else recipe.description
    ingredients = (
        resolve_ingredients(repository, request.ingredients)
        if request.ingredients is not None
        else recipe.ingredients
    )
    recipe = repository.update_recipe(recipe, name, description, ingredients)
    return to_recipe_response(repository, recipe)


def archive_recipe(repository: Repository, user_id: str, recipe_id: str) -> None:
    repository.archive_recipe(get_owned_recipe(repository, user_id, recipe_id))
