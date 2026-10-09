from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.repositories.memory import get_repository


client = TestClient(app)


def setup_function() -> None:
    get_repository().reset()


def test_ingredient_catalog_lists_seed_data() -> None:
    response = client.get("/api/v1/ingredients", headers={"Authorization": "Bearer user-a"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 33
    assert body["items"][0] == {
        "id": 1,
        "name": "鸡胸肉",
        "category": "meat",
        "nutrition_basis": "raw",
        "kcal_per_100g": 133.0,
        "protein_per_100g": 23.3,
        "carbs_per_100g": 0.0,
        "fat_per_100g": 4.7,
    }


def test_ingredient_catalog_supports_search_and_category() -> None:
    response = client.get(
        "/api/v1/ingredients?q=鸡&category=meat",
        headers={"Authorization": "Bearer user-a"},
    )

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["items"]] == ["鸡胸肉", "鸡腿肉"]


def test_ingredient_catalog_requires_authentication() -> None:
    response = client.get("/api/v1/ingredients")

    assert response.status_code == 401
