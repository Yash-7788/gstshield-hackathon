"""Real local channel/storage/business tests with fixture provider I/O; no live Meta calls."""

import hashlib
import hmac
import json
import sqlite3
import time
from contextlib import closing
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.adapters.whatsapp import ProviderError
from app.config import Settings
from app.errors import StorageError
from app.jobs.whatsapp import WhatsAppWorker
from app.main import create_app
from app.services.access import AccessService
from app.services.whatsapp import hashed
from app.services.whatsapp_commands import WhatsAppCommands
from app.storage.local import (
    APPLICATION_ID,
    SCHEMA_VERSION,
    VERSION5_DIGEST,
    VERSION5_SCHEMA,
    LocalStore,
)
from tests.integration.test_imports import completed, confirm, signed_in
from tests.unit.test_import_parsers import csv_content

PHONE = "919876543210"
SECRET = "synthetic-signing-secret-only"


class FixtureProvider:
    def __init__(self):
        self.sent = []
        self.media_reads = 0
        self.send_error = None

    def media(self, identifier, mime):
        self.media_reads += 1
        return csv_content()

    def send(self, phone, body, logical_id):
        self.sent.append((phone, body, logical_id))
        if self.send_error:
            raise self.send_error
        return "wamid.fixture." + logical_id


@pytest.fixture
def channel():
    settings = Settings(
        app_env="test",
        whatsapp_enabled=True,
        whatsapp_public_url="https://callback.example.test",
        meta_graph_version="v25.0",
        meta_phone_number_id="123",
        meta_waba_id="456",
        meta_access_token="synthetic-token",
        meta_app_secret=SECRET,
        meta_verify_token="synthetic-verify-token",
        read_requests_per_minute=5000,
        mutation_requests_per_minute=1000,
        import_requests_per_minute=100,
    )
    store = LocalStore(settings)
    store.acquire()
    store.initialize()
    access = AccessService(store)
    user, workspace = access.provision("alice", "synthetic-passphrase-only", "Channel")
    registration = access.add_registration(workspace, "27ABCDE1234F1Z5", "Synthetic company")
    access.grant("alice", workspace, "REVIEWER")
    with store.transaction() as con:
        con.execute(
            "INSERT INTO team_profile VALUES(?,?,?,?,1)", (workspace, user, "Channel CA", '["CA"]')
        )
    store.close()
    with TestClient(create_app(settings)) as client:
        # Run deterministically without a competing channel loop.
        client.app.app.app.state.channel_worker.close()
        service = client.app.app.app.state.whatsapp
        provider = FixtureProvider()
        service.provider = provider
        headers = signed_in(client)
        yield client, service, provider, user, workspace, registration, headers


def event(text="HELP", *, phone=PHONE, identifier=None, document=None, status=None, timestamp=None):
    item = {
        "id": identifier or "wamid." + str(uuid4()),
        "timestamp": str(timestamp or int(time.time())),
    }
    if status:
        item |= {"recipient_id": phone, "status": status}
        category = "statuses"
    else:
        item |= {"from": phone, "type": "document" if document else "text"}
        item["document" if document else "text"] = document or {"body": text}
        category = "messages"
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "456",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "123"},
                            category: [item],
                        },
                    }
                ],
            }
        ],
    }


def callback(client, payload, *, signature=None, host=None):
    raw = json.dumps(payload).encode() if isinstance(payload, dict) else payload
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": signature
        or "sha256=" + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest(),
    }
    if host:
        headers["Host"] = host
    return client.post("/webhooks/whatsapp", content=raw, headers=headers)


def post(client, workspace, suffix, headers, payload):
    return client.post(
        f"/api/v1/workspaces/{workspace}/whatsapp/{suffix}",
        json=payload,
        headers=headers | {"Idempotency-Key": str(uuid4())},
    )


def link(channel):
    client, service, provider, user, workspace, registration, headers = channel
    reply = post(
        client,
        workspace,
        "link-code",
        headers,
        {"registration_id": registration, "period": "2024-05"},
    )
    assert reply.status_code == 200, reply.text
    code = reply.json()["data"]["code"]
    assert callback(client, event("LINK " + code)).status_code == 200
    assert WhatsAppCommands(service).process_one()
    result = client.get(f"/api/v1/workspaces/{workspace}/whatsapp").json()["data"]["link"]
    assert result["masked_phone"] == "••••3210"
    return result, code


