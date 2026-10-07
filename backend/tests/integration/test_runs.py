"""Import-to-run browser flows, review races, durable recovery and scope denial."""

import os
import socket
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import APIError
from app.main import create_app
from app.services.access import AccessService
from app.storage.local import (
    APPLICATION_ID,
    SCHEMA_VERSION,
    VERSION2_DIGEST,
    VERSION2_SCHEMA,
    VERSION3_DIGEST,
    VERSION3_SCHEMA,
    LocalStore,
)
from tests.integration.test_imports import (
    PASSWORD,
    completed,
    confirm,
    signed_in,
    upload,
)
from tests.integration.test_imports import (
    account as account,
)
from tests.integration.test_restart import maintenance, running_backend
from tests.unit.test_import_parsers import ROW, csv_content


def source(client, workspace, registration, headers, rows, kind, **changes):
    response = upload(
        client, workspace, registration, headers, content=csv_content(rows), kind=kind, **changes
    )
    assert response.status_code == 202, response.text
    data = completed(client, workspace, response.json()["data"]["id"])
    assert data["state"] == "AWAITING_CONFIRMATION", data
    response = confirm(
        client,
        workspace,
        data["id"],
        data["version"],
        headers,
        allow_rejected_rows=True,
        confirmed_supersession=bool(changes.get("supersedes_import_id")),
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def prepare(client, workspace, registration, headers, purchases=None, portals=None):
    purchase = source(
        client,
        workspace,
        registration,
        headers,
        purchases or [ROW | {"invoice_number": "INV/001"}],
        "PURCHASE",
    )
    portal = source(client, workspace, registration, headers, portals or [ROW], "PORTAL_2B")
    return {
        "registration_id": registration,
        "period": "2024-05",
        "purchase_import_id": purchase["id"],
        "portal_import_id": portal["id"],
    }


def create(client, workspace, headers, payload, key=None):
    return client.post(
        f"/api/v1/workspaces/{workspace}/runs",
        json=payload,
        headers=headers | {"Idempotency-Key": key or str(uuid4())},
    )


def finished(client, workspace, identifier):
    deadline = time.monotonic() + 15
    while True:
        response = client.get(f"/api/v1/workspaces/{workspace}/runs/{identifier}")
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        if data["state"] not in {"QUEUED", "RUNNING"}:
            return data
        assert time.monotonic() < deadline, data
        time.sleep(0.03)


def review(client, workspace, result, headers, *, key=None, action="ACCEPT_CANDIDATE", **changes):
    payload = {
        "expected_version": result["version"],
        "action": action,
        "candidate_id": result["candidates"][0]["id"] if action == "ACCEPT_CANDIDATE" else None,
        "reason": "Checked synthetic source voucher.",
    } | changes
    return client.post(
        f"/api/v1/workspaces/{workspace}/results/{result['id']}/review",
        json=payload,
        headers=headers | {"Idempotency-Key": key or str(uuid4())},
    )


def details(client, workspace, identifier):
    return client.get(f"/api/v1/workspaces/{workspace}/results/{identifier}").json()["data"]


def test_independent_golden_run_pagination_review_summary_and_retries(account):
    settings, _, workspace, registration = account
    purchases = [
        ROW | {"voucher_id": "A", "invoice_number": "A"},
        ROW | {"voucher_id": "F", "invoice_number": "INV/001"},
        ROW | {"voucher_id": "Z", "invoice_number": "Z"},
        ROW | {"voucher_id": "M", "invoice_number": "M"},
        ROW | {"voucher_id": "U", "invoice_number": "U", "cess": ""},
        ROW | {"voucher_id": "C", "invoice_number": "C", "document_type": "CREDIT_NOTE"},
        ROW | {"voucher_id": "D", "invoice_number": "D"},
    ]
    portals = [
        ROW | {"invoice_number": "A"},
        ROW,
        ROW | {"invoice_number": "M", "cgst": "91.00", "gross_total": "1181.00"},
        ROW | {"invoice_number": "D"},
        ROW | {"invoice_number": "D"},
    ]
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        payload = prepare(client, workspace, registration, headers, purchases, portals)
        key = str(uuid4())
        response = create(client, workspace, headers, payload, key)
        assert response.status_code == 202, response.text
        receipt = response.json()["data"]
        assert receipt["summary"] is None and receipt["state"] == "QUEUED"
        assert create(client, workspace, headers, payload, key).json()["data"] == receipt
        assert (
            create(client, workspace, headers, payload | {"period": "2024-04"}, key).status_code
            == 409
        )
        run = finished(client, workspace, receipt["id"])
        assert run["state"] == "COMPLETED", run
        summary = run["summary"]
        assert summary["counts"] == {
            "EXACT_MATCH": 1,
            "FUZZY_SUGGESTION": 1,
            "AMOUNT_MISMATCH": 1,
            "MISSING_IN_SNAPSHOT": 2,
            "AMBIGUOUS": 1,
            "EVIDENCE_INCOMPLETE": 1,
            "REVIEW_ACCEPTED": 0,
            "REJECTED": 0,
        }
        assert (
            summary["tax_exposure_review"] == "540.00"
            and summary["credit_note_tax_review"] == "180.00"
        )
        assert summary["unknown_tax_exposure_rows"] == 1
        base = f"/api/v1/workspaces/{workspace}"
        job = client.get(base + "/jobs/" + run["job_id"]).json()["data"]
        assert job["state"] == "SUCCEEDED" and job["kind"] == "RUN" and job["run_id"] == run["id"]
        assert "lease" not in job and job["import_id"] is None
        first = client.get(base + f"/runs/{run['id']}/results?limit=3").json()["data"]
        assert len(first["results"]) == 3 and first["next_cursor"] == 3
        second = client.get(base + f"/runs/{run['id']}/results?cursor=3").json()["data"]
        assert len(second["results"]) == 4 and second["next_cursor"] is None
        results = first["results"] + second["results"]
        assert [item["source_row_number"] for item in results] == list(range(1, 8))
        fuzzy = details(client, workspace, results[1]["id"])
        review_key = str(uuid4())
        accepted = review(client, workspace, fuzzy, headers, key=review_key)
        assert accepted.status_code == 200, accepted.text
        updated = accepted.json()["data"]
        assert updated["status"] == "REVIEW_ACCEPTED" and updated["version"] == 2
        assert (
            updated["assigned_portal_document_id"] == fuzzy["candidates"][0]["portal_document_id"]
        )
        assert len(updated["review_timeline"]) == 1
        assert review(client, workspace, fuzzy, headers, key=review_key).json()["data"] == updated
        assert review(client, workspace, fuzzy, headers).json()["error"]["code"] == "STALE_VERSION"
        assert (
            review(
                client, workspace, fuzzy, headers, key=review_key, reason="Different request"
            ).json()["error"]["code"]
            == "IDEMPOTENCY_CONFLICT"
        )
        mismatch = details(client, workspace, results[3]["id"])
        assert (
            review(client, workspace, mismatch, headers).json()["error"]["code"]
            == "CANDIDATE_INELIGIBLE"
        )
        exact = details(client, workspace, results[0]["id"])
        assert review(client, workspace, exact, headers, action="REJECT_MATCH").status_code == 200
        summary = client.get(base + f"/runs/{run['id']}").json()["data"]["summary"]
        assert summary["tax_exposure_review"] == "720.00" and summary["counts"]["REJECTED"] == 1
        assert summary["counts"]["REVIEW_ACCEPTED"] == 1 and sum(summary["counts"].values()) == 7
        filtered = client.get(base + f"/runs/{run['id']}/results?status=REVIEW_ACCEPTED").json()[
            "data"
        ]
        assert len(filtered["results"]) == 1
        assert client.get(base + "/runs?limit=1").json()["data"]["runs"][0]["id"] == run["id"]
        assert client.get("/health/ready").status_code == 200


def test_contested_reviews_serialize_without_double_assignment_and_reject_releases(account):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        payload = prepare(
            client,
            workspace,
            registration,
            headers,
            [
                ROW | {"invoice_number": "INV/001"},
                ROW | {"invoice_number": "INV.001", "voucher_id": "V2"},
            ],
            [ROW],
        )
        response = create(client, workspace, headers, payload)
        run = finished(client, workspace, response.json()["data"]["id"])
        assert run["state"] == "COMPLETED", run
        results = client.get(f"/api/v1/workspaces/{workspace}/runs/{run['id']}/results").json()[
            "data"
        ]["results"]
        results = [details(client, workspace, item["id"]) for item in results]
        assert all(item["status"] == "AMBIGUOUS" for item in results)
        access = client.app.app.app.state.access
        identity = access.identity(client.cookies.get("gstshield_session"))
        service = client.app.app.app.state.runs

        def accept(item):
            try:
                return service.review(
                    identity,
                    workspace,
                    item["id"],
                    {
                        "expected_version": 1,
                        "action": "ACCEPT_CANDIDATE",
                        "candidate_id": item["candidates"][0]["id"],
                        "reason": "Synthetic independent concurrent decision",
                    },
                    str(uuid4()),
                    str(uuid4()),
                )
            except APIError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(accept, results))
        assert sum(isinstance(item, dict) for item in outcomes) == 1
        assert [item.code for item in outcomes if isinstance(item, APIError)] == [
            "ASSIGNMENT_CONFLICT"
        ]
        winner = next(item for item in outcomes if isinstance(item, dict))
        loser = next(item for item in results if item["id"] != winner["id"])
        assert not details(client, workspace, loser["id"])["candidates"][0]["currently_available"]
        assert review(client, workspace, winner, headers, action="REJECT_MATCH").status_code == 200
        assert review(client, workspace, loser, headers).status_code == 200
        summary = client.get(f"/api/v1/workspaces/{workspace}/runs/{run['id']}").json()["data"][
            "summary"
        ]
        assert summary["counts"]["REVIEW_ACCEPTED"] == summary["counts"]["REJECTED"] == 1
        assert summary["tax_exposure_review"] == "180.00"
        # Two same-version writes to a single result produce exactly one audit entry.
        current = details(client, workspace, loser["id"])

        def reject(_):
            try:
                return service.review(
                    identity,
                    workspace,
                    current["id"],
                    {
                        "expected_version": current["version"],
                        "action": "REJECT_MATCH",
                        "candidate_id": None,
                        "reason": "Concurrent stale test",
                    },
                    str(uuid4()),
                    str(uuid4()),
                )
            except APIError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(reject, range(2)))
        assert [item.code for item in outcomes if isinstance(item, APIError)] == ["STALE_VERSION"]
        assert len(details(client, workspace, loser["id"])["review_timeline"]) == 2


