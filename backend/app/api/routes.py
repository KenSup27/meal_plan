from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from backend.app.core.auth import get_auth_client, get_current_user_id
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
from backend.app.schemas.auth import (
    AuthResponse,
    AuthSessionResponse,
    AuthUserResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    StatusResponse,
)
from backend.app.services.auth import AuthProviderError, AuthResult, SupabaseAuthClient
from backend.app.schemas.nutrition import (
    NutritionCalculateRequest,
    NutritionCalculateResponse,
)
from backend.app.services.nutrition import calculate_nutrition


router = APIRouter(prefix="/api/v1")


def _auth_response(result: AuthResult, message: str | None = None) -> AuthResponse:
    session = result.session
    return AuthResponse(
        user=AuthUserResponse(
            id=result.user.id,
            email=result.user.email,
            email_confirmed_at=result.user.email_confirmed_at,
        ),
        session=(
            AuthSessionResponse(
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                token_type=session.token_type,
                expires_in=session.expires_in,
                expires_at=session.expires_at,
            )
            if session
            else None
        ),
        message=message,
    )


def _raise_auth_error(exc: AuthProviderError) -> None:
    if exc.status_code == 429:
        status_code = 429
    elif exc.status_code in (401, 403):
        status_code = 401
    elif exc.status_code == 409 or exc.code in {"user_already_exists", "email_exists"}:
        status_code = 409
    elif 400 <= exc.status_code < 500:
        status_code = 400
    else:
        status_code = 502 if exc.status_code != 503 else 503
    raise HTTPException(status_code=status_code, detail=exc.message) from exc


def _require_auth_client(auth_client: SupabaseAuthClient | None) -> SupabaseAuthClient:
    if auth_client is None:
        raise HTTPException(status_code=503, detail="Supabase Auth 尚未配置")
    return auth_client


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/auth/register", response_model=AuthResponse, status_code=201)
def auth_register(
    request: RegisterRequest,
    auth_client: Annotated[SupabaseAuthClient | None, Depends(get_auth_client)] = None,
) -> AuthResponse:
    client = _require_auth_client(auth_client)
    try:
        result = client.sign_up(request.email, request.password)
        message = None if result.session else "注册成功，请先完成邮箱确认后再登录"
        return _auth_response(result, message)
    except AuthProviderError as exc:
        _raise_auth_error(exc)


@router.post("/auth/login", response_model=AuthResponse)
def auth_login(
    request: LoginRequest,
    auth_client: Annotated[SupabaseAuthClient | None, Depends(get_auth_client)] = None,
) -> AuthResponse:
    client = _require_auth_client(auth_client)
    try:
        return _auth_response(client.sign_in(request.email, request.password))
    except AuthProviderError as exc:
        _raise_auth_error(exc)


@router.post("/auth/refresh", response_model=AuthResponse)
def auth_refresh(
    request: RefreshRequest,
    auth_client: Annotated[SupabaseAuthClient | None, Depends(get_auth_client)] = None,
) -> AuthResponse:
    client = _require_auth_client(auth_client)
    try:
        return _auth_response(client.refresh_session(request.refresh_token))
    except AuthProviderError as exc:
        _raise_auth_error(exc)


@router.post("/auth/logout", response_model=StatusResponse)
def auth_logout(
    authorization: Annotated[str | None, Header()] = None,
    auth_client: Annotated[SupabaseAuthClient | None, Depends(get_auth_client)] = None,
) -> StatusResponse:
    client = _require_auth_client(auth_client)
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 Authorization Bearer 凭证")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Authorization 必须使用 Bearer 凭证")
    try:
        client.sign_out(token.strip())
        return StatusResponse(status="ok")
    except AuthProviderError as exc:
        _raise_auth_error(exc)


@router.get("/auth/me", response_model=AuthUserResponse)
def auth_me(
    authorization: Annotated[str | None, Header()] = None,
    auth_client: Annotated[SupabaseAuthClient | None, Depends(get_auth_client)] = None,
) -> AuthUserResponse:
    client = _require_auth_client(auth_client)
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 Authorization Bearer 凭证")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Authorization 必须使用 Bearer 凭证")
    try:
        user = client.get_user(token.strip())
        return AuthUserResponse(id=user.id, email=user.email, email_confirmed_at=user.email_confirmed_at)
    except AuthProviderError as exc:
        _raise_auth_error(exc)


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
