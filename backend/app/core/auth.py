from typing import Annotated

from fastapi import Header, HTTPException, status


def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
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
    return token.strip()
