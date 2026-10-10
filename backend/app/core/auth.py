from typing import Annotated, Protocol

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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


bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


def get_bearer_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    if not request.headers.get("Authorization"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 Authorization Bearer 凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials.strip() if credentials else ""
    if not token or any(char.isspace() for char in token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization 必须使用 Bearer 凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def get_current_user_id(
    token: Annotated[str, Depends(get_bearer_token)],
    auth_client: Annotated[AuthClient | None, Depends(get_auth_client)] = None,
) -> str:
    """Resolve a real authenticated identity; test adapters are explicit overrides."""
    if auth_client is None:
        raise HTTPException(status_code=503, detail="Supabase Auth 尚未配置")
    try:
        return auth_client.get_user(token).id
    except AuthProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录凭证无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
