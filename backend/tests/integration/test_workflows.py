"""HTTP phases 1–5 integration and security boundaries."""

import csv
import io
import time
from uuid import uuid4

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.main import create_app
from tests.integration.test_imports import account as account
from tests.integration.test_imports import signed_in
from tests.integration.test_runs import create, finished, prepare
from tests.unit.test_import_parsers import ROW


def post(client, workspace, path, headers, payload, key=None):
    return client.post(
        f"/api/v1/workspaces/{workspace}/{path}",
        json=payload,
        headers=headers | {"Idempotency-Key": key or str(uuid4())},
    )


def get(client, workspace, path):
    return client.get(f"/api/v1/workspaces/{workspace}/{path}")


def ready_run(client, workspace, registration, headers):
    payload = prepare(client, workspace, registration, headers, purchases=[ROW], portals=[ROW])
    response = create(client, workspace, headers, payload)
    assert response.status_code == 202, response.text
    run = finished(client, workspace, response.json()["data"]["id"])
    assert run["state"] == "COMPLETED", run
    result = get(client, workspace, f"runs/{run['id']}/results").json()["data"]["results"][0]
    return run, result, payload


def case_payload(registration, result):
    return {
        "registration_id": registration,
        "result_id": result["id"],
        "purchase_document_id": result["purchase_document_id"],
        "kind": "RULE37_REVIEW",
        "amount": "180.00",
        "facts": {"original_claim_period": "2024-04", "original_claim_amount": "180.00"},
    }


