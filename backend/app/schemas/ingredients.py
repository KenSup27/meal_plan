from typing import Literal

from pydantic import BaseModel, ConfigDict


IngredientCategory = Literal[
    "meat",
    "seafood",
    "dairy",
    "vegetable",
    "fruit",
    "carb",
    "seasoning",
    "other",
]


class IngredientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: IngredientCategory
    nutrition_basis: Literal["raw"]
    kcal_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float


class IngredientListResponse(BaseModel):
    items: list[IngredientResponse]
    total: int
