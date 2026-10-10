from backend.app.domain import IngredientRecord
from backend.app.repositories.base import Repository
from backend.app.schemas.ingredients import IngredientResponse


def to_ingredient_response(ingredient: IngredientRecord) -> IngredientResponse:
    return IngredientResponse(
        id=ingredient.id,
        name=ingredient.name,
        category=ingredient.category,
        nutrition_basis=ingredient.nutrition_basis,
        kcal_per_100g=float(ingredient.nutrition.kcal),
        protein_per_100g=float(ingredient.nutrition.protein_g),
        carbs_per_100g=float(ingredient.nutrition.carbs_g),
        fat_per_100g=float(ingredient.nutrition.fat_g),
    )


def list_ingredients(
    repository: Repository,
    query: str | None = None,
    category: str | None = None,
) -> list[IngredientResponse]:
    return [
        to_ingredient_response(ingredient)
        for ingredient in repository.list_ingredients(query=query, category=category)
    ]
