from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.core.auth import get_current_user_id
from backend.app.repositories.memory import get_repository
from backend.app.schemas.ingredients import (
    IngredientCategory,
    IngredientListResponse,
)
from backend.app.schemas.recipes import (
    RecipeCreate,
    RecipeListResponse,
    RecipeResponse,
    RecipeUpdate,
)
from backend.app.schemas.meal_plans import (
    MealPlanCreate,
    MealPlanItemInput,
    MealPlanItemsRequest,
    MealPlanNutritionResponse,
    MealPlanResponse,
    ShoppingListResponse,
)
from backend.app.schemas.profile import BaselineConfirmRequest, BaselineResponse
from backend.app.schemas.nutrition import (
    NutritionCalculateRequest,
    NutritionCalculateResponse,
)
from backend.app.services.nutrition import calculate_nutrition


router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ingredients", response_model=IngredientListResponse)
def ingredients(
    _user_id: Annotated[str, Depends(get_current_user_id)],
    query: Annotated[str | None, Query(alias="q", min_length=1, max_length=80)] = None,
    category: IngredientCategory | None = None,
) -> IngredientListResponse:
    from backend.app.services.ingredients import list_ingredients

    items = list_ingredients(get_repository(), query=query, category=category)
    return IngredientListResponse(items=items, total=len(items))


@router.post("/recipes", response_model=RecipeResponse, status_code=201)
def recipe_create(
    request: RecipeCreate,
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> RecipeResponse:
    from backend.app.services.recipes import create_recipe

    try:
        return create_recipe(get_repository(), user_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/recipes", response_model=RecipeListResponse)
def recipe_list(user_id: Annotated[str, Depends(get_current_user_id)]) -> RecipeListResponse:
    from backend.app.services.recipes import list_recipes

    items = list_recipes(get_repository(), user_id)
    return RecipeListResponse(items=items, total=len(items))


@router.get("/recipes/{recipe_id}", response_model=RecipeResponse)
def recipe_get(
    recipe_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> RecipeResponse:
    from backend.app.services.recipes import get_owned_recipe, to_recipe_response

    try:
        return to_recipe_response(get_repository(), get_owned_recipe(get_repository(), user_id, recipe_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/recipes/{recipe_id}", response_model=RecipeResponse)
def recipe_update(
    recipe_id: str,
    request: RecipeUpdate,
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> RecipeResponse:
    from backend.app.services.recipes import update_recipe

    try:
        return update_recipe(get_repository(), user_id, recipe_id, request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/recipes/{recipe_id}", status_code=204)
def recipe_archive(
    recipe_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> None:
    from backend.app.services.recipes import archive_recipe

    try:
        archive_recipe(get_repository(), user_id, recipe_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/meal-plans", response_model=MealPlanResponse, status_code=201)
def meal_plan_create(
    request: MealPlanCreate,
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> MealPlanResponse:
    from backend.app.services.meal_plans import create_plan

    try:
        return create_plan(get_repository(), user_id, request)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/meal-plans/{week_start}", response_model=MealPlanResponse)
def meal_plan_get(
    week_start: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> MealPlanResponse:
    from datetime import date

    from backend.app.services.meal_plans import get_owned_plan, to_plan_response

    try:
        parsed_week_start = date.fromisoformat(week_start)
        return to_plan_response(get_owned_plan(get_repository(), user_id, parsed_week_start))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="week_start 必须是 YYYY-MM-DD") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/meal-plans/{week_start}/items", response_model=MealPlanResponse)
def meal_plan_item_add(
    week_start: str,
    request: MealPlanItemInput,
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> MealPlanResponse:
    from datetime import date

    from backend.app.services.meal_plans import add_item

    try:
        return add_item(get_repository(), user_id, date.fromisoformat(week_start), request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/meal-plans/{week_start}/items", response_model=MealPlanResponse)
def meal_plan_items_replace(
    week_start: str,
    request: MealPlanItemsRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> MealPlanResponse:
    from datetime import date

    from backend.app.services.meal_plans import replace_items

    try:
        return replace_items(
            get_repository(), user_id, date.fromisoformat(week_start), request.items
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/meal-plans/{week_start}/nutrition", response_model=MealPlanNutritionResponse)
def meal_plan_nutrition(
    week_start: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> MealPlanNutritionResponse:
    from datetime import date

    from backend.app.services.derived import summarize_nutrition

    try:
        return summarize_nutrition(get_repository(), user_id, date.fromisoformat(week_start))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="week_start 必须是 YYYY-MM-DD") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/meal-plans/{week_start}/shopping-list", response_model=ShoppingListResponse)
def meal_plan_shopping_list(
    week_start: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ShoppingListResponse:
    from datetime import date

    from backend.app.services.derived import shopping_list

    try:
        return shopping_list(get_repository(), user_id, date.fromisoformat(week_start))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="week_start 必须是 YYYY-MM-DD") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/nutrition/calculate", response_model=NutritionCalculateResponse)
def nutrition_calculate(
    request: NutritionCalculateRequest,
    _user_id: Annotated[str, Depends(get_current_user_id)],
) -> NutritionCalculateResponse:
    try:
        return calculate_nutrition(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/profile/baseline", response_model=BaselineResponse)
def profile_baseline_confirm(
    request: BaselineConfirmRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> BaselineResponse:
    from backend.app.services.profile import confirm_baseline

    try:
        return confirm_baseline(get_repository(), user_id, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/profile/baseline", response_model=BaselineResponse)
def profile_baseline_get(
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> BaselineResponse:
    from backend.app.services.profile import get_baseline

    try:
        return get_baseline(get_repository(), user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
