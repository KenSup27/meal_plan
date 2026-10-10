from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from backend.app.schemas.recipes import NutritionResponse


MealType = Literal["breakfast", "lunch", "dinner"]
InputMode = Literal["recipe", "manual"]


class MealPlanCreate(BaseModel):
    week_start: date
    target_kcal: Decimal = Field(gt=0, max_digits=7, decimal_places=1)
    target_protein_g: Decimal = Field(ge=0, max_digits=6, decimal_places=1)
    target_carbs_g: Decimal = Field(ge=0, max_digits=6, decimal_places=1)
    target_fat_g: Decimal = Field(ge=0, max_digits=6, decimal_places=1)


class MealPlanItemInput(BaseModel):
    id: UUID | None = None
    planned_date: date
    meal_type: MealType
    input_mode: InputMode
    recipe_id: str | None = None
    meal_name: str | None = Field(default=None, max_length=80)
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)
    manual_kcal: Decimal | None = Field(default=None, ge=0, max_digits=8, decimal_places=1)
    manual_protein_g: Decimal | None = Field(default=None, ge=0, max_digits=7, decimal_places=1)
    manual_carbs_g: Decimal | None = Field(default=None, ge=0, max_digits=7, decimal_places=1)
    manual_fat_g: Decimal | None = Field(default=None, ge=0, max_digits=7, decimal_places=1)
    sort_order: int = Field(default=0, ge=0, le=10000)

    @model_validator(mode="after")
    def validate_mode_fields(self):
        if self.input_mode == "recipe":
            if not self.recipe_id:
                raise ValueError("菜谱餐必须提供 recipe_id")
            if self.quantity is None:
                raise ValueError("菜谱餐必须提供 quantity")
            if any(value is not None for value in (
                self.manual_kcal,
                self.manual_protein_g,
                self.manual_carbs_g,
                self.manual_fat_g,
            )):
                raise ValueError("菜谱餐不能提供人工营养值")
        else:
            if self.recipe_id is not None:
                raise ValueError("人工餐不能提供 recipe_id")
            if self.quantity is not None:
                raise ValueError("人工餐不能提供 quantity")
            if any(value is None for value in (
                self.manual_kcal,
                self.manual_protein_g,
                self.manual_carbs_g,
                self.manual_fat_g,
            )):
                raise ValueError("人工餐必须完整提供营养值")
        return self


class MealPlanItemsRequest(BaseModel):
    items: list[MealPlanItemInput] = Field(max_length=100)
    expected_revision: str | None = Field(default=None, max_length=80)


class MealPlanItemResponse(BaseModel):
    id: str
    planned_date: date
    meal_type: MealType
    input_mode: InputMode
    recipe_id: str | None
    meal_name: str | None
    quantity: float | None
    manual_nutrition: NutritionResponse | None
    sort_order: int


class MealPlanTargetResponse(BaseModel):
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class MealPlanResponse(BaseModel):
    id: str
    week_start: date
    status: Literal["draft", "confirmed"]
    revision: str | None = None
    target: MealPlanTargetResponse
    items: list[MealPlanItemResponse]


class NutritionDayResponse(BaseModel):
    planned_date: date
    nutrition: NutritionResponse
    planned_meal_types: list[MealType]
    missing_meal_types: list[MealType]


class MealPlanNutritionResponse(BaseModel):
    week_start: date
    target: MealPlanTargetResponse
    total: NutritionResponse
    days: list[NutritionDayResponse]


class ShoppingListItemResponse(BaseModel):
    ingredient_id: int
    ingredient_name: str
    category: str
    total_raw_weight_g: float


class ShoppingListResponse(BaseModel):
    week_start: date
    items: list[ShoppingListItemResponse]
