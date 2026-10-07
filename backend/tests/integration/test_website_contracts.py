"""Server filters before pagination; report history uses live workspace authorization."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.access import AccessService
from app.storage.local import LocalStore
from tests.integration.test_imports import account as account
from tests.integration.test_imports import signed_in
from tests.integration.test_runs import create, finished, source
from tests.integration.test_workflows import get, payment_case, post, proposal_payload
from tests.unit.test_import_parsers import ROW


def test_month_registration_filter_before_cursor_with_all_report_source_kinds(account):
    settings, _, workspace, registration = account
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    second = AccessService(store).add_registration(workspace, "29ABCDE1234F1Z5", "Second")
    store.close()
    with TestClient(create_app(settings)) as client:
        headers = signed_in(client)
        scopes = []
        for reg, gstin in [(registration, "27ABCDE1234F1Z5"), (second, "29ABCDE1234F1Z5")]:
            for period in ["2024-05", "2024-06"]:
                row = ROW | {"recipient_gstin": gstin, "invoice_number": period + gstin[:2]}
                purchase = source(client, workspace, reg, headers, [row], "PURCHASE", period=period)
                portal = source(client, workspace, reg, headers, [row], "PORTAL_2B", period=period)
                response = create(
                    client,
                    workspace,
                    headers,
                    {
                        "registration_id": reg,
                        "period": period,
                        "purchase_import_id": purchase["id"],
                        "portal_import_id": portal["id"],
                    },
                )
                assert response.status_code == 202, response.text
                run = finished(client, workspace, response.json()["data"]["id"])
                result = get(client, workspace, f"runs/{run['id']}/results").json()["data"][
                    "results"
                ][0]
                case = payment_case(client, workspace, reg, headers, result)
                proposal = post(
                    client, workspace, "proposals", headers, proposal_payload(run, result, case)
                ).json()["data"]
                approved = post(
                    client,
                    workspace,
                    f"proposals/{proposal['id']}/approve",
                    headers,
                    {"expected_version": proposal["version"], "reason": "Synthetic approval."},
                )
                assert approved.status_code == 200, approved.text
                artifact_ids = []
                for kind, item in [
                    ("RECONCILIATION_PDF", run),
                    ("EVIDENCE_PDF", case),
                    ("PROPOSAL_CSV", approved.json()["data"]),
                    ("ROW_ERRORS_CSV", purchase),
                ]:
                    response = post(
                        client,
                        workspace,
                        "artifacts",
                        headers,
                        {
                            "kind": kind,
                            "source_id": item["id"],
                            "expected_version": item["version"],
                        },
                    )
                    assert response.status_code == 202, response.text
                    artifact_ids.append(response.json()["data"]["id"])
                scopes.append((reg, period, run, case, proposal, artifact_ids))
        for reg, period, run, case, proposal, artifact_ids in scopes:
            query = f"registration_id={reg}&period={period}"
            for endpoint, key, expected in [
                ("runs", "runs", [run["id"]]),
                ("cases", "cases", [case["id"]]),
                ("proposals", "proposals", [proposal["id"]]),
                ("artifacts", "artifacts", artifact_ids),
            ]:
                seen = []
                cursor = ""
                while True:
                    response = get(client, workspace, f"{endpoint}?{query}&limit=1{cursor}")
                    assert response.status_code == 200, response.text
                    data = response.json()["data"]
                    seen += [item["id"] for item in data[key]]
                    assert all(
                        "content" not in item and "snapshot_json" not in item for item in data[key]
                    )
                    if not data["next_cursor"]:
                        break
                    cursor = f"&cursor={data['next_cursor']}"
                    assert len(seen) < 20
                assert sorted(seen) == sorted(expected)
            actions = get(client, workspace, f"actions?{query}&limit=20").json()["data"]["actions"]
            assert actions and all(
                a["registration_id"] == reg and a["period"] == period for a in actions
            )
        for endpoint, key in [
            ("runs", "runs"),
            ("cases", "cases"),
            ("proposals", "proposals"),
            ("actions", "actions"),
            ("artifacts", "artifacts"),
        ]:
            assert (
                get(client, workspace, f"{endpoint}?registration_id={uuid4()}").json()["data"][key]
                == []
            )


@pytest.mark.parametrize("endpoint", ["runs", "cases", "proposals", "actions", "artifacts"])
def test_list_scope_validation(endpoint, account):
    settings, _, workspace, _ = account
    with TestClient(create_app(settings)) as client:
        assert get(client, workspace, endpoint).status_code == 401
        signed_in(client)
        for query in ["cursor=bad", "limit=0", "period=2024-13", "registration_id=not-a-uuid"]:
            assert get(client, workspace, f"{endpoint}?{query}").status_code == 422
        assert get(client, str(uuid4()), f"{endpoint}?period=2024-05").status_code == 404
