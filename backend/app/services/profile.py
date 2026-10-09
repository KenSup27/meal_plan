from datetime import datetime, timezone
from decimal import Decimal

from backend.app.domain import ProfileRecord
from backend.app.repositories.memory import MemoryRepository
from backend.app.schemas.nutrition import NutritionCalculateRequest
from backend.app.schemas.profile import BaselineConfirmRequest, BaselineResponse
from backend.app.services.nutrition import calculate_nutrition


def confirm_baseline(
    repository: MemoryRepository,
    user_id: str,
    request: BaselineConfirmRequest,
) -> BaselineResponse:
    recommendation = calculate_nutrition(
        NutritionCalculateRequest(
            sex=request.sex,
            age=request.age,
            height_cm=float(request.height_cm),
            weight_kg=float(request.weight_kg),
            activity_factor=float(request.activity_factor),
            goal=request.goal,
        )
    )
    target_kcal = request.target_kcal if request.target_kcal is not None else Decimal(str(recommendation.target_kcal))
    protein_g = request.protein_g if request.protein_g is not None else Decimal(str(recommendation.protein_g))
    fat_g = request.fat_g
    if fat_g is None:
        fat_g = target_kcal * Decimal("0.25") / Decimal("9")
    carbs_g = request.carbs_g
    if carbs_g is None:
        carbs_g = (target_kcal - protein_g * Decimal("4") - fat_g * Decimal("9")) / Decimal("4")
    if carbs_g < 0:
        raise ValueError("目标热量不足以分配出非负碳水，请调整手动目标")
    profile = repository.save_profile(
        ProfileRecord(
            user_id=user_id,
            sex=request.sex,
            age=request.age,
            height_cm=request.height_cm,
            weight_kg=request.weight_kg,
            activity_factor=request.activity_factor,
            goal=request.goal,
            target_kcal=target_kcal,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            baseline_confirmed_at=datetime.now(timezone.utc),
        )
    )
    return to_baseline_response(repository, profile)


def to_baseline_response(repository: MemoryRepository, profile: ProfileRecord) -> BaselineResponse:
    calculation = calculate_nutrition(
        NutritionCalculateRequest(
            sex=profile.sex,
            age=profile.age,
            height_cm=float(profile.height_cm),
            weight_kg=float(profile.weight_kg),
            activity_factor=float(profile.activity_factor),
            goal=profile.goal,
        )
    )
    return BaselineResponse(
        sex=profile.sex,
        age=profile.age,
        height_cm=float(profile.height_cm),
        weight_kg=float(profile.weight_kg),
        activity_factor=float(profile.activity_factor),
        goal=profile.goal,
        bmr_kcal=calculation.bmr_kcal,
        tdee_kcal=calculation.tdee_kcal,
        target_kcal=float(profile.target_kcal.quantize(Decimal("0.1"))),
        protein_g=float(profile.protein_g.quantize(Decimal("0.1"))),
        carbs_g=float(profile.carbs_g.quantize(Decimal("0.1"))),
        fat_g=float(profile.fat_g.quantize(Decimal("0.1"))),
        baseline_confirmed=profile.baseline_confirmed_at is not None,
    )


def get_baseline(repository: MemoryRepository, user_id: str) -> BaselineResponse:
    profile = repository.get_profile(user_id)
    if profile is None or profile.baseline_confirmed_at is None:
        raise LookupError("营养基线尚未确认")
    return to_baseline_response(repository, profile)
