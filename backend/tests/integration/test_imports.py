"""Phase 1-3 browser flows, scope isolation, immutable mapping and safe recovery."""

import hashlib
import os
import socket
import time
from contextlib import closing
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.access import AccessService
from app.storage.local import APPLICATION_ID, BASE_SCHEMA, LEGACY_DIGEST, LocalStore
from tests.integration.test_restart import maintenance, running_backend
from tests.unit.test_import_parsers import ROW, csv_content, demo_content, xlsx_content

PASSWORD = "synthetic-passphrase-only"
ORIGIN = "http://localhost:3000"


@pytest.fixture
def account():
    settings = Settings(
        app_env="test",
        read_requests_per_minute=2000,
        mutation_requests_per_minute=100,
        import_requests_per_minute=50,
    )
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    access = AccessService(store)
    user, workspace = access.provision("alice", PASSWORD, "Imports")
    registration = access.add_registration(workspace, "27ABCDE1234F1Z5", "Synthetic")
    store.close()
    return settings, user, workspace, registration


def signed_in(client, origin=ORIGIN):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": PASSWORD},
        headers={"Origin": origin},
    )
    assert response.status_code == 200
    return {"Origin": origin, "X-CSRF-Token": response.json()["data"]["csrf_token"]}


def upload(
    client, workspace, registration, headers, *, content=None, key=None, adapter="csv-v1", **changes
):
    fields = {
        "registration_id": registration,
        "period": "2024-05",
        "kind": "PURCHASE",
        "adapter_version": adapter,
    } | changes
    extensions = {"csv-v1": "csv", "xlsx-v1": "xlsx", "canonical-demo-v1": "json"}
    return client.post(
        f"/api/v1/workspaces/{workspace}/imports",
        data=fields,
        files={
            "file": ("input." + extensions[adapter], csv_content() if content is None else content)
        },
        headers=headers | {"Idempotency-Key": key or str(uuid4())},
    )


def completed(client, workspace, identifier):
    deadline = time.monotonic() + 15
    while True:
        response = client.get(f"/api/v1/workspaces/{workspace}/imports/{identifier}")
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        if data["state"] not in {"RECEIVED", "PARSING"}:
            return data
        assert time.monotonic() < deadline, "Import worker did not finish"
        time.sleep(0.03)


def confirm(client, workspace, identifier, version, headers, **changes):
    return client.post(
        f"/api/v1/workspaces/{workspace}/imports/{identifier}/confirm",
        json={"expected_version": version} | changes,
        headers=headers | {"Idempotency-Key": str(uuid4())},
    )


def test_upload_preview_idempotency_partial_confirmation_and_scope(account):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        assert upload(client, workspace, registration, {}).status_code == 401
        headers = signed_in(client)
        assert upload(client, str(uuid4()), registration, headers).status_code == 404
        assert upload(client, workspace, str(uuid4()), headers).status_code == 404
        assert upload(client, workspace, registration, {"Origin": ORIGIN}).status_code == 403
        content = csv_content(
            [ROW, {**ROW, "voucher_id": "V2", "invoice_number": "I2", "gross_total": "1.00"}]
        )
        key = str(uuid4())
        response = upload(client, workspace, registration, headers, content=content, key=key)
        assert response.status_code == 202, response.text
        identifier = response.json()["data"]["id"]
        assert (
            upload(client, workspace, registration, headers, content=content, key=key).json()[
                "data"
            ]["id"]
            == identifier
        )
        assert (
            upload(client, workspace, registration, headers, content=content).json()["data"]["id"]
            == identifier
        )
        assert upload(client, workspace, registration, headers, key=key).status_code == 409
        data = completed(client, workspace, identifier)
        assert data["state"] == "AWAITING_CONFIRMATION", data
        assert (data["accepted_rows"], data["rejected_rows"]) == (1, 1)
        base = f"/api/v1/workspaces/{workspace}/imports/{identifier}"
        rows = client.get(base + "/rows?limit=1").json()["data"]
        assert rows["next_cursor"] == 1 and rows["rows"][0]["canonical"]["gross_total"] == "1180.00"
        rejected = client.get(base + "/rows?state=REJECTED").json()["data"]["rows"]
        assert len(rejected) == 1 and rejected[0]["errors"][0]["reason"] == "GROSS_TOTAL_INVALID"
        assert client.get(f"/api/v1/workspaces/{uuid4()}/imports/{identifier}").status_code == 404
        assert confirm(client, workspace, identifier, 1, headers).status_code == 409
        assert (
            confirm(client, workspace, identifier, data["version"], headers).json()["error"]["code"]
            == "PARTIAL_ACK_REQUIRED"
        )
        confirmation_key = str(uuid4())
        payload = {"expected_version": data["version"], "allow_rejected_rows": True}
        response = client.post(
            base + "/confirm", json=payload, headers=headers | {"Idempotency-Key": confirmation_key}
        )
        assert response.status_code == 200 and response.json()["data"]["state"] == "READY"
        assert (
            client.post(
                base + "/confirm",
                json=payload,
                headers=headers | {"Idempotency-Key": confirmation_key},
            ).status_code
            == 200
        )
        assert (
            client.get(f"/api/v1/workspaces/{workspace}/jobs/{data['job_id']}").json()["data"][
                "state"
            ]
            == "SUCCEEDED"
        )
        listed = client.get(f"/api/v1/workspaces/{workspace}/imports?period=2024-05").json()["data"]
        assert [item["id"] for item in listed["imports"]] == [identifier]
        assert (
            client.get(f"/api/v1/workspaces/{workspace}/imports?period=2024-06").json()["data"][
                "imports"
            ]
            == []
        )
        assert client.get(f"/api/v1/workspaces/{uuid4()}/imports").status_code == 404
        assert client.get("/health/ready").status_code == 200
        app = client.app.app.app
        with app.state.store.transaction(write=False) as connection:
            assert connection.execute(
                "SELECT typeof(gross_total),gross_total FROM import_rows WHERE accepted=1"
            ).fetchone()[:] == ("integer", 118000)
            assert connection.execute("SELECT count(*) FROM import_files").fetchone()[0] == 1
            assert (
                connection.execute(
                    "SELECT count(*) FROM import_events WHERE action='CONFIRM'"
                ).fetchone()[0]
                == 1
            )
        app.state.access.grant("alice", workspace, "VIEWER")
        assert client.get(base).status_code == 200
        assert upload(client, workspace, registration, headers).status_code == 403
        app.state.access.grant("alice", workspace, "VIEWER", active=False)
        assert client.get(base).status_code == 404


