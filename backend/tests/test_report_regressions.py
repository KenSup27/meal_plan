from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.auth import get_current_user_id
from backend.app.repositories.base import RepositoryError
from backend.app.repositories.memory import get_repository
from backend.app.repositories.supabase import SupabaseRepository
from backend.app.services.auth import AuthProviderError, SupabaseAuthClient


@pytest.mark.parametrize('operation', ['sign_up', 'sign_in', 'refresh_session'])
def test_raw_rest_token_responses(operation):
    body = {'user': {'id': 'test-user'}, 'access_token': 'synthetic-access', 'refresh_token': 'synthetic-refresh', 'expires_in': 3600}
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)))
    auth = SupabaseAuthClient('https://synthetic.invalid', 'public-key', client=client)
    try:
        result = getattr(auth, operation)(*(['synthetic-refresh'] if operation == 'refresh_session' else ['test@example.invalid', 'Synthetic123!']))
        assert result.session.access_token == 'synthetic-access'
        assert result.session.refresh_token == 'synthetic-refresh'
    finally:
        auth.close()


@pytest.mark.parametrize('payload', [{'access_token': 'x'}, {'refresh_token': 'x'}, {'session': {'access_token': 'x'}}])
def test_incomplete_session_is_not_silent_success(payload):
    with pytest.raises(AuthProviderError):
        SupabaseAuthClient._parse_session(payload)


def test_session_shapes_and_confirmation_only_registration():
    assert SupabaseAuthClient._parse_session({'user': {'id': 'u'}}) is None
    assert SupabaseAuthClient._parse_session({'session': {'access_token': 'a', 'refresh_token': 'r'}}).access_token == 'a'


def test_real_business_auth_requires_configuration():
    override = app.dependency_overrides.pop(get_current_user_id)
    try:
        response = TestClient(app).get('/api/v1/ingredients', headers={'Authorization': 'Bearer synthetic-user'})
        assert response.status_code == 503
    finally:
        app.dependency_overrides[get_current_user_id] = override


def test_runtime_config_does_not_expose_secret_keys(monkeypatch):
    import backend.app.main as main
    monkeypatch.setattr(main, 'settings', SimpleNamespace(supabase_url='https://synthetic.invalid', supabase_anon_key='sb_secret_do-not-expose'))
    response = TestClient(app).get('/runtime-config.js')
    assert 'do-not-expose' not in response.text
    assert response.headers['cache-control'] == 'no-store'


def test_request_scoped_repository_uses_jwt_and_owner_filter():
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=[])
    client = httpx.Client(transport=httpx.MockTransport(handle))
    with SupabaseRepository('https://synthetic.invalid', 'public', 'token-a', 'user-a', client=client) as repo:
        assert repo.list_recipes('user-a') == []
        with pytest.raises(RepositoryError):
            repo.list_recipes('user-b')
    with SupabaseRepository('https://synthetic.invalid', 'public', 'token-b', 'user-b', client=client) as repo:
        assert repo.list_recipes('user-b') == []
    assert [r.headers['authorization'] for r in requests] == ['Bearer token-a', 'Bearer token-b']
    assert [r.url.params['user_id'] for r in requests] == ['eq.user-a', 'eq.user-b']
    client.close()


@pytest.mark.parametrize('status,body,expected', [(409, {'code': '23505'}, 409), (400, {'code': '23514'}, 422), (400, {'code': 'PT409'}, 409), (401, {}, 401), (500, {}, 503)])
def test_database_errors_are_classified_without_leaking_sql(status, body, expected):
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body | {'message': 'secret SQL'})))
    repo = SupabaseRepository('https://synthetic.invalid', 'public', 'token', 'u', client=client)
    with pytest.raises(RepositoryError) as exc:
        repo.request('GET', 'recipes')
    assert exc.value.status_code == expected
    assert 'secret SQL' not in exc.value.message
    client.close()


def test_cross_month_plan_and_stale_replace():
    get_repository().reset()
    client = TestClient(app)
    headers = {'Authorization': 'Bearer user-a'}
    week = '2026-09-28'
    plan = client.post('/api/v1/meal-plans', headers=headers, json={'week_start': week, 'target_kcal': 1800, 'target_protein_g': 120, 'target_carbs_g': 200, 'target_fat_g': 60}).json()
    recipe = client.post('/api/v1/recipes', headers=headers, json={'name': 'test', 'ingredients': [{'ingredient_id': 1, 'raw_weight_g': 150}]}).json()
    item = {'planned_date': '2026-10-04', 'meal_type': 'lunch', 'input_mode': 'recipe', 'recipe_id': recipe['id'], 'quantity': 2}
    added = client.post(f'/api/v1/meal-plans/{week}/items', headers=headers, json=item)
    assert added.status_code == 200
    stale = client.put(f'/api/v1/meal-plans/{week}/items', headers=headers, json={'items': [], 'expected_revision': plan['revision']})
    assert stale.status_code == 409
    assert client.put(f'/api/v1/meal-plans/{week}/items', headers=headers, json={'items': []}).status_code == 409
    assert len(client.get(f'/api/v1/meal-plans/{week}', headers=headers).json()['items']) == 1


def test_archived_historical_items_survive_unrelated_replacement():
    get_repository().reset()
    client = TestClient(app)
    headers = {'Authorization': 'Bearer user-a'}
    week = '2026-10-05'
    client.post('/api/v1/meal-plans', headers=headers, json={'week_start': week, 'target_kcal': 1800, 'target_protein_g': 120, 'target_carbs_g': 200, 'target_fat_g': 60})
    recipe = client.post('/api/v1/recipes', headers=headers, json={'name': 'archive', 'ingredients': [{'ingredient_id': 1, 'raw_weight_g': 150}]}).json()
    body = client.post(f'/api/v1/meal-plans/{week}/items', headers=headers, json={'planned_date': week, 'meal_type': 'lunch', 'input_mode': 'recipe', 'recipe_id': recipe['id'], 'quantity': 1}).json()
    client.delete(f"/api/v1/recipes/{recipe['id']}", headers=headers)
    assert client.get(f"/api/v1/recipes/{recipe['id']}", headers=headers).status_code == 200
    original = {key: value for key, value in body['items'][0].items() if key != 'manual_nutrition'}
    manual = {'planned_date': week, 'meal_type': 'breakfast', 'input_mode': 'manual', 'manual_kcal': 100, 'manual_protein_g': 10, 'manual_carbs_g': 10, 'manual_fat_g': 1}
    saved = client.put(f'/api/v1/meal-plans/{week}/items', headers=headers, json={'items': [original, manual], 'expected_revision': body['revision']})
    assert saved.status_code == 200
    assert len(saved.json()['items']) == 2
    original['quantity'] = 2
    assert client.put(f'/api/v1/meal-plans/{week}/items', headers=headers, json={'items': [original], 'expected_revision': saved.json()['revision']}).status_code == 404
