"""Connected invoice-to-payment demo, scope denials and source-change invalidation."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.adapters import gemini
from app.errors import APIError
from app.main import create_app
from tests.integration.test_imports import account as account
from tests.integration.test_imports import signed_in
from tests.integration.test_runs import source

FIELDS = {
    "supplier_gstin": "27PQRSX5678L1Z2",
    "supplier_name": "Demo Supplier",
    "invoice_number": "DEMO-18000",
    "invoice_date": "2024-05-10",
    "taxable_value": "100000.00",
    "igst": "0.00",
    "cgst": "9000.00",
    "sgst": "9000.00",
    "cess": "0.00",
    "other_charges": "0.00",
    "round_off": "0.00",
    "gross_total": "118000.00",
    "irn": "",
    "quantity": "10",
    "items": [
        {
            "description": "Industrial pumps",
            "sku": "PUMP-01",
            "unit": "pieces",
            "quantity": "10",
            "taxable_value": "100000.00",
        }
    ],
}


def test_connected_demo_all_tools_and_saved_source_change(account, monkeypatch):
    settings, _, ws, rid = account
    monkeypatch.setattr(
        gemini, "extract", lambda *_: FIELDS | {"uncertainties": [], "evidence_quotes": {}}
    )
    app = create_app(settings)
    with TestClient(app) as client:
        # Advance background scans explicitly so expected versions cannot race the timer.
        app.app.app.state.action_monitor.close()
        headers = signed_in(client)
        base = f"/api/v1/workspaces/{ws}/passports"
        uploaded = client.post(
            base + "/documents",
            data={"registration_id": rid, "period": "2024-05", "consent": "true"},
            files={"file": ("invoice.pdf", b"%PDF-1.7 synthetic test fixture")},
            headers=headers | {"Idempotency-Key": str(uuid4())},
        )
        assert uploaded.status_code == 200, uploaded.text
        invoice = uploaded.json()["data"]
        assert invoice["extraction"]["status"] == "AWAITING_REVIEW"
        pid = invoice["id"]
        command_key = str(uuid4())

        def post(suffix, payload, key=None):
            response = client.post(
                base + "/" + pid + "/" + suffix,
                json=payload,
                headers=headers | {"Idempotency-Key": key or str(uuid4())},
            )
            assert response.status_code == 200, response.text
            return response.json()["data"]

        invoice = post(
            "confirm", {"expected_version": invoice["version"], "fields": FIELDS}, command_key
        )
        # Reviewed OCR creates a normal purchase source, available to earlier workflows.
        purchase = client.get(
            f"/api/v1/workspaces/{ws}/imports/{invoice['purchase_import_id']}"
        ).json()["data"]
        assert purchase["state"] == "READY" and purchase["accepted_rows"] == 1
        replay = post("confirm", {"expected_version": 2, "fields": FIELDS}, command_key)
        assert replay["id"] == pid
        for kind in ("PO", "RECEIPT"):
            invoice = post(
                "evidence",
                {
                    "expected_version": invoice["version"],
                    "kind": kind,
                    "reference": kind + "-001",
                    "taxable_value": "100000.00",
                    "quantity": "10",
                    "items": FIELDS["items"],
                    "observed_on": "2024-05-10",
                },
            )
        invoice = post(
            "simulate-fetch", {"expected_version": invoice["version"], "status": "MISSING"}
        )
        assert invoice["findings"]["gst"] == "MISSING"
        assert invoice["gate"]["recorded_tax_under_review"] == "18000.00"
        assert invoice["gate"]["recommendation"] == "PARTIAL_CONTROLLED_PAYMENT"
        invoice = post(
            "clocks",
            {
                "expected_version": invoice["version"],
                "msme_covered": True,
                "accepted_on": "2024-05-10",
                "agreed_days": 30,
                "claimed_on": "2024-05-20",
                "supplier_3b_due_on": "2024-06-20",
                "amount_paid": "0.00",
            },
        )
        assert invoice["clocks"]["pay_by"] == "2024-06-09"
        assert invoice["gate"]["recommendation"] == "ESCALATE"
        denied = client.post(
            base + "/" + pid + "/approve",
            json={
                "expected_version": invoice["version"],
                "source_signature": invoice["source_signature"],
                "decision": "PAY",
                "amount": "118000.00",
                "reason": "Cannot pay missing GST.",
            },
            headers=headers | {"Idempotency-Key": str(uuid4())},
        )
        assert denied.status_code == 409
        invoice = post(
            "approve",
            {
                "expected_version": invoice["version"],
                "source_signature": invoice["source_signature"],
                "decision": "PARTIAL_CONTROLLED_PAYMENT",
                "amount": "100000.00",
                "reason": "Order and delivery checked; supplier correction requested.",
            },
        )
        assert invoice["approval"]["state"] == "APPROVED"
        invoice = post("resolution", {"expected_version": invoice["version"], "action": "DRAFT"})
        assert invoice["resolution"]["delivery"] == "NOT_SENT"
        assert "DEMO-18000" in invoice["resolution"]["draft"]
        invoice = post("watch", {"expected_version": invoice["version"], "enabled": True})
        row = {k: v for k, v in FIELDS.items() if k not in {"quantity", "irn"}} | {
            "recipient_gstin": "27ABCDE1234F1Z5",
            "voucher_id": "PORTAL-DEMO",
        }
        portal = source(client, ws, rid, headers, [row | {"document_type": "INVOICE"}], "PORTAL_2B")
        invoice = post(
            "portal", {"expected_version": invoice["version"], "import_id": portal["id"]}
        )
        assert invoice["findings"]["gst"] == "MATCHED"
        assert invoice["approval"]["state"] == "STALE"
        assert invoice["gate"]["recommendation"] == "PAY"
        assert invoice["findings"]["ims_recommendation"] == "ACCEPT"
        invoice = post("refresh", {})
        assert any(e["action"] == "SOURCE_RECHECKED" for e in invoice["history"])
        invoice = post("resolution", {"expected_version": invoice["version"], "action": "RESOLVED"})
        snapshot = client.get(base, params={"registration_id": rid, "period": "2024-05"})
        assert snapshot.status_code == 200
        data = snapshot.json()["data"]
        assert data["metrics"]["evidence_aligned_itc"] == "18000.00"
        assert data["metrics"]["reviewed_resolutions"] == 1
        assert data["vendors"][0]["score"] == 100
        assert (
            post(
                "scenario",
                {
                    "expected_version": invoice["version"],
                    "cash_available": "150000.00",
                    "proposed_payment": "100000.00",
                },
            )["cash_after_payment"]
            == "50000.00"
        )
        intelligence = client.post(
            base + "/intelligence",
            json={"registration_id": rid, "period": "2024-05", "question": "What needs attention?"},
            headers=headers,
        )
        assert intelligence.status_code == 200
        assert intelligence.json()["data"]["provider"] == "SAVED_FACTS"
        assert client.get(base + "/" + pid + "/notice-draft").status_code == 200
        notice = post(
            "notice-assistance", {"notice_text": "Explain the missing supplier statement record."}
        )
        assert notice["submission"] == "NOT_SUBMITTED"
        assert notice["sources"]["source_signature"] == invoice["source_signature"]
        assert notice["missing_evidence"]
        bad_case = client.post(
            base + "/" + pid + "/notice-assistance",
            json={
                "notice_text": "Explain the missing supplier statement.",
                "case_id": str(uuid4()),
            },
            headers=headers,
        )
        assert bad_case.status_code == 404
        pdf = client.get(base + "/" + pid + "/dossier")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        assert client.get(f"/api/v1/workspaces/{uuid4()}/passports/{pid}").status_code == 404
        assert (
            client.post(
                base + "/" + pid + "/refresh", json={}, headers={"Idempotency-Key": str(uuid4())}
            ).status_code
            == 403
        )
        # A changed amount in a replacement 2B invalidates the resolution and approval.
        changed = row | {
            "cgst": "8000.00",
            "sgst": "8000.00",
            "gross_total": "116000.00",
            "document_type": "INVOICE",
        }
        source(client, ws, rid, headers, [changed], "PORTAL_2B", supersedes_import_id=portal["id"])
        newer = client.get(base + "/" + pid).json()["data"]
        assert newer["findings"]["gst"] == "MISMATCH"
        assert newer["resolution"]["state"] == "REVIEW_REQUIRED"
        with app.app.app.state.store.transaction() as connection:
            connection.execute("UPDATE memberships SET role='VIEWER' WHERE workspace_id=?", (ws,))
        denied = client.post(
            base + "/" + pid + "/refresh",
            json={},
            headers=headers | {"Idempotency-Key": str(uuid4())},
        )
        assert denied.status_code == 403
        app.app.app.state.passports.scan(ws)
        assert client.get(base + "/" + pid).status_code == 200


def test_provider_failure_is_saved_and_never_fake_success(account, monkeypatch):
    settings, _, ws, rid = account

    def fail(*_):
        raise APIError(503, "AI_PROVIDER_REJECTED", "Check backend credentials.")

    monkeypatch.setattr(gemini, "extract", fail)
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        base = f"/api/v1/workspaces/{ws}/passports"
        response = client.post(
            base + "/documents",
            data={"registration_id": rid, "period": "2024-05", "consent": "true"},
            files={"file": ("invoice.pdf", b"%PDF-1.7 fixture")},
            headers=headers | {"Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 200
        invoice = response.json()["data"]
        assert invoice["extraction"]["status"] == "FAILED"
        assert invoice["fields"] == {}
        response = client.post(
            base + "/" + invoice["id"] + "/confirm",
            json={
                "expected_version": invoice["version"],
                "fields": FIELDS | {"gross_total": "1.00"},
            },
            headers=headers | {"Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 422


def test_upgrade_preserves_version_six_accounts_and_creates_backup(account):
    from app.storage.local import VERSION6_DIGEST, LocalStore

    settings, user, ws, _ = account
    store = LocalStore(settings)
    store.acquire()
    try:
        with store.transaction() as connection:
            for table in (
                "passport_decisions",
                "passport_events",
                "passport_evidence",
                "invoice_passports",
            ):
                connection.execute("DROP TABLE " + table)
            connection.execute("PRAGMA user_version=6")
            connection.execute("UPDATE metadata SET value=? WHERE key='schema'", (VERSION6_DIGEST,))
        backup = store.upgrade()
        assert backup
        store.validate()
        with store.transaction(write=False) as connection:
            assert connection.execute("SELECT id FROM users WHERE id=?", (user,)).fetchone()
            assert connection.execute("SELECT id FROM workspaces WHERE id=?", (ws,)).fetchone()
            assert connection.execute("PRAGMA user_version").fetchone()[0] == 7
    finally:
        store.close()
