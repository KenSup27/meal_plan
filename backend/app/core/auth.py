from typing import Annotated, Protocol

from fastapi import Depends, Header, HTTPException, status

from backend.app.core.config import settings
from backend.app.services.auth import AuthProviderError, SupabaseAuthClient


class AuthClient(Protocol):
    def get_user(self, access_token: str): ...


_configured_auth_client: SupabaseAuthClient | None = None
_configured_auth_signature: tuple[str, str, float] | None = None


def get_auth_client() -> SupabaseAuthClient | None:
    global _configured_auth_client, _configured_auth_signature
    if not settings.supabase_url or not settings.supabase_anon_key:
        return None
    signature = (
        settings.supabase_url,
        settings.supabase_anon_key,
        settings.supabase_auth_timeout_seconds,
    )
    if _configured_auth_client is None or _configured_auth_signature != signature:
        if _configured_auth_client is not None:
            _configured_auth_client.close()
        _configured_auth_client = SupabaseAuthClient(
            settings.supabase_url,
            settings.supabase_anon_key,
            timeout_seconds=settings.supabase_auth_timeout_seconds,
        )
        _configured_auth_signature = signature
    return _configured_auth_client


def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
    auth_client: Annotated[AuthClient | None, Depends(get_auth_client)] = None,
) -> str:
    """Resolve the current user for the local repository adapter.

    The adapter deliberately treats the bearer token as an opaque user id. A
    production Supabase integration can replace this dependency with JWT
    verification without changing the route handlers or service layer.
    """

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 Authorization Bearer 凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization 必须使用 Bearer 凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = token.strip()
    if auth_client is None:
        return token
    try:
        return auth_client.get_user(token).id
    except AuthProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录凭证无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
