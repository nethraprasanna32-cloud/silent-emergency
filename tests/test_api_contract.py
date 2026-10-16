from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def test_frontend_routes_are_published_in_openapi():
    paths=client.get('/openapi.json').json()['paths']
    expected={
        '/signals':'post','/persons':'post','/households':'post','/needs':'get',
        '/matches':'get','/matches/{match_id}/accept':'post','/matches/{match_id}/reject':'post',
        '/matches/{match_id}/complete':'post','/simulate':'post','/metrics':'get','/audit':'get',
        '/audit/verify':'get','/imports':'post','/imports/{batch_id}/report':'get',
        '/resources/{resource_id}':'patch','/volunteers/{volunteer_id}/availability':'patch',
        '/resources':'get','/volunteers':'get','/history':'get','/stats':'get','/scan':'post',
        '/needs/{need_id}/matches':'get',
    }
    for path,method in expected.items():
        assert method in paths[path]

def test_cors_preflight_for_default_frontend_origin():
    response=client.options('/needs',headers={
        'Origin':'http://localhost:5173',
        'Access-Control-Request-Method':'GET',
    })
    assert response.status_code==200
    assert response.headers['access-control-allow-origin']=='http://localhost:5173'

def test_health_reports_database_unavailable_without_failing_liveness(monkeypatch):
    from contextlib import contextmanager
    @contextmanager
    def unavailable():
        raise OSError('database unavailable')
        yield
    monkeypatch.setattr('app.main.connection',unavailable)
    response=client.get('/health')
    assert response.status_code==200
    assert response.json()['ok'] is False

def test_api_version_header_is_present():
    response=client.get('/openapi.json')
    assert response.headers['x-sed-api-version']=='1'

def test_assignment_request_contract_is_json_body():
    schema=client.get('/openapi.json').json()
    operation=schema['paths']['/matches/assign']['post']
    assert operation['requestBody']['required'] is True
    assert 'application/json' in operation['requestBody']['content']

def test_frontend_is_served_by_same_fastapi_origin():
    response=client.get('/ui/')
    assert response.status_code==200
    assert 'Silent Emergency Database System' in response.text
