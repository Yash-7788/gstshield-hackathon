"""Assigned-role route isolation and the connected OCR-to-evidence journey."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.adapters import gemini
from app.main import create_app
from tests.integration.test_imports import ORIGIN, signed_in
from tests.integration.test_imports import account as account
from tests.integration.test_imports import owner_account as owner_account
from tests.integration.test_passports import FIELDS

PASSWORD = "synthetic-role-passphrase"


def enter(client, name, password=PASSWORD):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": name, "password": password},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200, response.text
    return {"Origin": ORIGIN, "X-CSRF-Token": response.json()["data"]["csrf_token"]}


def create(client, base, headers, role):
    response = client.post(
        base + "/product/team/members",
        json={
            "username": "test-" + role.lower(),
            "password": PASSWORD,
            "display_name": role,
            "roles": [role],
        },
        headers=headers | {"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_one_role_owner_readonly_and_each_role_route_scope(owner_account):
    settings, uid, ws, rid = owner_account
    with TestClient(create_app(settings)) as client:
        owner = signed_in(client)
        base = f"/api/v1/workspaces/{ws}"
        scope = {"registration_id": rid, "period": "2024-05"}
        portal = client.get(base + "/product/portal").json()["data"]
        assert portal["roles"] == ["OWNER"] and not portal["financial_write"]
        denied = client.post(
            base + "/passports/from-source",
            json=scope | {"purchase_import_id": str(uuid4()), "row_number": 1},
            headers=owner | {"Idempotency-Key": str(uuid4())},
        )
        assert denied.status_code == 403
        assert client.get(base + "/passports", params=scope).status_code == 403
        bad = client.post(
            base + "/product/team/members",
            json={
                "username": "multi-role",
                "password": PASSWORD,
                "display_name": "Ambiguous",
                "roles": ["CA", "CMA"],
            },
            headers=owner | {"Idempotency-Key": str(uuid4())},
        )
        assert bad.status_code == 422
        roles = [
            "CA",
            "CFO",
            "CMA",
            "CMO",
            "CEO",
            "COO",
            "CTO",
            "ACCOUNTS",
            "WAREHOUSE",
            "FOLLOWUP",
        ]
        for role in roles:
            create(client, base, owner, role)
        for role in roles:
            h = enter(client, "test-" + role.lower())
            assert client.get(base + "/product/portal").json()["data"]["roles"] == [role]
            assert client.get(base + "/product/workflows", params=scope).status_code == 200
            read = client.get(base + "/passports", params=scope)
            assert read.status_code == (
                200 if role in {"CA", "CFO", "ACCOUNTS", "WAREHOUSE", "FOLLOWUP"} else 403
            ), (role, read.text)
            for assistant in {"CA", "CMA", "CFO", "CMO", "CTO"} - {role}:
                denied = client.post(
                    base + "/product/assistants/" + assistant,
                    json=scope | {"question": "Show my saved facts"},
                    headers=h,
                )
                assert denied.status_code == 403, (role, assistant, denied.text)
            assert (
                client.post(
                    base + "/product/business",
                    json=scope | {"expected_version": 0, "profile": {"business_name": "Private"}},
                    headers=h | {"Idempotency-Key": str(uuid4())},
                ).status_code
                == 403
            )


def test_reviewed_ocr_proofs_no_fabricated_receipt_prices_and_replay(owner_account, monkeypatch):
    settings, _, ws, rid = owner_account
    monkeypatch.setattr(
        gemini, "extract", lambda *_: FIELDS | {"uncertainties": [], "evidence_quotes": {}}
    )
    count = []

    def proof(_settings, _content, _mime, kind):
        count.append(kind)
        return {
            "document_kind": kind,
            "reference": kind + "-REAL-1",
            "observed_on": "2024-05-10",
            "taxable_value": "100000.00" if kind == "PO" else None,
            "quantity": "10",
            "items": [FIELDS["items"][0] | ({"taxable_value": None} if kind == "RECEIPT" else {})],
            "uncertainties": [],
        }

    monkeypatch.setattr(gemini, "extract_commercial", proof)
    with TestClient(create_app(settings)) as client:
        base = f"/api/v1/workspaces/{ws}"
        owner = signed_in(client)
        create(client, base, owner, "CA")
        h = enter(client, "test-ca")
        upload = client.post(
            base + "/passports/documents",
            data={"registration_id": rid, "period": "2024-05", "consent": "true"},
            files={"file": ("invoice.pdf", b"%PDF-test-invoice")},
            headers=h | {"Idempotency-Key": str(uuid4())},
        )
        assert upload.status_code == 200, upload.text
        invoice = upload.json()["data"]
        assert invoice["fields"]["items"] == FIELDS["items"]
        pid = invoice["id"]
        endpoint = base + "/passports/" + pid
        confirmed = client.post(
            endpoint + "/confirm",
            json={"expected_version": invoice["version"], "fields": FIELDS},
            headers=h | {"Idempotency-Key": str(uuid4())},
        )
        assert confirmed.status_code == 200, confirmed.text
        invoice = confirmed.json()["data"]
        processes = client.get(
            base + "/product/workflows", params={"registration_id": rid, "period": "2024-05"}
        ).json()["data"]
        assert processes["workflows"][0]["passport_id"] == pid
        for kind in ["PO", "RECEIPT"]:
            key = str(uuid4())
            arguments = {
                "data": {"kind": kind, "consent": "true"},
                "files": {"file": ("proof.pdf", b"%PDF-test-" + kind.encode())},
                "headers": h | {"Idempotency-Key": key},
            }
            response = client.post(endpoint + "/evidence-documents", **arguments)
            assert response.status_code == 200, response.text
            proposal = response.json()["data"]
            replay = client.post(endpoint + "/evidence-documents", **arguments)
            assert replay.json()["data"] == proposal
            payload = {
                "expected_version": invoice["version"],
                "kind": kind,
                "document_proposal_id": proposal["proposal_id"],
                **{
                    k: v
                    for k, v in proposal["fields"].items()
                    if k not in {"document_kind", "uncertainties"}
                },
            }
            key = str(uuid4())
            result = client.post(
                endpoint + "/evidence", json=payload, headers=h | {"Idempotency-Key": key}
            )
            assert result.status_code == 200, result.text
            invoice = result.json()["data"]
            assert (
                client.post(
                    endpoint + "/evidence", json=payload, headers=h | {"Idempotency-Key": key}
                ).status_code
                == 200
            )
        assert count == ["PO", "RECEIPT"]
        assert invoice["findings"]["po"] == invoice["findings"]["receipt"] == "MATCHED"
        assert invoice["findings"]["receipt_items"]["lines"][0]["record_value"] is None
        assert invoice["gate"]["remaining_amount"] is None
        assert invoice["gate"]["recorded_tax_under_review"] == "18000.00"
        assert any(e["facts"].get("provenance") == "OCR_REVIEWED" for e in invoice["history"])
        monkeypatch.setattr(gemini, "extract_commercial", lambda *_: {"document_kind": "OTHER"})
        wrong = client.post(
            endpoint + "/evidence-documents",
            data={"kind": "PO", "consent": "true"},
            files={"file": ("invoice.pdf", b"%PDF-wrong-file")},
            headers=h | {"Idempotency-Key": str(uuid4())},
        )
        assert wrong.status_code == 422


def test_month_statement_reuses_sources_and_invalidates_old_approval(account, monkeypatch):
    settings, _, ws, rid = account
    monkeypatch.setattr(
        gemini, "extract", lambda *_: FIELDS | {"uncertainties": [], "evidence_quotes": {}}
    )
    app = create_app(settings)
    with TestClient(app) as client:
        app.app.app.state.action_monitor.close()
        h = signed_in(client)
        root = f"/api/v1/workspaces/{ws}"

        def write(url, payload):
            res = client.post(
                root + url, json=payload, headers=h | {"Idempotency-Key": str(uuid4())}
            )
            assert res.status_code == 200, res.text
            return res.json()["data"]

        invoices = []
        for number in ["SHARED-1", "SHARED-2"]:
            res = client.post(
                root + "/passports/documents",
                data={"registration_id": rid, "period": "2024-05", "consent": "true"},
                files={"file": (number + ".pdf", b"%PDF-test-" + number.encode())},
                headers=h | {"Idempotency-Key": str(uuid4())},
            )
            assert res.status_code == 200, res.text
            p = res.json()["data"]
            p = write(
                "/passports/" + p["id"] + "/confirm",
                {"expected_version": p["version"], "fields": FIELDS | {"invoice_number": number}},
            )
            invoices.append(p)
        path = "/passports/" + invoices[0]["id"]
        missing = write(
            path + "/simulate-fetch",
            {"expected_version": invoices[0]["version"], "status": "MISSING"},
        )
        first = missing["findings"]["gst_source"]["id"]
        approved = write(
            path + "/approve",
            {
                "expected_version": missing["version"],
                "source_signature": missing["source_signature"],
                "decision": "HOLD",
                "amount": "0.00",
                "reason": "Hold while the saved GST evidence is missing.",
            },
        )
        aligned = write(
            path + "/simulate-fetch", {"expected_version": approved["version"], "status": "MATCHED"}
        )
        second = aligned["findings"]["gst_source"]["id"]
        assert first != second
        legacy = write(
            path + "/portal", {"expected_version": aligned["version"], "import_id": first}
        )
        assert legacy["findings"]["gst_source"]["id"] == first
        payload = {"registration_id": rid, "period": "2024-05", "import_id": second}
        key = str(uuid4())
        res = client.post(
            root + "/product/gst-statement", json=payload, headers=h | {"Idempotency-Key": key}
        )
        assert res.status_code == 200, res.text
        replay = client.post(
            root + "/product/gst-statement", json=payload, headers=h | {"Idempotency-Key": key}
        )
        assert replay.json()["data"] == res.json()["data"]
        views = client.get(
            root + "/passports", params={"registration_id": rid, "period": "2024-05"}
        ).json()["data"]["passports"]
        assert all(p["findings"]["gst_source"]["id"] == second for p in views)
        p = next(p for p in views if p["id"] == invoices[0]["id"])
        assert p["findings"]["gst"] == "MATCHED"
        assert p["approval"]["state"] == "STALE"
        assert (
            next(p for p in views if p["id"] == invoices[1]["id"])["findings"]["gst"] == "MISSING"
        )
