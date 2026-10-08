"""Whole-backend access inventory and safe shutdown, without repeating every business fixture."""

import asyncio
import json
import socket
from http.client import HTTPResponse
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import StorageError
from app.main import create_app
from app.storage.local import LocalStore
from tests.fixtures.product_access import inventory
from tests.integration.test_imports import PASSWORD, signed_in
from tests.integration.test_imports import account as account
from tests.integration.test_restart import running_backend
from tests.integration.test_startup import child_environment


@pytest.mark.parametrize("stuck", ["dispatcher", "monitor", "both", "none"])
def test_lifespan_retains_exclusive_storage_until_both_background_threads_stop(monkeypatch, stuck):
    class Worker:
        def __init__(self, *args):
            self.thread = self
            self.alive = False

        def start(self):
            self.alive = True

        def is_alive(self):
            return self.alive

        def close(self):
            if self.kind in stuck or stuck == "both":
                raise StorageError("Synthetic worker shutdown timeout")
            self.alive = False

    class Dispatcher(Worker):
        kind = "dispatcher"

    class Monitor(Worker):
        kind = "monitor"

    monkeypatch.setattr("app.main.ImportDispatcher", Dispatcher)
    monkeypatch.setattr("app.main.ActionMonitor", Monitor)
    settings = Settings(app_env="test")
    app = create_app(settings).app.app

    async def lifecycle():
        async with app.router.lifespan_context(app):
            assert app.state.ready

    try:
        if stuck == "none":
            asyncio.run(lifecycle())
            assert not app.state.store.opened
            other = LocalStore(settings)
            other.acquire()
            other.close()
        else:
            with pytest.raises(StorageError, match="shutdown timeout"):
                asyncio.run(lifecycle())
            assert app.state.store.opened
            other = LocalStore(settings)
            with pytest.raises(StorageError, match="Cannot lock"):
                other.acquire()
        assert not app.state.ready
    finally:
        # The fake threads do no work. Release only after explicitly stopping them.
        app.state.dispatcher.alive = False
        app.state.action_monitor.alive = False
        app.state.store.close()


