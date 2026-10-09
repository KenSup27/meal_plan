from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx


class AuthProviderError(Exception):
    def __init__(self, status_code: int, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.code = code


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None
    email_confirmed_at: datetime | None = None


@dataclass(frozen=True)
class AuthSession:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int | None = None
    expires_at: int | None = None


@dataclass(frozen=True)
class AuthResult:
    user: AuthUser
    session: AuthSession | None


class SupabaseAuthClient:
    """Small Auth API adapter; no service-role key is needed for these flows."""

    def __init__(
        self,
        url: str,
        anon_key: str,
        timeout_seconds: float = 10,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._anon_key = anon_key

    def close(self) -> None:
        self._client.close()

    def _headers(self, access_token: str | None = None) -> dict[str, str]:
        headers = {"apikey": self._anon_key, "Content-Type": "application/json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._client.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers(access_token),
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise AuthProviderError(503, "认证服务暂时不可用") from exc
        if response.is_error:
            try:
                body = response.json()
            except ValueError:
                body = {}
            message = (
                body.get("message")
                or body.get("msg")
                or body.get("error_description")
                or "认证请求失败"
            )
            raise AuthProviderError(response.status_code, str(message), body.get("code"))
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise AuthProviderError(502, "认证服务返回了无效响应") from exc

    @staticmethod
    def _parse_user(payload: dict[str, Any]) -> AuthUser:
        raw = payload.get("user", payload)
        if not raw.get("id"):
            raise AuthProviderError(502, "认证服务返回的用户信息不完整")
        confirmed = raw.get("email_confirmed_at") or raw.get("confirmed_at")
        try:
            parsed_confirmed = datetime.fromisoformat(confirmed.replace("Z", "+00:00")) if confirmed else None
        except (AttributeError, ValueError) as exc:
            raise AuthProviderError(502, "认证服务返回的邮箱确认时间无效") from exc
        return AuthUser(id=str(raw["id"]), email=raw.get("email"), email_confirmed_at=parsed_confirmed)

    @staticmethod
    def _parse_session(payload: dict[str, Any]) -> AuthSession | None:
        raw = payload.get("session")
        if not raw:
            return None
        if not raw.get("access_token") or not raw.get("refresh_token"):
            raise AuthProviderError(502, "认证服务返回的会话信息不完整")
        return AuthSession(
            access_token=raw["access_token"],
            refresh_token=raw["refresh_token"],
            token_type=raw.get("token_type", "bearer"),
            expires_in=raw.get("expires_in"),
            expires_at=raw.get("expires_at"),
        )

    def sign_up(self, email: str, password: str, display_name: str | None = None) -> AuthResult:
        payload: dict[str, Any] = {"email": email, "password": password}
        if display_name:
            payload["options"] = {"data": {"display_name": display_name}}
        response = self._request("POST", "/auth/v1/signup", payload=payload)
        return AuthResult(self._parse_user(response), self._parse_session(response))

    def sign_in(self, email: str, password: str) -> AuthResult:
        response = self._request(
            "POST",
            "/auth/v1/token?grant_type=password",
            payload={"email": email, "password": password},
        )
        return AuthResult(self._parse_user(response), self._parse_session(response))

    def refresh_session(self, refresh_token: str) -> AuthResult:
        response = self._request(
            "POST",
            "/auth/v1/token?grant_type=refresh_token",
            payload={"refresh_token": refresh_token},
        )
        return AuthResult(self._parse_user(response), self._parse_session(response))

    def get_user(self, access_token: str) -> AuthUser:
        response = self._request("GET", "/auth/v1/user", access_token=access_token)
        return self._parse_user(response)

    def sign_out(self, access_token: str) -> None:
        self._request("POST", "/auth/v1/logout", access_token=access_token)
