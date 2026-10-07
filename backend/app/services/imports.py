"""Private import commands, immutable previews and durable local job admission."""

import hashlib
import json
import threading
import time
from uuid import uuid4

from app.errors import APIError
from app.services.access import AccessService, Identity

WRITE_ROLES = {"OWNER", "REVIEWER"}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


class ImportService:
    def __init__(self, access: AccessService):
        self.access = access
        self.store = access.store
        self.settings = access.settings
        self.upload_slot = threading.BoundedSemaphore(1)
        self.wakeup = threading.Event()

    def authorize(self, identity, workspace, *, mutation=False):
        with self.store.transaction(write=False) as connection:
            self.access.require_membership(
                connection,
                identity,
                workspace,
                roles=WRITE_ROLES if mutation else {"OWNER", "REVIEWER", "VIEWER"},
            )

    def scoped(self, connection, identity, workspace, identifier, *, mutation=False):
        self.access.require_membership(
            connection,
            identity,
            workspace,
            roles=WRITE_ROLES if mutation else {"OWNER", "REVIEWER", "VIEWER"},
        )
        row = connection.execute(
            "SELECT * FROM imports WHERE workspace_id=? AND id=?", (workspace, identifier)
        ).fetchone()
        if row is None:
            raise APIError(404, "NOT_FOUND", "Resource was not found.")
        return row

    def detail_row(self, connection, row):
        result = dict(row)
        result["job_id"] = connection.execute(
            "SELECT id FROM jobs WHERE import_id=?", (row["id"],)
        ).fetchone()[0]
        for key in ("mapping", "errors", "columns"):
            result[key] = json.loads(result.pop(key + "_json"))
        result.pop("mapping_hash")
        result.pop("file_id")
        result.pop("created_by")
        return result

    def detail(self, identity, workspace, identifier):
        with self.store.transaction(write=False) as connection:
            return self.detail_row(
                connection, self.scoped(connection, identity, workspace, identifier)
            )

    def list_imports(self, identity, workspace, *, cursor, limit, registration, kind, period):
        with self.store.transaction(write=False) as connection:
            self.access.require_membership(connection, identity, workspace)
            rows = connection.execute(
                "SELECT * FROM imports WHERE workspace_id=? AND id>? "
                "AND (? IS NULL OR registration_id=?) AND (? IS NULL OR kind=?) "
                "AND (? IS NULL OR period=?) ORDER BY id LIMIT ?",
                (
                    workspace,
                    cursor or "",
                    registration,
                    registration,
                    kind,
                    kind,
                    period,
                    period,
                    limit + 1,
                ),
            ).fetchall()
            more = len(rows) > limit
            rows = rows[:limit]
            return {
                "imports": [self.detail_row(connection, row) for row in rows],
                "next_cursor": rows[-1]["id"] if more else None,
            }

    def rows(self, identity, workspace, identifier, *, cursor, limit, state):
        with self.store.transaction(write=False) as connection:
            self.scoped(connection, identity, workspace, identifier)
            result = []
            for row in connection.execute(
                "SELECT * FROM import_rows WHERE workspace_id=? AND import_id=? AND row_number>? "
                "AND (?='ALL' OR accepted=?) ORDER BY row_number LIMIT ?",
                (workspace, identifier, cursor, state, int(state == "ACCEPTED"), limit + 1),
            ):
                result.append(
                    {
                        "row_number": row["row_number"],
                        "original": json.loads(row["original_json"]),
                        "canonical": json.loads(row["canonical_json"]),
                        "errors": json.loads(row["errors_json"]),
                        "accepted": bool(row["accepted"]),
                        "duplicate": bool(row["duplicate"]),
                    }
                )
            more = len(result) > limit
            result = result[:limit]
            return {"rows": result, "next_cursor": result[-1]["row_number"] if more else None}

    def job(self, identity, workspace, identifier):
        with self.store.transaction(write=False) as connection:
            self.access.require_membership(connection, identity, workspace)
            row = connection.execute(
                "SELECT * FROM jobs WHERE workspace_id=? AND id=?", (workspace, identifier)
            ).fetchone()
            if row is None:
                row = connection.execute(
                    "SELECT id,workspace_id,run_id,kind,state,error_code,created_at,updated_at "
                    "FROM run_jobs WHERE workspace_id=? AND id=?",
                    (workspace, identifier),
                ).fetchone()
            if row is None:
                row = connection.execute(
                    "SELECT "
                    "id,workspace_id,artifact_id,kind,state,error_code,created_at,updated_at "
                    "FROM artifact_jobs WHERE workspace_id=? AND id=?",
                    (workspace, identifier),
                ).fetchone()
            if row is None:
                raise APIError(404, "NOT_FOUND", "Resource was not found.")
            return dict(row)

    def operation(self, connection, identity, workspace, route, key, request_hash):
        row = connection.execute(
            "SELECT * FROM import_operations WHERE workspace_id=? AND "
            "actor_id=? AND route=? AND key=?",
            (workspace, identity.user_id, route, key),
        ).fetchone()
        if row:
            if row["request_hash"] != request_hash:
                raise APIError(
                    409, "IDEMPOTENCY_CONFLICT", "This request key was used for another action."
                )
            return row["import_id"]
        return None

    def record_operation(
        self, connection, identity, workspace, route, key, request_hash, identifier
    ):
        if (
            connection.execute(
                "SELECT count(*) FROM import_operations WHERE workspace_id=?", (workspace,)
            ).fetchone()[0]
            >= 1000
        ):
            raise APIError(409, "OPERATION_LIMIT", "Workspace request history limit reached.")
        connection.execute(
            "INSERT INTO import_operations VALUES (?,?,?,?,?,?)",
            (workspace, identity.user_id, route, key, request_hash, identifier),
        )

    def event(self, connection, identity, workspace, identifier, action, request_id):
        connection.execute(
            "INSERT INTO import_events VALUES (?,?,?,?,?,?,?)",
            (
                str(uuid4()),
                workspace,
                identifier,
                identity.user_id,
                action,
                request_id,
                int(time.time()),
            ),
        )

    def admit(self, connection, workspace):
        if (
            connection.execute(
                "SELECT count(*) FROM imports WHERE workspace_id=?", (workspace,)
            ).fetchone()[0]
            >= self.settings.max_imports_per_workspace
        ):
            raise APIError(409, "IMPORT_LIMIT", "Workspace import limit reached.")
        if (
            connection.execute(
                (
                    "SELECT (SELECT count(*) FROM jobs WHERE workspace_id=? AND state IN "
                    "('QUEUED','RUNNING')) + (SELECT count(*) FROM run_jobs WHERE "
                    "workspace_id=? AND state IN ('QUEUED','RUNNING')) "
                    "+ (SELECT count(*) FROM artifact_jobs WHERE workspace_id=? "
                    "AND state IN ('QUEUED','RUNNING'))"
                ),
                (workspace, workspace, workspace),
            ).fetchone()[0]
            >= self.settings.max_queued_jobs_per_workspace
        ):
            raise APIError(429, "QUEUE_FULL", "Workspace processing queue is full.", retry_after=2)

    def create(
        self, connection, identity, workspace, metadata, file_id, file_hash, *, derived=None
    ):
        mapping_hash = digest(
            {"mapping": metadata["mapping"], "sheet_name": metadata["sheet_name"]}
        )
        duplicate = connection.execute(
            "SELECT id FROM imports WHERE workspace_id=? AND "
            "registration_id=? AND kind=? AND period=? "
            "AND file_sha256=? AND mapping_hash=? AND adapter_version=? AND "
            "ifnull(supersedes_import_id,'')=? AND ifnull(derived_from_import_id,'')=?",
            (
                workspace,
                metadata["registration_id"],
                metadata["kind"],
                metadata["period"],
                file_hash,
                mapping_hash,
                metadata["adapter_version"],
                metadata.get("supersedes_import_id") or "",
                derived or "",
            ),
        ).fetchone()
        if duplicate:
            return duplicate[0]
        self.admit(connection, workspace)
        self.access.rate(
            connection, "import:" + workspace, self.settings.import_requests_per_minute, 60
        )
        identifier, job_id = str(uuid4()), str(uuid4())
        now = int(time.time())
        parent = metadata.get("supersedes_import_id")
        if parent:
            old = self.scoped(connection, identity, workspace, parent, mutation=True)
            if old["state"] != "READY" or any(
                old[field] != metadata[field] for field in ("registration_id", "kind", "period")
            ):
                raise APIError(
                    409, "SUPERSESSION_INVALID", "Choose a ready import in the same context."
                )
        connection.execute(
            "INSERT INTO imports "
            "(id,workspace_id,registration_id,file_id,file_sha256,kind,period,"
            "adapter_version,sheet_name,mapping_json,mapping_hash,provenance,s"
            "tate,supersedes_import_id,"
            "derived_from_import_id,created_by,created_at,updated_at) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                identifier,
                workspace,
                metadata["registration_id"],
                file_id,
                file_hash,
                metadata["kind"],
                metadata["period"],
                metadata["adapter_version"],
                metadata["sheet_name"],
                encode(metadata["mapping"]),
                mapping_hash,
                "SYNTHETIC_DEMO"
                if metadata["adapter_version"] == "canonical-demo-v1"
                else "USER_PROVIDED",
                "RECEIVED",
                parent,
                derived,
                identity.user_id,
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO jobs VALUES (?,?,?,'IMPORT','QUEUED',NULL,?,?)",
            (job_id, workspace, identifier, now, now),
        )
        return identifier

    def upload(
        self,
        identity: Identity,
        workspace: str,
        metadata: dict,
        content: bytes,
        filename: str,
        key: str,
        request_id: str,
    ):
        file_hash = hashlib.sha256(content).hexdigest()
        request_hash = digest(
            {"metadata": metadata, "file_sha256": file_hash, "filename": filename}
        )
        self.store.capacity(len(content) + 131072)
        with self.store.transaction() as connection:
            self.access.require_membership(connection, identity, workspace, roles=WRITE_ROLES)
            registration = connection.execute(
                "SELECT id FROM registrations WHERE workspace_id=? AND id=?",
                (workspace, metadata["registration_id"]),
            ).fetchone()
            if registration is None:
                raise APIError(404, "NOT_FOUND", "Resource was not found.")
            prior = self.operation(connection, identity, workspace, "upload", key, request_hash)
            if prior:
                return self.detail_row(
                    connection, self.scoped(connection, identity, workspace, prior)
                )
            # A repeated byte/context import must not retain another copy of its source.
            file = connection.execute(
                "SELECT id FROM import_files WHERE workspace_id=? AND "
                "registration_id=? AND sha256=?",
                (workspace, metadata["registration_id"], file_hash),
            ).fetchone()
            file_id = file[0] if file else str(uuid4())
            if not file:
                connection.execute(
                    "INSERT INTO import_files VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        file_id,
                        workspace,
                        metadata["registration_id"],
                        filename,
                        content,
                        len(content),
                        file_hash,
                        identity.user_id,
                        int(time.time()),
                    ),
                )
            identifier = self.create(connection, identity, workspace, metadata, file_id, file_hash)
            self.record_operation(
                connection, identity, workspace, "upload", key, request_hash, identifier
            )
            self.event(connection, identity, workspace, identifier, "UPLOAD", request_id)
            result = self.detail_row(
                connection, self.scoped(connection, identity, workspace, identifier)
            )
        self.wakeup.set()
        return result

    def remap(self, identity, workspace, identifier, payload, key, request_id):
        route = "mapping:" + identifier
        request_hash = digest(payload)
        with self.store.transaction() as connection:
            row = self.scoped(connection, identity, workspace, identifier, mutation=True)
            prior = self.operation(connection, identity, workspace, route, key, request_hash)
            if prior:
                return self.detail_row(
                    connection, self.scoped(connection, identity, workspace, prior)
                )
            if row["version"] != payload["expected_version"]:
                raise APIError(409, "VERSION_CONFLICT", "Refresh this import before editing.")
            if row["state"] in {"RECEIVED", "PARSING", "SUPERSEDED"}:
                raise APIError(
                    409, "STATE_CONFLICT", "This import cannot be mapped in its current state."
                )
            metadata = {
                field: row[field]
                for field in ("registration_id", "kind", "period", "adapter_version")
            }
            if row["adapter_version"] == "canonical-demo-v1" and (
                payload["mapping"] or payload["sheet_name"] is not None
            ):
                raise APIError(422, "MAPPING_INVALID", "Demo JSON uses fixed canonical fields.")
            if row["adapter_version"] != "xlsx-v1" and payload["sheet_name"] is not None:
                raise APIError(422, "SHEET_INVALID", "Only XLSX supports sheet selection.")
            metadata.update(
                mapping=payload["mapping"],
                sheet_name=payload["sheet_name"],
                supersedes_import_id=identifier
                if row["state"] == "READY"
                else row["supersedes_import_id"],
            )
            new_id = self.create(
                connection,
                identity,
                workspace,
                metadata,
                row["file_id"],
                row["file_sha256"],
                derived=identifier,
            )
            self.record_operation(connection, identity, workspace, route, key, request_hash, new_id)
            self.event(connection, identity, workspace, new_id, "MAPPING", request_id)
            result = self.detail_row(
                connection, self.scoped(connection, identity, workspace, new_id)
            )
        self.wakeup.set()
        return result

    def confirm(self, identity, workspace, identifier, payload, key, request_id):
        route = "confirm:" + identifier
        request_hash = digest(payload)
        with self.store.transaction() as connection:
            row = self.scoped(connection, identity, workspace, identifier, mutation=True)
            prior = self.operation(connection, identity, workspace, route, key, request_hash)
            if prior:
                return self.detail_row(connection, row)
            if row["version"] != payload["expected_version"]:
                raise APIError(409, "VERSION_CONFLICT", "Refresh this import before confirming.")
            if (
                row["state"] != "AWAITING_CONFIRMATION"
                or row["accepted_rows"] == 0
                or json.loads(row["errors_json"])
            ):
                raise APIError(
                    409,
                    "IMPORT_NOT_CONFIRMABLE",
                    "Resolve mapping and row errors before confirming.",
                )
            if row["rejected_rows"] and not payload["allow_rejected_rows"]:
                raise APIError(409, "PARTIAL_ACK_REQUIRED", "Explicitly acknowledge excluded rows.")
            if row["supersedes_import_id"]:
                if not payload["confirmed_supersession"]:
                    raise APIError(
                        409, "SUPERSESSION_ACK_REQUIRED", "Explicitly acknowledge supersession."
                    )
                parent = self.scoped(
                    connection, identity, workspace, row["supersedes_import_id"], mutation=True
                )
                if parent["state"] != "READY":
                    raise APIError(
                        409, "SUPERSESSION_INVALID", "The previous import is no longer current."
                    )
                connection.execute(
                    "UPDATE imports SET "
                    "state='SUPERSEDED',version=version+1,updated_at=? WHERE id=?",
                    (int(time.time()), parent["id"]),
                )
            connection.execute(
                "UPDATE imports SET state='READY',version=version+1,updated_at=? WHERE id=?",
                (int(time.time()), identifier),
            )
            self.record_operation(
                connection, identity, workspace, route, key, request_hash, identifier
            )
            self.event(connection, identity, workspace, identifier, "CONFIRM", request_id)
            return self.detail_row(
                connection, self.scoped(connection, identity, workspace, identifier)
            )