def transition(client, workspace, headers, case, state):
    response = post(
        client,
        workspace,
        f"cases/{case['id']}/transition",
        headers,
        {
            "expected_version": case["version"],
            "state": state,
            "reason": "Checked recorded synthetic evidence.",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def payment_case(client, workspace, registration, headers, result):
    response = post(client, workspace, "cases", headers, case_payload(registration, result))
    assert response.status_code == 201, response.text
    case = transition(client, workspace, headers, response.json()["data"], "EVIDENCE_REQUIRED")
    response = post(
        client,
        workspace,
        f"cases/{case['id']}/evidence",
        headers,
        {
            "expected_version": case["version"],
            "event_kind": "PAYMENT_OBSERVATION",
            "reason": "Recorded synthetic payment balance; not a bank confirmation.",
            "facts_patch": {"amount_paid": "180.00", "payment_observed_on": "2024-05-01"},
        },
    )
    assert response.status_code == 200, response.text
    return transition(client, workspace, headers, response.json()["data"], "REVIEW_READY")


def proposal_payload(run, result, case, amount="1000.00"):
    return {
        "run_id": run["id"],
        "expected_run_version": run["version"],
        "expected_result_versions": {result["id"]: result["version"]},
        "balance_observations": [
            {
                "document_id": result["purchase_document_id"],
                "evidence_case_id": case["id"],
                "expected_case_version": case["version"],
            }
        ],
        "allocations": [
            {
                "document_id": result["purchase_document_id"],
                "amount": amount,
                "purpose": "SUPPLIER_PROPOSED",
            }
        ],
    }


def artifact(client, workspace, headers, kind, source, **changes):
    response = post(
        client,
        workspace,
        "artifacts",
        headers,
        {"kind": kind, "source_id": source["id"], "expected_version": source["version"]} | changes,
    )
    assert response.status_code == 202, response.text
    identifier = response.json()["data"]["id"]
    deadline = time.monotonic() + 20
    while True:
        response = get(client, workspace, f"artifacts/{identifier}")
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        if data["state"] != "PENDING":
            return data
        assert time.monotonic() < deadline, data
        time.sleep(0.03)


def test_complete_flow_private_reports_and_proposals_do_not_pay(account, tmp_path):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        run, result, _ = ready_run(client, workspace, registration, headers)
        case = payment_case(client, workspace, registration, headers, result)
        assert not case["missing_facts"]
        response = post(
            client, workspace, "proposals", headers, proposal_payload(run, result, case)
        )
        assert response.status_code == 201, response.text
        proposal = response.json()["data"]
        assert (
            post(
                client,
                workspace,
                "artifacts",
                headers,
                {"kind": "PROPOSAL_CSV", "source_id": proposal["id"], "expected_version": 1},
            ).status_code
            == 409
        )
        response = post(
            client,
            workspace,
            f"proposals/{proposal['id']}/approve",
            headers,
            {"expected_version": 1, "reason": "Reviewed synthetic proposal only."},
        )
        assert response.status_code == 200, response.text
        proposal = response.json()["data"]
        for kind, source in [
            ("RECONCILIATION_PDF", run),
            ("EVIDENCE_PDF", case),
            ("PROPOSAL_CSV", proposal),
        ]:
            report = artifact(client, workspace, headers, kind, source)
            assert report["state"] == "READY", report
            download = get(client, workspace, f"artifacts/{report['id']}/download")
            assert download.status_code == 200, download.text
            assert download.headers["cache-control"] == "no-store"
            assert download.headers["content-disposition"].startswith(
                'attachment; filename="gstshield-'
            )
            assert download.headers["x-content-type-options"] == "nosniff"
            assert (
                get(client, str(uuid4()), f"artifacts/{report['id']}/download").status_code == 404
            )
            job = get(client, workspace, f"jobs/{report['job_id']}")
            assert job.status_code == 200 and job.json()["data"]["kind"] == "ARTIFACT"
            assert "lease" not in job.text
            if kind.endswith("_PDF"):
                (tmp_path / f"{kind}.pdf").write_bytes(download.content)
                text = "\n".join(
                    page.extract_text() for page in PdfReader(io.BytesIO(download.content)).pages
                )
                assert "human review" in text.lower() and "180.00" in text
            else:
                rows = list(csv.DictReader(io.StringIO(download.content.decode("utf-8-sig"))))
                assert rows[0]["instruction"] == "PROPOSAL_ONLY"
                assert rows[0]["remaining_balance"] == rows[0]["proposed_amount"] == "1000.00"
        assert (
            get(client, workspace, f"proposals/{proposal['id']}").json()["data"]["state"]
            == "EXPORTED"
        )
        assert (
            get(client, workspace, f"cases/{case['id']}").json()["data"]["facts"]["amount_paid"]
            == "180.00"
        )
        assert get(client, workspace, "cases").json()["data"]["cases"]
        assert get(client, workspace, "proposals").json()["data"]["proposals"]
        client.cookies.clear()
        assert get(client, workspace, f"artifacts/{report['id']}/download").status_code == 401


def test_case_versions_context_idempotency_and_reopen(account):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        _, result, _ = ready_run(client, workspace, registration, headers)
        key, payload = str(uuid4()), case_payload(registration, result)
        first = post(client, workspace, "cases", headers, payload, key)
        assert first.status_code == 201, first.text
        assert (
            post(client, workspace, "cases", headers, payload, key).json()["data"]
            == first.json()["data"]
        )
        assert (
            post(client, workspace, "cases", headers, payload | {"amount": "100"}, key).status_code
            == 409
        )
        case = transition(client, workspace, headers, first.json()["data"], "EVIDENCE_REQUIRED")
        assert (
            post(
                client,
                workspace,
                f"cases/{case['id']}/transition",
                headers,
                {
                    "expected_version": case["version"],
                    "state": "REVIEW_READY",
                    "reason": "Missing payment.",
                },
            ).status_code
            == 409
        )
        evidence = {"expected_version": 1, "event_kind": "NOTE", "reason": "Old browser version."}
        assert (
            post(client, workspace, f"cases/{case['id']}/evidence", headers, evidence).status_code
            == 409
        )
        evidence.update(
            expected_version=case["version"],
            event_kind="PAYMENT_OBSERVATION",
            facts_patch={"amount_paid": "1180.01", "payment_observed_on": "2024-05-01"},
        )
        assert (
            post(client, workspace, f"cases/{case['id']}/evidence", headers, evidence).status_code
            == 422
        )
        evidence["facts_patch"]["amount_paid"] = "0.00"
        response = post(client, workspace, f"cases/{case['id']}/evidence", headers, evidence)
        assert response.status_code == 200, response.text
        case = transition(client, workspace, headers, response.json()["data"], "REVIEW_READY")
        case = transition(client, workspace, headers, case, "CLOSED")
        evidence.update(expected_version=case["version"])
        assert (
            post(client, workspace, f"cases/{case['id']}/evidence", headers, evidence).status_code
            == 409
        )
        assert transition(client, workspace, headers, case, "OPEN")["state"] == "OPEN"
        assert (
            post(
                client,
                workspace,
                "cases",
                headers,
                payload | {"purchase_document_id": str(uuid4())},
            ).status_code
            == 422
        )


def test_changed_case_stales_proposal_and_pdf_history_is_explicit(account):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        run, result, _ = ready_run(client, workspace, registration, headers)
        case = payment_case(client, workspace, registration, headers, result)
        assert (
            post(
                client,
                workspace,
                "proposals",
                headers,
                proposal_payload(run, result, case, "1000.01"),
            ).status_code
            == 422
        )
        response = post(
            client, workspace, "proposals", headers, proposal_payload(run, result, case)
        )
        assert response.status_code == 201, response.text
        proposal = response.json()["data"]
        report = artifact(client, workspace, headers, "EVIDENCE_PDF", case)
        assert report["state"] == "READY", report
        response = post(
            client,
            workspace,
            f"cases/{case['id']}/evidence",
            headers,
            {
                "expected_version": case["version"],
                "event_kind": "NOTE",
                "reason": "Changed balance needs a new payment observation.",
                "facts_patch": {"amount_paid": "200.00"},
            },
        )
        assert response.status_code == 200, response.text
        changed = response.json()["data"]
        assert changed["state"] == "EVIDENCE_REQUIRED"
        assert "evidence:PAYMENT_OBSERVATION" in changed["missing_facts"]
        assert (
            get(client, workspace, f"proposals/{proposal['id']}").json()["data"]["state"] == "STALE"
        )
        assert (
            post(
                client,
                workspace,
                f"proposals/{proposal['id']}/approve",
                headers,
                {"expected_version": 1, "reason": "Outdated draft."},
            ).status_code
            == 409
        )
        assert get(client, workspace, f"artifacts/{report['id']}/download").status_code == 409
        historical = get(client, workspace, f"artifacts/{report['id']}/download?historical=true")
        assert (
            historical.status_code == 200 and historical.headers["x-gstshield-historical"] == "true"
        )


def test_expiry_cleanup_preserves_sources_and_owner_role(account):
    settings, user, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        run, _, payload = ready_run(client, workspace, registration, headers)
        report = artifact(client, workspace, headers, "RECONCILIATION_PDF", run)
        assert report["state"] == "READY", report
        state = client.app.app.app.state
        with state.store.transaction() as conn:
            conn.execute(
                "UPDATE artifacts SET expires_at=? WHERE id=?", (int(time.time()) - 1, report["id"])
            )
        assert (
            get(client, workspace, f"artifacts/{report['id']}").json()["data"]["state"] == "EXPIRED"
        )
        assert get(client, workspace, f"artifacts/{report['id']}/download").status_code == 410
        response = post(client, workspace, "artifacts/cleanup", headers, {})
        assert response.status_code == 200 and response.json()["data"]["expired_artifacts"] == 1
        with state.store.transaction() as conn:
            row = conn.execute(
                "SELECT state,content,sha256 FROM artifacts WHERE id=?", (report["id"],)
            ).fetchone()
            assert row["state"] == "EXPIRED" and row["content"] is None and row["sha256"]
            assert (
                conn.execute(
                    "SELECT count(*) FROM import_rows WHERE import_id=?",
                    (payload["purchase_import_id"],),
                ).fetchone()[0]
                == 1
            )
            conn.execute("UPDATE memberships SET role='REVIEWER' WHERE user_id=?", (user,))
        assert post(client, workspace, "artifacts/cleanup", headers, {}).status_code == 403
        with state.store.transaction() as conn:
            conn.execute("UPDATE memberships SET role='VIEWER' WHERE user_id=?", (user,))
        assert (
            post(
                client,
                workspace,
                "artifacts",
                headers,
                {
                    "kind": "RECONCILIATION_PDF",
                    "source_id": run["id"],
                    "expected_version": run["version"],
                },
            ).status_code
            == 403
        )
        assert get(client, workspace, f"artifacts/{report['id']}").status_code == 200


def test_report_retries_interruption_leases_and_corruption(account):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        run, _, _ = ready_run(client, workspace, registration, headers)
        state = client.app.app.app.state
        state.dispatcher.close()
        payload = {
            "kind": "RECONCILIATION_PDF",
            "source_id": run["id"],
            "expected_version": run["version"],
        }
        key = str(uuid4())
        first = post(client, workspace, "artifacts", headers, payload, key)
        assert first.status_code == 202, first.text
        report = first.json()["data"]
        assert post(client, workspace, "artifacts", headers, payload, key).json()["data"] == report
        assert (
            post(client, workspace, "artifacts", headers, payload).json()["data"]["id"]
            == report["id"]
        )
        assert (
            post(
                client, workspace, "artifacts", headers, payload | {"expected_version": 999}, key
            ).status_code
            == 409
        )
        claimed = state.dispatcher.claim()
        assert claimed["job_kind"] == "ARTIFACT"
        # Old/foreign lease must not publish.
        state.reports.publish(claimed | {"lease": str(uuid4())}, {"error_code": "WRONG_LEASE"})
        assert (
            get(client, workspace, f"artifacts/{report['id']}").json()["data"]["state"] == "PENDING"
        )
        state.reports.publish(claimed, {"content": "not base64", "sha256": "0" * 64})
        invalid = get(client, workspace, f"artifacts/{report['id']}").json()["data"]
        assert invalid["state"] == "FAILED" and invalid["error_code"] == "ARTIFACT_INVALID"
        report = post(client, workspace, "artifacts", headers, payload).json()["data"]
        state.dispatcher.claim()
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        interrupted = get(client, workspace, f"artifacts/{report['id']}").json()["data"]
        assert (
            interrupted["state"] == "FAILED"
            and interrupted["error_code"] == "PROCESSING_INTERRUPTED"
        )
        retry = artifact(client, workspace, headers, "RECONCILIATION_PDF", run)
        assert retry["id"] != report["id"] and retry["state"] == "READY"
        state = client.app.app.app.state
        with state.store.transaction() as conn:
            conn.execute("UPDATE artifacts SET sha256=? WHERE id=?", ("0" * 64, retry["id"]))
        assert get(client, workspace, f"artifacts/{retry['id']}/download").status_code == 503
        assert "snapshot_json" not in get(client, workspace, f"artifacts/{retry['id']}").text


def test_review_changes_report_totals_and_blocks_old_proposal_csv(account):
    from tests.integration.test_runs import details, review

    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        run, result, _ = ready_run(client, workspace, registration, headers)
        case = payment_case(client, workspace, registration, headers, result)
        proposal = post(
            client, workspace, "proposals", headers, proposal_payload(run, result, case)
        ).json()["data"]
        approved = post(
            client,
            workspace,
            f"proposals/{proposal['id']}/approve",
            headers,
            {"expected_version": 1, "reason": "Reviewed before later source change."},
        ).json()["data"]
        csv_report = artifact(client, workspace, headers, "PROPOSAL_CSV", approved)
        old_pdf = artifact(client, workspace, headers, "RECONCILIATION_PDF", run)
        assert old_pdf["state"] == csv_report["state"] == "READY"
        result = details(client, workspace, result["id"])
        changed = review(client, workspace, result, headers, action="REJECT_MATCH")
        assert changed.status_code == 200, changed.text
        assert (
            get(
                client, workspace, f"artifacts/{csv_report['id']}/download?historical=true"
            ).status_code
            == 409
        )
        assert get(client, workspace, f"artifacts/{old_pdf['id']}/download").status_code == 409
        run = get(client, workspace, f"runs/{run['id']}").json()["data"]
        assert run["summary"]["tax_exposure_review"] == "180.00"
        new_pdf = artifact(client, workspace, headers, "RECONCILIATION_PDF", run)
        assert new_pdf["state"] == "READY", new_pdf
        content = get(client, workspace, f"artifacts/{new_pdf['id']}/download").content
        text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(content)).pages)
        assert "REJECTED" in text and "tax_exposure_review: 180.00" in text


