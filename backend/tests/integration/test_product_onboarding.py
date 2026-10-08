"""New onboarding formats pass through admission, the worker and explicit review."""

import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from tests.integration.test_imports import account as account
from tests.integration.test_imports import completed, confirm, signed_in
from tests.unit.test_product_adapters import payload


def test_product_import_formats_are_connected_and_fixed(account):
    settings, _, ws, rid = account
    with TestClient(create_app(settings)) as client:
        h = signed_in(client)
        root = f"/api/v1/workspaces/{ws}/imports"
        cases = [
            (
                "five-column-v1",
                "PURCHASE",
                "register.csv",
                (
                    b"GSTIN,invoice number,date,taxable value,tax\n27PQR"
                    b"SX5678L1Z2,INV-001,2024-05-10,100000,18000\n"
                ),
            ),
            ("gst-2b-json-v1", "PORTAL_2B", "statement.json", json.dumps(payload()).encode()),
        ]
        for adapter, kind, filename, content in cases:
            res = client.post(
                root,
                data={
                    "registration_id": rid,
                    "period": "2024-05",
                    "kind": kind,
                    "adapter_version": adapter,
                },
                files={"file": (filename, content)},
                headers=h | {"Idempotency-Key": str(uuid4())},
            )
            assert res.status_code == 202, res.text
            item = completed(client, ws, res.json()["data"]["id"])
            assert item["accepted_rows"] == 1 and item["provenance"] == "USER_PROVIDED"
            rows = client.get(root + "/" + item["id"] + "/rows").json()["data"]["rows"]
            assert rows[0]["canonical"]["total_tax"] == "18000.00"
            assert rows[0]["canonical"]["cgst"] == (None if kind == "PURCHASE" else "9000.00")
            bad = client.patch(
                root + "/" + item["id"] + "/mapping",
                json={
                    "expected_version": item["version"],
                    "mapping": {"total_tax": "taxable_value"},
                },
                headers=h | {"Idempotency-Key": str(uuid4())},
            )
            assert bad.status_code == 422
            confirmed = confirm(client, ws, item["id"], item["version"], h)
            assert confirmed.status_code == 200 and confirmed.json()["data"]["state"] == "READY"
        wrong_kind = client.post(
            root,
            data={
                "registration_id": rid,
                "period": "2024-05",
                "kind": "PURCHASE",
                "adapter_version": "gst-2b-json-v1",
            },
            files={"file": ("wrong.json", json.dumps(payload()).encode())},
            headers=h | {"Idempotency-Key": str(uuid4())},
        )
        assert wrong_kind.status_code == 422
