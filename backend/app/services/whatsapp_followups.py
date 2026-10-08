"""Supplier consent is draft-specific; it grants no buyer workspace or report access."""

import json
import secrets
from uuid import uuid4

from app.errors import APIError
from app.services.whatsapp import PHONE, hashed


class WhatsAppFollowups:
    def __init__(self, channel):
        self.channel = channel

    def draft(self, connection, identity, workspace, payload):
        channel = self.channel
        channel.access.require_membership(
            connection, identity, workspace, roles={"OWNER", "REVIEWER"}
        )
        action = channel.actions.row(connection, workspace, payload["action_id"])
        channel.actions.version(action, payload["expected_version"])
        channel.actions.ensure_current(connection, action)
        if action["state"] == "CLOSED":
            raise APIError(409, "ACTION_CLOSED", "Reopen the action before sending a follow-up.")
        draft = connection.execute(
            (
                "SELECT * FROM action_events WHERE workspace_id=? AND action_id=? "
                "AND id=? AND kind='FOLLOWUP_DRAFT'"
            ),
            (workspace, action["id"], payload["draft_id"]),
        ).fetchone()
        if draft is None:
            raise APIError(422, "INVALID_DRAFT", "Choose a saved draft for this action.")
        snapshot = json.loads(draft["snapshot_json"])
        phone = snapshot["contact"].removeprefix("+")
        if not PHONE.fullmatch(phone):
            raise APIError(
                422,
                "RECIPIENT_PHONE",
                "The saved draft needs a full international WhatsApp number.",
            )
        return action, draft, snapshot, phone

    def code(self, identity, workspace, payload):
        channel = self.channel
        with channel.store.transaction(write=False) as connection:
            channel.access.require_membership(
                connection, identity, workspace, roles={"OWNER", "REVIEWER"}
            )
        channel.enabled()
        code = "".join(secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567") for _ in range(12))
        now = int(channel.clock())
        with channel.store.transaction() as connection:
            action, draft, snapshot, phone = self.draft(connection, identity, workspace, payload)
            if not channel.rate(connection, "consent-code:" + identity.user_id, 5, 600):
                result = None
            else:
                connection.execute(
                    "DELETE FROM wa_consent_codes WHERE expires_at<=? OR draft_id=?",
                    (now, draft["id"]),
                )
                connection.execute(
                    "UPDATE wa_recipients SET active=0 WHERE draft_id=?", (draft["id"],)
                )
                version = connection.execute(
                    "SELECT version FROM users WHERE id=?", (identity.user_id,)
                ).fetchone()[0]
                connection.execute(
                    "INSERT INTO wa_consent_codes VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        hashed(code),
                        workspace,
                        identity.user_id,
                        version,
                        action["id"],
                        draft["id"],
                        action["version"],
                        phone,
                        now + 600,
                    ),
                )
                result = {
                    "code": code,
                    "expires_at": now + 600,
                    "masked_phone": "••••" + phone[-4:],
                    "draft_id": draft["id"],
                }
        if result is None:
            raise APIError(
                429, "LINK_RATE_LIMIT", "Consent request limit reached.", retry_after=600
            )
        return result

    def consume(self, connection, event, data):
        channel = self.channel
        now = int(channel.clock())
        allowed = channel.rate(connection, "consent:" + hashed(event["phone"]), 5, 600)
        allowed = channel.rate(connection, "consent:global", 50, 600) and allowed
        code = (
            connection.execute(
                "SELECT * FROM wa_consent_codes WHERE code_hash=? AND phone=? AND expires_at>?",
                (data["code_hash"], event["phone"], now),
            ).fetchone()
            if allowed
            else None
        )
        if code:
            user = connection.execute(
                "SELECT active,version FROM users WHERE id=?", (code["user_id"],)
            ).fetchone()
            member = connection.execute(
                "SELECT role FROM memberships WHERE workspace_id=? AND user_id=? AND active=1",
                (code["workspace_id"], code["user_id"]),
            ).fetchone()
            action = channel.actions.row(connection, code["workspace_id"], code["action_id"])
            valid = (
                user["active"]
                and user["version"] == code["user_version"]
                and member is not None
                and member["role"] in {"OWNER", "REVIEWER"}
                and action["state"] != "CLOSED"
                and action["version"] == code["action_version"]
                and channel.actions.current(connection, action)
                and now - data["timestamp"] < 600
            )
        else:
            valid = False
        if not valid:
            channel.queue(
                connection,
                event["event_key"],
                event["phone"],
                (
                    "Consent code unavailable. Ask the requester for a fresh code. No "
                    "account access was granted."
                ),
            )
            return
        connection.execute("DELETE FROM wa_consent_codes WHERE code_hash=?", (data["code_hash"],))
        connection.execute(
            "INSERT INTO wa_recipients VALUES (?,?,?,?,?,?,?,?,?,?,1)",
            (
                str(uuid4()),
                code["workspace_id"],
                code["user_id"],
                code["user_version"],
                code["action_id"],
                code["draft_id"],
                code["action_version"],
                code["phone"],
                now,
                min(now, data["timestamp"]),
            ),
        )
        channel.queue(
            connection,
            event["event_key"],
            event["phone"],
            (
                "Consent recorded for one saved supplier follow-up draft. This does "
                "not grant access to the buyer workspace or reports. Reply STOP to "
                "revoke consent."
            ),
        )

    def recipients(self, identity, workspace):
        channel = self.channel
        with channel.store.transaction(write=False) as connection:
            channel.access.require_membership(
                connection, identity, workspace, roles={"OWNER", "REVIEWER"}
            )
            return [
                {
                    "id": row["id"],
                    "action_id": row["action_id"],
                    "draft_id": row["draft_id"],
                    "masked_phone": "••••" + row["phone"][-4:],
                    "verified_at": row["verified_at"],
                }
                for row in connection.execute(
                    (
                        "SELECT * FROM wa_recipients WHERE workspace_id=? AND user_id=? AND "
                        "active=1 ORDER BY verified_at DESC,id LIMIT 20"
                    ),
                    (workspace, identity.user_id),
                )
            ]

    def send(self, identity, workspace, payload):
        channel = self.channel
        with channel.store.transaction(write=False) as connection:
            channel.access.require_membership(
                connection, identity, workspace, roles={"OWNER", "REVIEWER"}
            )
        channel.enabled()
        if not channel.settings.whatsapp_send_budget:
            raise APIError(
                409,
                "SEND_DISABLED",
                "Verify the provider entitlement and configure a send budget first.",
            )
        now = int(channel.clock())
        with channel.store.transaction() as connection:
            channel.access.require_membership(
                connection, identity, workspace, roles={"OWNER", "REVIEWER"}
            )
            recipient = connection.execute(
                (
                    "SELECT * FROM wa_recipients WHERE id=? AND workspace_id=? AND "
                    "user_id=? AND action_id=? AND draft_id=?"
                ),
                (
                    payload["recipient_id"],
                    workspace,
                    identity.user_id,
                    payload["action_id"],
                    payload["draft_id"],
                ),
            ).fetchone()
            if recipient is None:
                raise APIError(404, "NOT_FOUND", "Recipient proof was not found.")
            previous = connection.execute(
                (
                    "SELECT o.* FROM wa_outbox o JOIN wa_followups f ON f.outbox_id=o.id "
                    "WHERE f.recipient_id=?"
                ),
                (recipient["id"],),
            ).fetchone()
            if previous:
                return {
                    key: previous[key]
                    for key in ("id", "state", "error_code", "created_at", "updated_at")
                }
            action, draft, snapshot, phone = self.draft(connection, identity, workspace, payload)
            version = connection.execute(
                "SELECT version FROM users WHERE id=? AND active=1", (identity.user_id,)
            ).fetchone()
            if (
                not recipient["active"]
                or version is None
                or version[0] != recipient["user_version"]
                or recipient["phone"] != phone
                or recipient["action_version"] != action["version"]
                or now - recipient["last_inbound"] >= 86400
            ):
                raise APIError(
                    409,
                    "RECIPIENT_UNVERIFIED",
                    "Obtain fresh recipient consent for the unchanged draft.",
                )
            body = (
                "GSTShield supplier request. "
                + snapshot["text"]
                .removesuffix("This is a draft request; no message has been sent.")
                .strip()
            )
            identifier = channel.queue(connection, "supplier:" + recipient["id"], phone, body)
            connection.execute(
                "INSERT INTO wa_followups VALUES (?,?,?,?,?,?,?)",
                (
                    identifier,
                    recipient["id"],
                    workspace,
                    action["id"],
                    draft["id"],
                    identity.user_id,
                    action["signature"],
                ),
            )
            connection.execute(
                "UPDATE business_actions SET version=version+1,updated_at=? WHERE id=?",
                (now, action["id"]),
            )
            channel.actions.event(
                connection,
                channel.actions.row(connection, workspace, action["id"]),
                "CHANNEL_FOLLOWUP_QUEUED",
                "Consented supplier follow-up queued; not delivered or corrected.",
                {
                    "draft_id": draft["id"],
                    "outbox_id": identifier,
                    "delivery": "QUEUED",
                    "masked_phone": "••••" + phone[-4:],
                },
                actor=identity.user_id,
                request_id="WHATSAPP",
            )
            return {
                "id": identifier,
                "state": "QUEUED",
                "error_code": None,
                "created_at": now,
                "updated_at": now,
            }

    def permitted(self, connection, outbox):
        channel = self.channel
        row = connection.execute(
            (
                "SELECT r.*,f.source_signature FROM wa_followups f JOIN "
                "wa_recipients r ON r.id=f.recipient_id WHERE f.outbox_id=?"
            ),
            (outbox["id"],),
        ).fetchone()
        if row is None:
            return None
        user = connection.execute(
            "SELECT active,version FROM users WHERE id=?", (row["user_id"],)
        ).fetchone()
        member = connection.execute(
            "SELECT role FROM memberships WHERE workspace_id=? AND user_id=? AND active=1",
            (row["workspace_id"], row["user_id"]),
        ).fetchone()
        action = channel.actions.row(connection, row["workspace_id"], row["action_id"])
        return (
            row["active"]
            and user["active"]
            and user["version"] == row["user_version"]
            and member is not None
            and member["role"] in {"OWNER", "REVIEWER"}
            and action["state"] != "CLOSED"
            and action["signature"] == row["source_signature"]
            and channel.actions.current(connection, action)
            and row["phone"] == outbox["phone"]
            and int(channel.clock()) - row["last_inbound"] < 86400
        )
