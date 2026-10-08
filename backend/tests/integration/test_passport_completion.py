"""One connected verification batch for item, action, watch and messaging completion."""

from uuid import uuid4

from app.adapters import gemini
from app.adapters.whatsapp import ProviderError
from app.services.whatsapp_commands import WhatsAppCommands
from tests.integration.test_passports import FIELDS
from tests.integration.test_whatsapp import PHONE, callback, event
from tests.integration.test_whatsapp import channel as channel


def create_invoice(channel, monkeypatch):
    client, transport, _, _, ws, rid, headers = channel
    app = client.app.app.app
    app.state.action_monitor.close()
    transport.settings = transport.settings.model_copy(update={"whatsapp_send_budget": 30})
    monkeypatch.setattr(
        gemini, "extract", lambda *_: FIELDS | {"uncertainties": [], "evidence_quotes": {}}
    )
    base = f"/api/v1/workspaces/{ws}/passports"
    response = client.post(
        base + "/documents",
        data={"registration_id": rid, "period": "2024-05", "consent": "true"},
        files={"file": ("fixture.pdf", b"%PDF-1.7 fixture")},
        headers=headers | {"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 200, response.text
    invoice = response.json()["data"]
    pid = invoice["id"]

    def post(suffix, payload, code=200, key=None):
        response = client.post(
            base + "/" + pid + "/" + suffix,
            json=payload,
            headers=headers | {"Idempotency-Key": key or str(uuid4())},
        )
        assert response.status_code == code, response.text
        return response.json()["data"] if code == 200 else response.json()

    invoice = post("confirm", {"expected_version": invoice["version"], "fields": FIELDS})
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
    return client, transport, base, pid, invoice, post


def test_item_identity_review_and_complete_ims_actions(channel, monkeypatch):
    client, _, base, pid, invoice, post = create_invoice(channel, monkeypatch)
    invoice = post("simulate-fetch", {"expected_version": invoice["version"], "status": "MATCHED"})
    assert invoice["findings"]["summary"] == "MATCHED"
    signature = invoice["source_signature"]
    for action in ("ACCEPT", "PENDING", "HUMAN_REVIEW", "REJECT"):
        invoice = post(
            "ims-review",
            {
                "expected_version": invoice["version"],
                "source_signature": signature,
                "action": action,
                "reason": "Reviewer checked the invoice context.",
                "confirm_rejection": action == "REJECT",
            },
        )
        assert invoice["findings"]["ims_review"]["state"] == "CURRENT"
        assert invoice["findings"]["ims_review"]["submission"] == "NOT_SUBMITTED"
        assert invoice["source_signature"] == signature
    post(
        "ims-review",
        {
            "expected_version": invoice["version"],
            "source_signature": signature,
            "action": "REJECT",
            "reason": "Reviewer checked the invoice context.",
        },
        422,
    )
    invoice = post(
        "evidence",
        {
            "expected_version": invoice["version"],
            "kind": "RECEIPT",
            "reference": "WRONG-PRODUCT",
            "taxable_value": "100000.00",
            "quantity": "10",
            "items": [
                FIELDS["items"][0] | {"sku": "OTHER-02", "description": "Different products"}
            ],
            "observed_on": "2024-05-10",
        },
    )
    assert invoice["findings"]["receipt"] == "MISMATCH"
    assert invoice["findings"]["ims_review"]["state"] == "STALE"
    post(
        "ims-review",
        {
            "expected_version": invoice["version"],
            "source_signature": invoice["source_signature"],
            "action": "ACCEPT",
            "reason": "Cannot accept different delivered goods.",
        },
        409,
    )
    invoice = post(
        "evidence",
        {
            "expected_version": invoice["version"],
            "kind": "RECEIPT",
            "reference": "NO-ITEMS",
            "taxable_value": "100000.00",
            "quantity": "10",
            "observed_on": "2024-05-10",
        },
    )
    assert invoice["findings"]["receipt"] == "REVIEW"
    post(
        "details",
        {
            "expected_version": invoice["version"],
            "items": [FIELDS["items"][0] | {"taxable_value": "1.00"}],
        },
        422,
    )
    invoice = post(
        "details",
        {
            "expected_version": invoice["version"],
            "items": FIELDS["items"],
            "supplier_bank_account": "1234567890",
            "irn_required": True,
            "payment_dispute": True,
        },
    )
    data = client.get(base, params={"registration_id": channel[5], "period": "2024-05"}).json()[
        "data"
    ]
    assert data["vendors"][0]["missing_required_irns"] == 1
    assert data["vendors"][0]["recorded_disputes"] == 1
    assert any(signal["signal"] == "MISSING_IRN" for signal in data["anomalies"])
    assert client.get(base + "/" + pid).status_code == 200


def opt_in(client, transport, post, invoice, phone=PHONE):
    invoice = post("resolution", {"expected_version": invoice["version"], "action": "DRAFT"})
    invitation = post("supplier-invite", {"expected_version": invoice["version"], "phone": phone})
    assert callback(client, event("PCONSENT " + invitation["code"], phone=phone)).status_code == 200
    assert WhatsAppCommands(transport).process_one()
    return invitation


def test_supplier_opt_in_auto_send_replies_verified_resolution(channel, monkeypatch):
    client, transport, base, pid, invoice, post = create_invoice(channel, monkeypatch)
    invoice = post("watch", {"expected_version": invoice["version"], "enabled": True})
    invitation = opt_in(client, transport, post, invoice)
    saved = client.get(base + "/" + pid).json()["data"]
    assert saved["supplier_channel"]["state"] == "VERIFIED"
    assert all(
        "phone" not in event["facts"] and "code_hash" not in event["facts"]
        for event in saved["history"]
    )
    assert saved["supplier_channel"]["delivery"]["state"] == "QUEUED"
    assert transport.send_one()
    assert len(channel[2].sent) == 1
    saved = client.get(base + "/" + pid).json()["data"]
    assert saved["supplier_channel"]["delivery"]["state"] == "ACKNOWLEDGED"
    reference = pid.replace("-", "").upper()
    payload = event("PCASE " + reference + " ACK")
    assert callback(client, payload).status_code == 200
    assert WhatsAppCommands(transport).process_one()
    assert callback(client, payload).status_code == 200
    assert not WhatsAppCommands(transport).process_one()
    saved = client.get(base + "/" + pid).json()["data"]
    assert saved["resolution"]["state"] == "ACKNOWLEDGED"
    assert (
        callback(
            client, event("PCASE " + reference + " CORRECTED", phone="919000000001")
        ).status_code
        == 200
    )
    assert WhatsAppCommands(transport).process_one()
    assert client.get(base + "/" + pid).json()["data"]["resolution"]["state"] == "ACKNOWLEDGED"
    assert callback(client, event("PCASE " + reference + " CORRECTED")).status_code == 200
    assert WhatsAppCommands(transport).process_one()
    saved = client.get(base + "/" + pid).json()["data"]
    assert saved["resolution"]["state"] == "CORRECTION_RECEIVED"
    saved = post("simulate-fetch", {"expected_version": saved["version"], "status": "MATCHED"})
    client.app.app.app.state.passports.scan(channel[4])
    assert client.get(base + "/" + pid).json()["data"]["resolution"]["state"] == "RESOLVED"
    assert callback(client, event("PCONSENT " + invitation["code"])).status_code == 200
    assert WhatsAppCommands(transport).process_one()
    assert len(channel[2].sent) == 1


def test_stale_outbox_unknown_send_and_stop(channel, monkeypatch):
    client, transport, base, pid, invoice, post = create_invoice(channel, monkeypatch)
    opt_in(client, transport, post, invoice)
    saved = client.get(base + "/" + pid).json()["data"]
    saved = post(
        "details",
        {"expected_version": saved["version"], "items": FIELDS["items"], "payment_dispute": True},
    )
    assert transport.send_one()  # Cancels queued work whose saved evidence changed.
    assert not channel[2].sent
    assert (
        client.get(base + "/" + pid).json()["data"]["supplier_channel"]["delivery"]["state"]
        == "CANCELLED"
    )
    saved = post("resolution", {"expected_version": saved["version"], "action": "DRAFT"})
    key = str(uuid4())
    saved = post("supplier-send", {"expected_version": saved["version"]}, key=key)
    channel[2].send_error = ProviderError("PROVIDER_INTERRUPTED", uncertain=True)
    assert transport.send_one()
    assert len(channel[2].sent) == 1
    saved = client.get(base + "/" + pid).json()["data"]
    assert saved["supplier_channel"]["delivery"]["state"] == "UNKNOWN"
    post("supplier-send", {"expected_version": saved["version"]})
    assert not transport.send_one()  # Never duplicate an uncertain send.
    assert callback(client, event("STOP")).status_code == 200
    assert WhatsAppCommands(transport).process_one()
    saved = client.get(base + "/" + pid).json()["data"]
    assert saved["supplier_channel"]["state"] != "VERIFIED"
    post("supplier-send", {"expected_version": saved["version"]}, 409)


def test_revoked_inviter_stops_queued_message_and_consent(channel, monkeypatch):
    client, transport, _, pid, invoice, post = create_invoice(channel, monkeypatch)
    opt_in(client, transport, post, invoice)
    with transport.store.transaction() as con:
        con.execute("UPDATE users SET version=version+1 WHERE id=?", (channel[3],))
    assert transport.send_one()
    assert not channel[2].sent
    with transport.store.transaction(write=False) as con:
        row = client.app.app.app.state.passports.row(con, channel[4], pid)
        assert client.app.app.app.state.passports.channel.contact(con, row) is None
        assert (
            client.app.app.app.state.passports.channel.status(con, row)["delivery"]["state"]
            == "CANCELLED"
        )


def test_demo_bank_blocks_full_payment_preserves_tax_and_requires_fresh_approval(
    channel, monkeypatch
):
    client, _, base, pid, invoice, post = create_invoice(channel, monkeypatch)
    invoice = post(
        "clocks",
        {
            "expected_version": invoice["version"],
            "amount_paid": "0.00",
            "payment_observed_on": "2024-05-10",
        },
    )

    def bank(amount, key=None, payload=None):
        nonlocal invoice
        payload = payload or {
            "expected_version": invoice["version"],
            "source_signature": invoice["source_signature"],
            "amount": amount,
        }
        invoice = post("demo-bank-payment", payload, key=key)
        return invoice["demo_bank"]

    def approve(decision, amount):
        nonlocal invoice
        invoice = post(
            "approve",
            {
                "expected_version": invoice["version"],
                "source_signature": invoice["source_signature"],
                "decision": decision,
                "amount": amount,
                "reason": "Approver checked the saved commercial and tax evidence.",
            },
        )

    assert bank("118000.00")["last_attempt"]["status"] == "BLOCKED"
    approve("PARTIAL_CONTROLLED_PAYMENT", "100000.00")
    assert bank("118000.00")["last_attempt"]["status"] == "BLOCKED"
    key = str(uuid4())
    payload = {
        "expected_version": invoice["version"],
        "source_signature": invoice["source_signature"],
        "amount": "100000.00",
    }
    ledger = bank("100000.00", key, payload)
    assert ledger["last_attempt"]["status"] == "RELEASED"
    assert ledger["released_amount"] == "100000.00"
    assert ledger["tax_protected"] == ledger["remaining_amount"] == "18000.00"
    assert bank("100000.00", key, payload)["released_amount"] == "100000.00"
    # A second part-payment approval cannot bypass the cumulative base-only limit.
    approve("PARTIAL_CONTROLLED_PAYMENT", "100000.00")
    assert bank("18000.00")["last_attempt"]["status"] == "BLOCKED"
    invoice = post("simulate-fetch", {"expected_version": invoice["version"], "status": "MATCHED"})
    assert invoice["approval"]["state"] == "STALE"
    assert bank("18000.00")["last_attempt"]["status"] == "BLOCKED"
    approve("PAY", "118000.00")
    ledger = bank("18000.00")
    assert ledger["last_attempt"]["status"] == "RELEASED"
    assert ledger["released_amount"] == "118000.00" and ledger["remaining_amount"] == "0.00"
    assert invoice["clocks"]["facts"]["amount_paid"] == "0.00"
    assert invoice["gate"]["remaining_amount"] == "118000.00"
    assert ledger["execution"] == "NO_BANK_TRANSFER"
    assert bank("1.00")["last_attempt"]["status"] == "BLOCKED"
    assert client.get(base + "/" + pid).status_code == 200
