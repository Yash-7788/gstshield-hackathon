"""Six original problem scenarios through private APIs, including persistence and failure gates."""

import os
import socket
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.errors import APIError, StorageError
from app.main import create_app
from app.services.access import AccessService
from app.storage.local import (
    APPLICATION_ID,
    SCHEMA_VERSION,
    VERSION4_DIGEST,
    VERSION4_SCHEMA,
    LocalStore,
)
from tests.integration.test_imports import PASSWORD, signed_in
from tests.integration.test_imports import account as account
from tests.integration.test_restart import maintenance, running_backend
from tests.integration.test_runs import create, finished, prepare, source
from tests.integration.test_workflows import artifact, get, post, ready_run
from tests.unit.test_import_parsers import ROW


def queue(client, workspace):
    response = get(client, workspace, "actions?limit=20")
    assert response.status_code == 200, response.text
    return response.json()["data"]


def action(client, workspace, kind, case_id=None):
    rows = queue(client, workspace)["actions"]
    matches = [
        row
        for row in rows
        if row["kind"] == kind and (case_id is None or row["case_id"] == case_id)
    ]
    assert len(matches) == 1, rows
    return matches[0]


def change(client, workspace, headers, row, path, **payload):
    response = post(
        client,
        workspace,
        f"actions/{row['id']}/{path}",
        headers,
        {
            "expected_version": row["version"],
            "reason": "Reviewed synthetic observations.",
            **payload,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def new_case(client, workspace, registration, headers, result, kind, facts):
    response = post(
        client,
        workspace,
        "cases",
        headers,
        {
            "registration_id": registration,
            "result_id": result["id"],
            "purchase_document_id": result["purchase_document_id"],
            "kind": kind,
            "amount": "180.00",
            "facts": facts,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def evidence(client, workspace, headers, case, kind, patch):
    response = post(
        client,
        workspace,
        f"cases/{case['id']}/evidence",
        headers,
        {
            "expected_version": case["version"],
            "reason": "Synthetic dated observation.",
            "event_kind": kind,
            "facts_patch": patch,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_missing_invoice_is_tracked_across_new_snapshot_without_repeat_purchase_upload(account):
    settings, user, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        purchase_row = ROW | {
            "taxable_value": "100000.00",
            "cgst": "10000.00",
            "sgst": "10000.00",
            "gross_total": "120000.00",
        }
        payload = prepare(
            client,
            workspace,
            registration,
            headers,
            purchases=[purchase_row],
            portals=[ROW | {"invoice_number": "OTHER-999"}],
        )
        run = finished(
            client, workspace, create(client, workspace, headers, payload).json()["data"]["id"]
        )
        tracked = action(client, workspace, "INVOICE_REVIEW")
        assert tracked["source"]["status"] == "MISSING_IN_SNAPSHOT"
        assert tracked["source"]["recorded_tax"] == "20000.00"
        tracked = change(
            client,
            workspace,
            headers,
            tracked,
            "followups",
            contact="+919876543210",
            request="Please correct or report the missing invoice.",
        )
        draft = tracked["timeline"][-1]
        assert draft["snapshot"]["delivery"] == "NOT_SENT"
        tracked = change(
            client,
            workspace,
            headers,
            tracked,
            "followups",
            kind="ATTEMPT_RECORDED",
            contact="+919876543210",
            request="Please correct or report the missing invoice.",
            draft_id=draft["id"],
            observed_on="2024-06-01",
        )
        assert tracked["state"] == "AWAITING_SUPPLIER"
        later = source(
            client,
            workspace,
            registration,
            headers,
            [purchase_row],
            "PORTAL_2B",
            supersedes_import_id=payload["portal_import_id"],
        )
        new_payload = payload | {"portal_import_id": later["id"]}
        latest = finished(
            client, workspace, create(client, workspace, headers, new_payload).json()["data"]["id"]
        )
        fresh = action(client, workspace, "INVOICE_REVIEW")
        assert fresh["id"] == tracked["id"] and fresh["document_id"] == tracked["document_id"]
        assert fresh["source"]["status"] == "EXACT_MATCH" and fresh["state"] == "REVIEW_REQUIRED"
        assert fresh["source"]["legal_eligibility"] == "NOT_DETERMINED"
        assert fresh["run_id"] == latest["id"] != run["id"]
        assert fresh["timeline"][-1]["snapshot"]["previous"]["status"] == "MISSING_IN_SNAPSHOT"
        again = action(client, workspace, "INVOICE_REVIEW")
        assert again == fresh
        reviewed = change(
            client,
            workspace,
            headers,
            fresh,
            "outcomes",
            kind="REVIEW_DECISION",
            decision="REVIEW_ACCEPTED",
        )
        closed = change(client, workspace, headers, reviewed, "update", state="CLOSED")
        assert (
            closed["state"] == "CLOSED"
            and closed["source"]["legal_eligibility"] == "NOT_DETERMINED"
        )
        # A later disappearance reopens the same action rather than erasing previous closure.
        third = source(
            client,
            workspace,
            registration,
            headers,
            [ROW | {"invoice_number": "OTHER-998"}],
            "PORTAL_2B",
            supersedes_import_id=later["id"],
        )
        finished(
            client,
            workspace,
            create(client, workspace, headers, payload | {"portal_import_id": third["id"]}).json()[
                "data"
            ]["id"],
        )
        reopened = action(client, workspace, "INVOICE_REVIEW")
        assert reopened["state"] == "REVIEW_REQUIRED" and reopened["outcome"] is None
        assert reopened["id"] == tracked["id"]


def test_msme_payment_change_updates_remaining_balance_and_due_alerts_deduplicate(account):
    settings, user, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        run, result, _ = ready_run(client, workspace, registration, headers)
        case = new_case(client, workspace, registration, headers, result, "MSME_REVIEW", {})
        tracked = action(client, workspace, "MSME_REVIEW", case["id"])
        assert tracked["source"]["review"]["remaining_balance"] is None
        assert "acceptance_date" in tracked["source"]["review"]["missing_facts"]
        tracked = change(
            client,
            workspace,
            headers,
            tracked,
            "update",
            state="EVIDENCE_REQUIRED",
            review_on="2024-05-01",
            assigned_to=user,
        )
        tracked = action(client, workspace, "MSME_REVIEW", case["id"])
        assert len([e for e in tracked["timeline"] if e["kind"] == "REVIEW_DUE"]) == 1
        assert tracked["reminded_at"] == tracked["due_at"]
        case = evidence(
            client,
            workspace,
            headers,
            case,
            "PAYMENT_OBSERVATION",
            {"amount_paid": "500.00", "payment_observed_on": "2024-05-02"},
        )
        changed = action(client, workspace, "MSME_REVIEW", case["id"])
        assert changed["source"]["review"]["remaining_balance"] == "680.00"
        assert changed["state"] == "REVIEW_REQUIRED"
        assert changed["due_at"] == tracked["due_at"]
        assert len([e for e in changed["timeline"] if e["kind"] == "REVIEW_DUE"]) == 1
        assert (
            get(client, workspace, "actions?due_only=true").json()["data"]["actions"][0]["id"]
            == tracked["id"]
        )


def test_reclaim_candidate_requires_prior_reversal_and_matching_filing_evidence(account):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        run, result, payload = ready_run(client, workspace, registration, headers)
        case = new_case(
            client,
            workspace,
            registration,
            headers,
            result,
            "RULE37A_REVIEW",
            {
                "original_claim_period": "2024-04",
                "original_claim_amount": "180.00",
                "reversal_period": "2024-05",
                "reversal_amount": "180.00",
                "supplier_return_period": "2024-04",
                "supplier_return_status": "NOT_FILED",
            },
        )
        tracked = action(client, workspace, "RULE37A_REVIEW", case["id"])
        assert not tracked["source"]["review"]["reclaim_candidate"]
        case = evidence(
            client,
            workspace,
            headers,
            case,
            "FILING_OBSERVATION",
            {
                "supplier_return_status": "FILED",
                "filing_observed_on": "2024-06-01",
            },
        )
        tracked = action(client, workspace, "RULE37A_REVIEW", case["id"])
        assert tracked["source"]["review"]["reclaim_candidate"]
        assert tracked["source"]["review"]["proposed_reclaim_amount"] == "180.00"
        document = post(
            client,
            workspace,
            f"cases/{case['id']}/evidence",
            headers,
            {
                "expected_version": case["version"],
                "reason": "Supporting retained demo document",
                "event_kind": "DOCUMENT",
                "import_id": payload["purchase_import_id"],
            },
        )
        assert document.status_code == 200, document.text
        case = document.json()["data"]
        tracked = action(client, workspace, "RULE37A_REVIEW", case["id"])
        tracked = change(
            client,
            workspace,
            headers,
            tracked,
            "outcomes",
            kind="REVIEW_DECISION",
            decision="REVIEW_ACCEPTED",
            amount="180.00",
        )
        assert tracked["outcome"]["execution"] == "NOT_PERFORMED"
        tracked = change(
            client,
            workspace,
            headers,
            tracked,
            "outcomes",
            kind="FILING_OBSERVATION",
            reference="USER-RECORDED-RETURN-REF",
            observed_on="2024-06-02",
            amount="180.00",
            evidence_event_ids=case["facts"]["observation_refs"],
        )
        worksheet = get(client, workspace, f"actions/{tracked['id']}/worksheet").json()["data"]
        assert worksheet["label"] == "REVIEW_WORKSHEET_NOT_FILED_RETURN"
        assert not worksheet["recovery_guarantee"]
        assert worksheet["reviewed_outcome"]["government_verified"] is False
        assert worksheet["reviewed_outcome"]["amount"] == "180.00"
        # An equal supplier observation retains the reviewed outcome and creates no review trigger.
        evidence(client, workspace, headers, case, "FILING_OBSERVATION", {})
        fresh = action(client, workspace, "RULE37A_REVIEW", case["id"])
        assert fresh["outcome"] == tracked["outcome"]
        assert fresh["timeline"][-1]["kind"] == "SOURCE_REFRESHED"
        # A first-time claim without recorded reversal is never a reclaim candidate.
        missing = new_case(
            client,
            workspace,
            registration,
            headers,
            result,
            "RULE37A_REVIEW",
            {
                "supplier_return_period": "2024-04",
                "supplier_return_status": "FILED",
                "filing_observed_on": "2024-06-01",
            },
        )
        assert not action(client, workspace, "RULE37A_REVIEW", missing["id"])["source"]["review"][
            "reclaim_candidate"
        ]


def test_irn_format_and_notice_readiness_remain_evidence_review(account, tmp_path):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        run, result, payload = ready_run(client, workspace, registration, headers)
        irn = new_case(
            client,
            workspace,
            registration,
            headers,
            result,
            "IRN_REVIEW",
            {"irn": "a" * 64, "applicability": "APPLIES"},
        )
        tracked = action(client, workspace, "IRN_REVIEW", irn["id"])
        assert tracked["source"]["review"]["irn_observation"] == "FORMAT_ONLY"
        assert tracked["source"]["review"]["government_verification"] == "NOT_IMPLEMENTED"
        notice = new_case(
            client,
            workspace,
            registration,
            headers,
            result,
            "NOTICE_REVIEW",
            {
                "notice_reference": "SYNTHETIC-NOTICE",
                "notice_date": "2024-05-01",
                "response_due_date": "2024-05-20",
            },
        )
        tracked = action(client, workspace, "NOTICE_REVIEW", notice["id"])
        assert "evidence:DOCUMENT" in tracked["source"]["review"]["missing_facts"]
        assert len([e for e in tracked["timeline"] if e["kind"] == "REVIEW_DUE"]) == 1
        report = artifact(client, workspace, headers, "EVIDENCE_PDF", notice)
        assert report["state"] == "READY"
        before = action(client, workspace, "NOTICE_REVIEW", notice["id"])
        assert before["outcome"] is None and before["state"] != "CLOSED"
        assert before["source"]["facts"]["response_due_date"] == "2024-05-20"
        # A generic note is insufficient evidence for a claimed notice submission.
        response = post(
            client,
            workspace,
            f"actions/{before['id']}/outcomes",
            headers,
            {
                "expected_version": before["version"],
                "reason": "Test",
                "kind": "NOTICE_SUBMISSION_OBSERVATION",
                "reference": "SUBMIT-REF",
                "observed_on": "2024-05-20",
                "evidence_event_ids": [str(uuid4())],
            },
        )
        assert response.status_code == 422
        document = post(
            client,
            workspace,
            f"cases/{notice['id']}/evidence",
            headers,
            {
                "expected_version": notice["version"],
                "event_kind": "DOCUMENT",
                "reason": "Supporting retained evidence",
                "import_id": payload["purchase_import_id"],
            },
        )
        assert document.status_code == 200, document.text
        notice = document.json()["data"]
        tracked = action(client, workspace, "NOTICE_REVIEW", notice["id"])
        assert not tracked["source"]["review"]["missing_facts"]
        tracked = change(
            client,
            workspace,
            headers,
            tracked,
            "outcomes",
            kind="REVIEW_DECISION",
            decision="REVIEW_ACCEPTED",
        )
        tracked = change(
            client,
            workspace,
            headers,
            tracked,
            "outcomes",
            kind="NOTICE_SUBMISSION_OBSERVATION",
            reference="USER-REPORTED-SUBMISSION",
            observed_on="2024-05-20",
            evidence_event_ids=notice["facts"]["observation_refs"],
        )
        assert tracked["outcome"]["execution"] == "NOT_PERFORMED"
        assert tracked["outcome"]["government_verified"] is False
        assert (
            get(client, workspace, f"artifacts/{report['id']}").json()["data"]["sources_current"]
            is False
        )
        report = artifact(client, workspace, headers, "EVIDENCE_PDF", notice)
        assert report["state"] == "READY", report
        download = get(client, workspace, f"artifacts/{report['id']}/download")
        assert download.status_code == 200
        (tmp_path / "notice-actions.pdf").write_bytes(download.content)
        # Independent closed action retains its submission history; PDF still changes no status.
        tracked = change(client, workspace, headers, tracked, "update", state="CLOSED")
        assert tracked["outcome"]["reference"] == "USER-REPORTED-SUBMISSION"


def test_private_action_commands_stale_versions_idempotency_and_transaction_rollback(
    account, monkeypatch
):
    settings, user, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        _, result, _ = ready_run(client, workspace, registration, headers)
        case = new_case(client, workspace, registration, headers, result, "IRN_REVIEW", {})
        tracked = action(client, workspace, "IRN_REVIEW", case["id"])
        assert get(client, str(uuid4()), f"actions/{tracked['id']}").status_code == 404
        payload = {"expected_version": tracked["version"], "state": "OPEN", "reason": "Reviewed"}
        assert (
            post(client, workspace, f"actions/{tracked['id']}/update", {}, payload).status_code
            == 403
        )
        key = str(uuid4())
        response = post(client, workspace, f"actions/{tracked['id']}/update", headers, payload, key)
        assert response.status_code == 200, response.text
        assert (
            post(
                client, workspace, f"actions/{tracked['id']}/update", headers, payload, key
            ).json()["data"]
            == response.json()["data"]
        )
        assert (
            post(
                client,
                workspace,
                f"actions/{tracked['id']}/update",
                headers,
                payload | {"state": "REVIEW_REQUIRED"},
                key,
            ).status_code
            == 409
        )
        assert (
            post(client, workspace, f"actions/{tracked['id']}/update", headers, payload).status_code
            == 409
        )
        data = response.json()["data"]
        assert (
            post(
                client,
                workspace,
                f"actions/{data['id']}/update",
                headers,
                {
                    "expected_version": data["version"],
                    "state": "CLOSED",
                    "reason": "No outcome",
                },
            ).status_code
            == 409
        )
        # Audit failure rolls back the command rather than applying an unaudited state.
        app = client.app.app.app if hasattr(client.app, "app") else client.app
        # FastAPI state is available through the established workflow accessor's inner app.
        while not hasattr(app, "state"):
            app = app.app
        service = app.state.actions
        original = service.event

        def fail(*args, **kwargs):
            raise APIError(409, "AUDIT_TEST_FAILURE", "Synthetic audit fault.")

        monkeypatch.setattr(service, "event", fail)
        denied = post(
            client,
            workspace,
            f"actions/{data['id']}/update",
            headers,
            {
                "expected_version": data["version"],
                "state": "REVIEW_REQUIRED",
                "reason": "Test rollback",
            },
        )
        assert denied.status_code == 409
        monkeypatch.setattr(service, "event", original)
        assert action(client, workspace, "IRN_REVIEW", case["id"])["version"] == data["version"]
        with service.store.transaction() as connection:
            connection.execute(
                "UPDATE memberships SET role='VIEWER' WHERE workspace_id=? AND user_id=?",
                (workspace, user),
            )
        assert (
            post(
                client,
                workspace,
                f"actions/{data['id']}/update",
                headers,
                {
                    "expected_version": data["version"],
                    "state": "OPEN",
                    "reason": "Viewer denied",
                },
            ).status_code
            == 403
        )
        assert get(client, workspace, f"actions/{data['id']}").status_code == 200
        with service.store.transaction() as connection:
            connection.execute(
                "UPDATE memberships SET active=0 WHERE workspace_id=? AND user_id=?",
                (workspace, user),
            )
        assert get(client, workspace, f"actions/{data['id']}").status_code == 404


def test_schema_four_upgrade_preserves_original_backup_and_adds_only_action_tables():
    from app.config import Settings

    store = LocalStore(Settings())
    store.acquire()
    try:
        with closing(sqlite3.connect(store.path)) as connection:
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute("PRAGMA user_version=4")
            for statement in VERSION4_SCHEMA:
                connection.execute(statement)
            connection.execute("INSERT INTO metadata VALUES ('schema',?)", (VERSION4_DIGEST,))
            connection.commit()
        access = AccessService(store)
        user, workspace = access.provision("preserved", PASSWORD, "Old phase five workspace")
        registration = access.add_registration(
            workspace, "27ABCDE1234F1Z5", "Preserved registration"
        )
        with store.transaction(write=False) as connection:
            before = {
                table: [tuple(r) for r in connection.execute(f'SELECT * FROM "{table}"')]
                for table in ("users", "workspaces", "memberships", "registrations")
            }
        with pytest.raises(StorageError):
            store.initialize()
        identifier = store.upgrade()
        assert identifier
        with store.transaction(write=False) as connection:
            assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
            assert connection.execute("SELECT count(*) FROM business_actions").fetchone()[0] == 0
            for table, rows in before.items():
                assert [tuple(r) for r in connection.execute(f'SELECT * FROM "{table}"')] == rows
            assert connection.execute("SELECT id FROM users").fetchone()[0] == user
            assert connection.execute("SELECT id FROM registrations").fetchone()[0] == registration
        store.validate(store.root / "backups" / f"{identifier}.sqlite3", version=4)
        assert store.upgrade() is None
    finally:
        store.close()


def inner_app(client):
    application = client.app
    while not hasattr(application, "state"):
        application = application.app
    return application


def test_background_monitor_runs_without_queue_queries_and_does_not_replay(account):
    settings, _, workspace, registration = account
    settings = settings.model_copy(update={"automation_interval_seconds": 1})
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        _, result, _ = ready_run(client, workspace, registration, headers)
        notice = new_case(
            client,
            workspace,
            registration,
            headers,
            result,
            "NOTICE_REVIEW",
            {
                "notice_reference": "LOCAL",
                "notice_date": "2024-05-01",
                "response_due_date": "2024-05-20",
            },
        )
        service = inner_app(client).state.actions
        deadline = time.monotonic() + 6
        while True:
            with service.store.transaction(write=False) as connection:
                row = connection.execute(
                    "SELECT * FROM business_actions WHERE case_id=?", (notice["id"],)
                ).fetchone()
                if row is not None and row["reminded_at"] is not None:
                    recorded = dict(row)
                    count = connection.execute(
                        "SELECT count(*) FROM action_events WHERE action_id=?", (row["id"],)
                    ).fetchone()[0]
                    break
            assert time.monotonic() < deadline
            time.sleep(0.05)
        time.sleep(1.1)
        with service.store.transaction(write=False) as connection:
            assert (
                connection.execute(
                    "SELECT count(*) FROM action_events WHERE action_id=?", (recorded["id"],)
                ).fetchone()[0]
                == count
                == 2
            )
    with TestClient(create_app(settings)) as client:
        signed_in(client)
        tracked = action(client, workspace, "NOTICE_REVIEW", notice["id"])
        assert tracked["version"] == recorded["version"]
        assert len([e for e in tracked["timeline"] if e["kind"] == "REVIEW_DUE"]) == 1


def test_new_actions_stale_report_and_concurrent_commands_have_one_winner(account):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        run, result, _ = ready_run(client, workspace, registration, headers)
        report = artifact(client, workspace, headers, "RECONCILIATION_PDF", run)
        assert report["state"] == "READY", report
        case = new_case(client, workspace, registration, headers, result, "IRN_REVIEW", {})
        tracked = action(client, workspace, "IRN_REVIEW", case["id"])
        assert (
            get(client, workspace, f"artifacts/{report['id']}").json()["data"]["sources_current"]
            is False
        )
        payload = {
            "expected_version": tracked["version"],
            "reason": "Concurrent reviewer",
            "state": "OPEN",
        }
        with ThreadPoolExecutor(max_workers=2) as executor:
            replies = list(
                executor.map(
                    lambda _: post(
                        client, workspace, f"actions/{tracked['id']}/update", headers, payload
                    ),
                    range(2),
                )
            )
        assert sorted(r.status_code for r in replies) == [200, 409]
        updated = action(client, workspace, "IRN_REVIEW", case["id"])
        assert updated["version"] == tracked["version"] + 1
        assert len([e for e in updated["timeline"] if e["kind"] == "UPDATE"]) == 1
        bad = post(
            client,
            workspace,
            f"actions/{updated['id']}/update",
            headers,
            {
                "expected_version": updated["version"],
                "reason": "Invalid owner",
                "state": "OPEN",
                "assigned_to": str(uuid4()),
            },
        )
        assert bad.status_code == 422


def test_history_and_action_caps_surface_failure_without_corrupting_prior_phases(account):
    settings, _, workspace, registration = account
    settings = settings.model_copy(update={"max_actions_per_workspace": 1, "max_action_events": 5})
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        run, result, _ = ready_run(client, workspace, registration, headers)
        first = new_case(client, workspace, registration, headers, result, "IRN_REVIEW", {})
        tracked = action(client, workspace, "IRN_REVIEW", first["id"])
        new_case(client, workspace, registration, headers, result, "NOTICE_REVIEW", {})
        data = queue(client, workspace)
        assert data["automation"]["error_code"] == "ACTION_LIMIT"
        assert data["automation"]["pending_sources"] >= 1
        assert len(data["actions"]) == 1
        for _ in range(4):
            tracked = change(client, workspace, headers, tracked, "update", state="OPEN")
        response = post(
            client,
            workspace,
            f"actions/{tracked['id']}/update",
            headers,
            {
                "expected_version": tracked["version"],
                "reason": "At cap",
                "state": "REVIEW_REQUIRED",
            },
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "ACTION_HISTORY_LIMIT"
        assert action(client, workspace, "IRN_REVIEW", first["id"])["version"] == tracked["version"]
        assert get(client, workspace, f"runs/{run['id']}").json()["data"]["state"] == "COMPLETED"
        assert get(client, workspace, f"cases/{first['id']}").status_code == 200


def test_different_purchase_source_never_autolinks_reused_invoice_and_stale_action_denies_write(
    account,
):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        payload = prepare(
            client,
            workspace,
            registration,
            headers,
            purchases=[ROW],
            portals=[ROW | {"invoice_number": "OTHER-999"}],
        )
        finished(
            client, workspace, create(client, workspace, headers, payload).json()["data"]["id"]
        )
        old = action(client, workspace, "INVOICE_REVIEW")
        purchase = source(
            client,
            workspace,
            registration,
            headers,
            [ROW | {"invoice_date": "2024-05-02"}],
            "PURCHASE",
        )
        portal = source(
            client,
            workspace,
            registration,
            headers,
            [ROW | {"invoice_number": "OTHER-998"}],
            "PORTAL_2B",
            supersedes_import_id=payload["portal_import_id"],
        )
        second = {
            "registration_id": registration,
            "period": "2024-05",
            "purchase_import_id": purchase["id"],
            "portal_import_id": portal["id"],
        }
        finished(client, workspace, create(client, workspace, headers, second).json()["data"]["id"])
        rows = queue(client, workspace)["actions"]
        assert len(rows) == 2 and len({r["document_id"] for r in rows}) == 2
        old = next(r for r in rows if r["id"] == old["id"])
        assert old["sources_current"] is False
        denied = post(
            client,
            workspace,
            f"actions/{old['id']}/update",
            headers,
            {"expected_version": old["version"], "reason": "Stale", "state": "OPEN"},
        )
        assert denied.status_code == 409 and denied.json()["error"]["code"] == "ACTION_SOURCE_STALE"


def test_real_process_restart_backup_restore_retains_action_history_and_revokes_access(account):
    settings, _, workspace, registration = account
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    environment = os.environ.copy()
    environment.update(
        PORT=str(port),
        PUBLIC_API_URL=f"http://localhost:{port}",
        APP_ENV="test",
        READ_REQUESTS_PER_MINUTE="2000",
        MUTATION_REQUESTS_PER_MINUTE="100",
        IMPORT_REQUESTS_PER_MINUTE="50",
        AUTOMATION_INTERVAL_SECONDS="1",
    )
    with running_backend(port, environment) as client:
        headers = signed_in(client)
        _, result, _ = ready_run(client, workspace, registration, headers)
        case = new_case(client, workspace, registration, headers, result, "IRN_REVIEW", {})
        tracked = action(client, workspace, "IRN_REVIEW", case["id"])
        tracked = change(
            client, workspace, headers, tracked, "update", state="OPEN", review_on="2024-06-01"
        )
        tracked = action(client, workspace, "IRN_REVIEW", case["id"])
        tracked = change(
            client,
            workspace,
            headers,
            tracked,
            "followups",
            contact="supplier@example.com",
            request="Provide IRN evidence",
        )
        assert tracked["state"] == "OPEN"  # Draft alone cannot imply awaiting an actual response.
        token = client.cookies.get("gstshield_session")
    backup = maintenance(environment, "backup")
    assert backup.returncode == 0, backup.stderr
    identifier = backup.stdout.strip().removeprefix("Backup ID: ")
    with running_backend(port, environment) as client:
        client.cookies.set("gstshield_session", token, path="/api/v1")
        kept = action(client, workspace, "IRN_REVIEW", case["id"])
        assert kept == tracked
    restored = maintenance(environment, "restore", "--backup-id", identifier)
    assert restored.returncode == 0, restored.stderr
    with running_backend(port, environment) as client:
        client.cookies.set("gstshield_session", token, path="/api/v1")
        assert client.get("/api/v1/auth/session").status_code == 401
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    try:
        AccessService(store).reset_password("alice", PASSWORD)
    finally:
        store.close()
    with running_backend(port, environment) as client:
        signed_in(client)
        assert action(client, workspace, "IRN_REVIEW", case["id"]) == tracked


def test_due_batch_skips_stale_and_full_history_actions_instead_of_starving_current(account):
    settings, _, workspace, registration = account
    settings = settings.model_copy(update={"automation_due_batch": 1})
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        _, result, _ = ready_run(client, workspace, registration, headers)
        cases = [
            new_case(client, workspace, registration, headers, result, kind, {})
            for kind in ("IRN_REVIEW", "NOTICE_REVIEW", "RULE37_REVIEW")
        ]
        for case in cases:
            action(client, workspace, case["kind"], case["id"])
        service = inner_app(client).state.actions
        inner_app(client).state.action_monitor.close()
        with service.store.transaction() as connection:
            rows = connection.execute("SELECT * FROM business_actions ORDER BY id").fetchall()
            connection.execute("UPDATE business_actions SET due_at=?", (int(time.time()) - 1,))
            # Controlled storage faults are separate from the six API business journeys.
            connection.execute(
                "UPDATE cases SET version=version+1 WHERE id=?", (rows[0]["case_id"],)
            )
        service.settings = settings.model_copy(update={"max_action_events": 1})
        assert service.remind(workspace) == "ACTION_HISTORY_LIMIT"
        service.settings = settings.model_copy(update={"max_action_events": 2})
        assert service.remind(workspace) is None
        with service.store.transaction(write=False) as connection:
            counts = {
                r[0]: r[1]
                for r in connection.execute(
                    "SELECT action_id,count(*) FROM action_events WHERE kind='REVIEW_DUE' "
                    "GROUP BY action_id"
                )
            }
        assert rows[0]["id"] not in counts
        assert counts == {rows[1]["id"]: 1}
        assert service.remind(workspace) is None
        with service.store.transaction(write=False) as connection:
            assert (
                connection.execute(
                    "SELECT count(*) FROM action_events WHERE kind='REVIEW_DUE'"
                ).fetchone()[0]
                == 2
            )


def test_failed_source_rotates_pending_batch_and_leaves_independent_due_work_available(
    account, monkeypatch
):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        _, result, _ = ready_run(client, workspace, registration, headers)
        first = new_case(client, workspace, registration, headers, result, "IRN_REVIEW", {})
        second = new_case(client, workspace, registration, headers, result, "NOTICE_REVIEW", {})
        action(client, workspace, "IRN_REVIEW", first["id"])
        action(client, workspace, "NOTICE_REVIEW", second["id"])
        application = inner_app(client)
        application.state.action_monitor.close()
        service = application.state.actions
        service.settings = settings.model_copy(update={"automation_source_batch": 1})
        first = evidence(client, workspace, headers, first, "IRN_OBSERVATION", {"irn": "a" * 64})
        second = evidence(client, workspace, headers, second, "NOTE", {"notice_reference": "READY"})
        original = service.sync_case

        def fail_one(connection, row):
            if row["id"] == first["id"]:
                raise APIError(409, "TEST_SOURCE_FAILURE", "Synthetic fault")
            original(connection, row)

        monkeypatch.setattr(service, "sync_case", fail_one)
        for _ in range(3):
            service.refresh(workspace)
        with service.store.transaction(write=False) as connection:
            updated = connection.execute(
                "SELECT source_json FROM business_actions WHERE case_id=?", (second["id"],)
            ).fetchone()[0]
            assert "READY" in updated
            status = service.status(connection, workspace)
            assert status["error_code"] == "TEST_SOURCE_FAILURE" and status["pending_sources"] == 1
        monkeypatch.setattr(service, "sync_case", original)
        service.refresh(workspace)
        assert queue(client, workspace)["automation"]["error_code"] is None


def test_two_accounts_cannot_read_worksheets_or_use_another_actions_draft(account):
    settings, _, workspace, registration = account
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    try:
        AccessService(store).provision("bob", PASSWORD, "Other taxpayer")
    finally:
        store.close()
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        _, result, _ = ready_run(client, workspace, registration, headers)
        irn = new_case(client, workspace, registration, headers, result, "IRN_REVIEW", {})
        notice = new_case(client, workspace, registration, headers, result, "NOTICE_REVIEW", {})
        first = action(client, workspace, "IRN_REVIEW", irn["id"])
        first = change(
            client,
            workspace,
            headers,
            first,
            "followups",
            contact="supplier@example.com",
            request="Check evidence",
        )
        draft = first["timeline"][-1]["id"]
        second = action(client, workspace, "NOTICE_REVIEW", notice["id"])
        denied = post(
            client,
            workspace,
            f"actions/{second['id']}/followups",
            headers,
            {
                "expected_version": second["version"],
                "reason": "Forged",
                "kind": "ATTEMPT_RECORDED",
                "contact": "supplier@example.com",
                "request": "Check evidence",
                "draft_id": draft,
                "observed_on": "2024-06-01",
            },
        )
        assert denied.status_code == 422
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "bob", "password": PASSWORD},
            headers={"Origin": headers["Origin"]},
        )
        assert login.status_code == 200
        assert get(client, workspace, "actions").status_code == 404
        assert get(client, workspace, f"actions/{first['id']}/worksheet").status_code == 404


def test_incomplete_tax_case_keeps_unknown_review_action_without_automation_failure(account):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        payload = prepare(
            client, workspace, registration, headers, purchases=[ROW | {"cess": ""}], portals=[ROW]
        )
        run = finished(
            client, workspace, create(client, workspace, headers, payload).json()["data"]["id"]
        )
        assert run["state"] == "COMPLETED"
        result = get(client, workspace, f"runs/{run['id']}/results").json()["data"]["results"][0]
        case = new_case(
            client,
            workspace,
            registration,
            headers,
            result,
            "RULE37A_REVIEW",
            {
                "original_claim_period": "2024-04",
                "original_claim_amount": "180.00",
                "reversal_period": "2024-05",
                "reversal_amount": "180.00",
                "supplier_return_period": "2024-04",
                "supplier_return_status": "FILED",
                "filing_observed_on": "2024-06-01",
            },
        )
        tracked = action(client, workspace, "RULE37A_REVIEW", case["id"])
        assert tracked["source"]["recorded_tax"] is None
        assert not tracked["source"]["review"]["reclaim_candidate"]
        assert "recorded_tax_incomplete" in tracked["source"]["review"]["missing_facts"]
        assert queue(client, workspace)["automation"]["error_code"] is None


def test_competing_refresh_rechecks_checkpoint_after_writer_lock(account, monkeypatch):
    import threading

    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        run, _, _ = ready_run(client, workspace, registration, headers)
        application = inner_app(client)
        application.state.action_monitor.close()
        service = application.state.actions
        service.refresh(workspace)
        with service.store.transaction() as connection:
            connection.execute(
                "DELETE FROM action_checkpoints WHERE workspace_id=? AND kind='RUN'",
                (workspace,),
            )
            before = connection.execute("SELECT count(*) FROM action_events").fetchone()[0]
        original_pending, original_sync = service.pending, service.sync_run
        barrier, calls = threading.Barrier(2), []

        def pending(connection, scope):
            rows = original_pending(connection, scope)
            barrier.wait(timeout=5)
            return rows

        def sync(connection, row):
            calls.append(row["id"])
            time.sleep(0.05)
            original_sync(connection, row)

        # Provenance derivation must not perform the whole run-detail query per row.
        def unexpected_detail(*args):
            raise AssertionError("Action source does not need run-detail rendering.")

        monkeypatch.setattr(service, "pending", pending)
        monkeypatch.setattr(service, "sync_run", sync)
        monkeypatch.setattr(service.runs, "detail_row", unexpected_detail)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(service.refresh, workspace) for _ in range(2)]
            for future in futures:
                future.result(timeout=10)
        assert calls == [run["id"]]
        with service.store.transaction(write=False) as connection:
            checkpoint = connection.execute(
                "SELECT version,error_code FROM action_checkpoints "
                "WHERE workspace_id=? AND kind='RUN' AND source_id=?",
                (workspace, run["id"]),
            ).fetchone()
            assert checkpoint["version"] == run["version"] and checkpoint["error_code"] is None
            assert connection.execute("SELECT count(*) FROM action_events").fetchone()[0] == before
