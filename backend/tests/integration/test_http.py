from uuid import UUID

import pytest
from fastapi import Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException

from app.config import Settings
from app.main import create_app

ORIGIN = "http://localhost:3000"


@pytest.fixture
def application():
    app = create_app(Settings(app_env="test"))
    # Add test-only routes to the wrapped FastAPI instance to exercise global handlers.
    api = app.app.app

    @api.get("/test/failure")
    async def fail():
        raise RuntimeError("private-bank-document-do-not-echo")

    @api.get("/test/validation")
    async def validate(count: int = Query(ge=1)):
        return {"count": count}

    class Payload(BaseModel):
        count: int = Field(ge=1)

    @api.post("/test/body")
    async def body(payload: Payload):
        return {"count": payload.count}

    @api.get("/test/forbidden")
    async def forbidden():
        raise HTTPException(403, detail="secret-owner-identity")

    return app


def assert_envelope(response, code):
    payload = response.json()
    assert payload["error"]["code"] == code
    assert set(payload["error"]) == {"code", "message", "details", "retryable"}
    assert str(UUID(payload["meta"]["request_id"])) == response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_health_readiness_tracks_storage_lifespan(application):
    client = TestClient(application)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert_envelope(response, "NOT_READY")
    with client:
        live = client.get("/health/live", headers={"X-Request-ID": "untrusted-client-id"})
        ready = client.get("/health/ready")
        assert live.status_code == ready.status_code == 200
        assert live.json()["data"] == {"status": "ok"}
        assert ready.json()["data"] == {"status": "ready"}
        assert live.json()["meta"]["request_id"] != "untrusted-client-id"
        assert live.headers["x-request-id"] != ready.headers["x-request-id"]
        assert set(ready.json()) == {"data", "meta"}
    assert client.get("/health/ready").status_code == 503


@pytest.mark.parametrize(
    ("method", "path", "status", "code"),
    [
        ("GET", "/api/v1/workspaces", 401, "AUTH_REQUIRED"),
        ("GET", "/webhooks/whatsapp", 503, "CHANNEL_DISABLED"),
        ("POST", "/health/live", 405, "METHOD_NOT_ALLOWED"),
        ("GET", "/test/forbidden", 403, "FORBIDDEN"),
        ("GET", "/test/validation?count=secret-value", 422, "VALIDATION_ERROR"),
    ],
)
def test_expected_errors_use_contract_and_never_echo_private_input(
    application, method, path, status, code
):
    with TestClient(application) as client:
        response = client.request(method, path, headers={"Origin": ORIGIN})
    assert response.status_code == status
    assert_envelope(response, code)
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "secret" not in response.text
    if status == 405:
        assert "GET" in response.headers["allow"]


def test_unexpected_failure_is_redacted_and_keeps_cors_headers(application, caplog):
    with TestClient(application) as client:
        response = client.get("/test/failure", headers={"Origin": ORIGIN})
    assert response.status_code == 500
    assert_envelope(response, "INTERNAL_ERROR")
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "private-bank" not in response.text
    assert "private-bank" not in caplog.text
    assert response.headers["x-request-id"] in caplog.text


def test_invalid_json_body_uses_the_same_redacted_contract(application):
    with TestClient(application) as client:
        response = client.post(
            "/test/body",
            content='{"count": "secret-value"',
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422
    assert_envelope(response, "VALIDATION_ERROR")
    assert "secret-value" not in response.text


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "http://localhost:3000.evil"])
def test_unapproved_origins_are_rejected_before_routes(application, origin):
    with TestClient(application) as client:
        response = client.get("/health/live", headers={"Origin": origin})
    assert response.status_code == 403
    assert_envelope(response, "ORIGIN_NOT_ALLOWED")
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    "host",
    [
        "evil.example",
        "localhost.evil",
        "evil@localhost",
        "localhost:70000",
        "localhost/path",
        "localhost?",
        "localhost#",
    ],
)
def test_host_boundary_prevents_dns_rebinding(application, host):
    with TestClient(application) as client:
        response = client.get("/health/live", headers={"Host": host})
    assert response.status_code == 400
    assert_envelope(response, "INVALID_HOST")


@pytest.mark.parametrize("host", ["localhost:8000", "127.0.0.1:8000", "[::1]:8000"])
def test_loopback_host_forms_work(application, host):
    with TestClient(application) as client:
        response = client.get("/health/live", headers={"Host": host})
    assert response.status_code == 200


def test_duplicate_origin_and_host_headers_are_rejected(application):
    with TestClient(application) as client:
        bad_host = client.get("/health/live", headers=[("Host", "localhost"), ("Host", "evil")])
        bad_origin = client.get(
            "/health/live", headers=[("Origin", ORIGIN), ("Origin", "https://evil.example")]
        )
    assert bad_host.status_code == 400
    assert bad_origin.status_code == 403


def test_cors_preflight_advertises_session_operations_with_credentials(application):
    with TestClient(application) as client:
        response = client.options(
            "/health/live",
            headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET"},
        )
        forbidden_method = client.options(
            "/health/live",
            headers={"Origin": ORIGIN, "Access-Control-Request-Method": "DELETE"},
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.headers["access-control-allow-methods"] == "GET, POST, PATCH"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert forbidden_method.status_code == 400


def test_demo_hides_schema_and_developer_docs():
    app = create_app(Settings(app_env="demo"))
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_openapi_describes_enveloped_health_responses(application):
    with TestClient(application) as client:
        schema = client.get("/openapi.json").json()
    response_schema = schema["paths"]["/health/live"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert response_schema["$ref"] == "#/components/schemas/HealthResponse"
    assert set(schema["components"]["schemas"]["HealthResponse"]["properties"]) == {"data", "meta"}


def test_no_provider_feature_is_silently_activated():
    settings = Settings(
        whatsapp_enabled=True,
        whatsapp_public_url="https://callback.example.test",
        meta_graph_version="v25.0",
        meta_phone_number_id="123",
        meta_waba_id="456",
        meta_access_token="secret",
        meta_app_secret="secret",
        meta_verify_token="secret",
    )
    with TestClient(create_app(settings)) as client:
        service = client.app.app.app.state.whatsapp
        assert settings.whatsapp_send_budget == 0
        assert service.send_one() is False
        assert client.get("/health/ready", headers={"Host": "localhost"}).status_code == 200