def test_sources_supersession_history_and_failed_replacement_do_not_erase_results(account):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        payload = prepare(client, workspace, registration, headers)
        first = finished(
            client, workspace, create(client, workspace, headers, payload).json()["data"]["id"]
        )
        result = client.get(f"/api/v1/workspaces/{workspace}/runs/{first['id']}/results").json()[
            "data"
        ]["results"][0]
        result = details(client, workspace, result["id"])
        dispatcher = client.app.app.app.state.dispatcher
        dispatcher.close()
        newer = create(client, workspace, headers, payload).json()["data"]
        assert (
            client.get(f"/api/v1/workspaces/{workspace}/runs/{first['id']}").json()["data"]["state"]
            == "COMPLETED"
        )
        claimed = dispatcher.claim()
        client.app.app.app.state.runs.publish(claimed, {"error_code": "PROCESSING_TIMEOUT"})
        failed = finished(client, workspace, newer["id"])
        assert failed["state"] == "FAILED" and failed["summary"] is None
        assert (
            client.get(f"/api/v1/workspaces/{workspace}/runs/{first['id']}").json()["data"]["state"]
            == "COMPLETED"
        )
        receipt = create(client, workspace, headers, payload).json()["data"]
        claimed = dispatcher.claim()
        client.app.app.app.state.runs.publish(
            claimed | {"lease": str(uuid4())}, {"error_code": "PROCESSING_TIMEOUT"}
        )
        assert (
            client.get(f"/api/v1/workspaces/{workspace}/runs/{receipt['id']}").json()["data"][
                "state"
            ]
            == "RUNNING"
        )
        dispatcher.stop_event.clear()
        dispatcher.publish(claimed, dispatcher.parse(claimed))
        assert finished(client, workspace, receipt["id"])["state"] == "COMPLETED"
        historical = client.get(f"/api/v1/workspaces/{workspace}/runs/{first['id']}").json()["data"]
        assert (
            historical["state"] == "SUPERSEDED"
            and historical["superseded_by_run_id"] == receipt["id"]
        )
        assert historical["summary"] is not None
        assert (
            review(client, workspace, result, headers).json()["error"]["code"]
            == "SOURCE_SUPERSEDED"
        )
        # Source supersession alone prevents reviews; historical results remain readable.
        current = client.get(f"/api/v1/workspaces/{workspace}/runs/{receipt['id']}/results").json()[
            "data"
        ]["results"][0]
        current = details(client, workspace, current["id"])
        store = client.app.app.app.state.store
        with store.transaction() as connection:
            connection.execute(
                "UPDATE imports SET state='SUPERSEDED',version=version+1 WHERE id=?",
                (payload["portal_import_id"],),
            )
        assert (
            review(client, workspace, current, headers).json()["error"]["code"]
            == "SOURCE_SUPERSEDED"
        )
        assert not client.get(f"/api/v1/workspaces/{workspace}/runs/{receipt['id']}").json()[
            "data"
        ]["sources_current"]
        assert (
            create(client, workspace, headers, payload).json()["error"]["code"]
            == "SOURCE_CONTEXT_INVALID"
        )


