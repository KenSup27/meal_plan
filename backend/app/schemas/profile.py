from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class BaselineConfirmRequest(BaseModel):
    sex: Literal["male", "female"]
    age: int = Field(ge=14, le=100)
    height_cm: Decimal = Field(gt=100, le=250, max_digits=5, decimal_places=1)
    weight_kg: Decimal = Field(gt=25, le=300, max_digits=5, decimal_places=1)
    activity_factor: Literal[Decimal("1.2"), Decimal("1.375"), Decimal("1.55")]
    goal: Literal["cut", "maintain", "bulk"]
    target_kcal: Decimal | None = Field(default=None, gt=0, max_digits=7, decimal_places=1)
    protein_g: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=1)
    carbs_g: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=1)
    fat_g: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=1)

    @field_validator("activity_factor", mode="before")
    @classmethod
    def decimal_activity_factor(cls, value: object) -> Decimal:
        # JSON numbers such as 1.2 cannot compare exactly with Decimal literals.
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("无效的活动系数") from exc


class BaselineResponse(BaseModel):
    sex: str
    age: int
    height_cm: float
    weight_kg: float
    activity_factor: float
    goal: str
    bmr_kcal: float
    tdee_kcal: float
    target_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    baseline_confirmed: bool