def test_row_errors_csv_and_unsupported_pdf_text_fail_safely(account):
    from tests.integration.test_imports import completed, upload
    from tests.unit.test_import_parsers import csv_content

    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        # One rejected row retains its formula-like source text for safe export.
        content = csv_content(
            [
                ROW,
                ROW
                | {
                    "voucher_id": "V2",
                    "invoice_number": '=HYPERLINK("bad")',
                    "gross_total": "oops",
                },
            ]
        )
        response = upload(client, workspace, registration, headers, content=content)
        assert response.status_code == 202, response.text
        imported = completed(client, workspace, response.json()["data"]["id"])
        report = artifact(client, workspace, headers, "ROW_ERRORS_CSV", imported)
        assert report["state"] == "READY", report
        rows = list(
            csv.DictReader(
                io.StringIO(
                    get(client, workspace, f"artifacts/{report['id']}/download").content.decode(
                        "utf-8-sig"
                    )
                )
            )
        )
        assert len(rows) == 1 and rows[0]["invoice_number"].startswith("'=")
        run, result, _ = ready_run(client, workspace, registration, headers)
        case = post(client, workspace, "cases", headers, case_payload(registration, result)).json()[
            "data"
        ]
        changed = post(
            client,
            workspace,
            f"cases/{case['id']}/evidence",
            headers,
            {"expected_version": 1, "event_kind": "NOTE", "reason": "Unsupported glyph 😀"},
        ).json()["data"]
        failed = artifact(client, workspace, headers, "EVIDENCE_PDF", changed)
        assert failed["state"] == "FAILED" and failed["error_code"] == "REPORT_UNSUPPORTED_TEXT"
        assert get(client, workspace, f"artifacts/{failed['id']}/download").status_code == 409


