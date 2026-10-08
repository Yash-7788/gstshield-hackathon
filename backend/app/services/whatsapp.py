"""Durable verified channel boundary and local linking/outbox controls.

Business commands use existing services; provider I/O never runs inside a DB transaction.
"""

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.adapters.whatsapp import MetaProvider, ProviderError
from app.errors import APIError
from app.security.roles import permitted_roles, require_role
from app.services.access import LinkedIdentity

PHONE = re.compile(r"[1-9][0-9]{6,14}")
CODE = re.compile(r"[A-Z2-7]{12}")
HELP = (
    "GSTShield commands: LINK code, STATUS, UPLOAD PURCHASE, UPLOAD 2B, RUN, REPORT, UNLINK. "
    "Files: CSV/XLSX up to 5 MiB. Review and confirm imports on the local website. "
    "Recorded matches are not legal credit approval; no filing, payment or guaranteed recovery."
)


def hashed(value):
    return hashlib.sha256(value.encode()).hexdigest()


def operation_key(value):
    return str(uuid5(NAMESPACE_URL, "gstshield-whatsapp:" + value))


class WhatsAppService:
    def __init__(self, access, imports, runs, reports, actions, provider=None):
        self.access, self.imports, self.runs = access, imports, runs
        self.reports, self.actions = reports, actions
        self.store, self.settings = access.store, access.settings
        self.provider = provider or MetaProvider(self.settings)
        self.clock = time.time

    def enabled(self):
        if not self.settings.whatsapp_enabled:
            raise APIError(
                503, "CHANNEL_DISABLED", "WhatsApp is not configured; use the local website."
            )

    def rate(self, connection, bucket, limit, seconds):
        now = int(self.clock())
        connection.execute("DELETE FROM wa_rates WHERE expires_at<=?", (now,))
        row = connection.execute("SELECT * FROM wa_rates WHERE bucket=?", (bucket,)).fetchone()
        if row is not None and row["count"] >= limit:
            return False
        if row is None:
            connection.execute("INSERT INTO wa_rates VALUES (?,?,1)", (bucket, now + seconds))
        else:
            connection.execute("UPDATE wa_rates SET count=count+1 WHERE bucket=?", (bucket,))
        return True

    def link_row(self, connection, identifier):
        row = connection.execute(
            "SELECT l.*,u.username FROM wa_links l JOIN users u ON u.id=l.user_id "
            "JOIN memberships m ON m.user_id=l.user_id AND m.workspace_id=l.workspace_id "
            "WHERE l.id=? AND l.active=1 AND u.active=1 AND u.version=l.user_version AND "
            "m.active=1",
            (identifier,),
        ).fetchone()
        if row:
            try:
                require_role(
                    self.access,
                    connection,
                    self.identity(row),
                    row["workspace_id"],
                    {"CA", "FOLLOWUP"},
                )
            except APIError:
                return None
        return row

    def report_allowed(self, connection, link):
        try:
            require_role(
                self.access,
                connection,
                self.identity(link),
                link["workspace_id"],
                permitted_roles("reports", False),
            )
            return True
        except APIError:
            return False

    def identity(self, row):
        return LinkedIdentity(row["user_id"], row["username"], 0, "", "", row["id"], row["version"])

    def context(self, connection, identity, workspace, registration):
        self.access.require_membership(connection, identity, workspace)
        row = connection.execute(
            "SELECT id FROM registrations WHERE workspace_id=? AND id=?", (workspace, registration)
        ).fetchone()
        if row is None:
            raise APIError(404, "NOT_FOUND", "Resource was not found.")

    def code(self, identity, workspace, payload):
        with self.store.transaction(write=False) as connection:
            self.context(connection, identity, workspace, payload["registration_id"])
        self.enabled()
        now = int(self.clock())
        code = "".join(secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567") for _ in range(12))
        with self.store.transaction() as connection:
            self.context(connection, identity, workspace, payload["registration_id"])
            if not self.rate(connection, "code:" + identity.user_id, 5, 600):
                # Commit the existing rate state; do not expose codes.
                result = None
            else:
                connection.execute(
                    "DELETE FROM wa_codes WHERE expires_at<=? OR user_id=?", (now, identity.user_id)
                )
                version = connection.execute(
                    "SELECT version FROM users WHERE id=?", (identity.user_id,)
                ).fetchone()[0]
                connection.execute(
                    "INSERT INTO wa_codes VALUES (?,?,?,?,?,?,?)",
                    (
                        hashed(code),
                        identity.user_id,
                        version,
                        workspace,
                        payload["registration_id"],
                        payload["period"],
                        now + min(self.settings.link_code_ttl_seconds, 600),
                    ),
                )
                result = {
                    "code": code,
                    "expires_at": now + min(self.settings.link_code_ttl_seconds, 600),
                    "registration_id": payload["registration_id"],
                    "period": payload["period"],
                }
        if result is None:
            raise APIError(
                429, "LINK_RATE_LIMIT", "Linking request limit reached.", retry_after=600
            )
        return result

    @staticmethod
    def public_link(row):
        return {
            name: row[name]
            for name in ("id", "workspace_id", "registration_id", "period", "version")
        } | {
            "active": bool(row["active"]),
            "consent_alerts": bool(row["consent_alerts"]),
            "masked_phone": "••••" + row["phone"][-4:],
        }

    def status(self, identity, workspace):
        with self.store.transaction(write=False) as connection:
            self.access.require_membership(connection, identity, workspace)
            row = connection.execute(
                "SELECT * FROM wa_links WHERE user_id=? AND workspace_id=? AND active=1",
                (identity.user_id, workspace),
            ).fetchone()
            live = self.link_row(connection, row["id"]) if row else None
            deliveries = [
                dict(x)
                for x in connection.execute(
                    "SELECT "
                    "o.id,o.state,o.error_code,o.created_at,o.updated_at,"
                    "f.action_id,f.draft_id FROM wa_outbox o "
                    "LEFT JOIN wa_followups f ON f.outbox_id=o.id WHERE o.link_id=? OR "
                    "(f.actor_id=? AND f.workspace_id=?) "
                    "ORDER BY o.created_at DESC,o.id DESC LIMIT 20",
                    (row["id"] if row else "", identity.user_id, workspace),
                )
            ]
            for delivery in deliveries:
                delivery["history"] = [
                    dict(event)
                    for event in connection.execute(
                        "SELECT state,created_at FROM wa_delivery_events WHERE outbox_id=? "
                        "ORDER BY rowid",
                        (delivery["id"],),
                    )
                ]
            remaining = max(
                0,
                self.settings.whatsapp_send_budget
                - connection.execute("SELECT used FROM wa_budget WHERE singleton=1").fetchone()[0],
            )
            return {
                "enabled": self.settings.whatsapp_enabled,
                "sending_enabled": self.settings.whatsapp_enabled and remaining > 0,
                "link": self.public_link(live) if live else None,
                "deliveries": deliveries,
                "remaining_send_budget": remaining,
                "physical_phone_verified": False,
            }

    def record_delivery(self, connection, identifier, state):
        connection.execute(
            "INSERT OR IGNORE INTO wa_delivery_events VALUES (?,?,?,?)",
            (str(uuid4()), identifier, state, int(self.clock())),
        )

    def recover(self, connection):
        connection.execute("UPDATE wa_events SET state='QUEUED' WHERE state='PROCESSING'")
        rows = connection.execute(
            "UPDATE wa_outbox SET state='UNKNOWN',error_code='SEND_INTERRUPTED' WHERE "
            "state='ATTEMPTED' RETURNING id"
        ).fetchall()
        for row in rows:
            self.record_delivery(connection, row["id"], "UNKNOWN")

    def invalidate(self, connection, row, *, revoke=False):
        connection.execute("DELETE FROM wa_intents WHERE link_id=?", (row["id"],))
        connection.execute("UPDATE wa_capabilities SET revoked=1 WHERE link_id=?", (row["id"],))
        connection.execute(
            "UPDATE wa_outbox SET state='CANCELLED',error_code='CONTEXT_CHANGED',updated_at=? "
            "WHERE link_id=? AND state='QUEUED'",
            (int(self.clock()), row["id"]),
        )
        for cancelled in connection.execute(
            "SELECT id FROM wa_outbox WHERE link_id=? AND state='CANCELLED'", (row["id"],)
        ):
            self.record_delivery(connection, cancelled["id"], "CANCELLED")
        connection.execute("UPDATE wa_watches SET state='DONE' WHERE link_id=?", (row["id"],))
        if revoke:
            connection.execute("DELETE FROM wa_codes WHERE user_id=?", (row["user_id"],))
            connection.execute(
                "UPDATE wa_links SET active=0,version=version+1 WHERE id=?", (row["id"],)
            )

    def update(self, identity, workspace, payload, *, revoke=False):
        with self.store.transaction() as connection:
            self.access.require_membership(connection, identity, workspace)
            row = connection.execute(
                "SELECT * FROM wa_links WHERE user_id=? AND workspace_id=? AND active=1",
                (identity.user_id, workspace),
            ).fetchone()
            if row is None:
                raise APIError(404, "NOT_FOUND", "Resource was not found.")
            if row["version"] != payload["expected_version"]:
                raise APIError(
                    409, "STALE_VERSION", "Refresh the current phone link before changing it."
                )
            if not revoke:
                self.context(connection, identity, workspace, payload["registration_id"])
            self.invalidate(connection, row, revoke=revoke)
            if not revoke:
                connection.execute(
                    (
                        "UPDATE wa_links SET "
                        "registration_id=?,period=?,consent_alerts=?,version=version+1 WHERE "
                        "id=?"
                    ),
                    (
                        payload["registration_id"],
                        payload["period"],
                        int(payload["consent_alerts"]),
                        row["id"],
                    ),
                )
        return self.status(identity, workspace)

    def normalize(self, payload):
        if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
            raise APIError(400, "WEBHOOK_INVALID", "Callback is not a supported account event.")
        events = []
        entries = payload.get("entry")
        if not isinstance(entries, list) or not 1 <= len(entries) <= 50:
            raise APIError(400, "WEBHOOK_INVALID", "Callback is not a supported account event.")
        now = int(self.clock())
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("id") != self.settings.meta_waba_id:
                raise APIError(403, "WEBHOOK_ACCOUNT", "Callback account is not permitted.")
            changes = entry.get("changes")
            if not isinstance(changes, list) or not 1 <= len(changes) <= 50:
                raise APIError(400, "WEBHOOK_INVALID", "Callback fields are invalid.")
            for change in changes:
                if not isinstance(change, dict):
                    raise APIError(400, "WEBHOOK_INVALID", "Callback fields are invalid.")
                if change.get("field") != "messages":
                    continue
                value = change.get("value")
                if (
                    not isinstance(value, dict)
                    or value.get("messaging_product") != "whatsapp"
                    or (
                        value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
                    ).get("phone_number_id")
                    != self.settings.meta_phone_number_id
                ):
                    raise APIError(
                        403, "WEBHOOK_ACCOUNT", "Callback sender account is not permitted."
                    )
                for category in ("messages", "statuses"):
                    items = value.get(category, [])
                    if not isinstance(items, list) or len(items) > 100:
                        raise APIError(400, "WEBHOOK_INVALID", "Callback event list is invalid.")
                    for item in items:
                        if not isinstance(item, dict):
                            raise APIError(400, "WEBHOOK_INVALID", "Callback event is invalid.")
                        phone = (
                            item.get("from") if category == "messages" else item.get("recipient_id")
                        )
                        identifier, timestamp = item.get("id"), item.get("timestamp")
                        if (
                            not isinstance(phone, str)
                            or not PHONE.fullmatch(phone)
                            or not isinstance(identifier, str)
                            or not 1 <= len(identifier) <= 256
                            or not isinstance(timestamp, str)
                            or not re.fullmatch(r"[0-9]{1,12}", timestamp)
                            or int(timestamp) > now + 300
                        ):
                            raise APIError(
                                400, "WEBHOOK_INVALID", "Callback identifiers are invalid."
                            )
                        if category == "statuses":
                            state = item.get("status")
                            if not isinstance(state, str):
                                raise APIError(
                                    400, "WEBHOOK_INVALID", "Delivery status is invalid."
                                )
                            if state not in {"sent", "delivered", "read", "failed"}:
                                continue
                            data = {
                                "provider_id": identifier,
                                "status": state,
                                "timestamp": int(timestamp),
                                "logical_id": item.get("biz_opaque_callback_data"),
                            }
                            key = hashed(f"status:{phone}:{identifier}:{state}:{timestamp}")
                            kind = "STATUS"
                        else:
                            key, kind = hashed("inbound:" + identifier), "TEXT"
                            data = {"timestamp": int(timestamp)}
                            if item.get("type") == "text":
                                text = (
                                    item.get("text") if isinstance(item.get("text"), dict) else {}
                                ).get("body")
                                if not isinstance(text, str) or len(text) > 512:
                                    text = "UNSUPPORTED"
                                text = text.strip().upper()
                                if text.startswith(("LINK ", "CONSENT ", "PCONSENT ")):
                                    command, code = text.split(" ", 1)
                                    code = code.strip()
                                    data |= {
                                        "command": command,
                                        "code_hash": hashed(code) if CODE.fullmatch(code) else "",
                                    }
                                elif re.fullmatch(
                                    (
                                        "PCASE [A-F0-9]{32} (ACK|CORRECTED|ESCALATE|PROMISE "
                                        "[0-9]{4}-[0-9]{2}-[0-9]{2})"
                                    ),
                                    text,
                                ):
                                    parts = text.split()
                                    data |= {
                                        "command": "PCASE",
                                        "case_reference": parts[1],
                                        "reply_action": parts[2],
                                        "promised_on": parts[3] if len(parts) == 4 else None,
                                    }
                                else:
                                    data["command"] = (
                                        text
                                        if text
                                        in {
                                            "HELP",
                                            "STATUS",
                                            "UPLOAD PURCHASE",
                                            "UPLOAD 2B",
                                            "RUN",
                                            "REPORT",
                                            "UNLINK",
                                            "STOP",
                                        }
                                        else "UNSUPPORTED"
                                    )
                            elif item.get("type") == "document":
                                document = item.get("document")
                                if not isinstance(document, dict):
                                    raise APIError(
                                        400, "WEBHOOK_INVALID", "Document metadata is invalid."
                                    )
                                kind = "DOCUMENT"
                                data |= {
                                    "media_id": document.get("id"),
                                    "mime": document.get("mime_type"),
                                    "filename": document.get("filename"),
                                }
                                if any(
                                    not isinstance(data[name], str) or len(data[name]) > 256
                                    for name in ("media_id", "mime", "filename")
                                ):
                                    raise APIError(
                                        400, "WEBHOOK_INVALID", "Document metadata is invalid."
                                    )
                            else:
                                data["command"] = "UNSUPPORTED"
                        events.append((key, kind, phone, data))
                        if len(events) > 100:
                            raise APIError(
                                413, "WEBHOOK_LIMIT", "Callback contains too many events."
                            )
        return events

    def ingest(self, payload):
        self.enabled()
        events = self.normalize(payload)
        now = int(self.clock())
        with self.store.transaction() as connection:
            for key, kind, phone, data in events:
                if connection.execute(
                    "SELECT 1 FROM wa_events WHERE event_key=?", (key,)
                ).fetchone():
                    continue
                if connection.execute("SELECT count(*) FROM wa_events").fetchone()[0] >= 10000:
                    raise APIError(
                        503,
                        "CHANNEL_CAPACITY",
                        "Channel history is full; contact the operator.",
                        retry_after=60,
                    )
                link = connection.execute(
                    "SELECT * FROM wa_links WHERE phone=? AND active=1", (phone,)
                ).fetchone()
                if link and kind != "STATUS":
                    connection.execute(
                        "UPDATE wa_links SET last_inbound=max(last_inbound,?) WHERE id=?",
                        (min(now, data["timestamp"]), link["id"]),
                    )
                connection.execute(
                    "INSERT INTO wa_events VALUES (?,?,?,?,?,?, 'QUEUED',NULL,?)",
                    (
                        key,
                        kind,
                        phone,
                        json.dumps(data),
                        link["id"] if link else None,
                        link["version"] if link else None,
                        now,
                    ),
                )
        return {"accepted": True}

    def queue(self, connection, logical_key, phone, body, link=None):
        previous = connection.execute(
            "SELECT id FROM wa_outbox WHERE logical_key=?", (logical_key,)
        ).fetchone()
        if previous:
            return previous[0]
        if connection.execute("SELECT count(*) FROM wa_outbox").fetchone()[0] >= 5000:
            raise APIError(409, "CHANNEL_CAPACITY", "Channel delivery history is full.")
        identifier, now = str(uuid4()), int(self.clock())
        if len(body) > 3500:
            raise APIError(422, "CHANNEL_MESSAGE_LIMIT", "Channel reply exceeds the allowed size.")
        connection.execute(
            "INSERT INTO wa_outbox VALUES (?,?,?,?,?,?,'QUEUED',NULL,NULL,?,NULL,?)",
            (
                identifier,
                logical_key,
                link["id"] if link else None,
                link["version"] if link else None,
                phone,
                body,
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO wa_delivery_events VALUES (?,?,'QUEUED',?)",
            (str(uuid4()), identifier, now),
        )
        return identifier

    def token(self, outbox_id):
        # A random outbox UUID plus secret-key PRF produces an unguessable bearer token.
        raw = hmac.new(
            self.settings.meta_app_secret.get_secret_value().encode(),
            ("gstshield-download-v1:" + outbox_id).encode(),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    def capability(self, connection, link, artifact_id, outbox_id):
        if not self.report_allowed(connection, link):
            raise APIError(403, "ROLE_FORBIDDEN", "Your current role cannot receive this report.")
        token = self.token(outbox_id)
        connection.execute(
            "INSERT OR IGNORE INTO wa_capabilities VALUES (?,?,?,?,?,0,0)",
            (
                hashed(token),
                link["id"],
                link["version"],
                artifact_id,
                int(self.clock()) + min(self.settings.download_capability_ttl_seconds, 600),
            ),
        )
        return token

    def download(self, token):
        self.enabled()
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise APIError(404, "NOT_FOUND", "Report link is unavailable.")
        with self.store.transaction() as connection:
            cap = connection.execute(
                "SELECT * FROM wa_capabilities WHERE token_hash=?", (hashed(token),)
            ).fetchone()
            link = self.link_row(connection, cap["link_id"]) if cap else None
            if (
                cap is None
                or link is None
                or not self.report_allowed(connection, link)
                or cap["revoked"]
                or cap["expires_at"] <= int(self.clock())
                or cap["link_version"] != link["version"]
                or cap["downloads"] >= min(self.settings.download_capability_max_downloads, 3)
            ):
                raise APIError(404, "NOT_FOUND", "Report link is unavailable.")
            row = self.reports.scoped(
                connection, "artifacts", link["workspace_id"], cap["artifact_id"]
            )
            if (
                row["state"] != "READY"
                or row["expires_at"] <= int(self.clock())
                or not self.reports.current(connection, row)
            ):
                raise APIError(404, "NOT_FOUND", "Report link is unavailable.")
            content = row["content"]
            if (
                row["kind"] != "RECONCILIATION_PDF"
                or len(content) > self.settings.max_artifact_bytes
                or len(content) != row["size_bytes"]
                or hashlib.sha256(content).hexdigest() != row["sha256"]
            ):
                raise APIError(404, "NOT_FOUND", "Report link is unavailable.")
            connection.execute(
                "UPDATE wa_capabilities SET downloads=downloads+1 WHERE token_hash=?",
                (hashed(token),),
            )
            return content, row["filename"]

    def consume_link(self, connection, event, data):
        now = int(self.clock())
        allowed = self.rate(
            connection,
            "link:" + hashed(event["phone"]),
            self.settings.link_attempts_per_window,
            min(self.settings.link_attempt_window_seconds, 600),
        )
        allowed = self.rate(connection, "link:global", 50, 600) and allowed
        code = (
            connection.execute(
                "SELECT c.* FROM wa_codes c JOIN users u ON u.id=c.user_id JOIN memberships m "
                "ON m.user_id=c.user_id AND m.workspace_id=c.workspace_id WHERE c.code_hash=? "
                "AND c.expires_at>? AND u.active=1 AND u.version=c.user_version AND m.active=1",
                (data["code_hash"], now),
            ).fetchone()
            if allowed
            else None
        )
        occupied = connection.execute(
            "SELECT 1 FROM wa_links WHERE active=1 AND (phone=? OR user_id=?)",
            (event["phone"], code["user_id"] if code else ""),
        ).fetchone()
        if code is None or occupied:
            self.queue(
                connection,
                event["event_key"],
                event["phone"],
                (
                    "Link unavailable. Generate a fresh code on the website or unlink "
                    "the existing phone first."
                ),
            )
            return
        connection.execute("DELETE FROM wa_codes WHERE code_hash=?", (data["code_hash"],))
        identifier = str(uuid4())
        connection.execute(
            "INSERT INTO wa_links VALUES (?,?,?,?,?,?,?,1,1,0,?,?)",
            (
                identifier,
                code["user_id"],
                code["user_version"],
                code["workspace_id"],
                code["registration_id"],
                code["period"],
                event["phone"],
                min(now, data["timestamp"]),
                now,
            ),
        )
        row = self.link_row(connection, identifier)
        self.queue(
            connection,
            event["event_key"],
            event["phone"],
            "Phone linked. " + self.context_label(connection, row) + " " + HELP,
            row,
        )

    def context_label(self, connection, link):
        registration = connection.execute(
            "SELECT gstin FROM registrations WHERE id=? AND workspace_id=?",
            (link["registration_id"], link["workspace_id"]),
        ).fetchone()
        return (
            ("SAMPLE MODE · " if self.settings.demo_mode else "")
            + "GSTIN ending "
            + registration[0][-4:]
            + " · "
            + link["period"]
            + "."
        )

    def process_status(self, connection, event, data):
        row = connection.execute(
            "SELECT * FROM wa_outbox WHERE provider_id=? AND phone=?",
            (data["provider_id"], event["phone"]),
        ).fetchone()
        if row is None and isinstance(data.get("logical_id"), str):
            row = connection.execute(
                (
                    "SELECT * FROM wa_outbox WHERE id=? AND phone=? AND state IN "
                    "('ATTEMPTED','UNKNOWN')"
                ),
                (data["logical_id"], event["phone"]),
            ).fetchone()
        if row is None:
            return
        target = {
            "sent": "ACKNOWLEDGED",
            "delivered": "DELIVERED",
            "read": "READ",
            "failed": "FAILED",
        }[data["status"]]
        ranks = {
            "ATTEMPTED": 0,
            "UNKNOWN": 0,
            "ACKNOWLEDGED": 1,
            "FAILED": 2,
            "DELIVERED": 3,
            "READ": 4,
        }
        if row["state"] not in ranks or ranks[target] < ranks[row["state"]]:
            return
        connection.execute(
            (
                "UPDATE wa_outbox SET "
                "state=?,provider_id=coalesce(provider_id,?),error_code=?,updated_at=? WHERE id=?"
            ),
            (
                target,
                data["provider_id"],
                "PROVIDER_DELIVERY_FAILED" if target == "FAILED" else None,
                int(self.clock()),
                row["id"],
            ),
        )
        connection.execute(
            "INSERT OR IGNORE INTO wa_delivery_events VALUES (?,?,?,?)",
            (str(uuid4()), row["id"], target, int(self.clock())),
        )

    def send_one(self):
        if not self.settings.whatsapp_enabled or not self.settings.whatsapp_send_budget:
            return False
        from app.services.whatsapp_followups import WhatsAppFollowups

        now = int(self.clock())
        with self.store.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM wa_outbox WHERE state='QUEUED' ORDER BY created_at,id LIMIT 1"
            ).fetchone()
            if row is None:
                return False
            link = self.link_row(connection, row["link_id"]) if row["link_id"] else None
            if row["link_id"]:
                valid = (
                    link is not None
                    and link["version"] == row["link_version"]
                    and now - link["last_inbound"] < 86400
                )
            else:
                last = connection.execute(
                    (
                        "SELECT payload FROM wa_events WHERE phone=? AND kind!='STATUS' "
                        "ORDER BY received_at DESC,event_key DESC LIMIT 1"
                    ),
                    (row["phone"],),
                ).fetchone()
                adapter = getattr(self, "passport_channel", None)
                supplier = adapter.permitted(connection, row) if adapter else None
                if supplier is None:
                    supplier = WhatsAppFollowups(self).permitted(connection, row)
                valid = (
                    supplier
                    if supplier is not None
                    else (last is not None and now - json.loads(last[0])["timestamp"] < 86400)
                )
            if not valid:
                connection.execute(
                    (
                        "UPDATE wa_outbox SET "
                        "state='CANCELLED',error_code='RECIPIENT_UNAVAILABLE',updated_at=? "
                        "WHERE id=?"
                    ),
                    (now, row["id"]),
                )
                self.record_delivery(connection, row["id"], "CANCELLED")
                return True
            used = connection.execute("SELECT used FROM wa_budget WHERE singleton=1").fetchone()[0]
            if used >= self.settings.whatsapp_send_budget:
                return False
            connection.execute("UPDATE wa_budget SET used=used+1 WHERE singleton=1")
            connection.execute(
                "UPDATE wa_outbox SET state='ATTEMPTED',attempted_at=?,updated_at=? WHERE id=?",
                (now, now, row["id"]),
            )
            body = row["body"]
            if "{report_link}" in body:
                cap = connection.execute(
                    "SELECT * FROM wa_capabilities WHERE token_hash=?",
                    (hashed(self.token(row["id"])),),
                ).fetchone()
                if cap is None or cap["expires_at"] <= now or cap["revoked"]:
                    connection.execute(
                        (
                            "UPDATE wa_outbox SET "
                            "state='CANCELLED',error_code='CAPABILITY_EXPIRED',updated_at=? "
                            "WHERE id=?"
                        ),
                        (now, row["id"]),
                    )
                    self.record_delivery(connection, row["id"], "CANCELLED")
                    return True
                body = body.replace(
                    "{report_link}",
                    self.settings.whatsapp_public_url + "/wa/reports/" + self.token(row["id"]),
                )
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO wa_delivery_events VALUES (?,?,'ATTEMPTED',?)",
                (str(uuid4()), row["id"], now),
            )
        try:
            provider_id = self.provider.send(row["phone"], body, row["id"])
            state, error = "ACKNOWLEDGED", None
        except ProviderError as exc:
            provider_id, state, error = None, "UNKNOWN" if exc.uncertain else "FAILED", exc.code
        with self.store.transaction() as connection:
            # A status callback may already have moved ATTEMPTED to DELIVERED/READ.
            connection.execute(
                (
                    "UPDATE wa_outbox SET "
                    "state=?,provider_id=?,error_code=?,updated_at=? WHERE id=? AND "
                    "state='ATTEMPTED'"
                ),
                (state, provider_id, error, int(self.clock()), row["id"]),
            )
        with self.store.transaction() as connection:
            actual = connection.execute(
                "SELECT state FROM wa_outbox WHERE id=?", (row["id"],)
            ).fetchone()[0]
            connection.execute(
                "INSERT OR IGNORE INTO wa_delivery_events VALUES (?,?,?,?)",
                (str(uuid4()), row["id"], actual, int(self.clock())),
            )
        return True
