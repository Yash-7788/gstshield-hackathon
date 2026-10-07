"""Real SQLite/browser flows, including negative ownership and recovery cases."""

import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import APIError, StorageError
from app.main import create_app
from app.services.access import AccessService, password_digest
from app.storage.local import LocalStore

PASSWORD = "synthetic-passphrase-only"
ORIGIN = "http://localhost:3000"


@pytest.fixture
def accounts():
    settings = Settings(app_env="test")
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    access = AccessService(store)
    alice, first = access.provision("alice", PASSWORD, "First workspace")
    bob, second = access.provision("bob", PASSWORD, "Second workspace")
    registration = access.add_registration(first, "27ABCDE1234F1Z5", "Synthetic supplier")
    store.close()
    return settings, alice, first, bob, second, registration


def login(client, username="alice", password=PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"Origin": ORIGIN},
    )


def test_browser_flow_private_scope_csrf_logout_and_headers(accounts):
    settings, alice, first, bob, second, registration = accounts
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/workspaces").status_code == 401
        response = login(client)
        assert response.status_code == 200
        assert response.json()["data"]["user_id"] == alice
        assert response.json()["data"]["expires_at"].endswith("Z")
        assert PASSWORD not in response.text
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        assert "path=/api/v1" in cookie and "max-age=1800" in cookie
        assert response.headers["access-control-allow-credentials"] == "true"
        csrf = response.json()["data"]["csrf_token"]
        assert client.get("/api/v1/auth/session").json()["data"]["csrf_token"] == csrf
        assert [item["id"] for item in client.get("/api/v1/workspaces").json()["data"]] == [first]
        rows = client.get(f"/api/v1/workspaces/{first}/registrations").json()["data"]
        assert rows[0]["id"] == registration and rows[0]["workspace_id"] == first
        denied = client.get(f"/api/v1/workspaces/{second}/registrations")
        assert denied.status_code == 404 and second not in denied.text and bob not in denied.text
        assert client.get(f"/api/v1/workspaces/{uuid4()}/registrations").status_code == 404
        assert client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN}).status_code == 403
        assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 403
        assert client.get("/api/v1/auth/session").status_code == 200
        old = client.cookies.get("gstshield_session")
        logout = client.post(
            "/api/v1/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}
        )
        assert logout.status_code == 200 and logout.json()["data"]["logged_out"] is True
        assert client.get("/api/v1/workspaces").status_code == 401
        assert (
            client.get(
                "/api/v1/workspaces", headers={"Cookie": "gstshield_session=" + old}
            ).status_code
            == 401
        )


def test_two_users_and_duplicate_cookie_or_csrf_cannot_change_scope(accounts):
    settings, _, first, _, second, _ = accounts
    with TestClient(create_app(settings)) as client:
        assert login(client, "bob").status_code == 200
        assert client.get(f"/api/v1/workspaces/{first}/registrations").status_code == 404
        assert client.get(f"/api/v1/workspaces/{second}/registrations").status_code == 200
        token = client.cookies.get("gstshield_session")
        assert (
            client.get(
                "/api/v1/workspaces",
                headers={"Cookie": f"gstshield_session={token}; gstshield_session=wrong"},
            ).status_code
            == 401
        )
        csrf = client.get("/api/v1/auth/session").json()["data"]["csrf_token"]
        assert (
            client.post(
                "/api/v1/auth/logout",
                headers=[("Origin", ORIGIN), ("X-CSRF-Token", csrf), ("X-CSRF-Token", csrf)],
            ).status_code
            == 403
        )


def test_login_requires_origin_and_invalid_credentials_are_redacted(accounts):
    settings = accounts[0]
    with TestClient(create_app(settings)) as client:
        assert (
            client.post(
                "/api/v1/auth/login", json={"username": "alice", "password": PASSWORD}
            ).status_code
            == 403
        )
        wrong = login(client, password="wrong-synthetic-password")
        unknown = login(client, username="unknown")
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json()["error"] == unknown.json()["error"]
        assert "synthetic" not in wrong.text + unknown.text
        assert client.get("/api/v1/auth/session").status_code == 401