def test_run_scope_role_csrf_context_and_review_validation(account):
    settings, _, workspace, registration = account
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    access = AccessService(store)
    _, foreign = access.provision("bob", PASSWORD, "Other scope")
    store.close()
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        payload = prepare(client, workspace, registration, headers)
        assert create(client, workspace, {}, payload).status_code == 403
        assert create(client, foreign, headers, payload).status_code == 404
        assert (
            create(
                client, workspace, headers, payload | {"registration_id": str(uuid4())}
            ).status_code
            == 409
        )
        assert (
            create(
                client, workspace, headers, payload | {"policy_version": "client-selected"}
            ).status_code
            == 422
        )
        assert (
            create(client, workspace, headers, payload | {"period": "0000-01"}).status_code == 422
        )
        run = finished(
            client, workspace, create(client, workspace, headers, payload).json()["data"]["id"]
        )
        result = client.get(f"/api/v1/workspaces/{workspace}/runs/{run['id']}/results").json()[
            "data"
        ]["results"][0]
        result = details(client, workspace, result["id"])
        assert review(client, workspace, result, headers, reason="   ").status_code == 422
        assert review(client, workspace, result, headers, expected_version=True).status_code == 422
        assert review(client, workspace, result, headers, candidate_id=None).status_code == 422
        assert (
            review(
                client, workspace, result, headers, action="REJECT_MATCH", candidate_id=str(uuid4())
            ).status_code
            == 422
        )
        assert (
            review(client, workspace, result, headers, candidate_id=str(uuid4())).status_code == 404
        )
        access = client.app.app.app.state.access
        access.grant("alice", workspace, "VIEWER")
        assert client.get(f"/api/v1/workspaces/{workspace}/runs/{run['id']}").status_code == 200
        assert review(client, workspace, result, headers).status_code == 403
        assert create(client, workspace, headers, payload).status_code == 403
        client.cookies.clear()
        assert client.get(f"/api/v1/workspaces/{workspace}/runs/{run['id']}").status_code == 401
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "bob", "password": PASSWORD},
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.status_code == 200
        bob_headers = {
            "Origin": "http://localhost:3000",
            "X-CSRF-Token": response.json()["data"]["csrf_token"],
        }
        for path in (f"/runs/{run['id']}", f"/results/{result['id']}", f"/jobs/{run['job_id']}"):
            assert client.get(f"/api/v1/workspaces/{foreign}" + path).status_code == 404
            assert client.get(f"/api/v1/workspaces/{workspace}" + path).status_code == 404
        assert create(client, foreign, bob_headers, payload).status_code == 404


