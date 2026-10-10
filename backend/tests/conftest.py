import pytest

from backend.app.core.auth import get_current_user_id
from backend.app.main import app
from backend.app.repositories.dependencies import get_business_repository
from backend.app.repositories.memory import get_repository


@pytest.fixture(autouse=True)
def explicit_test_repository():
    # Opaque identities and memory storage exist only as explicit test overrides.
    from fastapi import Depends
    from backend.app.core.auth import get_auth_client, get_bearer_token

    def identity(token: str = Depends(get_bearer_token), auth_client=Depends(get_auth_client)):
        if auth_client is not None:
            return get_current_user_id(token, auth_client)
        return token

    app.dependency_overrides[get_business_repository] = get_repository
    app.dependency_overrides[get_current_user_id] = identity
    yield
    app.dependency_overrides.pop(get_business_repository, None)
    app.dependency_overrides.pop(get_current_user_id, None)