def test_callback_signature_before_json_and_scoped_public_host(channel):
    client, service, provider, user, workspace, registration, headers = channel
    assert callback(client, b"{bad", signature="sha256=" + "0" * 64).status_code == 401
    assert callback(client, b"{bad").status_code == 400
    assert callback(client, b'{"object":"a","object":"b"}').status_code == 400
    assert callback(client, event(), host="callback.example.test").status_code == 200
    assert (
        client.get("/api/v1/workspaces", headers={"Host": "callback.example.test"}).status_code
        == 400
    )
    assert client.get("/health/live", headers={"Host": "other.example.test"}).status_code == 400
    payload = event()
    payload["entry"][0]["id"] = "999"
    assert callback(client, payload).status_code == 403
    payload = event()
    payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = "999"
    assert callback(client, payload).status_code == 403
    params = {
        "hub.mode": "subscribe",
        "hub.verify_token": "synthetic-verify-token",
        "hub.challenge": "12345",
    }
    assert client.get("/webhooks/whatsapp", params=params).text == "12345"
    assert (
        client.get("/webhooks/whatsapp", params=params | {"hub.verify_token": "wrong"}).status_code
        == 403
    )
    assert (
        client.get("/webhooks/whatsapp", params=params | {"hub.challenge": "<script>"}).status_code
        == 403
    )


def test_link_code_hashed_single_use_csrf_foreign_scope_and_context_revoke(channel):
    client, service, provider, user, workspace, registration, headers = channel
    assert (
        post(
            client,
            workspace,
            "link-code",
            {},
            {"registration_id": registration, "period": "2024-05"},
        ).status_code
        == 403
    )
    assert (
        post(
            client,
            str(uuid4()),
            "link-code",
            headers,
            {"registration_id": registration, "period": "2024-05"},
        ).status_code
        == 404
    )
    row, code = link(channel)
    with service.store.transaction(write=False) as connection:
        assert connection.execute("SELECT count(*) FROM wa_codes").fetchone()[0] == 0
        assert code not in " ".join(
            x[0] for x in connection.execute("SELECT payload FROM wa_events")
        )
    assert callback(client, event("LINK " + code, phone="919000000000")).status_code == 200
    WhatsAppCommands(service).process_one()
    with service.store.transaction(write=False) as connection:
        assert connection.execute("SELECT count(*) FROM wa_links WHERE active=1").fetchone()[0] == 1
    assert callback(client, event("UPLOAD PURCHASE")).status_code == 200
    WhatsAppCommands(service).process_one()
    update = post(
        client,
        workspace,
        "context",
        headers,
        {
            "registration_id": registration,
            "period": "2024-06",
            "expected_version": row["version"],
            "consent_alerts": True,
        },
    )
    assert update.status_code == 200, update.text
    with service.store.transaction(write=False) as connection:
        assert connection.execute("SELECT count(*) FROM wa_intents").fetchone()[0] == 0
        assert (
            connection.execute("SELECT count(*) FROM wa_outbox WHERE state='QUEUED'").fetchone()[0]
            == 1
        )  # generic denied link reply only
    assert (
        post(
            client,
            workspace,
            "context",
            headers,
            {
                "registration_id": registration,
                "period": "2024-05",
                "expected_version": row["version"],
            },
        ).status_code
        == 409
    )