def test_report_bytes_case_and_proposal_survive_real_restart_and_backup_restore(account):
    import os
    import socket

    from app.config import Settings
    from app.services.access import AccessService
    from app.storage.local import LocalStore
    from tests.integration.test_imports import PASSWORD
    from tests.integration.test_restart import maintenance, running_backend

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
        run, result, _ = ready_run(client, workspace, registration, headers)
        case = payment_case(client, workspace, registration, headers, result)
        proposal = post(
            client, workspace, "proposals", headers, proposal_payload(run, result, case)
        ).json()["data"]
        report = artifact(client, workspace, headers, "EVIDENCE_PDF", case)
        assert report["state"] == "READY", report
        saved_bytes = get(client, workspace, f"artifacts/{report['id']}/download").content
        token = client.cookies.get("gstshield_session")
    backup = maintenance(environment, "backup")
    assert backup.returncode == 0, backup.stderr
    identifier = backup.stdout.strip().removeprefix("Backup ID: ")
    with running_backend(port, environment) as client:
        client.cookies.set("gstshield_session", token, path="/api/v1")
        assert get(client, workspace, f"artifacts/{report['id']}/download").content == saved_bytes
        assert get(client, workspace, f"cases/{case['id']}").json()["data"] == case
        assert get(client, workspace, f"proposals/{proposal['id']}").json()["data"] == proposal
    restored = maintenance(environment, "restore", "--backup-id", identifier)
    assert restored.returncode == 0, restored.stderr
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    try:
        AccessService(store).reset_password("alice", PASSWORD)
    finally:
        store.close()
    with running_backend(port, environment) as client:
        client.cookies.set("gstshield_session", token, path="/api/v1")
        assert get(client, workspace, f"artifacts/{report['id']}/download").status_code == 401
        client.cookies.clear()
        signed_in(client, origin)
        downloaded = get(client, workspace, f"artifacts/{report['id']}/download")
        assert downloaded.status_code == 200, downloaded.text
        assert downloaded.content == saved_bytes
        assert get(client, workspace, f"cases/{case['id']}").json()["data"] == case


