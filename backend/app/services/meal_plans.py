from datetime import date
from decimal import Decimal
from uuid import uuid4

from backend.app.domain import MealPlanItemRecord, MealPlanRecord, NutritionValues
from backend.app.repositories.memory import MemoryRepository
from backend.app.schemas.meal_plans import (
    MealPlanCreate,
    MealPlanItemInput,
    MealPlanItemResponse,
    MealPlanResponse,
    MealPlanTargetResponse,
)
from backend.app.services.recipes import nutrition_response


def validate_week_start(week_start: date) -> None:
    if week_start.isoweekday() != 1:
        raise ValueError("week_start 必须是周一")


def to_item_record(
    repository: MemoryRepository,
    user_id: str,
    item: MealPlanItemInput,
) -> MealPlanItemRecord:
    if item.input_mode == "recipe":
        recipe = repository.get_recipe(item.recipe_id)
        if recipe is None or recipe.user_id != user_id or recipe.archived_at is not None:
            raise LookupError("计划餐项引用的菜谱不存在")
        manual_nutrition = None
    else:
        manual_nutrition = NutritionValues(
            kcal=item.manual_kcal,
            protein_g=item.manual_protein_g,
            carbs_g=item.manual_carbs_g,
            fat_g=item.manual_fat_g,
        )
    return MealPlanItemRecord(
        id=str(uuid4()),
        planned_date=item.planned_date,
        meal_type=item.meal_type,
        input_mode=item.input_mode,
        recipe_id=item.recipe_id,
        meal_name=item.meal_name,
        quantity=item.quantity,
        manual_nutrition=manual_nutrition,
        sort_order=item.sort_order,
    )


def to_plan_response(plan: MealPlanRecord) -> MealPlanResponse:
    return MealPlanResponse(
        id=plan.id,
        week_start=plan.week_start,
        status=plan.status,
        target=MealPlanTargetResponse(
            kcal=float(plan.target.kcal),
            protein_g=float(plan.target.protein_g),
            carbs_g=float(plan.target.carbs_g),
            fat_g=float(plan.target.fat_g),
        ),
        items=[
            MealPlanItemResponse(
                id=item.id,
                planned_date=item.planned_date,
                meal_type=item.meal_type,
                input_mode=item.input_mode,
                recipe_id=item.recipe_id,
                meal_name=item.meal_name,
                quantity=float(item.quantity) if item.quantity is not None else None,
                manual_nutrition=(
                    nutrition_response(item.manual_nutrition)
                    if item.manual_nutrition is not None
                    else None
                ),
                sort_order=item.sort_order,
            )
            for item in plan.items
        ],
    )


def create_plan(
    repository: MemoryRepository,
    user_id: str,
    request: MealPlanCreate,
) -> MealPlanResponse:
    validate_week_start(request.week_start)
    if repository.get_meal_plan(user_id, request.week_start) is not None:
        raise FileExistsError("该周计划已存在")
    plan = MealPlanRecord(
        id=str(uuid4()),
        user_id=user_id,
        week_start=request.week_start,
        target=NutritionValues(
            kcal=request.target_kcal,
            protein_g=request.target_protein_g,
            carbs_g=request.target_carbs_g,
            fat_g=request.target_fat_g,
        ),
    )
    repository.create_meal_plan(plan)
    return to_plan_response(plan)


def get_owned_plan(repository: MemoryRepository, user_id: str, week_start: date) -> MealPlanRecord:
    plan = repository.get_meal_plan(user_id, week_start)
    if plan is None:
        raise LookupError("周计划不存在")
    return plan


def add_item(
    repository: MemoryRepository,
    user_id: str,
    week_start: date,
    request: MealPlanItemInput,
) -> MealPlanResponse:
    validate_week_start(week_start)
    plan = get_owned_plan(repository, user_id, week_start)
    if not (week_start <= request.planned_date <= week_start.replace(day=week_start.day + 6)):
        raise ValueError("planned_date 必须位于该周计划内")
    plan.items.append(to_item_record(repository, user_id, request))
    return to_plan_response(plan)


def replace_items(
    repository: MemoryRepository,
    user_id: str,
    week_start: date,
    requests: list[MealPlanItemInput],
) -> MealPlanResponse:
    validate_week_start(week_start)
    plan = get_owned_plan(repository, user_id, week_start)
    records: list[MealPlanItemRecord] = []
    week_end = week_start.fromordinal(week_start.toordinal() + 6)
    for request in requests:
        if not (week_start <= request.planned_date <= week_end):
            raise ValueError("planned_date 必须位于该周计划内")
        records.append(to_item_record(repository, user_id, request))
    plan.items = records
    return to_plan_response(plan)