def test_expiry_revocation_role_and_replaced_session(accounts):
    settings, _, first, _, _, _ = accounts
    app = create_app(settings)
    with TestClient(app):
        access = app.app.app.state.access
        access.clock = lambda: 2000000000
        token, identity = access.login("alice", PASSWORD)
        next_token, _ = access.login("alice", PASSWORD)
        with pytest.raises(APIError) as denied:
            access.identity(token)
        assert denied.value.status == 401
        identity = access.identity(next_token)
        access.grant("alice", first, "VIEWER")
        with access.store.transaction(write=False) as connection:
            with pytest.raises(APIError) as forbidden:
                access.require_membership(connection, identity, first, roles={"OWNER"})
            assert forbidden.value.status == 403
        access.grant("alice", first, "VIEWER", active=False)
        with pytest.raises(APIError) as hidden:
            access.registrations(identity, first)
        assert hidden.value.status == 404
        access.clock = lambda: 2000001800
        with pytest.raises(APIError) as expired:
            access.identity(next_token)
        assert expired.value.status == 401


def test_password_reset_invalidates_sessions_and_only_hashes_are_retained(accounts):
    settings = accounts[0]
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    access = AccessService(store)
    try:
        token, _ = access.login("alice", PASSWORD)
        with store.transaction(write=False) as connection:
            user = connection.execute(
                "SELECT salt,digest FROM users WHERE username='alice'"
            ).fetchone()
            assert user[1] == password_digest(PASSWORD, user[0])
            assert connection.execute("SELECT token_hash FROM sessions").fetchone()[0] != token
        access.reset_password("alice", "new-synthetic-passphrase")
        with pytest.raises(APIError):
            access.identity(token)
        with pytest.raises(APIError):
            access.login("alice", PASSWORD)
        assert access.login("alice", "new-synthetic-passphrase")[1].username == "alice"
        assert PASSWORD.encode() not in store.path.read_bytes()
        assert token.encode() not in store.path.read_bytes()
    finally:
        store.close()


def test_login_and_private_read_rate_limits_survive_service_recreation(accounts):
    settings = accounts[0].model_copy(update={"read_requests_per_minute": 2})
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    access = AccessService(store)
    access.clock = lambda: 2000000000
    try:
        for _ in range(5):
            with pytest.raises(APIError) as wrong:
                access.login("alice", "wrong-synthetic-password")
            assert wrong.value.status == 401
        with pytest.raises(APIError) as limited:
            access.login("alice", PASSWORD)
        assert limited.value.status == 429 and limited.value.retry_after == 60
        access.clock = lambda: 2000000060
        token, _ = access.login("alice", PASSWORD)
        access.identity(token)
        access.identity(token)
        restarted = AccessService(store)
        restarted.clock = access.clock
        with pytest.raises(APIError) as read_limit:
            restarted.identity(token)
        assert read_limit.value.status == 429
    finally:
        store.close()


def test_session_capacity_hash_concurrency_and_busy_error(accounts):
    settings = accounts[0].model_copy(update={"max_active_demo_sessions": 1})
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    access = AccessService(store)
    try:
        token, _ = access.login("alice", PASSWORD)
        with pytest.raises(APIError) as full:
            access.login("bob", PASSWORD)
        assert full.value.code == "SESSION_LIMIT"
        assert access.identity(token).username == "alice"
        access.hash_slot.acquire()
        try:
            with pytest.raises(APIError) as busy:
                access.login("bob", PASSWORD)
            assert busy.value.code == "AUTH_BUSY"
        finally:
            access.hash_slot.release()
    finally:
        store.close()


