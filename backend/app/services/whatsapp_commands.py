"""Thin channel command adapter over the existing business services."""

import json
import re

from app.adapters.whatsapp import ProviderError
from app.errors import APIError
from app.security.roles import permitted_roles, require_role
from app.services.whatsapp import HELP, operation_key

MIMES = {
    ".csv": ({"text/csv", "text/plain"}, "csv-v1"),
    ".xlsx": ({"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}, "xlsx-v1"),
}


class WhatsAppCommands:
    def __init__(self, channel):
        self.channel = channel

    def authorize_command(self, connection, identity, workspace, event, command):
        # The phone channel must enforce the same assigned-role policy as HTTP.
        suffix = (
            "imports"
            if event["kind"] == "DOCUMENT" or command in {"UPLOAD PURCHASE", "UPLOAD 2B"}
            else "runs"
            if command == "RUN"
            else "reports"
            if command == "REPORT"
            else "runs"
            if command == "STATUS"
            else None
        )
        if suffix:
            require_role(
                self.channel.access,
                connection,
                identity,
                workspace,
                permitted_roles(suffix, command != "STATUS"),
            )

    def prepare(self, connection, event, data, link):
        channel = self.channel
        identity = channel.identity(link)
        command = data.get("command")
        self.authorize_command(connection, identity, link["workspace_id"], event, command)
        if "prepared" in data:
            return data["prepared"]
        if event["kind"] == "DOCUMENT":
            channel.access.require_membership(
                connection, identity, link["workspace_id"], roles={"OWNER", "REVIEWER"}
            )
            intent = connection.execute(
                "SELECT * FROM wa_intents WHERE link_id=?", (link["id"],)
            ).fetchone()
            if (
                intent is None
                or intent["link_version"] != link["version"]
                or intent["expires_at"] <= int(channel.clock())
                or intent["event_key"] not in {None, event["event_key"]}
            ):
                raise APIError(
                    409, "UPLOAD_INTENT_REQUIRED", "Choose UPLOAD PURCHASE or UPLOAD 2B first."
                )
            filename = data["filename"]
            extension = next((x for x in MIMES if filename.lower().endswith(x)), None)
            if (
                extension is None
                or data["mime"] not in MIMES[extension][0]
                or len(filename) > 128
                or any(ord(c) < 32 or ord(c) == 127 for c in filename)
                or "/" in filename
                or "\\" in filename
                or not re.fullmatch(r"[0-9]{1,40}", data["media_id"])
            ):
                raise APIError(
                    422, "MEDIA_TYPE", "Use a named CSV/XLSX document of the supported type."
                )
            prepared = {
                "kind": intent["kind"],
                "registration_id": link["registration_id"],
                "period": link["period"],
                "adapter_version": MIMES[extension][1],
                "sheet_name": None,
                "mapping": {},
                "supersedes_import_id": None,
            }
            connection.execute(
                "UPDATE wa_intents SET event_key=? WHERE link_id=?",
                (event["event_key"], link["id"]),
            )
        elif command in {"RUN", "REPORT"}:
            channel.access.require_membership(
                connection, identity, link["workspace_id"], roles={"OWNER", "REVIEWER"}
            )
            if command == "RUN":
                sources = {}
                for kind in ("PURCHASE", "PORTAL_2B"):
                    rows = connection.execute(
                        "SELECT id FROM imports WHERE workspace_id=? AND registration_id=? "
                        "AND period=? "
                        "AND kind=? AND state='READY' ORDER BY created_at DESC,id DESC LIMIT 2",
                        (link["workspace_id"], link["registration_id"], link["period"], kind),
                    ).fetchall()
                    if len(rows) > 1:
                        raise APIError(
                            409,
                            "SOURCE_SELECTION_REQUIRED",
                            "Multiple confirmed sources exist; choose them on the website.",
                        )
                    row = rows[0] if rows else None
                    if row is None:
                        raise APIError(
                            409,
                            "SOURCE_CONFIRMATION_REQUIRED",
                            "Confirm both sources on the website first.",
                        )
                    sources[kind] = row[0]
                prepared = {
                    "registration_id": link["registration_id"],
                    "period": link["period"],
                    "purchase_import_id": sources["PURCHASE"],
                    "portal_import_id": sources["PORTAL_2B"],
                }
            else:
                row = connection.execute(
                    "SELECT * FROM runs WHERE workspace_id=? AND registration_id=? AND period=? "
                    "AND state='COMPLETED' ORDER BY revision DESC LIMIT 1",
                    (link["workspace_id"], link["registration_id"], link["period"]),
                ).fetchone()
                if row is None:
                    raise APIError(409, "RUN_REQUIRED", "Complete a comparison first.")
                prepared = {
                    "kind": "RECONCILIATION_PDF",
                    "source_id": row["id"],
                    "expected_version": row["version"],
                    "selected_result_ids": [],
                }
        else:
            return None
        data["prepared"] = prepared
        connection.execute(
            "UPDATE wa_events SET payload=? WHERE event_key=?",
            (json.dumps(data), event["event_key"]),
        )
        return prepared

    def execute(self, event):
        channel = self.channel
        data = json.loads(event["payload"])
        with channel.store.transaction() as connection:
            if event["kind"] == "STATUS":
                channel.process_status(connection, event, data)
                return
            command = data.get("command")
            if int(channel.clock()) - data["timestamp"] >= 86400:
                # Acknowledge old callbacks without new private effects or spending.
                return
            adapter = getattr(channel, "passport_channel", None)
            if adapter and adapter.handle(connection, event, data):
                return
            if command in {"CONSENT", "STOP"}:
                from app.services.whatsapp_followups import WhatsAppFollowups

                if command == "CONSENT":
                    WhatsAppFollowups(channel).consume(connection, event, data)
                else:
                    connection.execute(
                        "UPDATE wa_recipients SET active=0 WHERE phone=?", (event["phone"],)
                    )
                    cancelled = connection.execute(
                        "UPDATE wa_outbox SET state='CANCELLED',error_code='CONSENT_REVOKED',"
                        "updated_at=? "
                        "WHERE state='QUEUED' AND id IN (SELECT f.outbox_id FROM wa_followups f "
                        "JOIN wa_recipients r ON r.id=f.recipient_id WHERE r.phone=?) RETURNING id",
                        (int(channel.clock()), event["phone"]),
                    ).fetchall()
                    for row in cancelled:
                        channel.record_delivery(connection, row["id"], "CANCELLED")
                    channel.queue(
                        connection,
                        event["event_key"],
                        event["phone"],
                        (
                            "Supplier follow-up consent revoked. Existing buyer links are "
                            "unchanged; use UNLINK to revoke those."
                        ),
                    )
                return
            if command == "LINK":
                channel.consume_link(connection, event, data)
                return
            link = channel.link_row(connection, event["link_id"]) if event["link_id"] else None
            if link is None or link["version"] != event["link_version"]:
                channel.queue(
                    connection,
                    event["event_key"],
                    event["phone"],
                    "Link unavailable. Generate LINK code on the website. " + HELP,
                )
                return
            identity = channel.identity(link)
            channel.access.require_membership(connection, identity, link["workspace_id"])
            self.authorize_command(connection, identity, link["workspace_id"], event, command)
            context = channel.context_label(connection, link)
            if command == "UNLINK":
                channel.invalidate(connection, link, revoke=True)
                channel.queue(
                    connection,
                    event["event_key"],
                    event["phone"],
                    "Phone unlinked. Existing report links and pending phone actions are revoked.",
                )
                return
            if command in {"HELP", "UNSUPPORTED"}:
                channel.queue(
                    connection, event["event_key"], event["phone"], context + " " + HELP, link
                )
                return
            if command in {"UPLOAD PURCHASE", "UPLOAD 2B"}:
                channel.access.require_membership(
                    connection, identity, link["workspace_id"], roles={"OWNER", "REVIEWER"}
                )
                kind = "PURCHASE" if command == "UPLOAD PURCHASE" else "PORTAL_2B"
                connection.execute(
                    "INSERT INTO wa_intents VALUES (?,?,?,?,NULL) ON CONFLICT(link_id) DO UPDATE "
                    "SET "
                    "link_version=excluded.link_version,kind=excluded.kind,expires_at=excluded.expires_at,event_key=NULL",
                    (link["id"], link["version"], kind, int(channel.clock()) + 600),
                )
                channel.queue(
                    connection,
                    event["event_key"],
                    event["phone"],
                    context
                    + " Next CSV/XLSX is "
                    + kind
                    + (
                        "; intent expires in 10 minutes. Review and confirm on the website. "
                        "Uploaded 2B is a snapshot, not government verification."
                    ),
                    link,
                )
                return
            if command == "STATUS":
                imports = connection.execute(
                    "SELECT id,kind,state,accepted_rows,rejected_rows FROM imports "
                    "WHERE workspace_id=? AND registration_id=? AND period=? ORDER BY "
                    "created_at DESC,id DESC LIMIT 4",
                    (link["workspace_id"], link["registration_id"], link["period"]),
                ).fetchall()
                run = connection.execute(
                    (
                        "SELECT * FROM runs WHERE workspace_id=? AND registration_id=? AND "
                        "period=? ORDER BY revision DESC LIMIT 1"
                    ),
                    (link["workspace_id"], link["registration_id"], link["period"]),
                ).fetchone()
                body = (
                    context
                    + " "
                    + "; ".join(
                        (
                            f"{x['kind']} {x['id']}: {x['state']}, {x['accepted_rows']} valid, "
                            f"{x['rejected_rows']} rejected"
                        )
                        for x in imports
                    )
                )
                if run:
                    body += f". Run {run['id']}: {run['state']}."
                    if run["summary_json"]:
                        summary = json.loads(run["summary_json"])
                        body += " Counts: " + ", ".join(
                            f"{key}={value}" for key, value in summary["counts"].items()
                        )
                        body += (
                            ". Recorded GST needing review: INR "
                            + summary["tax_exposure_review"]
                            + "; unknown rows="
                            + str(summary["unknown_tax_exposure_rows"])
                            + "."
                        )
                    if not channel.runs.sources_current(connection, run):
                        body += " Evidence changed; this comparison is historical."
                else:
                    body += ". No saved comparison yet."
                body += " Reconciliation is not confirmed ITC eligibility."
                channel.queue(connection, event["event_key"], event["phone"], body, link)
                return
            prepared = self.prepare(connection, event, data, link)
        if event["kind"] == "DOCUMENT":
            # After a crash, an existing operation receipt avoids re-fetching expired media.
            with channel.store.transaction(write=False) as connection:
                prior = connection.execute(
                    (
                        "SELECT import_id FROM import_operations WHERE workspace_id=? AND "
                        "actor_id=? AND route='upload' AND key=?"
                    ),
                    (link["workspace_id"], identity.user_id, operation_key(event["event_key"])),
                ).fetchone()
            if prior:
                receipt = channel.imports.detail(identity, link["workspace_id"], prior[0])
            else:
                content = channel.provider.media(data["media_id"], data["mime"])
                if (
                    not isinstance(content, bytes)
                    or not 0 < len(content) <= channel.settings.max_upload_bytes
                ):
                    raise APIError(413, "MEDIA_SIZE", "Document exceeds the supported size.")
                receipt = channel.imports.upload(
                    identity,
                    link["workspace_id"],
                    prepared,
                    content,
                    data["filename"],
                    operation_key(event["event_key"]),
                    event["event_key"],
                )
            kind, identifier = "IMPORT", receipt["id"]
            body = context + (
                f" Import {identifier} received: {receipt['state']}. Parsing does not "
                f"confirm it; review the preview on the local website."
            )
        elif command == "RUN":
            receipt = channel.runs.create(
                identity,
                link["workspace_id"],
                prepared,
                operation_key(event["event_key"]),
                event["event_key"],
            )
            kind, identifier = None, receipt["id"]
            body = context + (
                f" Comparison {identifier} queued; use STATUS for current results or "
                f"open the website."
            )
        elif command == "REPORT":
            receipt = channel.reports.create(
                identity,
                link["workspace_id"],
                prepared,
                operation_key(event["event_key"]),
                event["event_key"],
            )
            kind, identifier = "ARTIFACT", receipt["id"]
            body = context + (
                f" Report {identifier} requested. A report is not a filed return or "
                f"recovered money."
            )
        else:
            raise APIError(422, "COMMAND_UNSUPPORTED", "Use HELP for supported commands.")
        with channel.store.transaction() as connection:
            current = channel.link_row(connection, link["id"])
            if current is None or current["version"] != link["version"]:
                # Authorized processing survives; obsolete notifications do not.
                return
            channel.queue(connection, event["event_key"], event["phone"], body, current)
            if kind:
                connection.execute(
                    "INSERT OR IGNORE INTO wa_watches VALUES (?,?,?,?,?,'PENDING',?)",
                    (
                        event["event_key"] + ":complete",
                        link["id"],
                        link["version"],
                        kind,
                        identifier,
                        int(channel.clock()),
                    ),
                )
            if event["kind"] == "DOCUMENT":
                connection.execute(
                    "DELETE FROM wa_intents WHERE link_id=? AND event_key=?",
                    (link["id"], event["event_key"]),
                )

    def process_one(self):
        channel = self.channel
        with channel.store.transaction() as connection:
            event = connection.execute(
                "SELECT * FROM wa_events WHERE state='QUEUED' ORDER BY received_at,rowid LIMIT 1"
            ).fetchone()
            if event is None:
                return False
            connection.execute(
                "UPDATE wa_events SET state='PROCESSING' WHERE event_key=?", (event["event_key"],)
            )
        try:
            if event["kind"] != "STATUS":
                data = json.loads(event["payload"])
                read = data.get("command") in {"HELP", "STATUS", "UNSUPPORTED"}
                with channel.store.transaction() as connection:
                    admitted = channel.rate(
                        connection,
                        ("read:" if read else "mutation:") + event["phone"],
                        channel.settings.read_requests_per_minute
                        if read
                        else channel.settings.mutation_requests_per_minute,
                        60,
                    )
                if not admitted:
                    raise APIError(429, "CHANNEL_RATE_LIMIT", "Phone command limit reached.")
            self.execute(event)
            state, code = "DONE", None
        except (APIError, ProviderError) as exc:
            state, code = "FAILED", exc.code
            with channel.store.transaction() as connection:
                link = channel.link_row(connection, event["link_id"]) if event["link_id"] else None
                # A generic error carries no taxpayer data to a revoked recipient.
                channel.queue(
                    connection,
                    event["event_key"],
                    event["phone"],
                    "Phone action could not complete ("
                    + code
                    + "). Review the website or use HELP.",
                    link if link and link["version"] == event["link_version"] else None,
                )
        with channel.store.transaction() as connection:
            connection.execute(
                "UPDATE wa_events SET state=?,error_code=? WHERE event_key=?",
                (state, code, event["event_key"]),
            )
        return True

    def watches(self):
        channel = self.channel
        with channel.store.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM wa_watches WHERE state='PENDING' ORDER BY "
                "created_at,logical_key LIMIT 20"
            ).fetchall()
            for watch in rows:
                link = channel.link_row(connection, watch["link_id"])
                if (
                    link is None
                    or link["version"] != watch["link_version"]
                    or (watch["kind"] != "IMPORT" and not channel.report_allowed(connection, link))
                ):
                    connection.execute(
                        "UPDATE wa_watches SET state='DONE' WHERE logical_key=?",
                        (watch["logical_key"],),
                    )
                    continue
                table = "imports" if watch["kind"] == "IMPORT" else "artifacts"
                row = connection.execute(
                    f"SELECT * FROM {table} WHERE id=? AND workspace_id=?",
                    (watch["resource_id"], link["workspace_id"]),
                ).fetchone()
                if row is None or row["state"] in {"RECEIVED", "PARSING", "PENDING"}:
                    continue
                body = channel.context_label(connection, link)
                if watch["kind"] == "IMPORT":
                    body += (
                        f" Import {row['id']}: {row['state']}, {row['accepted_rows']} valid "
                        f"and {row['rejected_rows']} rejected rows. Review and confirm on the "
                        f"local website."
                    )
                    channel.queue(connection, watch["logical_key"], link["phone"], body, link)
                elif row["state"] == "READY" and channel.reports.current(connection, row):
                    body += (
                        " Evidence report ready: {report_link} (expires in 10 minutes; up to "
                        "three downloads). This is not a filed return."
                    )
                    identifier = channel.queue(
                        connection, watch["logical_key"], link["phone"], body, link
                    )
                    channel.capability(connection, link, row["id"], identifier)
                else:
                    body += (
                        f" Report {row['id']} is {row['state']} or its source changed. "
                        f"Request a current report on the website."
                    )
                    channel.queue(connection, watch["logical_key"], link["phone"], body, link)
                connection.execute(
                    "UPDATE wa_watches SET state='DONE' WHERE logical_key=?",
                    (watch["logical_key"],),
                )

    def alerts(self):
        channel = self.channel
        if not channel.settings.whatsapp_send_budget:
            return
        with channel.store.transaction() as connection:
            remaining = (
                channel.settings.whatsapp_send_budget
                - connection.execute("SELECT used FROM wa_budget WHERE singleton=1").fetchone()[0]
            )
            remaining -= connection.execute(
                "SELECT count(*) FROM wa_outbox WHERE state='QUEUED'"
            ).fetchone()[0]
            if remaining <= 0:
                return
            links = connection.execute(
                "SELECT id FROM wa_links WHERE active=1 AND consent_alerts=1 ORDER BY id LIMIT 20"
            ).fetchall()
            for item in links:
                link = channel.link_row(connection, item["id"])
                if link is None or int(channel.clock()) - link["last_inbound"] >= 86400:
                    continue
                role = channel.access.require_membership(
                    connection, channel.identity(link), link["workspace_id"]
                )
                if role not in {"OWNER", "REVIEWER"}:
                    continue
                events = connection.execute(
                    "SELECT e.id,e.snapshot_json,a.due_at,a.reminded_at,a.id AS action_id "
                    "FROM action_events e JOIN business_actions a ON a.id=e.action_id "
                    "WHERE e.workspace_id=? AND a.registration_id=? AND a.period=? "
                    "AND e.kind='REVIEW_DUE' AND a.state!='CLOSED' "
                    "AND NOT EXISTS (SELECT 1 FROM wa_outbox o WHERE "
                    "o.logical_key='due:' || ? || ':' || e.id) "
                    "ORDER BY e.created_at DESC LIMIT 20",
                    (link["workspace_id"], link["registration_id"], link["period"], link["id"]),
                ).fetchall()
                for event in events:
                    if remaining <= 0:
                        return
                    action = channel.actions.row(
                        connection, link["workspace_id"], event["action_id"]
                    )
                    if (
                        event["due_at"] is None
                        or event["reminded_at"] != event["due_at"]
                        or json.loads(event["snapshot_json"]).get("due_at") != event["due_at"]
                        or not channel.actions.current(connection, action)
                    ):
                        continue
                    channel.queue(
                        connection,
                        "due:" + link["id"] + ":" + event["id"],
                        link["phone"],
                        channel.context_label(connection, link)
                        + (
                            " A recorded review date is due. Open the work queue. This is a "
                            "recorded reminder, not a calculated statutory deadline."
                        ),
                        link,
                    )
                    remaining -= 1
