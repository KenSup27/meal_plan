from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.repositories.memory import get_repository


client = TestClient(app)
AUTH = {"Authorization": "Bearer user-a"}
WEEK = "2026-10-12"


def setup_function() -> None:
    get_repository().reset()


def create_plan() -> None:
    response = client.post(
        "/api/v1/meal-plans",
        json={
            "week_start": WEEK,
            "target_kcal": 1800,
            "target_protein_g": 120,
            "target_carbs_g": 200,
            "target_fat_g": 60,
        },
        headers=AUTH,
    )
    assert response.status_code == 201


def create_recipe(name: str, ingredient_id: int, weight: int) -> str:
    response = client.post(
        "/api/v1/recipes",
        json={"name": name, "ingredients": [{"ingredient_id": ingredient_id, "raw_weight_g": weight}]},
        headers=AUTH,
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_nutrition_summary_includes_recipe_quantity_and_manual_meal() -> None:
    create_plan()
    chicken = create_recipe("鸡胸", 1, 100)
    response = client.put(
        f"/api/v1/meal-plans/{WEEK}/items",
        json={
            "items": [
                {
                    "planned_date": WEEK,
                    "meal_type": "lunch",
                    "input_mode": "recipe",
                    "recipe_id": chicken,
                    "quantity": 2,
                },
                {
                    "planned_date": WEEK,
                    "meal_type": "dinner",
                    "input_mode": "manual",
                    "meal_name": "食堂晚餐",
                    "manual_kcal": 500,
                    "manual_protein_g": 25,
                    "manual_carbs_g": 60,
                    "manual_fat_g": 15,
                },
            ]
        },
        headers=AUTH,
    )
    assert response.status_code == 200

    summary = client.get(f"/api/v1/meal-plans/{WEEK}/nutrition", headers=AUTH)

    assert summary.status_code == 200
    body = summary.json()
    assert body["total"] == {"kcal": 766.0, "protein_g": 71.6, "carbs_g": 60.0, "fat_g": 24.4}
    assert body["days"][0]["nutrition"] == body["total"]
    assert body["days"][0]["planned_meal_types"] == ["lunch", "dinner"]
    assert "breakfast" in body["days"][0]["missing_meal_types"]
    assert body["days"][1]["nutrition"] == {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}


def test_shopping_list_merges_same_ingredient_and_excludes_manual_meal() -> None:
    create_plan()
    chicken = create_recipe("鸡胸一", 1, 150)
    chicken_and_broccoli = client.post(
        "/api/v1/recipes",
        json={
            "name": "鸡胸二",
            "ingredients": [
                {"ingredient_id": 1, "raw_weight_g": 100},
                {"ingredient_id": 12, "raw_weight_g": 200},
            ],
        },
        headers=AUTH,
    ).json()["id"]
    client.put(
        f"/api/v1/meal-plans/{WEEK}/items",
        json={
            "items": [
                {"planned_date": WEEK, "meal_type": "lunch", "input_mode": "recipe", "recipe_id": chicken, "quantity": 2},
                {"planned_date": WEEK, "meal_type": "dinner", "input_mode": "recipe", "recipe_id": chicken_and_broccoli, "quantity": 1},
                {"planned_date": WEEK, "meal_type": "breakfast", "input_mode": "manual", "meal_name": "外卖", "manual_kcal": 1, "manual_protein_g": 1, "manual_carbs_g": 1, "manual_fat_g": 1},
            ]
        },
        headers=AUTH,
    )

    response = client.get(f"/api/v1/meal-plans/{WEEK}/shopping-list", headers=AUTH)

    assert response.status_code == 200
    assert response.json()["items"] == [
        {"ingredient_id": 1, "ingredient_name": "鸡胸肉", "category": "meat", "total_raw_weight_g": 400.0},
        {"ingredient_id": 12, "ingredient_name": "西兰花", "category": "vegetable", "total_raw_weight_g": 200.0},
    ]


def test_derived_endpoints_report_missing_plan_and_broken_recipe_as_errors() -> None:
    assert client.get(f"/api/v1/meal-plans/{WEEK}/nutrition", headers=AUTH).status_code == 404
    assert client.get(f"/api/v1/meal-plans/{WEEK}/shopping-list", headers=AUTH).status_code == 404

    create_plan()
    recipe_id = create_recipe("待归档", 1, 100)
    client.post(
        f"/api/v1/meal-plans/{WEEK}/items",
        json={"planned_date": WEEK, "meal_type": "lunch", "input_mode": "recipe", "recipe_id": recipe_id, "quantity": 1},
        headers=AUTH,
    )
    client.delete(f"/api/v1/recipes/{recipe_id}", headers=AUTH)

    assert client.get(f"/api/v1/meal-plans/{WEEK}/nutrition", headers=AUTH).status_code == 409
    assert client.get(f"/api/v1/meal-plans/{WEEK}/shopping-list", headers=AUTH).status_code == 409