def test_mapping_creates_derived_preview_ready_immutable_and_supersession(account):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        source = {
            "Voucher": "V1",
            **{key: value for key, value in ROW.items() if key != "voucher_id"},
        }
        response = upload(
            client, workspace, registration, headers, content=csv_content([source], list(source))
        )
        identifier = response.json()["data"]["id"]
        initial = completed(client, workspace, identifier)
        assert (
            initial["accepted_rows"] == 0 and initial["errors"][0]["reason"] == "MAPPING_REQUIRED"
        )
        mapping = {key: key for key in ROW if key != "voucher_id"} | {"voucher_id": "Voucher"}
        base = f"/api/v1/workspaces/{workspace}/imports/{identifier}"
        patched = client.patch(
            base + "/mapping",
            json={"expected_version": initial["version"], "mapping": mapping},
            headers=headers | {"Idempotency-Key": str(uuid4())},
        )
        assert patched.status_code == 202, patched.text
        derived = completed(client, workspace, patched.json()["data"]["id"])
        assert derived["derived_from_import_id"] == identifier and derived["accepted_rows"] == 1
        assert client.get(base).json()["data"]["accepted_rows"] == 0
        ready = confirm(client, workspace, derived["id"], derived["version"], headers).json()[
            "data"
        ]
        assert ready["state"] == "READY"
        newer = client.patch(
            f"/api/v1/workspaces/{workspace}/imports/{ready['id']}/mapping",
            json={"expected_version": ready["version"], "mapping": mapping},
            headers=headers | {"Idempotency-Key": str(uuid4())},
        )
        assert newer.status_code == 202
        newer = completed(client, workspace, newer.json()["data"]["id"])
        assert newer["supersedes_import_id"] == ready["id"]
        assert (
            confirm(client, workspace, newer["id"], newer["version"], headers).json()["error"][
                "code"
            ]
            == "SUPERSESSION_ACK_REQUIRED"
        )
        assert (
            confirm(
                client,
                workspace,
                newer["id"],
                newer["version"],
                headers,
                confirmed_supersession=True,
            ).status_code
            == 200
        )
        assert (
            client.get(f"/api/v1/workspaces/{workspace}/imports/{ready['id']}").json()["data"][
                "state"
            ]
            == "SUPERSEDED"
        )