def test_all_workspace_route_families_enforce_identity_scope_and_live_role(account):
    settings, user, workspace, registration = account
    app = create_app(settings)
    with TestClient(app) as client:
        api = app.app.app
        access = api.state.access
        _, foreign = access.provision("bob", PASSWORD, "Other private workspace")
        # Ambiguous identity is refused before credential hashing/session creation.
        response = client.post(
            "/api/v1/auth/login",
            content=(
                '{"username":"alice","username":"bob","password":' + json.dumps(PASSWORD) + "}"
            ),
            headers={"Origin": "http://localhost:3000", "Content-Type": "application/json"},
        )
        assert response.status_code == 422
        with api.state.store.transaction(write=False) as connection:
            assert connection.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
        headers = signed_in(client)
        token = client.cookies.get("gstshield_session")
        identifier = str(uuid4())
        reason = {"expected_version": 1, "reason": "Synthetic scope check"}
        read_paths = [
            "/registrations",
            "/imports",
            "/imports/{id}",
            "/imports/{id}/rows",
            "/jobs/{id}",
            "/runs",
            "/runs/{id}",
            "/runs/{id}/results",
            "/results/{id}",
            "/cases",
            "/cases/{id}",
            "/proposals",
            "/proposals/{id}",
            "/artifacts",
            "/artifacts/{id}",
            "/artifacts/{id}/download",
            "/actions",
            "/actions/{id}",
            "/actions/{id}/worksheet",
        ]
        writes = [
            ("PATCH", "/imports/{id}/mapping", {"expected_version": 1, "mapping": {}}),
            ("POST", "/imports/{id}/confirm", {"expected_version": 1}),
            (
                "POST",
                "/runs",
                {
                    "registration_id": registration,
                    "period": "2024-04",
                    "purchase_import_id": identifier,
                    "portal_import_id": identifier,
                },
            ),
            ("POST", "/results/{id}/review", reason | {"action": "REJECT_MATCH"}),
            (
                "POST",
                "/cases",
                {
                    "registration_id": registration,
                    "result_id": identifier,
                    "purchase_document_id": identifier,
                    "kind": "IRN_REVIEW",
                    "amount": "180.00",
                    "facts": {},
                },
            ),
            ("POST", "/cases/{id}/evidence", reason | {"event_kind": "NOTE"}),
            ("POST", "/cases/{id}/transition", reason | {"state": "EVIDENCE_REQUIRED"}),
            (
                "POST",
                "/proposals",
                {
                    "run_id": identifier,
                    "expected_run_version": 1,
                    "expected_result_versions": {identifier: 1},
                    "balance_observations": [
                        {
                            "document_id": identifier,
                            "evidence_case_id": identifier,
                            "expected_case_version": 1,
                        }
                    ],
                    "allocations": [
                        {
                            "document_id": identifier,
                            "amount": "1.00",
                            "purpose": "SUPPLIER_PROPOSED",
                        }
                    ],
                },
            ),
            ("POST", "/proposals/{id}/approve", reason),
            (
                "POST",
                "/artifacts",
                {"kind": "EVIDENCE_PDF", "source_id": identifier, "expected_version": 1},
            ),
            ("POST", "/artifacts/cleanup", {"expired_only": True}),
            ("POST", "/actions/{id}/update", reason | {"state": "OPEN"}),
            (
                "POST",
                "/actions/{id}/followups",
                reason | {"contact": "+919876543210", "request": "Review invoice"},
            ),
            (
                "POST",
                "/actions/{id}/outcomes",
                reason | {"kind": "REVIEW_DECISION", "decision": "REJECTED"},
            ),
        ]
        # New workspace routes must be assigned an explicit access scenario here.
        import re

        prefix = "/api/v1/workspaces/{workspace_id}"
        actual = {
            (method.upper(), re.sub(r"\{[^}]+\}", "{id}", path[len(prefix) :]))
            for path, operations in api.openapi()["paths"].items()
            if path.startswith(prefix)
            for method in operations
            if method in {"get", "post", "patch"}
        }
        expected = (
            {("GET", path) for path in read_paths}
            | {(m, p) for m, p, _ in writes}
            | {("POST", "/imports")}
        )
        extra_reads, extra_writes, _, _ = inventory(registration, identifier)
        extra = (
            {("GET", p) for p in extra_reads}
            | {(m, p) for m, p, _ in extra_writes}
            | {
                ("POST", "/passports/documents"),
                ("POST", "/passports/{id}/evidence-documents"),
                ("POST", "/product/gst-statement"),
            }
        )
        assert actual == expected | extra
        tables = (
            "imports",
            "runs",
            "cases",
            "proposals",
            "artifacts",
            "workflow_operations",
            "run_events",
        )
        with api.state.store.transaction(write=False) as connection:
            before = {
                table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in tables
            }
        for mode, expected_status in (("anonymous", 401), ("foreign", 404), ("viewer", 403)):
            target = foreign if mode == "foreign" else workspace
            client.cookies.clear()
            if mode != "anonymous":
                client.cookies.set("gstshield_session", token)
            if mode == "viewer":
                access.grant("alice", workspace, "VIEWER")
            for method, path, payload in writes:
                response = client.request(
                    method,
                    f"/api/v1/workspaces/{target}" + path.format(id=identifier),
                    json=payload,
                    headers=headers | {"Idempotency-Key": str(uuid4())},
                )
                assert response.status_code == expected_status, (mode, path, response.text)
            # Upload must reject authority without waiting for/allocating multipart source bytes.
            response = client.post(
                f"/api/v1/workspaces/{target}/imports",
                content=b"not-multipart",
                headers=headers | {"Idempotency-Key": str(uuid4())},
            )
            assert response.status_code == expected_status
            for path in read_paths:
                response = client.get(f"/api/v1/workspaces/{target}" + path.format(id=identifier))
                if mode == "viewer":
                    expected_read = 200 if "{id}" not in path else 404
                else:
                    expected_read = expected_status
                assert response.status_code == expected_read, (mode, path, response.text)
                assert "Other private workspace" not in response.text
        with api.state.store.transaction(write=False) as connection:
            after = {
                table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in tables
            }
        assert before == after
        # Revocation denies even a previously valid read/session, with live checks.
        access.grant("alice", workspace, "VIEWER", active=False)
        assert client.get(f"/api/v1/workspaces/{workspace}/actions").status_code == 404
        with api.state.store.transaction() as connection:
            connection.execute("UPDATE users SET active=0 WHERE id=?", (user,))
        assert client.get("/api/v1/auth/session").status_code == 401


