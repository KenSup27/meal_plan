from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_calculate_nutrition() -> None:
    response = client.post(
        "/api/v1/nutrition/calculate",
        json={
            "sex": "female",
            "age": 30,
            "height_cm": 165,
            "weight_kg": 60,
            "activity_factor": 1.375,
            "goal": "cut",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "bmr_kcal": 1320.0,
        "tdee_kcal": 1815.0,
        "target_kcal": 1415.0,
        "protein_g": 108.0,
        "carbs_g": 154.2,
        "fat_g": 39.3,
    }


def test_invalid_nutrition_input() -> None:
    response = client.post(
        "/api/v1/nutrition/calculate",
        json={
            "sex": "female",
            "age": 10,
            "height_cm": 165,
            "weight_kg": 60,
            "activity_factor": 1.375,
            "goal": "cut",
        },
    )

    assert response.status_code == 422


def test_frontend_shell_is_served() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "带饭营养规划" in response.text