def test_upload_limits_xlsx_demo_and_failure_never_ready(account):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        bad = upload(client, workspace, registration, headers, content=b"a,a\n1,2")
        bad = completed(client, workspace, bad.json()["data"]["id"])
        assert bad["state"] == "FAILED" and bad["errors"][0]["reason"] == "DUPLICATE_HEADERS"
        assert confirm(client, workspace, bad["id"], bad["version"], headers).status_code == 409
        response = upload(
            client, workspace, registration, headers, adapter="xlsx-v1", content=xlsx_content()
        )
        assert completed(client, workspace, response.json()["data"]["id"])["accepted_rows"] == 1
        response = upload(
            client,
            workspace,
            registration,
            headers,
            adapter="canonical-demo-v1",
            kind="PORTAL_2B",
            content=demo_content(),
        )
        result = completed(client, workspace, response.json()["data"]["id"])
        assert result["accepted_rows"] == 1 and result["provenance"] == "SYNTHETIC_DEMO"
        assert (
            upload(
                client,
                workspace,
                registration,
                headers,
                content=b"x" * (settings.max_upload_bytes + 1),
            ).status_code
            == 413
        )
        assert client.get("/health/live").status_code == 200
        preflight = client.options(
            f"/api/v1/workspaces/{workspace}/imports/{bad['id']}/mapping",
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "Idempotency-Key,X-CSRF-Token",
            },
        )
        assert preflight.status_code == 200


def test_explicit_legacy_upgrade_preserves_validated_v1(tmp_path):
    store = LocalStore(Settings())
    store.acquire()
    # Construct the exact previously shipped schema, not an invented partial DB.
    import sqlite3

    with closing(sqlite3.connect(store.path)) as connection, connection:
        for statement in BASE_SCHEMA:
            connection.execute(statement)
        connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
        connection.execute("PRAGMA user_version=1")
        connection.execute("INSERT INTO metadata VALUES ('schema',?)", (LEGACY_DIGEST,))
    identifier = store.upgrade()
    store.validate()
    store.validate(store.root / "backups" / f"{identifier}.sqlite3", legacy=True)
    assert store.upgrade() is None
    store.close()


def test_real_process_import_restart_and_backup_restore(account):
    settings, _, workspace, registration = account
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    environment = os.environ.copy()
    environment.update(
        PORT=str(port),
        PUBLIC_API_URL=f"http://127.0.0.1:{port}",
        PUBLIC_WEB_URL="http://127.0.0.1:3000",
        READ_REQUESTS_PER_MINUTE="2000",
    )
    content = csv_content()
    with running_backend(port, environment) as client:
        headers = signed_in(client, "http://127.0.0.1:3000")
        token = client.cookies.get("gstshield_session")
        response = upload(client, workspace, registration, headers)
        assert response.status_code == 202, response.text
        data = completed(client, workspace, response.json()["data"]["id"])
        assert confirm(client, workspace, data["id"], data["version"], headers).status_code == 200
    backup = maintenance(environment, "backup")
    assert backup.returncode == 0, backup.stderr
    backup_id = backup.stdout.strip().removeprefix("Backup ID: ")
    with running_backend(port, environment) as client:
        client.cookies.set("gstshield_session", token, path="/api/v1")
        assert (
            client.get(f"/api/v1/workspaces/{workspace}/imports/{data['id']}").json()["data"][
                "state"
            ]
            == "READY"
        )
        assert client.get(f"/api/v1/workspaces/{workspace}/imports/{data['id']}/rows").json()[
            "data"
        ]["rows"][0]["accepted"]
    restored = maintenance(environment, "restore", "--backup-id", backup_id)
    assert restored.returncode == 0, restored.stderr
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    with store.transaction(write=False) as connection:
        source = connection.execute("SELECT content,sha256 FROM import_files").fetchone()
        assert source[0] == content and source[1] == hashlib.sha256(content).hexdigest()
        assert connection.execute("SELECT state FROM imports").fetchone()[0] == "READY"
        assert connection.execute("SELECT gross_total FROM import_rows").fetchone()[0] == 118000
        assert connection.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
    store.close()


def test_concurrent_same_operation_commits_one_source_and_job(account):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from app.contracts.imports import UploadMetadata

    settings, _, workspace, registration = account
    app = create_app(settings)
    with TestClient(app) as client:
        signed_in(client)
        state = app.app.app.state
        identity = state.access.identity(client.cookies.get("gstshield_session"))
        metadata = UploadMetadata(
            kind="PURCHASE",
            registration_id=registration,
            period="2024-05",
            adapter_version="csv-v1",
        ).model_dump(mode="json")
        key = str(uuid4())
        barrier = threading.Barrier(2)

        def send():
            barrier.wait(timeout=5)
            return state.imports.upload(
                identity, workspace, metadata, csv_content(), "same.csv", key, str(uuid4())
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(send) for _ in range(2)]
            results = [future.result(timeout=15) for future in futures]
        assert results[0]["id"] == results[1]["id"]
        completed(client, workspace, results[0]["id"])
        with state.store.transaction(write=False) as connection:
            assert connection.execute("SELECT count(*) FROM imports").fetchone()[0] == 1
            assert connection.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
            assert connection.execute("SELECT count(*) FROM import_files").fetchone()[0] == 1
            assert connection.execute("SELECT count(*) FROM import_operations").fetchone()[0] == 1
