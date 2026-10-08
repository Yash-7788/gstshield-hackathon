"""Cross-pillar invoice correction, two reviewers and stale completion safeguards."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.adapters import gemini
from app.main import create_app
from tests.integration.test_imports import account as account
from tests.integration.test_imports import signed_in
from tests.integration.test_passports import FIELDS
from tests.integration.test_runs import finished


def test_cross_pillar_process_and_evidence_reopening(account, monkeypatch):
    settings, _, ws, rid = account
    monkeypatch.setattr(
        gemini, "extract", lambda *_: FIELDS | {"uncertainties": [], "evidence_quotes": {}}
    )
    app = create_app(settings)
    with TestClient(app) as client:
        app.app.app.state.action_monitor.close()
        h = signed_in(client)
        root = f"/api/v1/workspaces/{ws}"
        product = root + "/product"
        base = root + "/passports"

        def command(url, payload, key=None, headers=None, actor=None):
            res = (actor or client).post(
                url, json=payload, headers=(headers or h) | {"Idempotency-Key": key or str(uuid4())}
            )
            assert res.status_code == 200, res.text
            return res.json()["data"]

        uploaded = client.post(
            base + "/documents",
            data={"registration_id": rid, "period": "2024-05", "consent": "true"},
            files={"file": ("invoice.pdf", b"%PDF-1.7 synthetic test")},
            headers=h | {"Idempotency-Key": str(uuid4())},
        )
        assert uploaded.status_code == 200, uploaded.text
        invoice = uploaded.json()["data"]
        pid = invoice["id"]

        def invoice_command(suffix, payload):
            return command(base + "/" + pid + "/" + suffix, payload)

        invoice = invoice_command(
            "confirm", {"expected_version": invoice["version"], "fields": FIELDS}
        )
        for kind in ["PO", "RECEIPT"]:
            invoice = invoice_command(
                "evidence",
                {
                    "expected_version": invoice["version"],
                    "kind": kind,
                    "reference": kind + "-ACTUAL",
                    "taxable_value": "100000.00",
                    "quantity": "10",
                    "items": FIELDS["items"],
                    "observed_on": "2024-05-10",
                },
            )
        invoice = invoice_command(
            "simulate-fetch", {"expected_version": invoice["version"], "status": "MISSING"}
        )
        invoice = invoice_command(
            "clocks",
            {
                "expected_version": invoice["version"],
                "msme_covered": False,
                "amount_paid": "0.00",
                "payment_observed_on": "2024-05-10",
            },
        )
        for role in ["CFO", "CMA", "CMO", "CA", "CEO", "COO", "CTO"]:
            reply = client.post(
                product + "/assistants/" + role,
                json={
                    "registration_id": rid,
                    "period": "2024-05",
                    "question": "What needs attention?",
                    "use_ai": False,
                },
                headers=h,
            )
            assert reply.status_code == (200 if role == "CA" else 403)
            if role == "CA":
                assert reply.json()["data"]["provider"] == "SAVED_FACTS"
        trap = client.get(product + "/invoices/" + pid + "/traps").json()["data"]
        assert len(trap["traps"]) == 6
        facts_payload = {
            "expected_version": 0,
            "source_signature": invoice["source_signature"],
            "credit_claimed": False,
            "note": "No original credit claim or notice has been reported.",
        }
        key = str(uuid4())
        facts = command(product + "/invoices/" + pid + "/review-facts", facts_payload, key)
        assert command(product + "/invoices/" + pid + "/review-facts", facts_payload, key) == facts
        process = command(product + "/workflows", {"passport_id": pid})
        batch_res = client.post(
            root + "/runs",
            json={
                "registration_id": rid,
                "period": "2024-05",
                "purchase_import_id": invoice["purchase_import_id"],
                "portal_import_id": invoice["findings"]["gst_source"]["id"],
            },
            headers=h | {"Idempotency-Key": str(uuid4())},
        )
        assert batch_res.status_code == 202, batch_res.text
        batch = finished(client, ws, batch_res.json()["data"]["id"])
        batch_process = command(product + "/workflows", {"batch_id": batch["id"]})
        assert batch_process["coverage_complete"] and batch_process["invoice_ids"] == [pid]

        def advance(index):
            nonlocal process
            process = client.get(product + "/workflows/" + process["id"]).json()["data"]
            node = process["nodes"][index]
            if node["state"] == "DONE":
                return
            process = command(
                product + "/nodes/" + node["id"] + "/transition",
                {
                    "expected_version": node["version"],
                    "fingerprint": process["fingerprint"],
                    "state": "DONE",
                    "note": "Reviewed the saved evidence and required next action.",
                },
            )

        final = process["nodes"][-1]
        denied = client.post(
            product + "/nodes/" + final["id"] + "/transition",
            json={
                "expected_version": final["version"],
                "fingerprint": process["fingerprint"],
                "state": "DONE",
                "note": "Cannot skip prerequisites.",
            },
            headers=h | {"Idempotency-Key": str(uuid4())},
        )
        assert denied.status_code == 409
        for i in range(5):
            advance(i)
        access = app.app.app.state.access
        access.provision("process-owner", "synthetic-owner-password", "Owner setup")
        access.grant("process-owner", ws, "OWNER")
        owner_client = TestClient(app)
        owner_login = owner_client.post(
            "/api/v1/auth/login",
            json={"username": "process-owner", "password": "synthetic-owner-password"},
            headers={"Origin": "http://localhost:3000"},
        )
        owner_headers = {
            "Origin": "http://localhost:3000",
            "X-CSRF-Token": owner_login.json()["data"]["csrf_token"],
        }
        users = []
        for i in [1, 2]:
            users.append(
                command(
                    product + "/team/members",
                    {
                        "username": f"processca{i}",
                        "display_name": f"Reviewer {i}",
                        "password": "synthetic-ca-password",
                        "roles": ["CA"],
                    },
                    headers=owner_headers,
                    actor=owner_client,
                )
            )
        second_ca = TestClient(app)
        second_login = second_ca.post(
            "/api/v1/auth/login",
            json={"username": "processca2", "password": "synthetic-ca-password"},
            headers={"Origin": "http://localhost:3000"},
        )
        second_headers = {
            "Origin": "http://localhost:3000",
            "X-CSRF-Token": second_login.json()["data"]["csrf_token"],
        }
        command(
            product + "/contributions",
            {
                "registration_id": rid,
                "period": "2024-05",
                "role": "CA",
                "note": "Second CA checked the statement and shared the missing supplier record.",
            },
            headers=second_headers,
            actor=second_ca,
        )
        assert (
            second_ca.get(product + "/workflows/" + process["id"]).json()["data"]["nodes"][4][
                "state"
            ]
            == "DONE"
        )
        ca_client = TestClient(app)
        ca_login = ca_client.post(
            "/api/v1/auth/login",
            json={"username": "processca1", "password": "synthetic-ca-password"},
            headers={"Origin": "http://localhost:3000"},
        )
        cah = {
            "Origin": "http://localhost:3000",
            "X-CSRF-Token": ca_login.json()["data"]["csrf_token"],
        }
        assert ca_client.get(product + "/workflows/" + process["id"]).status_code == 200
        denied_role = ca_client.post(
            product + "/assistants/CMO",
            json={
                "registration_id": rid,
                "period": "2024-05",
                "question": "Unapproved marketing scope",
                "use_ai": False,
            },
            headers=cah,
        )
        assert denied_role.status_code == 403
        node = process["nodes"][5]
        process = command(
            product + "/nodes/" + node["id"] + "/assign",
            {
                "expected_version": node["version"],
                "user_id": users[0]["id"],
                "due_on": "2024-06-01",
                "note": "Review the controlled payment with current evidence.",
            },
        )
        assigned_view = ca_client.get(product + "/workflows/" + process["id"]).json()["data"]
        other_view = second_ca.get(product + "/workflows/" + process["id"]).json()["data"]
        assert assigned_view["nodes"][5]["can_update"] is True
        assert other_view["nodes"][5]["can_update"] is False
        assert assigned_view["nodes"][5]["assignment_roles"] == ["CA", "CFO"]
        assert assigned_view["nodes"][5]["can_assign"] is True
        assert ca_client.get(product + "/notifications").json()["data"]["notifications"]
        invoice = invoice_command(
            "approve",
            {
                "expected_version": invoice["version"],
                "source_signature": invoice["source_signature"],
                "decision": "PARTIAL_CONTROLLED_PAYMENT",
                "amount": "100000.00",
                "reason": "Goods checked, missing supplier tax record retained for review.",
            },
        )
        process = client.get(product + "/workflows/" + process["id"]).json()["data"]
        assert process["nodes"][5]["state"] == "DONE"
        assert any(e["kind"] == "EVIDENCE_STEP_COMPLETED" for e in process["events"])
        invoice = invoice_command(
            "resolution", {"expected_version": invoice["version"], "action": "DRAFT"}
        )
        invoice = invoice_command(
            "resolution", {"expected_version": invoice["version"], "action": "ACKNOWLEDGED"}
        )
        advance(6)
        blocked = process["nodes"][7]
        denied = client.post(
            product + "/nodes/" + blocked["id"] + "/transition",
            json={
                "expected_version": blocked["version"],
                "fingerprint": process["fingerprint"],
                "state": "DONE",
                "note": "Supplier promise is not corrected GST evidence.",
            },
            headers=h | {"Idempotency-Key": str(uuid4())},
        )
        assert denied.status_code == 409
        old_signature = process["fingerprint"]
        invoice = invoice_command(
            "simulate-fetch", {"expected_version": invoice["version"], "status": "MATCHED"}
        )
        assert invoice["approval"]["state"] == "STALE"
        process = command(product + "/workflows/" + process["id"] + "/refresh", {})
        assert process["nodes"][4]["state"] == "STALE" and process["fingerprint"] != old_signature
        assert (
            client.get(product + "/invoices/" + pid + "/review-facts").json()["data"]["state"]
            == "STALE"
        )
        invoice = invoice_command(
            "approve",
            {
                "expected_version": invoice["version"],
                "source_signature": invoice["source_signature"],
                "decision": "PAY",
                "amount": "118000.00",
                "reason": "Corrected current statement aligns. Review complete.",
            },
        )
        tax = client.get(product + "/invoices/" + pid + "/tax-suggestions").json()["data"]
        for suggestion in tax["suggestions"]:
            command(
                product + "/tax-suggestions/review",
                {
                    "passport_id": pid,
                    "suggestion_id": suggestion["id"],
                    "fingerprint": tax["fingerprint"],
                    "conclusion": "NOT_APPLICABLE",
                    ("note"): (
                        "Synthetic demonstration reviewed; no original"
                        " claim or notice evidence supplied."
                    ),
                },
            )
        for i in range(3, 10):
            advance(i)
        assert process["state"] == "PROCESS_COMPLETED"
        receipt_key = str(uuid4())
        replayed = command(product + "/workflows", {"passport_id": pid}, receipt_key)
        assert replayed["state"] == "PROCESS_COMPLETED"

        assert len([e for e in process["events"] if e["kind"] == "PROCESS_COMPLETED"]) == 1
        invoice = invoice_command(
            "details",
            {
                "expected_version": invoice["version"],
                "items": FIELDS["items"],
                "supplier_bank_account": "CHANGEDACCOUNT",
                "irn_required": True,
                "payment_dispute": False,
            },
        )
        app.app.app.state.processes.scan(ws)
        process = client.get(product + "/workflows/" + process["id"]).json()["data"]
        assert process["state"] == "IN_PROGRESS" and any(
            n["state"] == "STALE" for n in process["nodes"]
        )
        assert any(e["kind"] == "PROCESS_REOPENED" for e in process["events"])
        assert (
            client.get(
                f"/api/v1/workspaces/{uuid4()}/product/workflows/" + process["id"]
            ).status_code
            == 404
        )
        replayed = command(product + "/workflows", {"passport_id": pid}, receipt_key)
        assert replayed["state"] == "IN_PROGRESS"
        assert (
            second_ca.get(product + "/workflows/" + process["id"]).json()["data"]["state"]
            == "IN_PROGRESS"
        )
        ca_client.close()
        second_ca.close()
        owner_client.close()