def test_queued_recovery_interruption_shared_queue_and_quota(account):
    settings, _, workspace, registration = account
    settings = settings.model_copy(
        update={"max_queued_jobs_per_workspace": 1, "max_runs_per_workspace": 3}
    )
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        payload = prepare(client, workspace, registration, headers)
        dispatcher = client.app.app.app.state.dispatcher
        dispatcher.close()
        receipt = create(client, workspace, headers, payload).json()["data"]
        assert create(client, workspace, headers, payload).json()["error"]["code"] == "QUEUE_FULL"
        # Import admission uses the same queued-job budget.
        assert (
            upload(
                client,
                workspace,
                registration,
                headers,
                content=csv_content([ROW | {"invoice_number": "DIFFERENT"}]),
            ).json()["error"]["code"]
            == "QUEUE_FULL"
        )
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        queued = finished(client, workspace, receipt["id"])
        assert queued["state"] == "COMPLETED", queued
        headers = signed_in(client)
        dispatcher = client.app.app.app.state.dispatcher
        dispatcher.close()
        interrupted = create(client, workspace, headers, payload).json()["data"]
        dispatcher.claim()
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        data = finished(client, workspace, interrupted["id"])
        assert data["state"] == "FAILED" and data["summary"] is None
        job = client.get(f"/api/v1/workspaces/{workspace}/jobs/{data['job_id']}").json()["data"]
        assert job["error_code"] == "PROCESSING_INTERRUPTED"
        headers = signed_in(client)
        third = create(client, workspace, headers, payload)
        assert third.status_code == 202
        assert finished(client, workspace, third.json()["data"]["id"])["state"] == "COMPLETED"
        assert create(client, workspace, headers, payload).json()["error"]["code"] == "RUN_LIMIT"


