"""Scoped durable runs and atomic, versioned human decisions."""

import json
import time
from decimal import Decimal
from uuid import UUID, uuid4, uuid5

from app.domain.imports import MONEY_FIELDS
from app.domain.reconciliation import amount_comparison, summarize
from app.domain.reconciliation import identity as row_identity
from app.errors import APIError
from app.security.roles import require_role
from app.services.imports import WRITE_ROLES, digest, encode


def document_id(import_id, row_number):
    return str(uuid5(UUID(import_id), str(row_number)))


class RunService:
    def __init__(self, imports):
        self.imports = imports
        self.access = imports.access
        self.store = imports.store
        self.settings = imports.settings

    def authorize(self, connection, identity, workspace, *, mutation=False):
        self.access.require_membership(
            connection,
            identity,
            workspace,
            roles=WRITE_ROLES if mutation else {"OWNER", "REVIEWER", "VIEWER"},
        )

    def scoped(self, connection, workspace, identifier):
        row = connection.execute(
            "SELECT * FROM runs WHERE workspace_id=? AND id=?", (workspace, identifier)
        ).fetchone()
        if row is None:
            raise APIError(404, "NOT_FOUND", "Resource was not found.")
        return row

    def sources_current(self, connection, run):
        for source in json.loads(run["sources_json"]):
            row = connection.execute(
                "SELECT state,version,file_sha256 FROM imports WHERE workspace_id=? AND id=?",
                (run["workspace_id"], source["id"]),
            ).fetchone()
            if (
                row is None
                or row["state"] != "READY"
                or row["version"] != source["version"]
                or row["file_sha256"] != source["sha256"]
            ):
                return False
        return True

    def detail_row(self, connection, row):
        result = dict(row)
        result["run_id"] = result["id"]
        result["job_id"] = connection.execute(
            "SELECT id FROM run_jobs WHERE run_id=?", (row["id"],)
        ).fetchone()[0]
        for name in ("policy", "sources", "summary"):
            raw = result.pop(name + "_json")
            result[name] = json.loads(raw) if raw is not None else None
        result["policy_version"] = result["policy"]["version"]
        result["provenance"] = (
            "SYNTHETIC_DEMO"
            if any(source["provenance"] == "SYNTHETIC_DEMO" for source in result["sources"])
            else "USER_PROVIDED"
        )
        result["sources_current"] = self.sources_current(connection, row)
        result.pop("created_by")
        return result

    def operation(self, connection, identity, workspace, route, key, payload):
        row = connection.execute(
            (
                "SELECT request_hash,response_json FROM run_operations WHERE "
                "workspace_id=? AND actor_id=? AND route=? AND key=?"
            ),
            (workspace, identity.user_id, route, key),
        ).fetchone()
        if row:
            if row["request_hash"] != digest(payload):
                raise APIError(
                    409, "IDEMPOTENCY_CONFLICT", "This request key was used for another action."
                )
            return json.loads(row["response_json"])
        if (
            connection.execute(
                "SELECT count(*) FROM run_operations WHERE workspace_id=?", (workspace,)
            ).fetchone()[0]
            >= 1000
        ):
            raise APIError(409, "OPERATION_LIMIT", "Workspace request history limit reached.")
        return None

    def record(self, connection, identity, workspace, route, key, payload, response):
        connection.execute(
            "INSERT INTO run_operations VALUES (?,?,?,?,?,?)",
            (workspace, identity.user_id, route, key, digest(payload), encode(response)),
        )

    def event(
        self,
        connection,
        identity,
        workspace,
        run_id,
        request_id,
        *,
        result_id=None,
        action="CREATE_RUN",
        reason=None,
        candidate_id=None,
        version=None,
    ):
        connection.execute(
            "INSERT INTO run_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                str(uuid4()),
                workspace,
                run_id,
                result_id,
                identity.user_id,
                action,
                reason,
                candidate_id,
                version,
                request_id,
                int(time.time()),
            ),
        )

    def create(self, identity, workspace, payload, key, request_id, *, automatic=False):
        with self.store.transaction() as connection:
            self.authorize(connection, identity, workspace, mutation=True)
            require_role(
                self.access,
                connection,
                identity,
                workspace,
                {"CA", "CFO", "ACCOUNTS", "WAREHOUSE", "FOLLOWUP"} if automatic else {"CA"},
            )
            existing = self.operation(connection, identity, workspace, "runs", key, payload)
            if existing is not None:
                return existing
            sources = []
            for field, kind in (
                ("purchase_import_id", "PURCHASE"),
                ("portal_import_id", "PORTAL_2B"),
            ):
                row = self.imports.scoped(
                    connection, identity, workspace, payload[field], mutation=True
                )
                if (
                    row["registration_id"] != payload["registration_id"]
                    or row["period"] != payload["period"]
                    or row["kind"] != kind
                    or row["state"] != "READY"
                ):
                    raise APIError(
                        409,
                        "SOURCE_CONTEXT_INVALID",
                        "Select confirmed imports from the same registration and period.",
                    )
                sources.append(
                    {
                        "id": row["id"],
                        "kind": kind,
                        "sha256": row["file_sha256"],
                        "version": row["version"],
                        "adapter_version": row["adapter_version"],
                        "provenance": row["provenance"],
                        "generated_at": row["generated_at"],
                        "accepted_rows": row["accepted_rows"],
                        "rejected_rows": row["rejected_rows"],
                    }
                )
            policy = {
                "version": self.settings.match_policy_version,
                "amount_tolerance": str(self.settings.match_amount_tolerance),
                "fuzzy_threshold": str(self.settings.fuzzy_suggestion_threshold),
                "fuzzy_gap": str(self.settings.fuzzy_min_score_gap),
                "max_pairs": self.settings.max_match_pairs,
                "max_candidates": self.settings.max_match_candidates,
                "max_rows": self.settings.max_import_rows,
                "max_result_bytes": self.settings.max_parsed_import_bytes,
                "comparison": "rapidfuzz-3.14.6-ratio-ascii-separators-floor-threshold-raw-gap",
            }
            if automatic:
                # Recheck under the writer lock so concurrent confirmations share one job.
                reusable = connection.execute(
                    "SELECT * FROM runs WHERE workspace_id=? AND registration_id=? "
                    "AND period=? AND purchase_import_id=? AND portal_import_id=? "
                    "AND sources_json=? AND policy_json=? "
                    "AND state IN ('QUEUED','RUNNING','COMPLETED','FAILED') "
                    "ORDER BY revision DESC LIMIT 1",
                    (
                        workspace,
                        payload["registration_id"],
                        payload["period"],
                        payload["purchase_import_id"],
                        payload["portal_import_id"],
                        encode(sources),
                        encode(policy),
                    ),
                ).fetchone()
                if reusable is not None:
                    return self.detail_row(connection, reusable)
            if (
                connection.execute(
                    "SELECT count(*) FROM runs WHERE workspace_id=?", (workspace,)
                ).fetchone()[0]
                >= self.settings.max_runs_per_workspace
            ):
                raise APIError(409, "RUN_LIMIT", "Workspace run limit reached.")
            pending = connection.execute(
                (
                    "SELECT (SELECT count(*) FROM jobs WHERE workspace_id=? AND state IN "
                    "('QUEUED','RUNNING')) + (SELECT count(*) FROM run_jobs WHERE "
                    "workspace_id=? AND state IN ('QUEUED','RUNNING')) "
                    "+ (SELECT count(*) FROM artifact_jobs WHERE workspace_id=? "
                    "AND state IN ('QUEUED','RUNNING'))"
                ),
                (workspace, workspace, workspace),
            ).fetchone()[0]
            if pending >= self.settings.max_queued_jobs_per_workspace:
                raise APIError(
                    429, "QUEUE_FULL", "Workspace processing queue is full.", retry_after=2
                )
            revision = connection.execute(
                (
                    "SELECT coalesce(max(revision),0)+1 FROM runs WHERE workspace_id=? AND "
                    "registration_id=? AND period=?"
                ),
                (workspace, payload["registration_id"], payload["period"]),
            ).fetchone()[0]
            identifier, job_id, now = str(uuid4()), str(uuid4()), int(time.time())
            connection.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    workspace,
                    payload["registration_id"],
                    payload["period"],
                    payload["purchase_import_id"],
                    payload["portal_import_id"],
                    revision,
                    1,
                    "QUEUED",
                    encode(policy),
                    encode(sources),
                    None,
                    None,
                    identity.user_id,
                    now,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO run_jobs VALUES (?,?,?,?,?,?,?,?,?)",
                (job_id, workspace, identifier, "RUN", "QUEUED", None, None, now, now),
            )
            self.event(connection, identity, workspace, identifier, request_id)
            response = self.detail_row(connection, self.scoped(connection, workspace, identifier))
            self.record(connection, identity, workspace, "runs", key, payload, response)
        self.imports.wakeup.set()
        return response

    def detail(self, identity, workspace, identifier):
        with self.store.transaction(write=False) as connection:
            self.authorize(connection, identity, workspace)
            return self.detail_row(connection, self.scoped(connection, workspace, identifier))

    def list_runs(self, identity, workspace, cursor, limit, registration=None, period=None):
        with self.store.transaction(write=False) as connection:
            self.authorize(connection, identity, workspace)
            rows = connection.execute(
                "SELECT * FROM runs WHERE workspace_id=? AND id>? "
                "AND (? IS NULL OR registration_id=?) AND (? IS NULL OR period=?) "
                "ORDER BY id LIMIT ?",
                (workspace, cursor or "", registration, registration, period, period, limit + 1),
            ).fetchall()
            return {
                "runs": [self.detail_row(connection, row) for row in rows[:limit]],
                "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None,
            }

    def result_row(self, connection, row, run, *, details=False):
        result = dict(row)
        canonical = json.loads(result.pop("canonical_json"))
        result["canonical"] = canonical
        result["reason_codes"] = json.loads(result.pop("reasons_json"))
        result["purchase_document_id"] = document_id(
            run["purchase_import_id"], row["source_row_number"]
        )
        result["assigned_portal_document_id"] = (
            document_id(run["portal_import_id"], row["assigned_portal_row"])
            if row["assigned_portal_row"] is not None
            else None
        )
        result.pop("assigned_portal_row")
        result.pop("purchase_import_id")
        result.pop("portal_import_id")
        result["provenance"] = (
            "SYNTHETIC_DEMO"
            if any(
                source["provenance"] == "SYNTHETIC_DEMO"
                for source in json.loads(run["sources_json"])
            )
            else "USER_PROVIDED"
        )
        if details:
            candidates = []
            for item in connection.execute(
                "SELECT * FROM run_candidates WHERE workspace_id=? AND result_id=? ORDER BY rank",
                (run["workspace_id"], row["id"]),
            ):
                assigned = connection.execute(
                    "SELECT id FROM run_results WHERE run_id=? AND assigned_portal_row=?",
                    (run["id"], item["portal_row_number"]),
                ).fetchone()
                candidates.append(
                    {
                        "id": item["id"],
                        "portal_document_id": document_id(
                            item["portal_import_id"], item["portal_row_number"]
                        ),
                        "original_invoice_number": item["original_invoice_number"],
                        "invoice_date": item["invoice_date"],
                        "score": item["score"],
                        "rank": item["rank"],
                        "hard_gates_passed": bool(item["eligible"]),
                        "currently_available": assigned is None or assigned[0] == row["id"],
                        "amount_differences": json.loads(item["differences_json"]),
                        "reason_codes": json.loads(item["reasons_json"]),
                    }
                )
            result["candidates"] = candidates
            result["review_timeline"] = [
                dict(item)
                for item in connection.execute(
                    (
                        "SELECT actor_id,action,reason,candidate_id,result_version,created_at "
                        "FROM run_events WHERE workspace_id=? AND result_id=? ORDER BY "
                        "result_version,id"
                    ),
                    (run["workspace_id"], row["id"]),
                )
            ]
        return result

    def results(self, identity, workspace, identifier, cursor, limit, status):
        with self.store.transaction(write=False) as connection:
            self.authorize(connection, identity, workspace)
            run = self.scoped(connection, workspace, identifier)
            rows = connection.execute(
                (
                    "SELECT * FROM run_results WHERE workspace_id=? AND run_id=? AND "
                    "source_row_number>? AND (? IS NULL OR status=?) ORDER BY "
                    "source_row_number LIMIT ?"
                ),
                (workspace, identifier, cursor, status, status, limit + 1),
            ).fetchall()
            return {
                "results": [self.result_row(connection, row, run) for row in rows[:limit]],
                "next_cursor": rows[limit - 1]["source_row_number"] if len(rows) > limit else None,
            }

    def result_detail(self, identity, workspace, identifier):
        with self.store.transaction(write=False) as connection:
            self.authorize(connection, identity, workspace)
            row = connection.execute(
                "SELECT * FROM run_results WHERE workspace_id=? AND id=?", (workspace, identifier)
            ).fetchone()
            if row is None:
                raise APIError(404, "NOT_FOUND", "Resource was not found.")
            return self.result_row(
                connection, row, self.scoped(connection, workspace, row["run_id"]), details=True
            )

    def summary(self, connection, run):
        rows = connection.execute(
            (
                "SELECT r.status,json_extract(r.canonical_json,'$.document_type') AS "
                "document_type,i.total_tax AS total_tax FROM run_results r JOIN "
                "import_rows i ON i.workspace_id=r.workspace_id AND "
                "i.import_id=r.purchase_import_id AND i.row_number=r.source_row_number "
                "WHERE r.workspace_id=? AND r.run_id=?"
            ),
            (run["workspace_id"], run["id"]),
        ).fetchall()
        return summarize(rows)

    def review(self, identity, workspace, identifier, payload, key, request_id):
        with self.store.transaction() as connection:
            self.authorize(connection, identity, workspace, mutation=True)
            route = "results/" + identifier + "/review"
            existing = self.operation(connection, identity, workspace, route, key, payload)
            if existing is not None:
                return existing
            row = connection.execute(
                "SELECT * FROM run_results WHERE workspace_id=? AND id=?", (workspace, identifier)
            ).fetchone()
            if row is None:
                raise APIError(404, "NOT_FOUND", "Resource was not found.")
            run = self.scoped(connection, workspace, row["run_id"])
            if run["state"] != "COMPLETED" or not self.sources_current(connection, run):
                raise APIError(
                    409,
                    "SOURCE_SUPERSEDED",
                    "This run is historical; reconcile the current confirmed sources.",
                )
            if row["version"] != payload["expected_version"]:
                raise APIError(409, "STALE_VERSION", "Refresh this result before reviewing it.")
            candidate = None
            assigned = None
            target = "REJECTED"
            if payload["action"] == "ACCEPT_CANDIDATE":
                candidate = connection.execute(
                    "SELECT * FROM run_candidates WHERE workspace_id=? AND result_id=? AND id=?",
                    (workspace, identifier, payload["candidate_id"]),
                ).fetchone()
                if candidate is None:
                    raise APIError(404, "NOT_FOUND", "Resource was not found.")
                left = connection.execute(
                    "SELECT * FROM import_rows WHERE workspace_id=? AND import_id=? "
                    "AND row_number=?",
                    (workspace, run["purchase_import_id"], row["source_row_number"]),
                ).fetchone()
                right = connection.execute(
                    "SELECT * FROM import_rows WHERE workspace_id=? AND import_id=? "
                    "AND row_number=?",
                    (workspace, run["portal_import_id"], candidate["portal_row_number"]),
                ).fetchone()
                fields = MONEY_FIELDS
                valid, _, _ = amount_comparison(
                    {"amounts": {field: left[field] for field in fields}},
                    {"amounts": {field: right[field] for field in fields}},
                    int(Decimal(json.loads(run["policy_json"])["amount_tolerance"]) * 100),
                )
                if (
                    not candidate["eligible"]
                    or not valid
                    or not left["accepted"]
                    or not right["accepted"]
                    or left["duplicate"]
                    or right["duplicate"]
                    or row_identity({"canonical": json.loads(left["canonical_json"])})
                    != row_identity({"canonical": json.loads(right["canonical_json"])})
                ):
                    raise APIError(
                        409,
                        "CANDIDATE_INELIGIBLE",
                        "This candidate lacks the required matching evidence.",
                    )
                assigned = candidate["portal_row_number"]
                if connection.execute(
                    "SELECT 1 FROM run_results WHERE run_id=? AND assigned_portal_row=? AND id<>?",
                    (run["id"], assigned, identifier),
                ).fetchone():
                    raise APIError(
                        409,
                        "ASSIGNMENT_CONFLICT",
                        "This portal row is already assigned to another result.",
                    )
                target = "REVIEW_ACCEPTED"
            reasons = sorted(set(json.loads(row["reasons_json"]) + ["HUMAN_" + target]))
            connection.execute(
                (
                    "UPDATE run_results SET "
                    "status=?,version=version+1,reasons_json=?,assigned_portal_row=? WHERE "
                    "id=?"
                ),
                (target, encode(reasons), assigned, identifier),
            )
            connection.execute(
                "UPDATE runs SET version=version+1,summary_json=?,updated_at=? WHERE id=?",
                (encode(self.summary(connection, run)), int(time.time()), run["id"]),
            )
            self.event(
                connection,
                identity,
                workspace,
                run["id"],
                request_id,
                result_id=identifier,
                action=payload["action"],
                reason=payload["reason"],
                candidate_id=candidate["id"] if candidate else None,
                version=row["version"] + 1,
            )
            updated = connection.execute(
                "SELECT * FROM run_results WHERE id=?", (identifier,)
            ).fetchone()
            response = self.result_row(connection, updated, run, details=True)
            self.record(connection, identity, workspace, route, key, payload, response)
            return response

    def recover(self, connection, now):
        connection.execute(
            (
                "UPDATE runs SET state='FAILED',version=version+1,updated_at=? WHERE id "
                "IN (SELECT run_id FROM run_jobs WHERE state='RUNNING')"
            ),
            (now,),
        )
        connection.execute(
            (
                "UPDATE run_jobs SET "
                "state='FAILED',lease=NULL,error_code='PROCESSING_INTERRUPTED',updated_at=?"
                " WHERE state='RUNNING'"
            ),
            (now,),
        )

    def claim(self, connection, identifier):
        row = connection.execute("SELECT * FROM runs WHERE id=?", (identifier,)).fetchone()
        if row is None or row["state"] != "QUEUED":
            return None
        lease = str(uuid4())
        now = int(time.time())
        connection.execute(
            (
                "UPDATE run_jobs SET state='RUNNING',lease=?,updated_at=? WHERE run_id=? "
                "AND state='QUEUED'"
            ),
            (lease, now, identifier),
        )
        connection.execute(
            "UPDATE runs SET state='RUNNING',version=version+1,updated_at=? WHERE id=?",
            (now, identifier),
        )
        return dict(row) | {"job_kind": "RUN", "lease": lease}

    def publish(self, row, outcome):
        now = int(time.time())
        with self.store.transaction() as connection:
            job = connection.execute(
                "SELECT * FROM run_jobs WHERE run_id=?", (row["id"],)
            ).fetchone()
            if job is None or job["state"] != "RUNNING" or job["lease"] != row["lease"]:
                return
            run = self.scoped(connection, row["workspace_id"], row["id"])
            error = outcome.get("error_code")
            if not self.sources_current(connection, run):
                error = "SOURCE_SUPERSEDED"
            if error:
                connection.execute(
                    (
                        "UPDATE run_jobs SET state='FAILED',lease=NULL,error_code=?,updated_at=? "
                        "WHERE run_id=?"
                    ),
                    (error, now, run["id"]),
                )
                connection.execute(
                    "UPDATE runs SET state='FAILED',version=version+1,updated_at=? WHERE id=?",
                    (now, run["id"]),
                )
                return
            values = outcome["result"]["results"]
            expected = connection.execute(
                "SELECT accepted_rows FROM imports WHERE id=?", (run["purchase_import_id"],)
            ).fetchone()[0]
            if len(values) != expected:
                raise ValueError("MATCH_RESULT_COUNT_INVALID")
            for item in values:
                result_id = str(uuid5(UUID(run["id"]), str(item["source_row_number"])))
                connection.execute(
                    "INSERT INTO run_results VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        result_id,
                        run["workspace_id"],
                        run["id"],
                        run["purchase_import_id"],
                        run["portal_import_id"],
                        item["source_row_number"],
                        item["status"],
                        1,
                        encode(item["canonical"]),
                        encode(item["reason_codes"]),
                        item["assigned_portal_row"],
                    ),
                )
                for candidate in item["candidates"]:
                    candidate_id = str(uuid5(UUID(result_id), str(candidate["portal_row_number"])))
                    connection.execute(
                        "INSERT INTO run_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            candidate_id,
                            run["workspace_id"],
                            run["id"],
                            result_id,
                            run["portal_import_id"],
                            candidate["portal_row_number"],
                            candidate["score"],
                            candidate["rank"],
                            int(candidate["hard_gates_passed"]),
                            candidate["original_invoice_number"],
                            candidate["invoice_date"],
                            encode(candidate["amount_differences"]),
                            encode(candidate["reason_codes"]),
                        ),
                    )
            summary = self.summary(connection, run)
            connection.execute(
                (
                    "UPDATE runs SET "
                    "state='COMPLETED',version=version+1,summary_json=?,updated_at=? WHERE "
                    "id=?"
                ),
                (encode(summary), now, run["id"]),
            )
            # Immutable revision order prevents UUID/time ties from reviving an older run.
            newer = connection.execute(
                (
                    "SELECT id FROM runs WHERE workspace_id=? AND registration_id=? AND "
                    "period=? AND purchase_import_id=? AND revision>? AND state='COMPLETED' "
                    "ORDER BY revision DESC "
                    "LIMIT 1"
                ),
                (
                    run["workspace_id"],
                    run["registration_id"],
                    run["period"],
                    run["purchase_import_id"],
                    run["revision"],
                ),
            ).fetchone()
            if newer:
                connection.execute(
                    (
                        "UPDATE runs SET "
                        "state='SUPERSEDED',superseded_by_run_id=?,version=version+1 WHERE id=?"
                    ),
                    (newer[0], run["id"]),
                )
            else:
                connection.execute(
                    (
                        "UPDATE runs SET "
                        "state='SUPERSEDED',superseded_by_run_id=?,version=version+1,updated_at=?"
                        " WHERE workspace_id=? AND registration_id=? AND period=? "
                        "AND purchase_import_id=? AND revision<? "
                        "AND state='COMPLETED'"
                    ),
                    (
                        run["id"],
                        now,
                        run["workspace_id"],
                        run["registration_id"],
                        run["period"],
                        run["purchase_import_id"],
                        run["revision"],
                    ),
                )
            connection.execute(
                "UPDATE run_jobs SET state='SUCCEEDED',lease=NULL,updated_at=? WHERE run_id=?",
                (now, run["id"]),
            )
