"""Snapshot reports in private SQLite, durable serial jobs and authenticated downloads."""

import base64
import binascii
import hashlib
import json
import time

from app.adapters.reports import generator_manifest
from app.errors import APIError
from app.security.roles import require_role
from app.services.imports import digest, encode
from app.services.workflows import WorkflowService


class ReportService(WorkflowService):
    def __init__(self, runs, cases, proposals):
        super().__init__(runs)
        self.cases, self.proposals = cases, proposals

    def snapshot(self, connection, identity, workspace, payload):
        kind, identifier = payload["kind"], payload["source_id"]
        selected = payload["selected_result_ids"]
        if selected and kind != "RECONCILIATION_PDF":
            raise APIError(
                422, "REPORT_SELECTION", "Selection applies only to reconciliation reports."
            )
        common = {
            "kind": kind,
            "source_id": identifier,
            "source_version": payload["expected_version"],
            "manifest": generator_manifest(),
        }
        if kind == "RECONCILIATION_PDF":
            row = self.runs.scoped(connection, workspace, identifier)
            self.version(row, payload["expected_version"])
            if row["state"] != "COMPLETED" or not self.runs.sources_current(connection, row):
                raise APIError(409, "STALE_SOURCE", "Report requires a current completed run.")
            if len(set(selected)) != len(selected) or len(selected) > self.settings.max_report_rows:
                raise APIError(
                    422, "REPORT_SELECTION", "Result selection is duplicate or excessive."
                )
            if selected:
                results = [
                    self.scoped(connection, "run_results", workspace, key) for key in selected
                ]
                if any(result["run_id"] != identifier for result in results):
                    raise APIError(
                        422, "REPORT_SELECTION", "Selected results belong to another run."
                    )
                results.sort(key=lambda result: result["source_row_number"])
            else:
                results = connection.execute(
                    "SELECT * FROM run_results WHERE workspace_id=? AND run_id=? "
                    "ORDER BY source_row_number LIMIT ?",
                    (workspace, identifier, self.settings.max_report_rows),
                ).fetchall()
            data = self.runs.detail_row(connection, row)
            common.update(
                {
                    "provenance": data["provenance"],
                    "run": data,
                    "total_rows": connection.execute(
                        "SELECT count(*) FROM run_results WHERE workspace_id=? AND run_id=?",
                        (workspace, identifier),
                    ).fetchone()[0],
                    "results": [
                        self.runs.result_row(connection, result, row, details=True)
                        for result in results
                    ],
                }
            )
            field = "run_id"
        elif kind == "EVIDENCE_PDF":
            row = self.scoped(connection, "cases", workspace, identifier)
            self.version(row, payload["expected_version"])
            data = self.cases.detail_row(connection, row)
            common.update({"provenance": row["provenance"], "case": data})
            field = "case_id"
        elif kind == "PROPOSAL_CSV":
            row = self.scoped(connection, "proposals", workspace, identifier)
            self.version(row, payload["expected_version"])
            if row["state"] not in {"APPROVED", "EXPORTED"} or not self.proposals.current(
                connection, row
            ):
                raise APIError(
                    409, "PROPOSAL_NOT_CURRENT", "Export requires a current approved proposal."
                )
            data = json.loads(row["snapshot_json"])
            common.update(
                {
                    "provenance": data["provenance"],
                    "proposal": data,
                    "proposal_sha256": row["snapshot_sha256"],
                }
            )
            field = "proposal_id"
        else:
            row = self.imports.scoped(connection, identity, workspace, identifier, mutation=True)
            self.version(row, payload["expected_version"])
            if row["state"] not in {"AWAITING_CONFIRMATION", "READY"}:
                raise APIError(409, "IMPORT_NOT_PARSED", "Row errors require a parsed import.")
            rows = connection.execute(
                "SELECT row_number,original_json,errors_json,accepted "
                "FROM import_rows WHERE workspace_id=? AND import_id=? "
                "AND accepted=0 ORDER BY row_number",
                (workspace, identifier),
            ).fetchall()
            common.update(
                {
                    "provenance": row["provenance"],
                    "file_sha256": row["file_sha256"],
                    "adapter_version": row["adapter_version"],
                    "columns": json.loads(row["columns_json"]),
                    "rows": [
                        {
                            "row_number": item["row_number"],
                            "original": json.loads(item["original_json"]),
                            "errors": json.loads(item["errors_json"]),
                            "accepted": False,
                        }
                        for item in rows
                    ],
                }
            )
            field = "import_id"
        if kind in {"RECONCILIATION_PDF", "EVIDENCE_PDF"} and hasattr(self, "actions"):
            if kind == "EVIDENCE_PDF":
                query = (
                    "SELECT * FROM business_actions WHERE workspace_id=? AND case_id=? ORDER BY id"
                )
                values = (workspace, identifier)
            else:
                query = (
                    "SELECT * FROM business_actions WHERE workspace_id=? AND run_id=? ORDER BY id"
                )
                values = (workspace, identifier)
            action_rows = connection.execute(query, values).fetchall()
            common["action_versions"] = [[r["id"], r["version"]] for r in action_rows]
            status = self.actions.status(connection, workspace)
            common["automation_coverage"] = {
                "pending_sources": status["pending_sources"],
                "error_code": status["error_code"],
                "label": "Pending or failed local derivation is not complete coverage",
            }
            common["action_coverage"] = {
                "shown": min(len(action_rows), self.settings.max_report_rows),
                "total": len(action_rows),
                "label": "Recorded business actions; not executed filings",
            }
            common["business_actions"] = []
            for action in action_rows[: self.settings.max_report_rows]:
                details = self.actions.detail_row(connection, action)
                common["business_actions"].append(
                    {
                        "invoice": details["source"]["invoice"],
                        "recorded_tax": details["source"]["recorded_tax"],
                        "comparison_status": details["source"]["status"],
                        "reason_codes": details["source"]["reason_codes"],
                        **{
                            key: details[key]
                            for key in (
                                "id",
                                "kind",
                                "state",
                                "version",
                                "due_at",
                                "assigned_to",
                                "outcome",
                                "sources_current",
                                "timeline",
                            )
                        },
                    }
                )
        if len(encode(common).encode()) > self.settings.max_report_snapshot_bytes:
            raise APIError(
                413, "REPORT_SNAPSHOT_LIMIT", "Select fewer rows or use a smaller report."
            )
        return common, field

    def current(self, connection, row):
        snapshot = json.loads(row["snapshot_json"])
        ws = row["workspace_id"]
        if "action_versions" in snapshot:
            field = "run_id" if row["run_id"] else "case_id"
            identifier = row[field]
            versions = [
                [r[0], r[1]]
                for r in connection.execute(
                    f"SELECT id,version FROM business_actions WHERE workspace_id=? AND {field}=? "
                    "ORDER BY id",
                    (ws, identifier),
                )
            ]
            if versions != snapshot["action_versions"]:
                return False
        for action in snapshot.get("business_actions", []):
            observed = connection.execute(
                "SELECT * FROM business_actions WHERE workspace_id=? AND id=?",
                (ws, action["id"]),
            ).fetchone()
            if (
                observed is None
                or observed["version"] != action["version"]
                or not self.actions.current(connection, observed)
            ):
                return False

        if row["run_id"]:
            run = self.runs.scoped(connection, ws, row["run_id"])
            return (
                run["state"] == "COMPLETED"
                and run["version"] == snapshot["source_version"]
                and self.runs.sources_current(connection, run)
            )
        if row["case_id"]:
            case = self.scoped(connection, "cases", ws, row["case_id"])
            return case["version"] == snapshot["source_version"] and self.cases.sources_current(
                connection, case
            )
        if row["proposal_id"]:
            proposal = self.scoped(connection, "proposals", ws, row["proposal_id"])
            return (
                proposal["state"] in {"APPROVED", "EXPORTED"}
                and proposal["snapshot_sha256"] == snapshot["proposal_sha256"]
                and self.proposals.current(connection, proposal)
            )
        imported = connection.execute(
            "SELECT version FROM imports WHERE workspace_id=? AND id=?", (ws, row["import_id"])
        ).fetchone()
        return imported is not None and imported["version"] == snapshot["source_version"]

    def detail_row(self, connection, row):
        data = {
            key: row[key]
            for key in (
                "id",
                "workspace_id",
                "kind",
                "filename",
                "mime_type",
                "state",
                "sha256",
                "size_bytes",
                "error_code",
                "expires_at",
                "created_at",
                "updated_at",
            )
        }
        snapshot = json.loads(row["snapshot_json"])
        data.update(
            {
                "source_id": snapshot["source_id"],
                "source_version": snapshot["source_version"],
                "snapshot_sha256": row["snapshot_sha256"],
                "manifest": snapshot["manifest"],
                "provenance": snapshot["provenance"],
                "sources_current": self.current(connection, row),
                "job_id": connection.execute(
                    "SELECT id FROM artifact_jobs WHERE artifact_id=?", (row["id"],)
                ).fetchone()[0],
            }
        )
        if row["expires_at"] <= int(time.time()):
            data["state"] = "EXPIRED"
        return data

    def expire(self, connection, workspace, now):
        rows = connection.execute(
            "SELECT id FROM artifacts WHERE workspace_id=? AND expires_at<=? AND state!='EXPIRED'",
            (workspace, now),
        ).fetchall()
        for row in rows:
            connection.execute(
                "UPDATE artifacts SET state='EXPIRED',content=NULL,error_code='ARTIFACT_EXPIRED',"
                "updated_at=? WHERE id=?",
                (now, row["id"]),
            )
            connection.execute(
                "UPDATE artifact_jobs SET state='FAILED',lease=NULL,error_code='ARTIFACT_EXPIRED',"
                "updated_at=? WHERE artifact_id=? AND state IN ('QUEUED','RUNNING')",
                (now, row["id"]),
            )
        return len(rows)

    def create(self, identity, workspace, payload, key, request_id):
        if hasattr(self, "actions"):
            self.actions.readable_refresh(identity, workspace)
        with self.store.transaction() as connection:
            self.authorize(connection, identity, workspace, mutation=True)
            require_role(self.access, connection, identity, workspace, {"CA", "CFO"})
            cached = self.operation(connection, identity, workspace, "artifacts", key, payload)
            if cached is not None:
                return cached
            now = int(time.time())
            self.expire(connection, workspace, now)
            snapshot, field = self.snapshot(connection, identity, workspace, payload)
            fingerprint = digest(snapshot)
            existing = connection.execute(
                "SELECT * FROM artifacts WHERE workspace_id=? AND kind=? "
                "AND snapshot_sha256=? AND state IN ('PENDING','READY') "
                "ORDER BY created_at,id LIMIT 1",
                (workspace, payload["kind"], fingerprint),
            ).fetchone()
            if existing is not None:
                response = self.detail_row(connection, existing)
            else:
                self.limit(
                    connection, "artifacts", workspace, self.settings.max_artifacts_per_workspace
                )
                pending = sum(
                    connection.execute(
                        f"SELECT count(*) FROM {table} WHERE workspace_id=? "
                        "AND state IN ('QUEUED','RUNNING')",
                        (workspace,),
                    ).fetchone()[0]
                    for table in ("jobs", "run_jobs", "artifact_jobs")
                )
                if pending >= self.settings.max_queued_jobs_per_workspace:
                    raise APIError(
                        429, "QUEUE_FULL", "Workspace processing queue is full.", retry_after=2
                    )
                identifier, job = self.identifier(), self.identifier()
                extension = "pdf" if payload["kind"].endswith("_PDF") else "csv"
                filename = f"gstshield-{payload['kind'].lower()}-{identifier}.{extension}"
                mime = "application/pdf" if extension == "pdf" else "text/csv; charset=utf-8"
                sources = {name: None for name in ("run_id", "case_id", "proposal_id", "import_id")}
                sources[field] = payload["source_id"]
                connection.execute(
                    "INSERT INTO artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        identifier,
                        workspace,
                        payload["kind"],
                        *sources.values(),
                        encode(snapshot),
                        fingerprint,
                        filename,
                        mime,
                        "PENDING",
                        None,
                        None,
                        None,
                        None,
                        now + self.settings.artifact_ttl_seconds,
                        identity.user_id,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    "INSERT INTO artifact_jobs VALUES (?,?,?,?,?,?,?,?,?)",
                    (job, workspace, identifier, "ARTIFACT", "QUEUED", None, None, now, now),
                )
                response = self.detail_row(
                    connection, self.scoped(connection, "artifacts", workspace, identifier)
                )
            self.record(connection, identity, workspace, "artifacts", key, payload, response)
        self.imports.wakeup.set()
        return response

    def list_artifacts(self, identity, workspace, cursor, limit, registration=None, period=None):
        with self.store.transaction(write=False) as connection:
            self.authorize(connection, identity, workspace)
            # Select IDs first, then one snapshot at a time. Never load report BLOBs for lists.
            rows = connection.execute(
                "SELECT a.id FROM artifacts a "
                "LEFT JOIN imports i ON i.workspace_id=a.workspace_id AND i.id=a.import_id "
                "LEFT JOIN cases c ON c.workspace_id=a.workspace_id AND c.id=a.case_id "
                "LEFT JOIN run_results rr ON rr.workspace_id=c.workspace_id AND rr.id=c.result_id "
                "LEFT JOIN proposals p ON p.workspace_id=a.workspace_id AND p.id=a.proposal_id "
                "LEFT JOIN runs r ON r.workspace_id=a.workspace_id "
                "AND r.id=coalesce(a.run_id,rr.run_id,p.run_id) "
                "WHERE a.workspace_id=? AND a.id>? "
                "AND (? IS NULL OR coalesce(i.registration_id,r.registration_id)=?) "
                "AND (? IS NULL OR coalesce(i.period,r.period)=?) ORDER BY a.id LIMIT ?",
                (workspace, cursor, registration, registration, period, period, limit + 1),
            ).fetchall()
            metadata = []
            for row in rows[:limit]:
                artifact = connection.execute(
                    "SELECT id,workspace_id,kind,run_id,case_id,proposal_id,import_id,"
                    "snapshot_json,snapshot_sha256,filename,mime_type,state,sha256,size_bytes,"
                    "error_code,expires_at,created_at,updated_at FROM artifacts "
                    "WHERE workspace_id=? AND id=?",
                    (workspace, row["id"]),
                ).fetchone()
                metadata.append(self.detail_row(connection, artifact))
            return {
                "artifacts": metadata,
                "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None,
            }

    def detail(self, identity, workspace, identifier):
        with self.store.transaction(write=False) as connection:
            self.authorize(connection, identity, workspace)
            return self.detail_row(
                connection, self.scoped(connection, "artifacts", workspace, identifier)
            )

    def download(self, identity, workspace, identifier, historical):
        with self.store.transaction(write=False) as connection:
            self.authorize(connection, identity, workspace)
            row = self.scoped(connection, "artifacts", workspace, identifier)
            if row["expires_at"] <= int(time.time()) or row["state"] == "EXPIRED":
                raise APIError(410, "ARTIFACT_EXPIRED", "Report has expired.")
            if row["state"] != "READY":
                raise APIError(409, "ARTIFACT_NOT_READY", "Report is not ready for download.")
            current = self.current(connection, row)
            if not current and (not historical or row["kind"] == "PROPOSAL_CSV"):
                raise APIError(
                    409,
                    "STALE_SOURCE",
                    "Report source changed; regenerate or request historical PDF.",
                )
            content = row["content"]
            if (
                len(content) > self.settings.max_artifact_bytes
                or len(content) != row["size_bytes"]
                or hashlib.sha256(content).hexdigest() != row["sha256"]
            ):
                raise APIError(503, "ARTIFACT_INVALID", "Stored report could not be validated.")
            return content, row["filename"], row["mime_type"], not current

    def cleanup(self, identity, workspace, payload, key):
        with self.store.transaction() as connection:
            self.access.require_membership(connection, identity, workspace, roles={"OWNER"})
            cached = self.operation(
                connection, identity, workspace, "artifacts/cleanup", key, payload
            )
            if cached is not None:
                return cached
            response = {
                "expired_artifacts": self.expire(connection, workspace, int(time.time())),
                "scope": "EXPIRED_ARTIFACT_CONTENT_ONLY",
            }
            self.record(
                connection, identity, workspace, "artifacts/cleanup", key, payload, response
            )
            return response

    def recover(self, connection, now):
        connection.execute(
            "UPDATE artifacts SET state='FAILED',"
            "error_code='PROCESSING_INTERRUPTED',"
            "updated_at=? WHERE id IN "
            "(SELECT artifact_id FROM artifact_jobs WHERE state='RUNNING')",
            (now,),
        )
        connection.execute(
            "UPDATE artifact_jobs SET "
            "state='FAILED',lease=NULL,error_code='PROCESSING_INTERRUPTED',"
            "updated_at=? WHERE state='RUNNING'",
            (now,),
        )
        for row in connection.execute(
            "SELECT DISTINCT workspace_id FROM artifacts WHERE expires_at<=?", (now,)
        ):
            self.expire(connection, row["workspace_id"], now)

    def claim(self, connection, identifier):
        row = connection.execute("SELECT * FROM artifacts WHERE id=?", (identifier,)).fetchone()
        now = int(time.time())
        if row["expires_at"] <= now:
            self.expire(connection, row["workspace_id"], now)
            return None
        lease = self.identifier()
        connection.execute(
            "UPDATE artifact_jobs SET state='RUNNING',lease=?,updated_at=? "
            "WHERE artifact_id=? AND state='QUEUED'",
            (lease, now, identifier),
        )
        return {
            "id": identifier,
            "workspace_id": row["workspace_id"],
            "lease": lease,
            "job_kind": "ARTIFACT",
        }

    def publish(self, row, outcome):
        with self.store.transaction() as connection:
            job = connection.execute(
                "SELECT * FROM artifact_jobs WHERE artifact_id=?", (row["id"],)
            ).fetchone()
            if job is None or job["state"] != "RUNNING" or job["lease"] != row["lease"]:
                return
            artifact = self.scoped(connection, "artifacts", row["workspace_id"], row["id"])
            now, error, content = int(time.time()), outcome.get("error_code"), None
            if artifact["expires_at"] <= now:
                self.expire(connection, row["workspace_id"], now)
                return
            if not self.current(connection, artifact):
                error = "STALE_SOURCE"
            if not error:
                try:
                    encoded = outcome["content"]
                    if len(encoded) > (self.settings.max_artifact_bytes + 2) // 3 * 4:
                        raise ValueError("oversized")
                    content = base64.b64decode(encoded, validate=True)
                    if (
                        not content
                        or len(content) > self.settings.max_artifact_bytes
                        or hashlib.sha256(content).hexdigest() != outcome["sha256"]
                    ):
                        raise ValueError("invalid")
                    if artifact["kind"].endswith("_PDF") and not (
                        content.startswith(b"%PDF-") and content.rstrip().endswith(b"%%EOF")
                    ):
                        raise ValueError("invalid PDF")
                except (KeyError, ValueError, TypeError, binascii.Error):
                    error, content = "ARTIFACT_INVALID", None
            if error:
                connection.execute(
                    "UPDATE artifacts SET state='FAILED',error_code=?,updated_at=? WHERE id=?",
                    (error, now, row["id"]),
                )
            else:
                connection.execute(
                    "UPDATE artifacts SET "
                    "state='READY',content=?,sha256=?,size_bytes=?,updated_at=? "
                    "WHERE id=?",
                    (content, outcome["sha256"], len(content), now, row["id"]),
                )
                if artifact["proposal_id"]:
                    connection.execute(
                        "UPDATE proposals SET state='EXPORTED',version=version+1,updated_at=? "
                        "WHERE id=? AND state='APPROVED'",
                        (now, artifact["proposal_id"]),
                    )
                    if connection.execute("SELECT changes()").fetchone()[0]:
                        proposal = self.scoped(
                            connection, "proposals", row["workspace_id"], artifact["proposal_id"]
                        )
                        connection.execute(
                            "INSERT INTO proposal_events VALUES (?,?,?,?,?,?,?,?,?)",
                            (
                                self.identifier(),
                                row["workspace_id"],
                                proposal["id"],
                                artifact["created_by"],
                                "EXPORT",
                                "Review-only CSV generated.",
                                proposal["version"],
                                job["id"],
                                now,
                            ),
                        )
            connection.execute(
                "UPDATE artifact_jobs SET state=?,lease=NULL,error_code=?,updated_at=? WHERE id=?",
                ("FAILED" if error else "SUCCEEDED", error, now, job["id"]),
            )