@pytest.mark.parametrize(
    "version,schema,fingerprint",
    [
        (2, VERSION2_SCHEMA, VERSION2_DIGEST),
        (3, VERSION3_SCHEMA, VERSION3_DIGEST),
    ],
)
def test_explicit_old_schema_upgrade_preserves_backup(version, schema, fingerprint):
    store = LocalStore(Settings())
    store.acquire()
    try:
        with closing(sqlite3.connect(store.path)) as connection, connection:
            for statement in schema:
                connection.execute(statement)
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute(f"PRAGMA user_version={version}")
            connection.execute("INSERT INTO metadata VALUES ('schema',?)", (fingerprint,))
        backup = store.upgrade()
        store.validate()
        store.validate(store.root / "backups" / f"{backup}.sqlite3", version=version)
        assert store.upgrade() is None
        with store.transaction(write=False) as connection:
            assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
            assert connection.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
    finally:
        store.close()


def test_review_failure_rolls_back_result_summary_audit_and_operation(account, monkeypatch):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        payload = prepare(client, workspace, registration, headers)
        run = finished(
            client, workspace, create(client, workspace, headers, payload).json()["data"]["id"]
        )
        result = client.get(f"/api/v1/workspaces/{workspace}/runs/{run['id']}/results").json()[
            "data"
        ]["results"][0]
        result = details(client, workspace, result["id"])
        service = client.app.app.app.state.runs
        original_event = service.event

        def fail(*args, **kwargs):
            raise RuntimeError("Synthetic transaction failure")

        monkeypatch.setattr(service, "event", fail)
        key = str(uuid4())
        response = review(client, workspace, result, headers, key=key)
        assert response.status_code == 500
        assert details(client, workspace, result["id"]) == result
        current = client.get(f"/api/v1/workspaces/{workspace}/runs/{run['id']}").json()["data"]
        assert current["summary"] == run["summary"] and current["version"] == run["version"]
        monkeypatch.setattr(service, "event", original_event)
        assert review(client, workspace, result, headers, key=key).status_code == 200


