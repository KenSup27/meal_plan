from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.repositories.memory import get_repository


client = TestClient(app)
AUTH_A = {"Authorization": "Bearer user-a"}
AUTH_B = {"Authorization": "Bearer user-b"}


def setup_function() -> None:
    get_repository().reset()


def recipe_payload() -> dict:
    return {
        "name": "鸡胸西兰花",
        "description": "一盘菜",
        "ingredients": [
            {"ingredient_id": 1, "raw_weight_g": 150},
            {"ingredient_id": 12, "raw_weight_g": 200},
            {"ingredient_id": 30, "raw_weight_g": 5},
        ],
    }


def test_create_recipe_recalculates_nutrition_from_ingredients() -> None:
    response = client.post("/api/v1/recipes", json=recipe_payload(), headers=AUTH_A)

    assert response.status_code == 201
    body = response.json()
    assert body["nutrition"] == {
        "kcal": 311.7,
        "protein_g": 40.6,
        "carbs_g": 8.6,
        "fat_g": 12.9,
    }
    assert len(body["ingredients"]) == 3


def test_recipe_list_is_scoped_to_current_user() -> None:
    client.post("/api/v1/recipes", json=recipe_payload(), headers=AUTH_A)
    client.post("/api/v1/recipes", json=recipe_payload() | {"name": "用户B的菜"}, headers=AUTH_B)

    response = client.get("/api/v1/recipes", headers=AUTH_A)

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["items"]] == ["鸡胸西兰花"]


def test_other_user_cannot_read_or_modify_recipe() -> None:
    created = client.post("/api/v1/recipes", json=recipe_payload(), headers=AUTH_A).json()
    recipe_id = created["id"]

    assert client.get(f"/api/v1/recipes/{recipe_id}", headers=AUTH_B).status_code == 404
    assert client.patch(
        f"/api/v1/recipes/{recipe_id}",
        json={"name": "越权修改"},
        headers=AUTH_B,
    ).status_code == 404
    assert client.delete(f"/api/v1/recipes/{recipe_id}", headers=AUTH_B).status_code == 404


def test_recipe_rejects_unknown_or_duplicate_ingredients() -> None:
    unknown = client.post(
        "/api/v1/recipes",
        json={"name": "坏菜谱", "ingredients": [{"ingredient_id": 999, "raw_weight_g": 10}]},
        headers=AUTH_A,
    )
    duplicate = client.post(
        "/api/v1/recipes",
        json={
            "name": "重复食材",
            "ingredients": [
                {"ingredient_id": 1, "raw_weight_g": 10},
                {"ingredient_id": 1, "raw_weight_g": 20},
            ],
        },
        headers=AUTH_A,
    )

    assert unknown.status_code == 422
    assert duplicate.status_code == 422


def test_recipe_update_and_archive() -> None:
    created = client.post("/api/v1/recipes", json=recipe_payload(), headers=AUTH_A).json()
    recipe_id = created["id"]

    updated = client.patch(
        f"/api/v1/recipes/{recipe_id}",
        json={"name": "更新后的菜谱", "ingredients": [{"ingredient_id": 2, "raw_weight_g": 100}]},
        headers=AUTH_A,
    )
    archived = client.delete(f"/api/v1/recipes/{recipe_id}", headers=AUTH_A)
    listed = client.get("/api/v1/recipes", headers=AUTH_A)

    assert updated.status_code == 200
    assert updated.json()["name"] == "更新后的菜谱"
    assert updated.json()["nutrition"]["kcal"] == 181.0
    assert archived.status_code == 204
    assert listed.json() == {"items": [], "total": 0}
