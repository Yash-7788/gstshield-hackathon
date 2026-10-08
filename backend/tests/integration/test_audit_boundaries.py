"""Small, isolated regressions for confirmed audit findings; no live accounts/providers."""

import hashlib
from datetime import date, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.adapters import gemini
from app.contracts.passports import ClockEvidence
from app.errors import APIError
from app.security.credential_receipts import credential_payload, upgrade_receipts
from app.services.imports import digest, encode
from app.services.whatsapp_commands import WhatsAppCommands
from tests.integration.test_passport_completion import create_invoice
from tests.integration.test_whatsapp import channel as channel
from tests.integration.test_whatsapp import link


def test_payment_unknown_caps_purchase_staleness_and_removal(channel, monkeypatch):
    client, transport, base, pid, invoice, post = create_invoice(channel, monkeypatch)
    app = client.app.app.app
    assert invoice["findings"]["purchase_source_current"]
    assert invoice["gate"]["remaining_amount"] is None
    invoice = post("simulate-fetch", {"expected_version": invoice["version"], "status": "MISSING"})
    invoice = post("clocks", {"expected_version": invoice["version"], "msme_covered": False})
    assert not invoice["gate"]["payment_facts_confirmed"]
    assert invoice["gate"]["remaining_amount"] is None

    def approve(amount, status):
        return post(
            "approve",
            {
                "expected_version": invoice["version"],
                "source_signature": invoice["source_signature"],
                "decision": "PARTIAL_CONTROLLED_PAYMENT",
                "amount": amount,
                "reason": "Order and delivery checked by reviewer.",
            },
            status,
        )

    approve("100000.00", 409)
    invoice = post(
        "clocks",
        {
            "expected_version": invoice["version"],
            "amount_paid": "50000.00",
            "payment_observed_on": "2024-05-10",
        },
    )
    assert invoice["gate"]["suggested_part_payment"] == "50000.00"
    approve("67000.00", 409)
    invoice = approve("50000.00", 200)
    assert invoice["demo_bank"]["allowed_amount"] == "50000.00"
    with app.state.store.transaction() as con:
        con.execute(
            "UPDATE imports SET state='SUPERSEDED',version=version+1 WHERE id=?",
            (invoice["purchase_import_id"],),
        )
    invoice = client.get(base + "/" + pid).json()["data"]
    assert not invoice["findings"]["purchase_source_current"]
    assert invoice["approval"]["state"] == "STALE"
    assert invoice["demo_bank"]["allowed_amount"] == "0.00"
    remove_key = str(uuid4())
    removal = {"expected_version": invoice["version"], "target": "INVOICE"}
    invoice = post("remove", removal, key=remove_key)
    assert invoice["removed"] and not invoice["original_available"]
    assert post("remove", removal, key=remove_key)["id"] == pid
    post("clocks", {"expected_version": invoice["version"], "amount_paid": "0.00"}, 410)
    listing = client.get(
        base, params={"registration_id": invoice["registration_id"], "period": "2024-05"}
    ).json()["data"]
    assert not listing["passports"]
    with app.state.store.transaction(write=False) as con:
        row = con.execute("SELECT content FROM invoice_passports WHERE id=?", (pid,)).fetchone()
        assert row[0] is None
        assert (
            con.execute(
                "SELECT count(*) FROM passport_decisions WHERE passport_id=?", (pid,)
            ).fetchone()[0]
            == 1
        )