def test_phone_upload_website_confirmation_run_and_duplicate_callbacks(channel):
    client, service, provider, user, workspace, registration, headers = channel
    row, code = link(channel)
    commands = WhatsAppCommands(service)
    for kind in ("PURCHASE", "2B"):
        assert callback(client, event("UPLOAD " + kind)).status_code == 200
        commands.process_one()
        payload = event(document={"id": "1234", "mime_type": "text/csv", "filename": "source.csv"})
        assert callback(client, payload).status_code == 200
        assert callback(client, payload).status_code == 200
        commands.process_one()
        with service.store.transaction(write=False) as connection:
            identifier = connection.execute(
                "SELECT id FROM imports WHERE kind=?",
                ("PURCHASE" if kind == "PURCHASE" else "PORTAL_2B",),
            ).fetchone()[0]
        parsed = completed(client, workspace, identifier)
        assert parsed["state"] == "AWAITING_CONFIRMATION"
        assert confirm(client, workspace, identifier, parsed["version"], headers).status_code == 200
        commands.watches()
    assert provider.media_reads == 2
    payload = event("RUN")
    assert callback(client, payload).status_code == 200
    original_queue = service.queue
    service.queue = lambda *args, **kwargs: (_ for _ in ()).throw(
        StorageError("synthetic interrupted receipt publication")
    )
    with pytest.raises(StorageError):
        commands.process_one()
    service.queue = original_queue
    WhatsAppWorker(service).tick()  # Recovery replays the frozen payload/key; one run remains.
    assert callback(client, payload).status_code == 200
    assert commands.process_one() is False
    deadline = time.monotonic() + 15
    while True:
        data = client.get(f"/api/v1/workspaces/{workspace}/runs").json()["data"]["runs"]
        assert len(data) == 1
        if data[0]["state"] == "COMPLETED":
            break
        assert time.monotonic() < deadline
        time.sleep(0.03)
    assert callback(client, event("STATUS")).status_code == 200
    commands.process_one()
    with service.store.transaction(write=False) as connection:
        bodies = [x[0] for x in connection.execute("SELECT body FROM wa_outbox")]
    assert any(data[0]["id"] in body and "EXACT_MATCH=1" in body for body in bodies)
    assert service.send_one() is False and provider.sent == []

    assert callback(client, event("REPORT")).status_code == 200
    commands.process_one()
    deadline = time.monotonic() + 20
    while True:
        artifacts = client.get(f"/api/v1/workspaces/{workspace}/artifacts").json()["data"][
            "artifacts"
        ]
        if artifacts and artifacts[0]["state"] == "READY":
            break
        assert time.monotonic() < deadline
        time.sleep(0.03)
    commands.watches()
    with service.store.transaction(write=False) as connection:
        outbox = connection.execute(
            "SELECT id,body FROM wa_outbox WHERE body LIKE '%{report_link}%' LIMIT 1"
        ).fetchone()
        token = service.token(outbox["id"])
        assert token not in outbox["body"]
        assert connection.execute(
            "SELECT token_hash FROM wa_capabilities WHERE token_hash=?", (hashed(token),)
        ).fetchone()
    public = "/wa/reports/" + token
    for _ in range(3):
        download = client.get(public, headers={"Cookie": "", "Host": "callback.example.test"})
        assert download.status_code == 200 and download.content.startswith(b"%PDF")
        assert download.headers["cache-control"] == "no-store"
    assert client.get(public).status_code == 404
    assert callback(client, event("REPORT")).status_code == 200
    commands.process_one()
    commands.watches()
    with service.store.transaction(write=False) as connection:
        newer = connection.execute(
            "SELECT id FROM wa_outbox WHERE body LIKE '%{report_link}%' ORDER BY rowid DESC LIMIT 1"
        ).fetchone()[0]
    token2 = service.token(newer)
    assert client.get("/wa/reports/" + token2).status_code == 200
    assert (
        post(client, workspace, "unlink", headers, {"expected_version": row["version"]}).status_code
        == 200
    )
    assert client.get("/wa/reports/" + token2).status_code == 404


def test_expired_codes_and_password_reset_revoke_link_authority(channel):
    client, service, provider, user, workspace, registration, headers = channel
    row, code = link(channel)
    service.access.reset_password("alice", "replacement-synthetic-passphrase")
    with service.store.transaction(write=False) as connection:
        assert service.link_row(connection, row["id"]) is None
    assert callback(client, event("STATUS")).status_code == 200
    WhatsAppCommands(service).process_one()
    with service.store.transaction(write=False) as connection:
        body = connection.execute(
            "SELECT body FROM wa_outbox ORDER BY rowid DESC LIMIT 1"
        ).fetchone()[0]
    assert "No saved comparison" not in body and "Link unavailable" in body


def test_expired_code_callback_batch_atomicity_and_no_raw_code(channel):
    client, service, provider, user, workspace, registration, headers = channel
    reply = post(
        client,
        workspace,
        "link-code",
        headers,
        {"registration_id": registration, "period": "2024-05"},
    )
    code = reply.json()["data"]["code"]
    with service.store.transaction() as connection:
        assert connection.execute("SELECT code_hash FROM wa_codes").fetchone()[0] == hashed(code)
        connection.execute("UPDATE wa_codes SET expires_at=0")
    callback(client, event("LINK " + code))
    WhatsAppCommands(service).process_one()
    assert client.get(f"/api/v1/workspaces/{workspace}/whatsapp").json()["data"]["link"] is None
    with service.store.transaction(write=False) as connection:
        initial = connection.execute("SELECT count(*) FROM wa_events").fetchone()[0]
    payload = event()
    payload["entry"].append({"id": "999", "changes": []})
    assert callback(client, payload).status_code == 403
    with service.store.transaction(write=False) as connection:
        assert connection.execute("SELECT count(*) FROM wa_events").fetchone()[0] == initial
    payload = event()
    payload["entry"][0]["changes"][0]["value"]["metadata"] = []
    assert callback(client, payload).status_code == 403
    malformed = event(status="sent")
    malformed["entry"][0]["changes"][0]["value"]["statuses"][0]["status"] = []
    assert callback(client, malformed).status_code == 400
    assert callback(client, b"x" * 65537).status_code == 413


