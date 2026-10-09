from fastapi import APIRouter, HTTPException

from backend.app.schemas.nutrition import (
    NutritionCalculateRequest,
    NutritionCalculateResponse,
)
from backend.app.services.nutrition import calculate_nutrition


router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/nutrition/calculate", response_model=NutritionCalculateResponse)
def nutrition_calculate(
    request: NutritionCalculateRequest,
) -> NutritionCalculateResponse:
    try:
        return calculate_nutrition(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