def test_duplicate_account_registration_and_foreign_key_rollback(accounts):
    settings, _, first, _, _, _ = accounts
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    access = AccessService(store)
    try:
        with pytest.raises(APIError) as duplicate:
            access.provision("alice", PASSWORD, "Never committed")
        assert duplicate.value.code == "ACCOUNT_CONFLICT"
        with pytest.raises(APIError):
            access.add_registration(first, "27ABCDE1234F1Z5", "Duplicate")
        with pytest.raises(sqlite3.IntegrityError), store.transaction() as connection:
            connection.execute("UPDATE workspaces SET name='Must roll back' WHERE id=?", (first,))
            connection.execute(
                "INSERT INTO memberships (workspace_id,user_id,role,active) VALUES (?,?,?,1)",
                (first, str(uuid4()), "OWNER"),
            )
        with store.transaction(write=False) as connection:
            assert connection.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0] == 2
            assert (
                connection.execute("SELECT name FROM workspaces WHERE id=?", (first,)).fetchone()[0]
                == "First workspace"
            )
    finally:
        store.close()


def test_ready_and_private_routes_fail_closed_if_database_disappears(accounts):
    app = create_app(accounts[0])
    with TestClient(app) as client:
        assert login(client).status_code == 200
        path = app.app.app.state.store.path
        path.unlink()
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        assert client.get("/api/v1/workspaces").status_code == 503
        assert not path.exists()


def test_streamed_body_limit_before_json_parser_keeps_error_headers():
    settings = Settings(app_env="test", max_api_body_bytes=1024)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/auth/login",
            content=iter([b"x" * 700, b"y" * 700]),
            headers={"Origin": ORIGIN, "Content-Type": "application/json"},
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
        assert response.headers["access-control-allow-origin"] == ORIGIN
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/health/ready").status_code == 200


def test_quota_failure_is_redacted_and_does_not_logout(accounts, monkeypatch):
    app = create_app(accounts[0])
    with TestClient(app) as client:
        assert login(client).status_code == 200

        def fail_capacity(*args):
            raise StorageError("private-filename-must-not-leak")

        monkeypatch.setattr(app.app.app.state.store, "capacity", fail_capacity)
        response = client.get("/api/v1/workspaces", headers={"Origin": ORIGIN})
        assert response.status_code == 503 and response.headers["retry-after"] == "2"
        assert "private-filename" not in response.text
        assert response.headers["access-control-allow-origin"] == ORIGIN


def test_small_body_bad_lengths_and_nested_json_fail_without_session_creation():
    app = create_app(Settings(app_env="test"))
    with TestClient(app) as client:
        for headers in (
            [("Content-Length", "1"), ("Content-Length", "2")],
            {"Content-Length": "9" * 5000},
        ):
            response = client.post("/api/v1/auth/login", content=b"x", headers=headers)
            assert response.status_code == 400
        nested = "[" * 1500 + "0" + "]" * 1500
        response = client.post(
            "/api/v1/auth/login",
            content=nested,
            headers={"Content-Type": "application/json", "Origin": ORIGIN},
        )
        assert response.status_code == 422
        with app.app.app.state.store.transaction(write=False) as connection:
            assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_provisioned_account_workspace_registration_limits_are_atomic():
    settings = Settings(
        max_local_users=1, max_local_workspaces=1, max_registrations_per_workspace=1
    )
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    access = AccessService(store)
    try:
        _, workspace = access.provision("alice", PASSWORD, "First")
        with pytest.raises(APIError) as limited:
            access.provision("bob", PASSWORD, "Second")
        assert limited.value.code == "ACCOUNT_LIMIT"
        access.add_registration(workspace, "27ABCDE1234F1Z5", "One")
        with pytest.raises(APIError) as registration_limit:
            access.add_registration(workspace, "27ABCDE1234F2Z5", "Two")
        assert registration_limit.value.code == "REGISTRATION_LIMIT"
        with store.transaction(write=False) as connection:
            assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
            assert connection.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0] == 1
            assert connection.execute("SELECT COUNT(*) FROM registrations").fetchone()[0] == 1
    finally:
        store.close()