def test_unknown_send_delivery_ordering_budget_and_no_automatic_resend(channel):
    client, service, provider, user, workspace, registration, headers = channel
    row, code = link(channel)
    service.settings = service.settings.model_copy(update={"whatsapp_send_budget": 1})
    provider.send_error = ProviderError("PROVIDER_INTERRUPTED", uncertain=True)
    assert service.send_one() is True
    assert len(provider.sent) == 1
    logical = provider.sent[0][2]
    assert service.send_one() is False
    assert len(provider.sent) == 1
    payload = event(status="read", identifier="wamid.accepted-after-timeout")
    item = payload["entry"][0]["changes"][0]["value"]["statuses"][0]
    item["biz_opaque_callback_data"] = logical
    assert callback(client, payload).status_code == 200
    WhatsAppCommands(service).process_one()
    assert callback(client, payload).status_code == 200
    assert WhatsAppCommands(service).process_one() is False
    assert (
        callback(
            client, event(status="sent", identifier="wamid.accepted-after-timeout")
        ).status_code
        == 200
    )
    WhatsAppCommands(service).process_one()
    with service.store.transaction(write=False) as connection:
        assert (
            connection.execute("SELECT state FROM wa_outbox WHERE id=?", (logical,)).fetchone()[0]
            == "READ"
        )
        assert connection.execute("SELECT used FROM wa_budget").fetchone()[0] == 1
        states = {
            x[0]
            for x in connection.execute(
                "SELECT state FROM wa_delivery_events WHERE outbox_id=?", (logical,)
            )
        }
    assert states == {"QUEUED", "ATTEMPTED", "UNKNOWN", "READ"}


def test_viewer_can_link_and_read_but_cannot_upload_or_run(channel):
    client, service, provider, user, workspace, registration, headers = channel
    row, code = link(channel)
    service.access.grant("alice", workspace, "VIEWER")
    callback(client, event("UPLOAD PURCHASE"))
    WhatsAppCommands(service).process_one()
    callback(client, event("RUN"))
    WhatsAppCommands(service).process_one()
    with service.store.transaction(write=False) as connection:
        assert connection.execute("SELECT count(*) FROM wa_intents").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
        assert set(
            x[0]
            for x in connection.execute("SELECT error_code FROM wa_events WHERE state='FAILED'")
        ) == {"ROLE_FORBIDDEN"}
    assert provider.media_reads == 0


def test_upload_intent_expiry_invalid_media_and_one_document(channel):
    client, service, provider, user, workspace, registration, headers = channel
    row, code = link(channel)
    commands = WhatsAppCommands(service)
    callback(client, event("UPLOAD PURCHASE"))
    commands.process_one()
    with service.store.transaction() as connection:
        connection.execute("UPDATE wa_intents SET expires_at=0")
    callback(
        client, event(document={"id": "123", "mime_type": "text/csv", "filename": "source.csv"})
    )
    commands.process_one()
    assert provider.media_reads == 0
    callback(client, event("UPLOAD PURCHASE"))
    commands.process_one()
    callback(
        client,
        event(document={"id": "123", "mime_type": "application/zip", "filename": "source.csv"}),
    )
    commands.process_one()
    assert provider.media_reads == 0
    with service.store.transaction(write=False) as connection:
        assert connection.execute("SELECT count(*) FROM imports").fetchone()[0] == 0


def test_old_inbound_cannot_execute_and_interrupted_send_is_not_retried(channel):
    client, service, provider, user, workspace, registration, headers = channel
    row, code = link(channel)
    callback(client, event("UPLOAD PURCHASE", timestamp=int(time.time()) - 90000))
    WhatsAppCommands(service).process_one()
    with service.store.transaction() as connection:
        assert connection.execute("SELECT count(*) FROM wa_intents").fetchone()[0] == 0
        connection.execute("UPDATE wa_outbox SET state='ATTEMPTED'")
    WhatsAppWorker(service).tick()
    with service.store.transaction(write=False) as connection:
        assert connection.execute("SELECT state FROM wa_outbox LIMIT 1").fetchone()[0] == "UNKNOWN"
    assert provider.sent == []


