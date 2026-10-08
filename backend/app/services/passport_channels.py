"""Connect invoice corrections to the durable, consent-bound Meta transport."""

import base64
import json
import secrets
from datetime import date
from types import SimpleNamespace
from uuid import UUID

from app.errors import APIError
from app.security.roles import actor_role
from app.services.whatsapp import hashed


class PassportChannels:
    def __init__(self, passports, transport):
        self.passports, self.transport = passports, transport

    def latest(self, con, row, actions):
        placeholders = ",".join("?" for _ in actions)
        event = con.execute(
            (
                "SELECT * FROM passport_events WHERE workspace_id=? AND passport_id=? "
                f"AND action IN ({placeholders}) ORDER BY sequence DESC LIMIT 1"
            ),
            (row["workspace_id"], row["id"], *actions),
        ).fetchone()
        return (event, json.loads(event["payload_json"])) if event else (None, {})

    def contact(self, con, row):
        if json.loads(row["extraction_json"]).get("removed_at"):
            return None
        event, data = self.latest(con, row, ("SUPPLIER_VERIFIED", "SUPPLIER_REVOKED"))
        return (
            data
            if event
            and event["action"] == "SUPPLIER_VERIFIED"
            and self.actor_valid(con, row["workspace_id"], event["actor_id"], data["user_version"])
            else None
        )

    def status(self, con, row):
        contact = self.contact(con, row)
        invited, invite_facts = self.latest(con, row, ("SUPPLIER_INVITED",))
        last_contact, _ = self.latest(con, row, ("SUPPLIER_VERIFIED", "SUPPLIER_REVOKED"))
        pending = bool(
            invited
            and invite_facts["expires_at"] > int(self.transport.clock())
            and (not last_contact or invited["sequence"] > last_contact["sequence"])
        )
        _, binding = self.latest(con, row, ("RESOLUTION_QUEUED",))
        outbox = con.execute(
            "SELECT state,error_code,updated_at FROM wa_outbox WHERE id=?",
            (binding.get("outbox_id", ""),),
        ).fetchone()
        return {
            "state": "VERIFIED" if contact else "AWAITING_CONSENT" if pending else "NOT_CONNECTED",
            "masked_phone": "••••" + contact["phone"][-4:] if contact else None,
            "delivery": dict(outbox) if outbox else None,
            "delivery_history": [
                dict(event)
                for event in con.execute(
                    (
                        "SELECT state,created_at FROM wa_delivery_events WHERE outbox_id=? "
                        "ORDER BY created_at,rowid"
                    ),
                    (binding.get("outbox_id", ""),),
                )
            ],
            "reply_reference": row["id"].replace("-", "").upper(),
            "sending_configured": bool(
                self.transport.settings.whatsapp_enabled
                and self.transport.settings.whatsapp_send_budget
            ),
        }

    def actor_valid(self, con, ws, actor, version):
        if actor_role(con, actor, ws) not in {"CA", "FOLLOWUP"}:
            return False
        return (
            con.execute(
                (
                    "SELECT 1 FROM users u JOIN memberships m ON m.user_id=u.id "
                    "WHERE u.id=? AND u.active=1 AND u.version=? AND "
                    "m.workspace_id=? AND m.active=1 AND m.role IN "
                    "('OWNER','REVIEWER')"
                ),
                (actor, version, ws),
            ).fetchone()
            is not None
        )

    def invite(self, identity, ws, pid, payload, request_id):
        svc = self.passports
        with svc.store.transaction() as con:
            svc.authorize(con, identity, ws, mutation=True)
            self.transport.enabled()
            row = svc.row(con, ws, pid)
            route = "passport-supplier-invite/" + pid
            if svc.operation(con, identity, ws, route, request_id, payload):
                raise APIError(
                    409,
                    "INVITATION_ALREADY_CREATED",
                    "Create a fresh invitation if the code was lost.",
                )
            svc.version(row, payload["expected_version"])
            if not row["confirmed"]:
                raise APIError(409, "CONFIRM_FIRST", "Confirm this invoice first.")
            self.transport.rate(con, "passport-invite/" + identity.user_id, 10, 600)
            token = base64.b32encode(secrets.token_bytes(8)).decode()[:12]
            view = svc.project(con, row)
            user = con.execute(
                "SELECT version FROM users WHERE id=?", (identity.user_id,)
            ).fetchone()
            now = int(self.transport.clock())
            svc.event(
                con,
                identity,
                ws,
                pid,
                "SUPPLIER_INVITED",
                {
                    "phone": payload["phone"].lstrip("+"),
                    "code_hash": hashed(token),
                    "expires_at": now + 600,
                    "user_version": user[0],
                    "source_signature": view["source_signature"],
                },
            )
            con.execute(
                "UPDATE invoice_passports SET version=version+1 WHERE id=? AND workspace_id=?",
                (pid, ws),
            )
            svc.record(con, identity, ws, route, request_id, payload, {"id": pid})
            return {
                "code": token,
                "expires_at": now + 600,
                "instruction": "Supplier sends PCONSENT "
                + token
                + (
                    " to your business WhatsApp number to allow correction "
                    "messages for this invoice."
                ),
                "version": row["version"] + 1,
            }

    def send(self, identity, ws, pid, payload, request_id):
        svc = self.passports
        with svc.store.transaction() as con:
            svc.authorize(con, identity, ws, mutation=True)
            self.transport.enabled()
            row = svc.row(con, ws, pid)
            route = "passport-supplier-send/" + pid
            if svc.operation(con, identity, ws, route, request_id, payload):
                return
            svc.version(row, payload["expected_version"])
            self.queue(con, identity, row, strict=True)
            svc.record(con, identity, ws, route, request_id, payload, {"id": pid})

    def queue(self, con, identity, row, strict=False):
        svc, transport = self.passports, self.transport
        view = svc.project(con, row)
        contact = self.contact(con, row)
        now = int(transport.clock())
        used = con.execute("SELECT used FROM wa_budget WHERE singleton=1").fetchone()[0]
        if (
            not transport.settings.whatsapp_enabled
            or not transport.settings.whatsapp_send_budget
            or used >= transport.settings.whatsapp_send_budget
        ):
            if strict:
                raise APIError(
                    409,
                    "WHATSAPP_SENDING_DISABLED",
                    "Set up WhatsApp and enable its send budget first.",
                )
            return None
        if not contact or now - contact["last_inbound"] >= 86400:
            if strict:
                raise APIError(
                    409,
                    "SUPPLIER_CONSENT_REQUIRED",
                    (
                        "Ask the supplier to opt in or reply again to open the "
                        "WhatsApp response window."
                    ),
                )
            return None
        resolution = view["resolution"]
        if (
            not row["confirmed"]
            or not resolution.get("draft")
            or resolution.get("source_signature") != view["source_signature"]
            or view["findings"]["summary"] == "MATCHED"
        ):
            if strict:
                raise APIError(
                    409,
                    "CURRENT_REQUEST_REQUIRED",
                    "Prepare a correction request from the current evidence first.",
                )
            return None
        user = con.execute("SELECT version FROM users WHERE id=?", (identity.user_id,)).fetchone()
        if not user or not self.actor_valid(con, row["workspace_id"], identity.user_id, user[0]):
            return None
        code = row["id"].replace("-", "").upper()
        body = (
            resolution["draft"]
            + "\nReply PCASE "
            + code
            + (
                " ACK, PROMISE YYYY-MM-DD, CORRECTED or ESCALATE. Send STOP "
                "to stop supplier follow-ups."
            )
        )
        logical = (
            "passport/"
            + row["id"]
            + "/"
            + view["source_signature"]
            + "/"
            + hashed(body)
            + "/"
            + contact["consent_event"]
        )
        previous = con.execute(
            "SELECT id FROM wa_outbox WHERE logical_key=?", (logical,)
        ).fetchone()
        if previous:
            return previous[0]  # Includes UNKNOWN: never retry an uncertain send.
        outbox = transport.queue(con, logical, contact["phone"], body)
        svc.event(
            con,
            identity,
            row["workspace_id"],
            row["id"],
            "RESOLUTION_QUEUED",
            resolution
            | {
                "delivery": "QUEUED",
                "outbox_id": outbox,
                "phone": contact["phone"],
                "user_version": user[0],
                "consent_event": contact["consent_event"],
            },
        )
        con.execute(
            "UPDATE invoice_passports SET version=version+1 WHERE id=? AND workspace_id=?",
            (row["id"], row["workspace_id"]),
        )
        return outbox

    def permitted(self, con, outbox):
        event = con.execute(
            (
                "SELECT * FROM passport_events WHERE "
                "action='RESOLUTION_QUEUED' AND "
                "json_extract(payload_json,'$.outbox_id')=? ORDER BY sequence "
                "DESC LIMIT 1"
            ),
            (outbox["id"],),
        ).fetchone()
        if event is None:
            return None
        facts = json.loads(event["payload_json"])
        row = self.passports.row(
            con, event["workspace_id"], event["passport_id"], allow_removed=True
        )
        contact = self.contact(con, row)
        if (
            not contact
            or contact["phone"] != outbox["phone"]
            or contact["consent_event"] != facts["consent_event"]
            or int(self.transport.clock()) - contact["last_inbound"] >= 86400
        ):
            return False
        if not self.actor_valid(con, row["workspace_id"], event["actor_id"], facts["user_version"]):
            return False
        view = self.passports.project(con, row)
        return (
            view["source_signature"] == facts["source_signature"]
            and view["findings"]["summary"] != "MATCHED"
        )

    def handle(self, con, event, data):
        svc, transport = self.passports, self.transport
        command = data.get("command")
        if command == "PCONSENT":
            invited = con.execute(
                (
                    "SELECT * FROM passport_events WHERE "
                    "action='SUPPLIER_INVITED' AND "
                    "json_extract(payload_json,'$.code_hash')=? ORDER BY sequence "
                    "DESC LIMIT 1"
                ),
                (data.get("code_hash", ""),),
            ).fetchone()
            if not invited:
                return True
            facts = json.loads(invited["payload_json"])
            now = int(transport.clock())
            used = con.execute(
                (
                    "SELECT 1 FROM passport_events WHERE "
                    "action='SUPPLIER_VERIFIED' AND "
                    "json_extract(payload_json,'$.consent_event')=?"
                ),
                (invited["id"],),
            ).fetchone()
            if (
                used
                or facts["phone"] != event["phone"]
                or facts["expires_at"] <= now
                or data["timestamp"] < invited["created_at"] - 5
                or not self.actor_valid(
                    con, invited["workspace_id"], invited["actor_id"], facts["user_version"]
                )
            ):
                return True
            row = svc.row(con, invited["workspace_id"], invited["passport_id"], allow_removed=True)
            if json.loads(row["extraction_json"]).get("removed_at"):
                return True
            if svc.project(con, row)["source_signature"] != facts["source_signature"]:
                return True
            actor = SimpleNamespace(user_id=invited["actor_id"])
            svc.event(
                con,
                actor,
                row["workspace_id"],
                row["id"],
                "SUPPLIER_VERIFIED",
                {
                    "phone": event["phone"],
                    "last_inbound": min(now, data["timestamp"]),
                    "consent_event": invited["id"],
                    "user_version": facts["user_version"],
                },
            )
            con.execute("UPDATE invoice_passports SET version=version+1 WHERE id=?", (row["id"],))
            # Opt-in opens the existing correction's response window.
            self.queue(con, actor, svc.row(con, row["workspace_id"], row["id"]))
            return True
        if command == "PCASE":
            try:
                pid = str(UUID(data["case_reference"]))
            except (ValueError, KeyError):
                return True
            row = con.execute("SELECT * FROM invoice_passports WHERE id=?", (pid,)).fetchone()
            if row is None:
                return True
            contact = self.contact(con, row)
            if (
                not contact
                or contact["phone"] != event["phone"]
                or data["timestamp"] < contact["last_inbound"]
                or not self.actor_valid(
                    con,
                    row["workspace_id"],
                    self.latest(con, row, ("SUPPLIER_VERIFIED",))[0]["actor_id"],
                    contact["user_version"],
                )
            ):
                return True
            action = data["reply_action"]
            if action == "PROMISE":
                try:
                    promised = date.fromisoformat(data.get("promised_on", ""))
                except ValueError:
                    return True
                if promised < date.fromtimestamp(data["timestamp"]):
                    return True
            verified, _ = self.latest(con, row, ("SUPPLIER_VERIFIED",))
            actor = SimpleNamespace(user_id=verified["actor_id"])
            view = svc.project(con, row)
            if view["resolution"]["state"] == "NOT_STARTED":
                return True
            state = {
                "ACK": "ACKNOWLEDGED",
                "PROMISE": "PROMISED",
                "CORRECTED": "CORRECTION_RECEIVED",
                "ESCALATE": "ESCALATED",
            }[action]
            if (
                view["resolution"]["state"] == "RESOLVED"
                or action == "CORRECTED"
                and view["findings"]["summary"] == "MATCHED"
            ):
                state = "RESOLVED"
            svc.event(
                con,
                actor,
                row["workspace_id"],
                pid,
                "SUPPLIER_VERIFIED",
                contact | {"last_inbound": min(int(transport.clock()), data["timestamp"])},
            )
            svc.event(
                con,
                actor,
                row["workspace_id"],
                pid,
                "RESOLUTION_SUPPLIER_REPLY",
                view["resolution"]
                | {
                    "state": state,
                    "source_signature": view["source_signature"],
                    "reply": action,
                    "promised_on": data.get("promised_on"),
                    "inbound_event": event["event_key"],
                    "reply_at": data["timestamp"],
                },
            )
            con.execute("UPDATE invoice_passports SET version=version+1 WHERE id=?", (pid,))
            return True
        if command == "STOP":
            rows = con.execute(
                (
                    "SELECT * FROM invoice_passports WHERE id IN (SELECT "
                    "passport_id FROM passport_events WHERE "
                    "action='SUPPLIER_VERIFIED' AND "
                    "json_extract(payload_json,'$.phone')=?)"
                ),
                (event["phone"],),
            ).fetchall()
            for row in rows:
                contact = self.contact(con, row)
                if not contact or contact["phone"] != event["phone"]:
                    continue
                verified, _ = self.latest(con, row, ("SUPPLIER_VERIFIED",))
                actor = SimpleNamespace(user_id=verified["actor_id"])
                svc.event(
                    con,
                    actor,
                    row["workspace_id"],
                    row["id"],
                    "SUPPLIER_REVOKED",
                    {"phone": event["phone"]},
                )
                con.execute(
                    "UPDATE invoice_passports SET version=version+1 WHERE id=?", (row["id"],)
                )
                cancelled = con.execute(
                    (
                        "UPDATE wa_outbox SET "
                        "state='CANCELLED',error_code='CONSENT_REVOKED',updated_at=? "
                        "WHERE state='QUEUED' AND id IN (SELECT "
                        "json_extract(payload_json,'$.outbox_id') FROM "
                        "passport_events WHERE passport_id=? AND "
                        "action='RESOLUTION_QUEUED') RETURNING id"
                    ),
                    (int(transport.clock()), row["id"]),
                ).fetchall()
                for outgoing in cancelled:
                    transport.record_delivery(con, outgoing["id"], "CANCELLED")
            return False  # Keep existing STOP handling and its single acknowledgement.
        return False
