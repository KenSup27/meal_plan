import pytest

from backend.app.core.auth import get_current_user_id
from backend.app.main import app
from backend.app.repositories.dependencies import get_business_repository
from backend.app.repositories.memory import get_repository


@pytest.fixture(autouse=True)
def explicit_test_repository():
    # Opaque identities and memory storage exist only as explicit test overrides.
    from fastapi import Depends, Header, HTTPException
    from backend.app.core.auth import get_auth_client

    def identity(authorization: str | None = Header(default=None), auth_client=Depends(get_auth_client)):
        if auth_client is not None:
            return get_current_user_id(authorization, auth_client)
        if not authorization or not authorization.lower().startswith("bearer ") or not authorization[7:].strip():
            raise HTTPException(401, "缺少 Authorization Bearer 凭证")
        return authorization[7:].strip()

    app.dependency_overrides[get_business_repository] = get_repository
    app.dependency_overrides[get_current_user_id] = identity
    yield
    app.dependency_overrides.pop(get_business_repository, None)
    app.dependency_overrides.pop(get_current_user_id, None)