def test_all_case_kinds_require_their_observations_and_irn_is_format_only(account):
    settings, _, workspace, registration = account
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        _, result, sources = ready_run(client, workspace, registration, headers)
        scenarios = [
            (
                "MSME_REVIEW",
                {
                    "supplier_classification": "MICRO",
                    "acceptance_date": "2024-04-10",
                    "agreed_credit_days": 30,
                    "amount_paid": "0.00",
                    "payment_observed_on": "2024-05-01",
                },
                ["ACCEPTANCE_OBSERVATION", "PAYMENT_OBSERVATION"],
            ),
            (
                "RULE37A_REVIEW",
                {
                    "original_claim_period": "2024-04",
                    "original_claim_amount": "180.00",
                    "reversal_period": "2024-05",
                    "reversal_amount": "180.00",
                    "supplier_return_period": "2024-04",
                    "supplier_return_status": "FILED",
                    "filing_observed_on": "2024-05-01",
                },
                ["FILING_OBSERVATION"],
            ),
            ("IRN_REVIEW", {"irn": "a" * 64, "applicability": "APPLIES"}, ["IRN_OBSERVATION"]),
            (
                "NOTICE_REVIEW",
                {
                    "notice_reference": "SAMPLE-1",
                    "notice_date": "2024-05-01",
                    "response_due_date": "2024-05-15",
                },
                ["DOCUMENT"],
            ),
        ]
        for kind, facts, kinds in scenarios:
            response = post(
                client,
                workspace,
                "cases",
                headers,
                case_payload(registration, result) | {"kind": kind, "facts": facts},
            )
            assert response.status_code == 201, response.text
            case = transition(
                client, workspace, headers, response.json()["data"], "EVIDENCE_REQUIRED"
            )
            for event_kind in kinds:
                evidence = {
                    "expected_version": case["version"],
                    "event_kind": event_kind,
                    "reason": "Recorded demonstration observation.",
                }
                if event_kind == "DOCUMENT":
                    evidence["import_id"] = sources["purchase_import_id"]
                response = post(
                    client, workspace, f"cases/{case['id']}/evidence", headers, evidence
                )
                assert response.status_code == 200, response.text
                case = response.json()["data"]
            ready = transition(client, workspace, headers, case, "REVIEW_READY")
            assert not ready["missing_facts"]
            if kind == "IRN_REVIEW":
                assert ready["irn_observation"] == "FORMAT_ONLY"
            if kind == "NOTICE_REVIEW":
                attached = [event for event in ready["timeline"] if event["kind"] == "DOCUMENT"][0]
                assert len(attached["evidence_source"]["file_sha256"]) == 64
                assert attached["evidence_source"]["id"] == sources["purchase_import_id"]


