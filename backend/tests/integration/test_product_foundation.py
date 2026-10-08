"""Owner/team isolation, financial privacy, versions and duplicate-role accounts."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from tests.integration.test_imports import owner_account as owner_account
from tests.integration.test_imports import signed_in


def test_owner_team_profiles_and_shared_work(owner_account):
    settings, uid, ws, rid = owner_account
    with TestClient(create_app(settings)) as client:
        base = f"/api/v1/workspaces/{ws}/product"
        assert client.get(base + "/portal").status_code == 401
        h = signed_in(client)
        assert client.get(base + "/portal").json()["data"]["owner"] is True
        payload = {
            "registration_id": rid,
            "period": "2024-05",
            "expected_version": 0,
            "profile": {
                "business_name": "Demo Pumps",
                "monthly_revenue": "1000000.00",
                "monthly_profit": "150000",
                "workforce_count": 2,
                "employees": [
                    {"name": "First person", "role": "Warehouse", "monthly_salary": "20000.00"}
                ],
            },
        }
        key = str(uuid4())
        res = client.post(base + "/business", json=payload, headers=h | {"Idempotency-Key": key})
        assert res.status_code == 200, res.text
        replay = client.post(base + "/business", json=payload, headers=h | {"Idempotency-Key": key})
        assert replay.status_code == 200 and replay.json()["data"] == res.json()["data"]
        assert res.json()["data"]["profile"]["monthly_profit"] == "150000.00"
        assert (
            client.post(
                base + "/business", json=payload, headers=h | {"Idempotency-Key": str(uuid4())}
            ).status_code
            == 409
        )
        users = []
        for i in [1, 2]:
            m = client.post(
                base + "/team/members",
                json={
                    "username": f"ca{i}",
                    "password": "synthetic-ca-passphrase",
                    "display_name": f"CA {i}",
                    "roles": ["CA"],
                },
                headers=h | {"Idempotency-Key": str(uuid4())},
            )
            assert m.status_code == 200, m.text
            users.append(m.json()["data"])
        assert users[0]["roles"] == users[1]["roles"] == ["CA"]
        owner_as_ca = client.post(
            base + "/team/members",
            json={
                "username": "badowner",
                "password": "synthetic-ca-passphrase",
                "display_name": "Wrong",
                "roles": ["OWNER"],
            },
            headers=h | {"Idempotency-Key": str(uuid4())},
        )
        assert owner_as_ca.status_code == 422
        ca = client.post(
            "/api/v1/auth/login",
            json={"username": "ca1", "password": "synthetic-ca-passphrase"},
            headers={"Origin": "http://localhost:3000"},
        )
        cah = {"Origin": "http://localhost:3000", "X-CSRF-Token": ca.json()["data"]["csrf_token"]}
        profile = client.get(
            base + "/business", params={"registration_id": rid, "period": "2024-05"}
        ).json()["data"]
        assert "employees" not in profile["profile"]
        assert profile["profile"]["recorded_payroll_total"] == "20000.00"
        assert (
            client.post(
                base + "/business", json=payload, headers=cah | {"Idempotency-Key": str(uuid4())}
            ).status_code
            == 403
        )
        update = {
            "registration_id": rid,
            "period": "2024-05",
            "role": "CA",
            "note": "Reviewing the first invoice with warehouse evidence.",
        }
        assert (
            client.post(
                base + "/contributions",
                json=update,
                headers=cah | {"Idempotency-Key": str(uuid4())},
            ).status_code
            == 200
        )
        assert (
            client.get(
                base + "/contributions", params={"registration_id": rid, "period": "2024-05"}
            ).json()["data"]["updates"][0]["role"]
            == "CA"
        )
        update["role"] = "CFO"
        assert (
            client.post(
                base + "/contributions",
                json=update,
                headers=cah | {"Idempotency-Key": str(uuid4())},
            ).status_code
            == 403
        )
        assert client.get(f"/api/v1/workspaces/{uuid4()}/product/team").status_code == 404