def test_schema_five_upgrade_preserves_every_original_table_and_backup():
    settings = Settings(app_env="test")
    store = LocalStore(settings)
    store.acquire()
    try:
        with closing(sqlite3.connect(store.path)) as connection:
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute("PRAGMA user_version=5")
            for statement in VERSION5_SCHEMA:
                connection.execute(statement)
            connection.execute("INSERT INTO metadata VALUES ('schema',?)", (VERSION5_DIGEST,))
            connection.commit()
        access = AccessService(store)
        user, workspace = access.provision(
            "preserved", "synthetic-passphrase-only", "Preserved workspace"
        )
        access.add_registration(workspace, "27ABCDE1234F1Z5", "Preserved registration")
        with store.transaction(write=False) as connection:
            tables = [
                r[0]
                for r in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name!='metadata'"
                )
            ]
            before = {
                name: [tuple(row) for row in connection.execute(f'SELECT * FROM "{name}"')]
                for name in tables
            }
        with pytest.raises(StorageError):
            store.initialize()
        backup = store.upgrade()
        assert backup
        with store.transaction(write=False) as connection:
            assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
            for name, rows in before.items():
                assert [tuple(row) for row in connection.execute(f'SELECT * FROM "{name}"')] == rows
        store.validate(store.root / "backups" / f"{backup}.sqlite3", version=5)
        assert store.upgrade() is None
    finally:
        store.close()


@pytest.mark.parametrize("revoke", [True, False])
def test_supplier_consent_draft_recipient_isolation_stop_and_due_alerts(channel, revoke):
    from tests.integration.test_actions import action, change
    from tests.integration.test_runs import create, finished, prepare
    from tests.unit.test_import_parsers import ROW

    client, service, provider, user, workspace, registration, headers = channel
    linked, code = link(channel)
    payload = prepare(
        client,
        workspace,
        registration,
        headers,
        purchases=[ROW],
        portals=[ROW | {"invoice_number": "OTHER-999"}],
    )
    run = finished(
        client, workspace, create(client, workspace, headers, payload).json()["data"]["id"]
    )
    assert run["state"] == "COMPLETED"
    tracked = action(client, workspace, "INVOICE_REVIEW")
    tracked = change(
        client,
        workspace,
        headers,
        tracked,
        "followups",
        kind="DRAFT",
        contact="+919000000000",
        request="Please correct the missing invoice.",
        draft_id=None,
        observed_on=None,
    )
    draft = next(x for x in tracked["timeline"] if x["kind"] == "FOLLOWUP_DRAFT")
    request = {
        "action_id": tracked["id"],
        "draft_id": draft["id"],
        "expected_version": tracked["version"],
    }
    response = post(client, workspace, "supplier-consent-code", headers, request)
    assert response.status_code == 200, response.text
    consent = response.json()["data"]["code"]
    callback(client, event("CONSENT " + consent, phone="919111111111"))
    WhatsAppCommands(service).process_one()
    assert (
        client.get(f"/api/v1/workspaces/{workspace}/whatsapp/supplier-recipients").json()["data"]
        == []
    )
    callback(client, event("CONSENT " + consent, phone="919000000000"))
    WhatsAppCommands(service).process_one()
    recipients = client.get(f"/api/v1/workspaces/{workspace}/whatsapp/supplier-recipients").json()[
        "data"
    ]
    assert len(recipients) == 1
    send = request | {"recipient_id": recipients[0]["id"]}
    assert (
        post(client, workspace, "supplier-followups", headers, send).status_code == 409
    )  # zero send budget
    service.settings = service.settings.model_copy(update={"whatsapp_send_budget": 20})
    queued = post(client, workspace, "supplier-followups", headers, send)
    assert queued.status_code == 200, queued.text
    delivery = queued.json()["data"]["id"]
    assert (
        post(client, workspace, "supplier-followups", headers, send).json()["data"]["id"]
        == delivery
    )
    tracked = action(client, workspace, "INVOICE_REVIEW")
    assert any(x["kind"] == "CHANNEL_FOLLOWUP_QUEUED" for x in tracked["timeline"])
    with service.store.transaction() as connection:
        connection.execute("UPDATE wa_outbox SET state='CANCELLED' WHERE id!=?", (delivery,))
        assert (
            connection.execute(
                "SELECT count(*) FROM wa_links WHERE phone='919000000000'"
            ).fetchone()[0]
            == 0
        )
    if revoke:
        callback(client, event("STOP", phone="919000000000"))
        WhatsAppCommands(service).process_one()
    service.send_one()
    with service.store.transaction(write=False) as connection:
        assert connection.execute("SELECT state FROM wa_outbox WHERE id=?", (delivery,)).fetchone()[
            0
        ] == ("CANCELLED" if revoke else "ACKNOWLEDGED")
    sent = [(phone, body) for phone, body, logical in provider.sent if logical == delivery]
    assert len(sent) == (0 if revoke else 1)
    if sent:
        assert sent[0][0] == "919000000000" and "Please correct the missing invoice" in sent[0][1]
        assert "no message has been sent" not in sent[0][1]
    tracked = change(
        client,
        workspace,
        headers,
        tracked,
        "update",
        state="REVIEW_REQUIRED",
        review_on="2024-05-01",
        assigned_to=user,
    )
    tracked = action(client, workspace, "INVOICE_REVIEW")
    updated = post(
        client,
        workspace,
        "context",
        headers,
        {
            "registration_id": registration,
            "period": "2024-05",
            "expected_version": linked["version"],
            "consent_alerts": True,
        },
    )
    assert updated.status_code == 200
    commands = WhatsAppCommands(service)
    commands.alerts()
    commands.alerts()
    with service.store.transaction(write=False) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM wa_outbox WHERE logical_key LIKE 'due:%'"
            ).fetchone()[0]
            == 1
        )
    changed_context = post(
        client,
        workspace,
        "context",
        headers,
        {
            "registration_id": registration,
            "period": "2024-05",
            "expected_version": updated.json()["data"]["link"]["version"],
            "consent_alerts": True,
        },
    )
    assert changed_context.status_code == 200
    commands.alerts()
    with service.store.transaction(write=False) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM wa_outbox WHERE logical_key LIKE 'due:%'"
            ).fetchone()[0]
            == 1
        )
    callback(client, event("STATUS", phone="919000000000"))
    commands.process_one()
    with service.store.transaction(write=False) as connection:
        assert (
            connection.execute("SELECT body FROM wa_outbox ORDER BY rowid DESC LIMIT 1")
            .fetchone()[0]
            .startswith("Link unavailable")
        )


