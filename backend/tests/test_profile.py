from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.repositories.memory import get_repository


client = TestClient(app)
AUTH_A = {"Authorization": "Bearer user-a"}
AUTH_B = {"Authorization": "Bearer user-b"}


def setup_function() -> None:
    get_repository().reset()


def baseline_payload() -> dict:
    return {
        "sex": "female",
        "age": 30,
        "height_cm": 165,
        "weight_kg": 60,
        "activity_factor": 1.375,
        "goal": "cut",
    }


@pytest.mark.parametrize("activity_factor", [1.2, 1.375, 1.55])
def test_baseline_accepts_all_frontend_activity_options(activity_factor: float) -> None:
    response = client.put(
        "/api/v1/profile/baseline",
        json=baseline_payload() | {"activity_factor": activity_factor},
        headers=AUTH_A,
    )
    assert response.status_code == 200
    assert response.json()["activity_factor"] == activity_factor
    assert client.get("/api/v1/profile/baseline", headers=AUTH_A).json() == response.json()


@pytest.mark.parametrize("activity_factor", [1.3, "invalid", None])
def test_baseline_rejects_unsupported_activity_options(activity_factor: object) -> None:
    response = client.put(
        "/api/v1/profile/baseline",
        json=baseline_payload() | {"activity_factor": activity_factor},
        headers=AUTH_A,
    )
    assert response.status_code == 422


def test_baseline_can_be_manually_adjusted_then_retrieved() -> None:
    response = client.put(
        "/api/v1/profile/baseline",
        json=baseline_payload() | {"target_kcal": 1500, "protein_g": 120, "carbs_g": 130, "fat_g": 45},
        headers=AUTH_A,
    )
    fetched = client.get("/api/v1/profile/baseline", headers=AUTH_A)

    assert response.status_code == 200
    assert response.json()["target_kcal"] == 1500.0
    assert response.json()["protein_g"] == 120.0
    assert response.json()["carbs_g"] == 130.0
    assert response.json()["fat_g"] == 45.0
    assert response.json()["baseline_confirmed"] is True
    assert fetched.status_code == 200
    assert fetched.json()["target_kcal"] == 1500.0


def test_baseline_is_scoped_to_user_and_rejects_negative_derived_carbs() -> None:
    assert client.get("/api/v1/profile/baseline", headers=AUTH_A).status_code == 404
    too_low = client.put(
        "/api/v1/profile/baseline",
        json=baseline_payload() | {"target_kcal": 100, "protein_g": 200, "fat_g": 100},
        headers=AUTH_A,
    )
    client.put("/api/v1/profile/baseline", json=baseline_payload(), headers=AUTH_A)
    other_user = client.get("/api/v1/profile/baseline", headers=AUTH_B)

    assert too_low.status_code == 422
    assert other_user.status_code == 404