@pytest.mark.parametrize("count", [100, 2000])
def test_bounded_real_worker_matching_benchmark_and_summary(account, count):
    settings, _, workspace, registration = account
    purchases = [
        ROW | {"voucher_id": f"V{index}", "invoice_number": f"INVOICE-{index:06d}"}
        for index in range(count)
    ]
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        payload = prepare(client, workspace, registration, headers, purchases, purchases)
        dispatcher = client.app.app.app.state.dispatcher
        dispatcher.peak_rss = 0
        started = time.monotonic()
        run = finished(
            client, workspace, create(client, workspace, headers, payload).json()["data"]["id"]
        )
        elapsed = time.monotonic() - started
        assert run["state"] == "COMPLETED", run
        assert run["summary"]["counts"]["EXACT_MATCH"] == count
        assert run["summary"]["accepted_purchase_rows"] == count
        assert run["summary"]["tax_exposure_review"] == "0.00"
        assert sum(run["summary"]["counts"].values()) == count
        assert dispatcher.peak_rss < settings.max_parser_rss_bytes
        print(
            f"MATCH_BASELINE rows={count} seconds={elapsed:.3f} "
            f"sampled_child_tree_rss_bytes={dispatcher.peak_rss}"
        )


def test_match_resource_limit_is_a_failed_job_with_no_partial_output(account):
    settings, _, workspace, registration = account
    settings = settings.model_copy(update={"max_match_candidates": 1})
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        payload = prepare(client, workspace, registration, headers, [ROW], [ROW, ROW])
        run = finished(
            client, workspace, create(client, workspace, headers, payload).json()["data"]["id"]
        )
        assert run["state"] == "FAILED" and run["summary"] is None
        base = f"/api/v1/workspaces/{workspace}"
        assert (
            client.get(base + f"/jobs/{run['job_id']}").json()["data"]["error_code"]
            == "MATCH_CANDIDATE_LIMIT"
        )
        assert client.get(base + f"/runs/{run['id']}/results").json()["data"]["results"] == []


def test_real_process_run_review_restart_and_backup_restore(account):
    settings, _, workspace, registration = account
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    environment = {
        key: value for key, value in os.environ.items() if key.lower() not in Settings.model_fields
    }
    environment.update(
        PORT=str(port),
        PUBLIC_API_URL=f"http://127.0.0.1:{port}",
        PUBLIC_WEB_URL="http://127.0.0.1:3000",
        READ_REQUESTS_PER_MINUTE="2000",
        MUTATION_REQUESTS_PER_MINUTE="100",
        IMPORT_REQUESTS_PER_MINUTE="50",
    )
    origin = "http://127.0.0.1:3000"
    with running_backend(port, environment) as client:
        headers = signed_in(client, origin)
        payload = prepare(client, workspace, registration, headers)
        run = finished(
            client, workspace, create(client, workspace, headers, payload).json()["data"]["id"]
        )
        assert run["state"] == "COMPLETED"
        result = client.get(f"/api/v1/workspaces/{workspace}/runs/{run['id']}/results").json()[
            "data"
        ]["results"][0]
        result = details(client, workspace, result["id"])
        accepted = review(client, workspace, result, headers)
        assert accepted.status_code == 200, accepted.text
        result = accepted.json()["data"]
        token = client.cookies.get("gstshield_session")
    backup = maintenance(environment, "backup")
    assert backup.returncode == 0, backup.stderr
    identifier = backup.stdout.strip().removeprefix("Backup ID: ")
    with running_backend(port, environment) as client:
        client.cookies.set("gstshield_session", token, path="/api/v1")
        saved = details(client, workspace, result["id"])
        assert saved == result
        current = client.get(f"/api/v1/workspaces/{workspace}/runs/{run['id']}").json()["data"]
        assert current["summary"]["counts"]["REVIEW_ACCEPTED"] == 1
        assert current["sources"] == run["sources"] and current["policy"] == run["policy"]
        assert (
            client.get(f"/api/v1/workspaces/{workspace}/jobs/{run['job_id']}").json()["data"][
                "state"
            ]
            == "SUCCEEDED"
        )
    restored = maintenance(environment, "restore", "--backup-id", identifier)
    assert restored.returncode == 0, restored.stderr
    with running_backend(port, environment) as client:
        client.cookies.set("gstshield_session", token, path="/api/v1")
        assert client.get(f"/api/v1/workspaces/{workspace}/runs/{run['id']}").status_code == 401
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    try:
        AccessService(store).reset_password("alice", PASSWORD)
    finally:
        store.close()
    with running_backend(port, environment) as client:
        signed_in(client, origin)
        assert details(client, workspace, result["id"]) == result
        assert (
            client.get(f"/api/v1/workspaces/{workspace}/runs/{run['id']}").json()["data"][
                "summary"
            ]["counts"]["REVIEW_ACCEPTED"]
            == 1
        )


