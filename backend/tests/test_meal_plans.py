from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.repositories.memory import get_repository


client = TestClient(app)
AUTH_A = {"Authorization": "Bearer user-a"}
AUTH_B = {"Authorization": "Bearer user-b"}
WEEK = "2026-10-12"


def setup_function() -> None:
    get_repository().reset()


def plan_payload() -> dict:
    return {
        "week_start": WEEK,
        "target_kcal": 1800,
        "target_protein_g": 120,
        "target_carbs_g": 200,
        "target_fat_g": 60,
    }


def recipe_payload() -> dict:
    return {"name": "鸡胸肉", "ingredients": [{"ingredient_id": 1, "raw_weight_g": 150}]}


def test_create_and_get_plan_keeps_target_snapshot() -> None:
    created = client.post("/api/v1/meal-plans", json=plan_payload(), headers=AUTH_A)
    fetched = client.get(f"/api/v1/meal-plans/{WEEK}", headers=AUTH_A)

    assert created.status_code == 201
    assert fetched.status_code == 200
    assert fetched.json()["target"] == {"kcal": 1800.0, "protein_g": 120.0, "carbs_g": 200.0, "fat_g": 60.0}
    assert fetched.json()["items"] == []


def test_plan_requires_monday_and_rejects_duplicate_week() -> None:
    not_monday = client.post(
        "/api/v1/meal-plans",
        json=plan_payload() | {"week_start": "2026-10-13"},
        headers=AUTH_A,
    )
    client.post("/api/v1/meal-plans", json=plan_payload(), headers=AUTH_A)
    duplicate = client.post("/api/v1/meal-plans", json=plan_payload(), headers=AUTH_A)

    assert not_monday.status_code == 422
    assert duplicate.status_code == 409


def test_plan_items_support_same_meal_multiple_recipes_and_manual_mode() -> None:
    client.post("/api/v1/meal-plans", json=plan_payload(), headers=AUTH_A)
    first_recipe = client.post("/api/v1/recipes", json=recipe_payload(), headers=AUTH_A).json()
    second_recipe = client.post(
        "/api/v1/recipes",
        json=recipe_payload() | {"name": "西兰花", "ingredients": [{"ingredient_id": 12, "raw_weight_g": 200}]},
        headers=AUTH_A,
    ).json()
    items = [
        {
            "planned_date": "2026-10-12",
            "meal_type": "lunch",
            "input_mode": "recipe",
            "recipe_id": first_recipe["id"],
            "quantity": 1,
        },
        {
            "planned_date": "2026-10-12",
            "meal_type": "lunch",
            "input_mode": "recipe",
            "recipe_id": second_recipe["id"],
            "quantity": 2,
        },
        {
            "planned_date": "2026-10-12",
            "meal_type": "breakfast",
            "input_mode": "manual",
            "meal_name": "外卖早餐",
            "manual_kcal": 400,
            "manual_protein_g": 20,
            "manual_carbs_g": 50,
            "manual_fat_g": 12,
        },
    ]

    response = client.put(f"/api/v1/meal-plans/{WEEK}/items", json={"items": items}, headers=AUTH_A)

    assert response.status_code == 200
    assert len(response.json()["items"]) == 3
    assert [item["meal_type"] for item in response.json()["items"]].count("lunch") == 2


def test_plan_rejects_invalid_mode_and_foreign_recipe() -> None:
    client.post("/api/v1/meal-plans", json=plan_payload(), headers=AUTH_A)
    foreign_recipe = client.post("/api/v1/recipes", json=recipe_payload(), headers=AUTH_B).json()
    invalid_mode = client.post(
        f"/api/v1/meal-plans/{WEEK}/items",
        json={
            "planned_date": WEEK,
            "meal_type": "lunch",
            "input_mode": "manual",
            "recipe_id": foreign_recipe["id"],
            "manual_kcal": 100,
            "manual_protein_g": 5,
            "manual_carbs_g": 10,
            "manual_fat_g": 2,
        },
        headers=AUTH_A,
    )
    foreign = client.post(
        f"/api/v1/meal-plans/{WEEK}/items",
        json={
            "planned_date": WEEK,
            "meal_type": "lunch",
            "input_mode": "recipe",
            "recipe_id": foreign_recipe["id"],
            "quantity": 1,
        },
        headers=AUTH_A,
    )

    assert invalid_mode.status_code == 422
    assert foreign.status_code == 404
