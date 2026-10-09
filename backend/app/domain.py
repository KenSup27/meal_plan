from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class NutritionValues:
    kcal: Decimal = Decimal("0")
    protein_g: Decimal = Decimal("0")
    carbs_g: Decimal = Decimal("0")
    fat_g: Decimal = Decimal("0")

    def __add__(self, other: "NutritionValues") -> "NutritionValues":
        return NutritionValues(
            self.kcal + other.kcal,
            self.protein_g + other.protein_g,
            self.carbs_g + other.carbs_g,
            self.fat_g + other.fat_g,
        )

    def scale(self, quantity: Decimal) -> "NutritionValues":
        return NutritionValues(
            self.kcal * quantity,
            self.protein_g * quantity,
            self.carbs_g * quantity,
            self.fat_g * quantity,
        )


@dataclass(frozen=True)
class IngredientRecord:
    id: int
    name: str
    category: str
    nutrition: NutritionValues
    nutrition_basis: str = "raw"
    is_active: bool = True


@dataclass(frozen=True)
class RecipeIngredientRecord:
    ingredient_id: int
    raw_weight_g: Decimal


@dataclass
class RecipeRecord:
    id: str
    user_id: str
    name: str
    description: str | None
    ingredients: list[RecipeIngredientRecord]
    archived_at: datetime | None = None


@dataclass
class ProfileRecord:
    user_id: str
    sex: str
    age: int
    height_cm: Decimal
    weight_kg: Decimal
    activity_factor: Decimal
    goal: str
    target_kcal: Decimal
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal
    baseline_confirmed_at: datetime | None = None


@dataclass
class MealPlanItemRecord:
    id: str
    planned_date: date
    meal_type: str
    input_mode: str
    recipe_id: str | None = None
    meal_name: str | None = None
    quantity: Decimal | None = None
    manual_nutrition: NutritionValues | None = None
    sort_order: int = 0


@dataclass
class MealPlanRecord:
    id: str
    user_id: str
    week_start: date
    target: NutritionValues
    items: list[MealPlanItemRecord] = field(default_factory=list)
    status: str = "draft"