def test_sqlite_run_constraints_reject_invalid_assignments_and_cross_source_candidates(account):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        payload = prepare(client, workspace, registration, headers)
        run = finished(
            client, workspace, create(client, workspace, headers, payload).json()["data"]["id"]
        )
        result = client.get(f"/api/v1/workspaces/{workspace}/runs/{run['id']}/results").json()[
            "data"
        ]["results"][0]
        result = details(client, workspace, result["id"])
        store = client.app.app.app.state.store
        for query, parameters in [
            (
                "UPDATE run_results SET assigned_portal_row=99999,status='REVIEW_ACCEPTED' "
                "WHERE id=?",
                (result["id"],),
            ),
            ("UPDATE run_results SET status='EXACT_MATCH' WHERE id=?", (result["id"],)),
            (
                "UPDATE run_candidates SET portal_import_id=? WHERE result_id=?",
                (payload["purchase_import_id"], result["id"]),
            ),
            ("UPDATE runs SET summary_json=NULL WHERE id=?", (run["id"],)),
            ("UPDATE run_jobs SET state='RUNNING',lease=NULL WHERE run_id=?", (run["id"],)),
        ]:
            with pytest.raises(sqlite3.IntegrityError), store.transaction() as connection:
                connection.execute(query, parameters)
        assert details(client, workspace, result["id"]) == result
        store.validate()


def test_matching_releases_read_snapshot_before_cpu_work(account, monkeypatch, capsys, tmp_path):
    import json
    import sys

    from app.jobs import run_worker

    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        payload = prepare(client, workspace, registration, headers)
        receipt = create(client, workspace, headers, payload).json()["data"]
        run = finished(client, workspace, receipt["id"])
        assert run["state"] == "COMPLETED"
        application = client.app.app.app
        application.state.action_monitor.close()
        application.state.dispatcher.close()
        store = application.state.store
        with store.transaction() as connection:
            connection.execute(
                "UPDATE runs SET state='RUNNING',summary_json=NULL WHERE id=?", (run["id"],)
            )
        task = tmp_path / "synthetic-match-task.json"
        task.write_text(
            json.dumps(
                {
                    "database": str(store.path),
                    "workspace_id": workspace,
                    "run_id": run["id"],
                }
            ),
            encoding="utf-8",
        )
        original, writes = run_worker.reconcile, []

        def compute(purchases, portals, policy):
            # Actual SQLite commit, while the worker still owns its immutable input.
            with store.transaction() as writer:
                writer.execute("INSERT INTO metadata VALUES ('synthetic-worker-write','confirmed')")
            writes.append(True)
            return original(purchases, portals, policy)

        monkeypatch.setattr(run_worker, "reconcile", compute)
        monkeypatch.setattr(sys, "argv", ["run_worker", str(task)])
        assert run_worker.main() == 0
        outcome = json.loads(capsys.readouterr().out)
        assert "error_code" not in outcome, outcome
        assert writes == [True] and len(outcome["result"]["results"]) == 1
