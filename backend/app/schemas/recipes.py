from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class NutritionResponse(BaseModel):
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class RecipeIngredientInput(BaseModel):
    ingredient_id: int = Field(ge=1)
    raw_weight_g: Decimal = Field(gt=0, max_digits=8, decimal_places=1)


class RecipeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    ingredients: list[RecipeIngredientInput] = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("菜谱名称不能为空")
        return value


class RecipeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    ingredients: list[RecipeIngredientInput] | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("菜谱名称不能为空")
        return value


class RecipeIngredientResponse(BaseModel):
    ingredient_id: int
    ingredient_name: str
    category: str
    raw_weight_g: float
    nutrition: NutritionResponse


class RecipeResponse(BaseModel):
    id: str
    name: str
    description: str | None
    ingredients: list[RecipeIngredientResponse]
    nutrition: NutritionResponse
    archived_at: datetime | None


class RecipeListResponse(BaseModel):
    items: list[RecipeResponse]
    total: int