def test_real_http_slow_body_times_out_while_health_remains_available():
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    environment = child_environment()
    environment.update(
        PORT=str(port),
        PUBLIC_API_URL=f"http://127.0.0.1:{port}",
        PUBLIC_WEB_URL="http://127.0.0.1:3000",
        MAX_API_RECEIVE_SECONDS="1",
    )
    with running_backend(port, environment) as client:
        with socket.create_connection(("127.0.0.1", port), timeout=5) as peer:
            peer.sendall(
                (
                    f"POST /api/v1/auth/login HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                    "Origin: http://localhost:3000\r\nContent-Type: application/json\r\n"
                    "Content-Length: 30\r\nConnection: close\r\n\r\n{"
                ).encode()
            )
            # A waiting JSON body cannot block the event loop or health endpoint.
            assert client.get("/health/live").status_code == 200
            response = HTTPResponse(peer)
            try:
                response.begin()
                assert response.status == 408
                assert response.getheader("Cache-Control") == "no-store"
                assert response.getheader("Access-Control-Allow-Origin") == "http://localhost:3000"
                assert json.loads(response.read())["error"]["code"] == "REQUEST_TIMEOUT"
            finally:
                response.close()
        assert client.get("/health/ready").status_code == 200


def test_extended_route_inventory_checks_scope_before_private_or_provider_state(account):
    settings, user, ws, rid = account
    settings = settings.model_copy(
        update={"mutation_requests_per_minute": 1000, "read_requests_per_minute": 5000}
    )
    app = create_app(settings)
    with TestClient(app) as client:
        api = app.app.app
        _, foreign = api.state.access.provision("bob", PASSWORD, "Other private workspace")
        h = signed_in(client)
        token = client.cookies.get("gstshield_session")
        identifier = str(uuid4())
        reads, writes, query_reads, scope = inventory(rid, identifier)
        tables = [
            "invoice_passports",
            "passport_events",
            "business_profile",
            "team_profile",
            "team_contribution",
            "product_events",
            "workflow_run",
            "node_event",
            "tax_suggestion_review",
            "wa_codes",
            "wa_outbox",
        ]
        with api.state.store.transaction(write=False) as con:
            before = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
        for mode in ("anonymous", "foreign", "viewer"):
            target = foreign if mode == "foreign" else ws
            client.cookies.clear()
            if mode != "anonymous":
                client.cookies.set("gstshield_session", token)
            if mode == "viewer":
                api.state.access.grant("alice", ws, "VIEWER")
                with api.state.store.transaction() as con:
                    con.execute(
                        "UPDATE team_profile SET roles_json=? WHERE workspace_id=? AND user_id=?",
                        ('["OBSERVER"]', ws, user),
                    )
            for path in reads:
                res = client.get(
                    f"/api/v1/workspaces/{target}" + path.format(id=identifier),
                    params=scope if path in query_reads else {},
                )
                shared_reads = {
                    "/command-center/glossary",
                    "/product/portal",
                    "/product/business",
                    "/product/team",
                    "/product/contributions",
                    "/product/workflows",
                    "/product/workflows/{id}",
                    "/product/notifications",
                }
                expected = (
                    401
                    if mode == "anonymous"
                    else 404
                    if mode == "foreign"
                    else (404 if "{id}" in path else 200)
                    if path in shared_reads
                    else 403
                )
                assert res.status_code == expected, (mode, path, res.text)
            for method, path, payload in writes:
                concrete = path.replace("/assistants/{id}", "/assistants/CA").format(id=identifier)
                res = client.request(
                    method,
                    f"/api/v1/workspaces/{target}" + concrete,
                    json=payload,
                    headers=h | {"Idempotency-Key": str(uuid4())},
                )
                if mode != "viewer":
                    expected = {401} if mode == "anonymous" else {404}
                elif path == "/product/notifications/{id}/read":
                    expected = {404}
                else:
                    expected = {403}
                assert res.status_code in expected, (mode, path, res.text)
            res = client.post(
                f"/api/v1/workspaces/{target}/passports/documents",
                content=b"not-multipart",
                headers=h | {"Idempotency-Key": str(uuid4())},
            )
            assert res.status_code == (
                401 if mode == "anonymous" else 404 if mode == "foreign" else 403
            )
        with api.state.store.transaction(write=False) as con:
            after = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
        assert before == after
