"""Durable local work queue, evidence-change tracking and reviewed follow-up history."""

import json
import time
from datetime import UTC, datetime

from app.domain.actions import ACCEPTED, case_review, review_time
from app.domain.imports import money_paise, money_string
from app.errors import APIError, StorageError
from app.services.imports import digest, encode
from app.services.runs import document_id
from app.services.workflows import WorkflowService


class ActionService(WorkflowService):
    def __init__(self, runs, cases):
        super().__init__(runs)
        self.cases = cases

    def row(self, connection, workspace, identifier):
        row = connection.execute(
            "SELECT * FROM business_actions WHERE workspace_id=? AND id=?", (workspace, identifier)
        ).fetchone()
        if row is None:
            raise APIError(404, "NOT_FOUND", "Resource was not found.")
        return row

    def events(self, connection, row):
        return [
            dict(event) | {"snapshot": json.loads(event["snapshot_json"])}
            for event in connection.execute(
                "SELECT * FROM action_events WHERE workspace_id=? AND action_id=? ORDER BY version",
                (row["workspace_id"], row["id"]),
            )
        ]

    def event(self, connection, row, kind, reason, snapshot, actor=None, request_id="SYSTEM"):
        if (
            connection.execute(
                "SELECT count(*) FROM action_events WHERE action_id=?", (row["id"],)
            ).fetchone()[0]
            >= self.settings.max_action_events
        ):
            raise APIError(
                409, "ACTION_HISTORY_LIMIT", "Action history is full; contact the operator."
            )
        identifier = self.identifier()
        connection.execute(
            "INSERT INTO action_events VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                identifier,
                row["workspace_id"],
                row["id"],
                actor,
                kind,
                reason,
                encode(snapshot),
                row["version"],
                request_id,
                int(time.time()),
            ),
        )
        return identifier

    def current(self, connection, row):
        source = json.loads(row["source_json"])
        run = self.runs.scoped(connection, row["workspace_id"], row["run_id"])
        result = self.scoped(connection, "run_results", row["workspace_id"], row["result_id"])
        valid = (
            run["state"] == "COMPLETED"
            and self.runs.sources_current(connection, run)
            and result["version"] == source["result_version"]
            and run["version"] == source["run_version"]
        )
        if row["case_id"]:
            case = self.scoped(connection, "cases", row["workspace_id"], row["case_id"])
            valid = (
                valid
                and case["version"] == source["case_version"]
                and self.cases.sources_current(connection, case)
            )
        return valid

    def detail_row(self, connection, row):
        data = dict(row)
        data["source"] = json.loads(data.pop("source_json"))
        data.pop("signature")
        outcome = data.pop("outcome_json")
        data["outcome"] = json.loads(outcome) if outcome else None
        data["sources_current"] = self.current(connection, row)
        data["timeline"] = self.events(connection, row)
        for event in data["timeline"]:
            event.pop("snapshot_json")
            event["actor_kind"] = "USER" if event["actor_id"] else "SYSTEM"
        return data

    def source(self, connection, run, result, case=None, *, sources=None):
        sources = json.loads(run["sources_json"]) if sources is None else sources
        invoice = json.loads(result["canonical_json"])
        imported = connection.execute(
            "SELECT total_tax FROM import_rows "
            "WHERE workspace_id=? AND import_id=? AND row_number=?",
            (run["workspace_id"], result["purchase_import_id"], result["source_row_number"]),
        ).fetchone()
        data = {
            "run_id": run["id"],
            "run_version": run["version"],
            "result_id": result["id"],
            "result_version": result["version"],
            "purchase_import_id": run["purchase_import_id"],
            "portal_import_id": run["portal_import_id"],
            "source_snapshots": sources,
            "invoice": invoice,
            "status": result["status"],
            "reason_codes": json.loads(result["reasons_json"]),
            "recorded_tax": money_string(imported["total_tax"])
            if imported["total_tax"] is not None
            else None,
            "provenance": (
                "SYNTHETIC_DEMO"
                if any(source["provenance"] == "SYNTHETIC_DEMO" for source in sources)
                else "USER_PROVIDED"
            ),
            "legal_eligibility": "NOT_DETERMINED",
            "automatic_fetching": "NOT_IMPLEMENTED",
            "comparison_basis": "SAME_RETAINED_PURCHASE_DOCUMENT",
        }
        data["portal_evidence"] = [
            json.loads(r[0])
            for r in connection.execute(
                "SELECT p.canonical_json FROM run_candidates c JOIN import_rows p "
                "ON p.workspace_id=c.workspace_id AND p.import_id=c.portal_import_id "
                "AND p.row_number=c.portal_row_number "
                "WHERE c.workspace_id=? AND c.result_id=? ORDER BY p.canonical_json",
                (run["workspace_id"], result["id"]),
            )
        ]
        if result["assigned_portal_row"] is not None:
            data["assigned_portal_evidence"] = json.loads(
                connection.execute(
                    "SELECT canonical_json FROM import_rows "
                    "WHERE workspace_id=? AND import_id=? AND row_number=?",
                    (run["workspace_id"], run["portal_import_id"], result["assigned_portal_row"]),
                ).fetchone()[0]
            )
        if case is not None:
            details = self.cases.detail_row(connection, case)
            data.update(
                {
                    "case_id": case["id"],
                    "case_version": case["version"],
                    "case_state": case["state"],
                    "facts": details["facts"],
                    "case_amount": details["amount"],
                    "review": case_review(details, invoice),
                    "evidence_event_ids": details["facts"]["observation_refs"],
                }
            )
            if case["provenance"] == "SYNTHETIC_DEMO":
                data["provenance"] = "SYNTHETIC_DEMO"
        return data

    def upsert(self, connection, run, result, case=None, *, sources=None):
        workspace = run["workspace_id"]
        doc = document_id(run["purchase_import_id"], result["source_row_number"])
        kind = case["kind"] if case is not None else "INVOICE_REVIEW"
        case_id = case["id"] if case is not None else None
        row = connection.execute(
            "SELECT * FROM business_actions WHERE workspace_id=? AND registration_id=? "
            "AND period=? AND document_id=? AND kind=? AND ifnull(case_id,'')=?",
            (workspace, run["registration_id"], run["period"], doc, kind, case_id or ""),
        ).fetchone()
        if row is None and case is None and result["status"] in ACCEPTED:
            return
        source = self.source(connection, run, result, case, sources=sources)
        signature = digest(source)
        now = int(time.time())
        due = None
        if case is not None:
            due_date = source["facts"].get("response_due_date") or source["facts"].get(
                "payment_due_date"
            )
            if due_date:
                due = review_time(due_date)
        if row is None:
            if (
                connection.execute(
                    "SELECT count(*) FROM business_actions WHERE workspace_id=?", (workspace,)
                ).fetchone()[0]
                >= self.settings.max_actions_per_workspace
            ):
                raise APIError(409, "ACTION_LIMIT", "Workspace action history limit reached.")
            identifier = self.identifier()
            connection.execute(
                "INSERT INTO business_actions (id,workspace_id,registration_id,period,document_id,"
                "kind,case_id,run_id,result_id,source_json,signature,state,version,due_at,created_at,"
                "updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    workspace,
                    run["registration_id"],
                    run["period"],
                    doc,
                    kind,
                    case_id,
                    run["id"],
                    result["id"],
                    encode(source),
                    signature,
                    "EVIDENCE_REQUIRED" if case is not None else "OPEN",
                    1,
                    due,
                    now,
                    now,
                ),
            )
            row = self.row(connection, workspace, identifier)
            self.event(
                connection, row, "DETECTED", "Recorded evidence requires a business review.", source
            )
            return
        if row["signature"] == signature:
            return
        old = json.loads(row["source_json"])

        # Ignore pure source/version churn for human outcome invalidation, but retain provenance.
        def meaningful(value):
            result = {
                key: value[key]
                for key in (
                    "invoice",
                    "status",
                    "reason_codes",
                    "portal_evidence",
                    "assigned_portal_evidence",
                    "recorded_tax",
                    "facts",
                    "review",
                    "provenance",
                )
                if key in value
            }
            if "facts" in result:
                result["facts"] = {
                    k: v for k, v in result["facts"].items() if k != "observation_refs"
                }
            return result

        changed = digest(meaningful(old)) != digest(meaningful(source))
        prior_outcome = json.loads(row["outcome_json"]) if row["outcome_json"] else {}
        if not set(prior_outcome.get("evidence_event_ids", [])).issubset(
            set(source.get("evidence_event_ids", []))
        ):
            changed = True
        state = "REVIEW_REQUIRED" if changed else row["state"]
        source_due_changed = case is not None and (
            old.get("facts", {}).get("response_due_date")
            != source["facts"].get("response_due_date")
            or old.get("facts", {}).get("payment_due_date")
            != source["facts"].get("payment_due_date")
        )
        connection.execute(
            "UPDATE business_actions SET run_id=?,result_id=?,source_json=?,signature=?,state=?,"
            "version=version+1,due_at=?,reminded_at=?,outcome_json=?,updated_at=? WHERE id=?",
            (
                run["id"],
                result["id"],
                encode(source),
                signature,
                state,
                due if source_due_changed else row["due_at"],
                None if source_due_changed else row["reminded_at"],
                None if changed else row["outcome_json"],
                now,
                row["id"],
            ),
        )
        updated = self.row(connection, workspace, row["id"])
        self.event(
            connection,
            updated,
            "EVIDENCE_CHANGED" if changed else "SOURCE_REFRESHED",
            "New recorded evidence; legal eligibility still requires review.",
            {"previous": old, "current": source, "requires_review": changed},
        )

    def sync_run(self, connection, run):
        if not self.runs.sources_current(connection, run):
            return
        # Transaction-local source metadata; no cached authorization or mutable truth.
        sources = json.loads(run["sources_json"])
        for result in connection.execute(
            "SELECT * FROM run_results WHERE workspace_id=? AND run_id=? "
            "ORDER BY source_row_number",
            (run["workspace_id"], run["id"]),
        ).fetchall():
            self.upsert(connection, run, result, sources=sources)
            doc = document_id(run["purchase_import_id"], result["source_row_number"])
            for case in connection.execute(
                "SELECT * FROM cases WHERE workspace_id=? AND registration_id=? "
                "AND purchase_document_id=?",
                (run["workspace_id"], run["registration_id"], doc),
            ).fetchall():
                self.upsert(connection, run, result, case, sources=sources)

    def sync_case(self, connection, case):
        original = self.scoped(connection, "run_results", case["workspace_id"], case["result_id"])
        run = connection.execute(
            "SELECT * FROM runs WHERE workspace_id=? AND registration_id=? AND "
            "purchase_import_id=? "
            "AND state='COMPLETED' ORDER BY revision DESC LIMIT 1",
            (case["workspace_id"], case["registration_id"], original["purchase_import_id"]),
        ).fetchone()
        if run is None or not self.runs.sources_current(connection, run):
            return
        result = connection.execute(
            "SELECT * FROM run_results WHERE run_id=? AND source_row_number=?",
            (run["id"], original["source_row_number"]),
        ).fetchone()
        if result is not None:
            self.upsert(connection, run, result, case)

    def pending(self, connection, workspace):
        return connection.execute(
            "SELECT 'RUN' AS kind,r.id,r.version,ifnull(c.attempted_at,0) AS attempted_at "
            "FROM runs r LEFT JOIN action_checkpoints c ON c.workspace_id=r.workspace_id "
            "AND c.kind='RUN' AND c.source_id=r.id WHERE r.workspace_id=? "
            "AND r.state='COMPLETED' AND (c.version IS NULL OR c.version!=r.version "
            "OR c.error_code IS NOT NULL) UNION ALL SELECT 'CASE',r.id,r.version,"
            "ifnull(c.attempted_at,0) FROM cases r LEFT JOIN action_checkpoints c "
            "ON c.workspace_id=r.workspace_id AND c.kind='CASE' AND c.source_id=r.id "
            "WHERE r.workspace_id=? AND (c.version IS NULL OR c.version!=r.version "
            "OR c.error_code IS NOT NULL) ORDER BY attempted_at,id,kind",
            (workspace, workspace),
        ).fetchall()

    def checkpoint(self, connection, workspace, item, error=None):
        connection.execute(
            "INSERT INTO action_checkpoints VALUES (?,?,?,?,?,?) ON "
            "CONFLICT(workspace_id,kind,source_id) DO UPDATE SET version=excluded.version,"
            "attempted_at=excluded.attempted_at,error_code=excluded.error_code",
            (workspace, item["kind"], item["id"], item["version"], time.time_ns(), error),
        )

    @staticmethod
    def failure(exc):
        if isinstance(exc, APIError):
            return exc.code
        if isinstance(exc, StorageError):
            return "STORAGE_UNAVAILABLE"
        import logging

        logging.getLogger("gstshield").error(
            "Action derivation failure exception_type=%s", type(exc).__name__
        )
        return "AUTOMATION_FAILED"

    def refresh(self, workspace):
        error = None
        with self.store.transaction(write=False) as connection:
            pending = self.pending(connection, workspace)[: self.settings.automation_source_batch]
        for item in pending:
            try:
                with self.store.transaction() as connection:
                    table = "runs" if item["kind"] == "RUN" else "cases"
                    row = connection.execute(
                        f"SELECT * FROM {table} WHERE workspace_id=? AND id=?",
                        (workspace, item["id"]),
                    ).fetchone()
                    if row is None:
                        continue
                    # The monitor and an HTTP refresh may both have observed the same
                    # pending source. Recheck only after acquiring the writer lock.
                    checkpoint = connection.execute(
                        "SELECT version,error_code FROM action_checkpoints "
                        "WHERE workspace_id=? AND kind=? AND source_id=?",
                        (workspace, item["kind"], item["id"]),
                    ).fetchone()
                    if (
                        checkpoint is not None
                        and checkpoint["version"] == row["version"]
                        and checkpoint["error_code"] is None
                    ):
                        continue
                    if item["kind"] == "RUN":
                        if row["state"] == "COMPLETED":
                            self.sync_run(connection, row)
                    else:
                        self.sync_case(connection, row)
                    self.checkpoint(connection, workspace, dict(item) | {"version": row["version"]})
            except Exception as exc:
                code = self.failure(exc)
                error = error or code
                with self.store.transaction() as connection:
                    self.checkpoint(connection, workspace, item, code)
        # A failed source must not prevent independent overdue reviews or hide pending failures.
        reminder_error = self.remind(workspace)
        error = error or reminder_error
        with self.store.transaction() as connection:
            failed = connection.execute(
                "SELECT error_code FROM action_checkpoints WHERE workspace_id=? "
                "AND error_code IS NOT NULL ORDER BY attempted_at LIMIT 1",
                (workspace,),
            ).fetchone()
            error = error or (failed[0] if failed else None)
            connection.execute(
                "INSERT INTO automation_status VALUES (?,?,?) ON CONFLICT(workspace_id) "
                "DO UPDATE SET checked_at=excluded.checked_at,error_code=excluded.error_code",
                (workspace, int(time.time()), error),
            )

    def remind(self, workspace):
        now, processed, error = int(time.time()), 0, None
        with self.store.transaction(write=False) as connection:
            # The action quota bounds this scan; stale rows do not consume the live due batch.
            identifiers = [
                row[0]
                for row in connection.execute(
                    "SELECT id FROM business_actions WHERE workspace_id=? AND state!='CLOSED' "
                    "AND due_at<=? AND (reminded_at IS NULL OR reminded_at!=due_at) "
                    "ORDER BY due_at,id",
                    (workspace, now),
                )
            ]
        for identifier in identifiers:
            try:
                with self.store.transaction() as connection:
                    row = self.row(connection, workspace, identifier)
                    if (
                        row["state"] == "CLOSED"
                        or row["due_at"] is None
                        or row["due_at"] > now
                        or row["reminded_at"] == row["due_at"]
                        or not self.current(connection, row)
                    ):
                        continue
                    connection.execute(
                        "UPDATE business_actions SET reminded_at=due_at,version=version+1,"
                        "updated_at=? WHERE id=?",
                        (now, identifier),
                    )
                    self.event(
                        connection,
                        self.row(connection, workspace, identifier),
                        "REVIEW_DUE",
                        "Recorded review date reached; no message has been sent.",
                        {"due_at": row["due_at"], "channel_delivery": "PENDING_CHANNEL_CHECK"},
                    )
                processed += 1
            except Exception as exc:
                error = error or self.failure(exc)
            if processed >= self.settings.automation_due_batch:
                break
        return error

    def channel_state(self, connection):
        if not self.settings.whatsapp_enabled:
            return "DISABLED"
        used = connection.execute("SELECT used FROM wa_budget WHERE singleton=1").fetchone()[0]
        return "ENABLED" if used < self.settings.whatsapp_send_budget else "PAUSED"

    def status(self, connection, workspace):
        row = connection.execute(
            "SELECT * FROM automation_status WHERE workspace_id=?", (workspace,)
        ).fetchone()
        return {
            "checked_at": row["checked_at"] if row else None,
            "error_code": row["error_code"] if row else None,
            "pending_sources": len(self.pending(connection, workspace)),
            "interval_seconds": self.settings.automation_interval_seconds,
            "channel_delivery": self.channel_state(connection),
        }

    def readable_refresh(self, identity, workspace):
        with self.store.transaction(write=False) as connection:
            self.authorize(connection, identity, workspace)
        self.refresh(workspace)

    def list_actions(
        self,
        identity,
        workspace,
        cursor,
        limit,
        state=None,
        due_only=False,
        registration=None,
        period=None,
    ):
        self.readable_refresh(identity, workspace)
        with self.store.transaction(write=False) as connection:
            self.authorize(connection, identity, workspace)
            rows = connection.execute(
                "SELECT * FROM business_actions WHERE workspace_id=? AND id>? "
                "AND (? IS NULL OR state=?) AND (?=0 OR (state!='CLOSED' AND due_at<=?)) "
                "AND (? IS NULL OR registration_id=?) AND (? IS NULL OR period=?) "
                "ORDER BY id LIMIT ?",
                (
                    workspace,
                    cursor,
                    state,
                    state,
                    int(due_only),
                    int(time.time()),
                    registration,
                    registration,
                    period,
                    period,
                    limit + 1,
                ),
            ).fetchall()
            return {
                "actions": [self.detail_row(connection, row) for row in rows[:limit]],
                "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None,
                "automation": self.status(connection, workspace),
            }

    def detail(self, identity, workspace, identifier):
        self.readable_refresh(identity, workspace)
        with self.store.transaction(write=False) as connection:
            self.authorize(connection, identity, workspace)
            return self.detail_row(connection, self.row(connection, workspace, identifier))

    def ensure_current(self, connection, row):
        if not self.current(connection, row):
            raise APIError(409, "ACTION_SOURCE_STALE", "Refresh current evidence before acting.")

    def mutate(self, identity, workspace, identifier, payload, key, request_id, *, kind):
        # Catch-up is an independent durable derivation, never included in a human command receipt.
        self.readable_refresh(identity, workspace)
        route = f"actions/{identifier}/{kind}"
        with self.store.transaction() as connection:
            self.authorize(connection, identity, workspace, mutation=True)
            cached = self.operation(connection, identity, workspace, route, key, payload)
            if cached is not None:
                return cached
            row = self.row(connection, workspace, identifier)
            self.version(row, payload["expected_version"])
            self.ensure_current(connection, row)
            event_kind, snapshot = kind.upper(), payload
            state, due, assigned, outcome = (
                row["state"],
                row["due_at"],
                row["assigned_to"],
                row["outcome_json"],
            )
            if kind == "update":
                state = payload["state"]
                if state == "CLOSED" and (
                    not outcome or json.loads(outcome).get("decision") == "EVIDENCE_REQUIRED"
                ):
                    raise APIError(
                        409, "REVIEW_OUTCOME_REQUIRED", "Record a reviewed outcome before closure."
                    )
                assigned = payload["assigned_to"]
                if (
                    assigned is not None
                    and not connection.execute(
                        "SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id WHERE "
                        "m.workspace_id=? "
                        "AND m.user_id=? AND m.active=1 AND u.active=1 "
                        "AND m.role IN ('OWNER','REVIEWER')",
                        (workspace, assigned),
                    ).fetchone()
                ):
                    raise APIError(422, "INVALID_ASSIGNEE", "Choose an active workspace reviewer.")
                due = review_time(payload["review_on"]) if payload["review_on"] else None
                if row["state"] == "CLOSED" and state != "CLOSED":
                    outcome = None
            elif kind == "followups":
                if state == "CLOSED":
                    raise APIError(409, "ACTION_CLOSED", "Reopen the action before follow-up.")
                invoice = json.loads(row["source_json"])["invoice"]
                if payload["kind"] == "DRAFT":
                    snapshot = payload | {
                        "text": (
                            f"Please review invoice {invoice['invoice_number']} "
                            f"dated {invoice['invoice_date']} "
                            f"for supplier {invoice['supplier_gstin']}. "
                            f"Requested action: {payload['request']}. "
                            "This is a draft request; no message has been sent."
                        ),
                        "delivery": "NOT_SENT",
                    }
                    event_kind = "FOLLOWUP_DRAFT"
                else:
                    draft = connection.execute(
                        "SELECT * FROM action_events WHERE workspace_id=? AND action_id=? AND id=? "
                        "AND kind='FOLLOWUP_DRAFT'",
                        (workspace, identifier, payload["draft_id"]),
                    ).fetchone()
                    if draft is None:
                        raise APIError(
                            422, "INVALID_DRAFT", "Choose a draft belonging to this action."
                        )
                    original = json.loads(draft["snapshot_json"])
                    if (
                        original["contact"] != payload["contact"]
                        or original["request"] != payload["request"]
                    ):
                        raise APIError(
                            422, "DRAFT_CHANGED", "The recorded attempt must use its draft details."
                        )
                    if payload["observed_on"] > datetime.now(UTC).date().isoformat():
                        raise APIError(422, "OBSERVATION_DATE", "Attempt cannot be future-dated.")
                    snapshot = payload | {"delivery": "USER_REPORTED_ATTEMPT_UNVERIFIED"}
                    event_kind = "FOLLOWUP_ATTEMPT"
                    state = "AWAITING_SUPPLIER"
            elif kind == "outcomes":
                if state == "CLOSED":
                    raise APIError(
                        409, "ACTION_CLOSED", "Reopen the action before another outcome."
                    )
                source = json.loads(row["source_json"])
                amount = payload["amount"]
                upper = source.get("case_amount") or source["invoice"]["gross_total"]
                if amount is not None and money_paise(amount, "gross_total") > money_paise(
                    upper, "gross_total"
                ):
                    raise APIError(
                        422, "OUTCOME_AMOUNT", "Outcome exceeds the recorded case/source amount."
                    )
                if payload["kind"] == "FILING_OBSERVATION":
                    if money_paise(amount, "gross_total") <= 0:
                        raise APIError(
                            422, "OUTCOME_AMOUNT", "A filing observation needs a positive amount."
                        )
                    if row["kind"] != "RULE37A_REVIEW" or not source["review"]["reclaim_candidate"]:
                        raise APIError(
                            409,
                            "RECLAIM_EVIDENCE_REQUIRED",
                            "Reclaim observation requires its supporting case.",
                        )
                    if amount is not None and money_paise(amount, "gross_total") > money_paise(
                        source["review"]["proposed_reclaim_amount"], "gross_total"
                    ):
                        raise APIError(
                            422, "OUTCOME_AMOUNT", "Observation exceeds the recorded reversal."
                        )
                if (
                    payload["kind"] == "NOTICE_SUBMISSION_OBSERVATION"
                    and row["kind"] != "NOTICE_REVIEW"
                ):
                    raise APIError(422, "OUTCOME_KIND", "Notice submission requires a notice case.")
                refs = payload["evidence_event_ids"]
                if refs and not set(refs).issubset(set(source.get("evidence_event_ids", []))):
                    raise APIError(
                        422, "INVALID_EVIDENCE", "Evidence must belong to the linked case."
                    )
                if payload["kind"] != "REVIEW_DECISION":
                    previous = json.loads(outcome) if outcome else {}
                    if previous.get("decision") != "REVIEW_ACCEPTED":
                        raise APIError(
                            409,
                            "REVIEW_OUTCOME_REQUIRED",
                            "Record an accepted review before a submission observation.",
                        )
                    documents = {
                        r[0]
                        for r in connection.execute(
                            "SELECT id FROM case_events WHERE workspace_id=? AND case_id=? "
                            "AND kind='DOCUMENT' AND import_id IS NOT NULL",
                            (workspace, row["case_id"]),
                        )
                    }
                    if not documents.intersection(refs):
                        raise APIError(
                            422,
                            "DOCUMENT_EVIDENCE_REQUIRED",
                            "Submission observations require a linked supporting document.",
                        )
                    if (
                        payload["kind"] == "NOTICE_SUBMISSION_OBSERVATION"
                        and self.cases.detail_row(
                            connection, self.scoped(connection, "cases", workspace, row["case_id"])
                        )["missing_facts"]
                    ):
                        raise APIError(
                            409,
                            "NOTICE_EVIDENCE_REQUIRED",
                            "Complete recorded notice facts before a submission observation.",
                        )
                snapshot = payload | {"government_verified": False, "execution": "NOT_PERFORMED"}
                if source["provenance"] == "SYNTHETIC_DEMO":
                    snapshot["provenance"] = "SYNTHETIC_DEMO"
                outcome = encode(snapshot)
                state = (
                    "EVIDENCE_REQUIRED"
                    if payload["decision"] == "EVIDENCE_REQUIRED"
                    else "REVIEW_REQUIRED"
                )
                event_kind = payload["kind"]
            else:
                raise ValueError("Unsupported action command")
            connection.execute(
                "UPDATE business_actions SET "
                "state=?,due_at=?,reminded_at=?,assigned_to=?,outcome_json=?,"
                "version=version+1,updated_at=? WHERE workspace_id=? AND id=?",
                (
                    state,
                    due,
                    row["reminded_at"] if due == row["due_at"] else None,
                    assigned,
                    outcome,
                    int(time.time()),
                    workspace,
                    identifier,
                ),
            )
            updated = self.row(connection, workspace, identifier)
            self.event(
                connection,
                updated,
                event_kind,
                payload["reason"],
                snapshot,
                identity.user_id,
                request_id,
            )
            response = self.detail_row(connection, updated)
            self.record(connection, identity, workspace, route, key, payload, response)
            return response

    def worksheet(self, identity, workspace, identifier):
        data = self.detail(identity, workspace, identifier)
        return {
            "label": "REVIEW_WORKSHEET_NOT_FILED_RETURN",
            "action_id": data["id"],
            "version": data["version"],
            "sources_current": data["sources_current"],
            "source": data["source"],
            "reviewed_outcome": data["outcome"],
            "pending_action_state": data["state"],
            "next_review_at": data["due_at"],
            "filing_execution": "NOT_IMPLEMENTED",
            "recovery_guarantee": False,
        }
