from decimal import Decimal, ROUND_HALF_UP

from backend.app.schemas.nutrition import (
    NutritionCalculateRequest,
    NutritionCalculateResponse,
)


def _round(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def calculate_nutrition(
    request: NutritionCalculateRequest,
) -> NutritionCalculateResponse:
    weight = Decimal(str(request.weight_kg))
    height = Decimal(str(request.height_cm))
    age = Decimal(request.age)
    activity = Decimal(str(request.activity_factor))

    base = Decimal("10") * weight + Decimal("6.25") * height - Decimal("5") * age
    bmr = base + (Decimal("5") if request.sex == "male" else Decimal("-161"))
    tdee = bmr * activity

    goal_adjustments = {
        "cut": Decimal("-400"),
        "maintain": Decimal("0"),
        "bulk": Decimal("300"),
    }
    target = tdee + goal_adjustments[request.goal]
    protein = weight * Decimal("1.8")
    fat = target * Decimal("0.25") / Decimal("9")
    carbs = (target - protein * Decimal("4") - fat * Decimal("9")) / Decimal("4")

    if carbs < 0:
        raise ValueError("目标热量不足以分配出非负碳水，请调整基础数据或目标")

    return NutritionCalculateResponse(
        bmr_kcal=_round(bmr),
        tdee_kcal=_round(tdee),
        target_kcal=_round(target),
        protein_g=_round(protein),
        carbs_g=_round(carbs),
        fat_g=_round(fat),
    )