def test_workspace_scope_atomic_failure_and_shared_queue_limit(account, monkeypatch):
    from app.errors import APIError

    settings, _, workspace, registration = account
    settings = settings.model_copy(update={"max_queued_jobs_per_workspace": 1})
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        run, result, _ = ready_run(client, workspace, registration, headers)
        state = client.app.app.app.state
        _, other_workspace = state.access.provision(
            "bob", "synthetic-passphrase-only", "Other scope"
        )
        assert (
            post(
                client, other_workspace, "cases", headers, case_payload(registration, result)
            ).status_code
            == 404
        )
        old_event = state.cases.event

        def failed_event(*args, **kwargs):
            raise APIError(409, "AUDIT_FAILURE_TEST", "Synthetic failure before commit.")

        monkeypatch.setattr(state.cases, "event", failed_event)
        assert (
            post(
                client, workspace, "cases", headers, case_payload(registration, result)
            ).status_code
            == 409
        )
        assert get(client, workspace, "cases").json()["data"]["cases"] == []
        monkeypatch.setattr(state.cases, "event", old_event)
        created = post(client, workspace, "cases", headers, case_payload(registration, result))
        assert created.status_code == 201, created.text
        case = created.json()["data"]
        state.dispatcher.close()
        queued = post(
            client,
            workspace,
            "artifacts",
            headers,
            {"kind": "EVIDENCE_PDF", "source_id": case["id"], "expected_version": case["version"]},
        )
        assert queued.status_code == 202, queued.text
        blocked = post(
            client,
            workspace,
            "artifacts",
            headers,
            {
                "kind": "RECONCILIATION_PDF",
                "source_id": run["id"],
                "expected_version": run["version"],
            },
        )
        assert blocked.status_code == 429
        with state.store.transaction(write=False) as conn:
            assert conn.execute("SELECT count(*) FROM artifacts").fetchone()[0] == 1
        assert (
            get(client, other_workspace, f"artifacts/{queued.json()['data']['id']}").status_code
            == 404
        )
