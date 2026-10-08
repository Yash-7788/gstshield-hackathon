"""Focused round-two error and public-capability boundary regressions."""

import asyncio
import json
import sqlite3
from contextlib import closing

import pytest
from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient

from app.config import Settings
from app.errors import StorageError
from app.main import create_app
from app.security.http import LocalHTTPBoundary


@pytest.mark.parametrize("cause", [sqlite3.OperationalError("private"), OSError("private")])
def test_storage_failure_returns_sanitized_retryable_response(cause):
    app = create_app(Settings(app_env="test")).app.app
    request = Request({"type": "http", "state": {"request_id": "synthetic"}})
    try:
        raise cause
    except (sqlite3.Error, OSError):
        try:
            raise StorageError(
                "Private storage operation failed; retry after checking local storage."
            )
        except StorageError as error:
            response = asyncio.run(app.exception_handlers[StorageError](request, error))
    assert response.status_code == 503
    assert response.headers["retry-after"] == "2"
    assert json.loads(response.body)["error"]["code"] == "STORAGE_UNAVAILABLE"
    assert b"private" not in response.body


@pytest.mark.parametrize(
    "method,path,expected",
    [
        ("GET", "/webhooks/whatsapp", 200),
        ("GET", "/wa/reports/" + "a" * 43, 200),
        ("GET", "/wa/reports/short", 400),
        ("POST", "/wa/reports/" + "a" * 43, 400),
        ("GET", "/api/v1/auth/session", 400),
    ],
)
def test_public_channel_only_admits_webhook_and_shaped_report_get(method, path, expected):
    async def endpoint(scope, receive, send):
        await Response("admitted")(scope, receive, send)

    app = LocalHTTPBoundary(
        endpoint, ["http://localhost:3000"], channel_origin="https://callback.example.test"
    )
    with closing(TestClient(app, base_url="https://callback.example.test")) as client:
        assert client.request(method, path).status_code == expected


def test_default_reader_model_matches_supported_example():
    assert Settings(app_env="test").gemini_model == "gemini-3.1-flash-lite"