def test_supporting_upload_boundary_and_current_supplier_role(channel, monkeypatch):
    client, transport, base, pid, invoice, _ = create_invoice(channel, monkeypatch)
    monkeypatch.setattr(gemini, "extract_commercial", lambda *_: {"document_kind": "PO"})
    headers = channel[-1]
    response = client.post(
        base + "/" + pid + "/evidence-documents",
        data={"kind": "PO", "consent": "true"},
        files={"file": ("order.pdf", b"%PDF-1.7 " + b"x" * 100000)},
        headers=headers | {"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 200, response.text
    app = client.app.app.app
    uid, ws = channel[3:5]
    linked, _ = link(channel)
    with app.state.store.transaction() as con:
        version = con.execute("SELECT version FROM users WHERE id=?", (uid,)).fetchone()[0]
        assert app.state.passports.channel.actor_valid(con, ws, uid, version)
        con.execute("UPDATE team_profile SET roles_json='[\"FOLLOWUP\"]' WHERE user_id=?", (uid,))
        current = transport.link_row(con, linked["id"])
        assert current
        with pytest.raises(APIError) as exc:
            WhatsAppCommands(transport).authorize_command(
                con, transport.identity(current), ws, {"kind": "TEXT"}, "RUN"
            )
        assert exc.value.code == "ROLE_FORBIDDEN"
        con.execute("UPDATE team_profile SET roles_json='[\"CFO\"]' WHERE user_id=?", (uid,))
        assert not app.state.passports.channel.actor_valid(con, ws, uid, version)
        assert transport.link_row(con, linked["id"]) is None


def test_preserving_scoped_credential_receipt_migration(channel):
    client, _, _, uid, ws, _, _ = channel
    store = client.app.app.app.state.store
    key = str(uuid4())
    safe = {
        "username": "fixture",
        "display_name": "Fixture",
        "roles": ["CA"],
        "password_fingerprint": hashlib.sha256(b"synthetic-only").hexdigest(),
    }
    old = digest(safe)
    response = encode({"id": "retained-response"})
    with store.transaction() as con:
        con.execute(
            "INSERT INTO workflow_operations VALUES(?,?,?,?,?,?)",
            (ws, uid, "member-create", key, old, response),
        )
    assert upgrade_receipts(store, ws) == 1
    assert upgrade_receipts(store, ws) == 0
    with store.transaction(write=False) as con:
        row = con.execute("SELECT * FROM workflow_operations WHERE key=?", (key,)).fetchone()
    assert row["response_json"] == response
    assert row["request_hash"] != old
    assert row["request_hash"] == digest(credential_payload(ws, uid, "member-create", key, old))
    assert row["route"] == "member-create-v2"


def test_future_payment_observation_rejected():
    with pytest.raises(ValidationError):
        ClockEvidence(
            expected_version=1,
            amount_paid="0.00",
            payment_observed_on=date.today() + timedelta(days=1),
        )


def test_unused_source_removal_preserves_receipt_and_rejects_used_source(channel, monkeypatch):
    from types import SimpleNamespace

    from tests.integration.test_runs import source
    from tests.unit.test_import_parsers import ROW

    client, _, _, _, invoice, _ = create_invoice(channel, monkeypatch)
    ws, rid, headers = channel[4:7]
    store = client.app.app.app.state.store
    unused = source(
        client,
        ws,
        rid,
        headers,
        [ROW | {"invoice_number": "REMOVE-001", "voucher_id": "REMOVE-001"}],
        "PURCHASE",
    )
    with store.transaction(write=False) as con:
        saved = con.execute(
            "SELECT * FROM import_operations WHERE import_id=? LIMIT 1", (unused["id"],)
        ).fetchone()
        file_id = con.execute("SELECT file_id FROM imports WHERE id=?", (unused["id"],)).fetchone()[
            0
        ]
    key = str(uuid4())
    url = f"/api/v1/workspaces/{ws}/imports/{unused['id']}/remove"
    payload = {"expected_version": unused["version"]}
    for _ in range(2):
        response = client.post(url, json=payload, headers=headers | {"Idempotency-Key": key})
        assert response.status_code == 200, response.text
    with store.transaction(write=False) as con:
        assert not con.execute("SELECT 1 FROM import_files WHERE id=?", (file_id,)).fetchone()
        assert not con.execute("SELECT 1 FROM imports WHERE id=?", (unused["id"],)).fetchone()
        with pytest.raises(APIError) as exc:
            client.app.app.app.state.imports.operation(
                con,
                SimpleNamespace(user_id=saved["actor_id"]),
                ws,
                saved["route"],
                saved["key"],
                saved["request_hash"],
            )
        assert exc.value.code == "SOURCE_REMOVED"
    used = client.get(f"/api/v1/workspaces/{ws}/imports/{invoice['purchase_import_id']}").json()[
        "data"
    ]
    response = client.post(
        f"/api/v1/workspaces/{ws}/imports/{used['id']}/remove",
        json={"expected_version": used["version"]},
        headers=headers | {"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "SOURCE_IN_USE"
