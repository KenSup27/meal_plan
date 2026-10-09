from datetime import datetime, timezone
import json

import httpx
from fastapi.testclient import TestClient

from backend.app.core.auth import get_auth_client
from backend.app.main import app
from backend.app.services.auth import (
    AuthProviderError,
    AuthResult,
    AuthSession,
    AuthUser,
    SupabaseAuthClient,
)


class FakeAuthClient:
    def __init__(self) -> None:
        self.user = AuthUser(
            id="user-uuid",
            email="person@example.com",
            email_confirmed_at=datetime(2026, 10, 9, tzinfo=timezone.utc),
        )
        self.session = AuthSession("access-token", "refresh-token", expires_in=3600, expires_at=1_800_000_000)
        self.calls: list[tuple[str, str]] = []

    def sign_up(self, email: str, password: str, display_name: str | None = None) -> AuthResult:
        self.calls.append(("sign_up", email))
        return AuthResult(self.user, self.session)

    def sign_in(self, email: str, password: str) -> AuthResult:
        self.calls.append(("sign_in", email))
        return AuthResult(self.user, self.session)

    def refresh_session(self, refresh_token: str) -> AuthResult:
        self.calls.append(("refresh", refresh_token))
        return AuthResult(self.user, self.session)

    def get_user(self, access_token: str) -> AuthUser:
        self.calls.append(("get_user", access_token))
        if access_token == "bad-token":
            raise AuthProviderError(401, "invalid token")
        return self.user

    def sign_out(self, access_token: str) -> None:
        self.calls.append(("sign_out", access_token))


def test_supabase_auth_adapter_maps_signup_and_provider_errors() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/signup"):
            return httpx.Response(
                200,
                json={
                    "user": {"id": "u1", "email": "person@example.com"},
                    "session": None,
                },
            )
        return httpx.Response(400, json={"code": "user_already_exists", "msg": "用户已存在"})

    client = SupabaseAuthClient(
        "https://project.supabase.co",
        "publishable-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = client.sign_up("person@example.com", "password123", "小明")

    assert result.user.id == "u1"
    assert result.session is None
    assert requests[0].headers["apikey"] == "publishable-key"
    assert json.loads(requests[0].content) == {
        "email": "person@example.com",
        "password": "password123",
        "options": {"data": {"display_name": "小明"}},
    }

    try:
        client.sign_in("person@example.com", "password123")
    except AuthProviderError as exc:
        assert exc.status_code == 400
        assert exc.code == "user_already_exists"
    else:
        raise AssertionError("expected AuthProviderError")

    client.close()


def test_auth_routes_register_login_refresh_me_logout() -> None:
    fake = FakeAuthClient()
    app.dependency_overrides[get_auth_client] = lambda: fake
    client = TestClient(app)

    try:
        register = client.post(
            "/api/v1/auth/register",
            json={"email": " Person@Example.com ", "password": "password123", "display_name": "小明"},
        )
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "person@example.com", "password": "password123"},
        )
        refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": "refresh-token"})
        me = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer access-token"})
        logout = client.post("/api/v1/auth/logout", headers={"Authorization": "Bearer access-token"})

        assert register.status_code == 201
        assert register.json()["user"]["email"] == "person@example.com"
        assert login.status_code == 200
        assert login.json()["session"]["access_token"] == "access-token"
        assert refresh.status_code == 200
        assert me.status_code == 200
        assert me.json()["id"] == "user-uuid"
        assert logout.status_code == 200
        assert [name for name, _ in fake.calls] == [
            "sign_up",
            "sign_in",
            "refresh",
            "get_user",
            "sign_out",
        ]
    finally:
        app.dependency_overrides.pop(get_auth_client, None)


def test_existing_api_uses_supabase_user_id_after_token_validation() -> None:
    fake = FakeAuthClient()
    app.dependency_overrides[get_auth_client] = lambda: fake
    client = TestClient(app)

    try:
        response = client.get("/api/v1/ingredients", headers={"Authorization": "Bearer access-token"})

        assert response.status_code == 200
        assert ("get_user", "access-token") in fake.calls
    finally:
        app.dependency_overrides.pop(get_auth_client, None)


def test_auth_routes_require_supabase_configuration_and_invalid_tokens_are_rejected() -> None:
    client = TestClient(app)

    register = client.post(
        "/api/v1/auth/register",
        json={"email": "person@example.com", "password": "password123"},
    )
    assert register.status_code == 503

    fake = FakeAuthClient()
    app.dependency_overrides[get_auth_client] = lambda: fake
    try:
        response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bad-token"})
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_auth_client, None)
