"""Guidance uses exact scoped saved facts and does not mutate invoice decisions."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from tests.integration.test_imports import account as account
from tests.integration.test_imports import signed_in
from tests.integration.test_runs import source
from tests.integration.test_workflows import post
from tests.unit.test_import_parsers import ROW


def test_guidance_scope_and_no_automatic_approval(account):
    settings, _, ws, rid = account
    with TestClient(create_app(settings)) as client:
        client.app.app.app.state.action_monitor.close()
        route = f"/api/v1/workspaces/{ws}/command-center"
        assert client.get(route + "/glossary").status_code == 401
        headers = signed_in(client)
        glossary = client.get(route + "/glossary")
        assert glossary.status_code == 200
        terms = glossary.json()["data"]["terms"]
        assert all(t["review"] == "NEEDS_CA_REVIEW" for t in terms if "reference" in t)
        assert client.get(f"/api/v1/workspaces/{uuid4()}/command-center/glossary").status_code in {
            403,
            404,
        }
        purchase = source(client, ws, rid, headers, [ROW], "PURCHASE")
        invoice = post(
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
        ).json()["data"]
        url = route + f"/invoices/{invoice['id']}/guide"
        before = client.get(f"/api/v1/workspaces/{ws}/passports/{invoice['id']}").json()["data"]
        result = client.get(url)
        assert result.status_code == 200, result.text
        data = result.json()["data"]
        assert data["next_step"]["id"] == "po"
        assert data["mode"] == "SAVED_FACTS_ONLY"
        assert len(data["staff"]) == 5
        assert client.get(url).json()["data"] == data
        after = client.get(f"/api/v1/workspaces/{ws}/passports/{invoice['id']}").json()["data"]
        assert after == before
        assert after["approval"] is None
        assert client.get(route + f"/invoices/{uuid4()}/guide").status_code == 404


def test_notice_ai_rechecks_authority_before_returning_private_draft(account, monkeypatch):
    from app.adapters import gemini

    settings, user, ws, rid = account
    app = create_app(settings)
    with TestClient(app) as client:
        app.app.app.state.action_monitor.close()
        headers = signed_in(client)
        purchase = source(client, ws, rid, headers, [ROW], "PURCHASE")
        invoice = post(
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
        ).json()["data"]

        def revoke_during_provider(*_):
            with app.app.app.state.store.transaction() as con:
                con.execute(
                    "UPDATE memberships SET active=0 WHERE workspace_id=? AND user_id=?", (ws, user)
                )
            return "Private draft must not leave the service after revocation."

        monkeypatch.setattr(gemini, "generate", revoke_during_provider)
        response = client.post(
            f"/api/v1/workspaces/{ws}/passports/{invoice['id']}/notice-assistance",
            headers=headers | {"Idempotency-Key": str(uuid4())},
            json={"notice_text": "Please explain this actual notice.", "use_ai": True},
        )
        assert response.status_code in {403, 404}
        assert "Private draft" not in response.text
