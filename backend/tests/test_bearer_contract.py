from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.core.auth import get_auth_client, get_current_user_id
from backend.app.main import app
from backend.app.repositories.dependencies import get_business_repository
from backend.app.services.auth import AuthProviderError
from backend.tests.test_auth import FakeAuthClient


@pytest.fixture
def real_dependencies():
    saved = {key: app.dependency_overrides.pop(key) for key in (get_current_user_id, get_business_repository)}
    fake = FakeAuthClient()
    app.dependency_overrides[get_auth_client] = lambda: fake
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_auth_client, None)
        app.dependency_overrides.update(saved)


def test_openapi_declares_bearer_for_every_protected_operation():
    schema = app.openapi()
    assert schema['components']['securitySchemes']['BearerAuth'] == {'type': 'http', 'scheme': 'bearer'}
    public = {'/api/v1/health', '/api/v1/auth/login', '/api/v1/auth/register', '/api/v1/auth/refresh'}
    for path, operations in schema['paths'].items():
        for operation in operations.values():
            assert not any(parameter['name'].lower() == 'authorization' for parameter in operation.get('parameters', []))
            assert operation.get('security', []) == ([] if path in public else [{'BearerAuth': []}])


@pytest.mark.parametrize('path,method', [('/api/v1/ingredients', 'get'), ('/api/v1/auth/me', 'get'), ('/api/v1/auth/logout', 'post')])
@pytest.mark.parametrize('header', [None, 'Basic synthetic', 'Bearer', 'Bearer ', 'Bearer token extra'])
def test_malformed_bearer_is_401_with_challenge(real_dependencies, path, method, header):
    response = getattr(TestClient(app), method)(path, headers={} if header is None else {'Authorization': header})
    assert response.status_code == 401
    assert response.headers['www-authenticate'] == 'Bearer'
    assert '凭证' in response.json()['detail']
    assert real_dependencies.calls == []


@pytest.mark.parametrize('path', ['/api/v1/ingredients', '/api/v1/auth/me'])
def test_expired_token_is_rejected(real_dependencies, path):
    response = TestClient(app).get(path, headers={'Authorization': 'Bearer bad-token'})
    assert response.status_code == 401
    assert response.headers['www-authenticate'] == 'Bearer'
    assert real_dependencies.calls == [('get_user', 'bad-token')]


def test_logout_rejects_an_expired_token_with_challenge(real_dependencies):
    def reject(token):
        raise AuthProviderError(401, '登录凭证无效或已过期')
    real_dependencies.sign_out = reject
    response = TestClient(app).post('/api/v1/auth/logout', headers={'Authorization': 'Bearer bad-token'})
    assert response.status_code == 401
    assert response.headers['www-authenticate'] == 'Bearer'


def test_identity_and_repository_receive_the_same_normalized_token(real_dependencies, monkeypatch):
    import backend.app.repositories.dependencies as dependencies
    calls = []

    @contextmanager
    def repository(url, key, token, user_id, **kwargs):
        calls.append((token, user_id))
        yield SimpleNamespace(list_ingredients=lambda **kwargs: [])

    monkeypatch.setattr(dependencies, 'settings', SimpleNamespace(supabase_url='https://synthetic.invalid', supabase_anon_key='public', supabase_auth_timeout_seconds=1))
    monkeypatch.setattr(dependencies, 'SupabaseRepository', repository)
    response = TestClient(app).get('/api/v1/ingredients', headers={'Authorization': 'bEaReR  access-token '})
    assert response.status_code == 200
    assert real_dependencies.calls == [('get_user', 'access-token')]
    assert calls == [('access-token', 'user-uuid')]


@pytest.mark.parametrize('path,method', [('/api/v1/ingredients', 'get'), ('/api/v1/auth/me', 'get'), ('/api/v1/auth/logout', 'post')])
def test_valid_bearer_without_configuration_is_503(real_dependencies, path, method):
    app.dependency_overrides[get_auth_client] = lambda: None
    response = getattr(TestClient(app), method)(path, headers={'Authorization': 'Bearer access-token'})
    assert response.status_code == 503
