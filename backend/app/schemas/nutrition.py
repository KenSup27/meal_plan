from typing import Literal

from pydantic import BaseModel, Field


class NutritionCalculateRequest(BaseModel):
    sex: Literal["male", "female"]
    age: int = Field(ge=14, le=100)
    height_cm: float = Field(gt=100, le=250)
    weight_kg: float = Field(gt=25, le=300)
    activity_factor: Literal[1.2, 1.375, 1.55]
    goal: Literal["cut", "maintain", "bulk"]


class NutritionCalculateResponse(BaseModel):
    bmr_kcal: float
    tdee_kcal: float
    target_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
