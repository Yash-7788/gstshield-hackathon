"""Exact invoice handoff, linked records and read-only security boundaries."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from tests.integration.test_imports import account as account
from tests.integration.test_imports import signed_in
from tests.integration.test_runs import finished, source
from tests.integration.test_workflows import payment_case, post, proposal_payload
from tests.unit.test_import_parsers import ROW


def test_invoice_handoff_resolves_exact_source_row_and_keeps_approval_explicit(account):
    settings, _, ws, rid = account
    with TestClient(create_app(settings)) as client:
        client.app.app.app.state.action_monitor.close()
        headers = signed_in(client)
        purchase = source(
            client,
            ws,
            rid,
            headers,
            [
                ROW | {"invoice_number": "FIRST-001", "voucher_id": "V-FIRST"},
                ROW | {"invoice_number": "SECOND-002", "voucher_id": "V-SECOND"},
            ],
            "PURCHASE",
        )
        portal = source(
            client,
            ws,
            rid,
            headers,
            [
                ROW | {"invoice_number": "FIRST-001", "voucher_id": "V-FIRST"},
                ROW | {"invoice_number": "SECOND-002", "voucher_id": "V-SECOND"},
            ],
            "PORTAL_2B",
        )
        created = post(
            client,
            ws,
            "passports/from-source",
            headers,
            {
                "registration_id": rid,
                "period": "2024-05",
                "purchase_import_id": purchase["id"],
                "row_number": 2,
            },
        )
        assert created.status_code == 200, created.text
        invoice = created.json()["data"]
        path = f"/api/v1/workspaces/{ws}/passports/{invoice['id']}/workflow"
        initial = client.get(path).json()["data"]
        assert initial["invoice_number"] == "SECOND-002"
        assert initial["portal_import_id"] == portal["id"]
        assert initial["run"] is not None
        assert initial["cases"] == initial["proposals"] == []
        run = finished(client, ws, initial["run"]["id"])
        assert run["state"] == "COMPLETED"
        results = client.get(f"/api/v1/workspaces/{ws}/runs/{run['id']}/results").json()["data"][
            "results"
        ]
        first = next(r for r in results if r["source_row_number"] == 1)
        second = next(r for r in results if r["source_row_number"] == 2)
        unrelated = payment_case(client, ws, rid, headers, first)
        linked = payment_case(client, ws, rid, headers, second)
        for result, case in [(first, unrelated), (second, linked)]:
            response = post(client, ws, "proposals", headers, proposal_payload(run, result, case))
            assert response.status_code == 201, response.text
        data = client.get(path).json()["data"]
        assert data["result"]["id"] == second["id"]
        assert data["purchase_document_id"] == second["purchase_document_id"]
        assert [c["id"] for c in data["cases"]] == [linked["id"]]
        assert len(data["proposals"]) == 1
        assert data["proposals"][0]["state"] == "DRAFT"
        assert data["cases"][0]["state"] == "REVIEW_READY"
        assert client.get(path).json()["data"] == data  # navigation creates no records or approvals
        assert (
            client.get(
                f"/api/v1/workspaces/{uuid4()}/passports/{invoice['id']}/workflow"
            ).status_code
            == 404
        )
        assert (
            client.get(f"/api/v1/workspaces/{ws}/passports/{uuid4()}/workflow").status_code == 404
        )
        # A newer GST selection must not reuse the old comparison or approve its draft.
        other = source(
            client,
            ws,
            rid,
            headers,
            [
                ROW
                | {
                    "invoice_number": "SECOND-002",
                    "voucher_id": "V-CHANGED",
                    "taxable_value": "999.00",
                    "gross_total": "1179.00",
                }
            ],
            "PORTAL_2B",
        )
        response = post(
            client,
            ws,
            f"passports/{invoice['id']}/portal",
            headers,
            {"expected_version": invoice["version"], "import_id": other["id"]},
        )
        assert response.status_code == 200, response.text
        changed = client.get(path).json()["data"]
        assert changed["portal_import_id"] == other["id"]
        assert changed["run"] is not None and changed["run"]["id"] != run["id"]
        assert changed["proposals"][0]["state"] in {"DRAFT", "STALE"}
        client.cookies.clear()
        assert client.get(path).status_code == 401


def test_automatic_source_confirmation_deduplicates_and_preserves_other_invoices(account):
    from concurrent.futures import ThreadPoolExecutor

    settings, _, ws, rid = account
    with TestClient(create_app(settings)) as client:
        app = client.app.app.app
        app.state.action_monitor.close()
        headers = signed_in(client)
        purchase = source(client, ws, rid, headers, [ROW], "PURCHASE")
        response = post(
            client,
            ws,
            "passports/from-source",
            headers,
            {
                "registration_id": rid,
                "period": "2024-05",
                "purchase_import_id": purchase["id"],
                "row_number": 1,
            },
        )
        invoice = response.json()["data"]
        base = f"/api/v1/workspaces/{ws}/passports/{invoice['id']}"
        assert client.get(base + "/workflow").json()["data"]["run"] is None
        # Confirming a statement alone starts comparison: no click in Reconciliation.
        portal = source(client, ws, rid, headers, [ROW], "PORTAL_2B")
        auto = client.get(base + "/workflow").json()["data"]
        assert auto["portal_import_id"] == portal["id"] and auto["run"] is not None
        run = finished(client, ws, auto["run"]["id"])
        identity = app.state.access.identity(client.cookies.get("gstshield_session"))
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(
                pool.map(
                    lambda _: app.state.passports.ensure_comparison(identity, ws, invoice["id"]),
                    range(8),
                )
            )
        runs = client.get(f"/api/v1/workspaces/{ws}/runs").json()["data"]["runs"]
        assert len(runs) == 1 and runs[0]["id"] == run["id"]
        # Another invoice in the same company/month stays current independently.
        second_purchase = source(
            client,
            ws,
            rid,
            headers,
            [ROW | {"invoice_number": "OTHER-002", "voucher_id": "V-OTHER"}],
            "PURCHASE",
        )
        other = post(
            client,
            ws,
            "passports/from-source",
            headers,
            {
                "registration_id": rid,
                "period": "2024-05",
                "purchase_import_id": second_purchase["id"],
                "row_number": 1,
            },
        ).json()["data"]
        other_path = f"/api/v1/workspaces/{ws}/passports/{other['id']}/workflow"
        other_run = client.get(other_path).json()["data"]["run"]
        finished(client, ws, other_run["id"])
        assert (
            client.get(f"/api/v1/workspaces/{ws}/runs/{run['id']}").json()["data"]["state"]
            == "COMPLETED"
        )
        # Superseding the GST statement reruns both affected invoices automatically.
        corrected = source(
            client,
            ws,
            rid,
            headers,
            [ROW, ROW | {"invoice_number": "OTHER-002", "voucher_id": "V-OTHER"}],
            "PORTAL_2B",
            supersedes_import_id=portal["id"],
        )
        for path, old in [(base + "/workflow", run), (other_path, other_run)]:
            data = client.get(path).json()["data"]
            assert data["portal_import_id"] == corrected["id"]
            assert data["run"]["id"] != old["id"]
            finished(client, ws, data["run"]["id"])
            assert client.get(path).json()["data"]["run"]["state"] == "COMPLETED"
        assert client.get(base).json()["data"]["approval"] is None
        assert client.get(base + "/workflow").json()["data"]["cases"] == []