def test_xlsx_phone_media_uses_existing_preview_parser(channel):
    from tests.unit.test_import_parsers import xlsx_content

    client, service, provider, user, workspace, registration, headers = channel
    link(channel)
    provider.media = lambda identifier, mime: xlsx_content()
    callback(client, event("UPLOAD PURCHASE"))
    commands = WhatsAppCommands(service)
    commands.process_one()
    callback(
        client,
        event(
            document={
                "id": "1234",
                "filename": "purchase.xlsx",
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
        ),
    )
    commands.process_one()
    with service.store.transaction(write=False) as connection:
        record = connection.execute("SELECT id FROM imports").fetchone()
    assert record is not None
    result = completed(client, workspace, record["id"])
    assert result["state"] == "AWAITING_CONFIRMATION"
    assert result["accepted_rows"] == 1


def test_phone_run_refuses_ambiguous_confirmed_sources(channel):
    from tests.integration.test_imports import upload

    client, service, provider, user, workspace, registration, headers = channel
    link(channel)
    from tests.unit.test_import_parsers import ROW

    for index, kind in enumerate(("PURCHASE", "PURCHASE", "PORTAL_2B")):
        receipt = upload(
            client,
            workspace,
            registration,
            headers,
            kind=kind,
            content=csv_content([ROW | {"voucher_id": f"V{index}"}]),
        )
        assert receipt.status_code == 202
        identifier = receipt.json()["data"]["id"]
        parsed = completed(client, workspace, identifier)
        assert confirm(client, workspace, identifier, parsed["version"], headers).status_code == 200
    callback(client, event("RUN"))
    WhatsAppCommands(service).process_one()
    with service.store.transaction(write=False) as connection:
        assert connection.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
        row = connection.execute(
            "SELECT error_code FROM wa_events ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        assert row[0] == "SOURCE_SELECTION_REQUIRED"
