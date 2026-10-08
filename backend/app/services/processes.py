"""Sequential team workflows with current evidence, exit checks and retained handoffs."""

import json
import time
from types import SimpleNamespace

from app.domain.tax_guidance import suggestions
from app.errors import APIError
from app.security.roles import require_role
from app.services.imports import digest, encode
from app.services.workflows import WorkflowService

STEPS = [
    ("INTAKE", "Bring the invoice"),
    ("CONFIRM", "Confirm the bill details"),
    ("COMMERCIAL", "Check order and delivery"),
    ("GST", "Compare the GST record"),
    ("RISK", "Review risks and dates"),
    ("PAYMENT", "Review the payment decision"),
    ("CORRECTION", "Follow up with the supplier"),
    ("RECHECK", "Recheck the corrected evidence"),
    ("TAX", "Confirm tax-review actions"),
    ("COMPLETE", "Complete the reviewed process"),
]
NODE_ROLES = {
    "INTAKE": {"ACCOUNTS", "CA"},
    "CONFIRM": {"ACCOUNTS", "CA"},
    "COMMERCIAL": {"WAREHOUSE", "CA"},
    "GST": {"CA"},
    "RISK": {"CA", "CFO"},
    "PAYMENT": {"CA", "CFO"},
    "CORRECTION": {"FOLLOWUP", "CA"},
    "RECHECK": {"CA"},
    "TAX": {"CA"},
    "COMPLETE": {"CA", "CFO"},
}


class ProcessService(WorkflowService):
    def __init__(self, guidance):
        super().__init__(guidance.runs)
        self.guidance = guidance
        self.business = guidance.business
        self.passports = guidance.passports
        self.scan_cursors = {}

    def row(self, con, ws, identifier):
        row = con.execute(
            "SELECT * FROM workflow_run WHERE workspace_id=? AND id=?", (ws, identifier)
        ).fetchone()
        if row is None:
            raise APIError(404, "NOT_FOUND", "Process was not found.")
        return row

    def node(self, con, ws, nid):
        row = con.execute("SELECT * FROM node WHERE workspace_id=? AND id=?", (ws, nid)).fetchone()
        if row is None:
            raise APIError(404, "NOT_FOUND", "Process step was not found.")
        return row

    def quota(self, con, ws, table, maximum):
        if table not in {"workflow_run", "node_event", "assignment", "process_notification"}:
            raise ValueError("Unsupported quota")
        if (
            con.execute(f"SELECT COUNT(*) FROM {table} WHERE workspace_id=?", (ws,)).fetchone()[0]
            >= maximum
        ):
            raise APIError(409, "HISTORY_LIMIT", "Local process history limit reached.")

    def event(self, con, identity, row, node, kind, before, after, signature, note):
        self.quota(con, row["workspace_id"], "node_event", 10000)
        con.execute(
            "INSERT INTO node_event VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                self.identifier(),
                row["workspace_id"],
                row["id"],
                node["id"] if node else None,
                identity.user_id,
                kind,
                before,
                after,
                signature,
                note,
                int(time.time()),
            ),
        )

    def notify(self, con, row, recipients, kind, payload):
        for uid in set(recipients):
            if con.execute(
                "SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id WHERE"
                " m.workspace_id=? AND m.user_id=? AND m.active=1 AND u.active=1",
                (row["workspace_id"], uid),
            ).fetchone():
                self.quota(con, row["workspace_id"], "process_notification", 10000)
                con.execute(
                    "INSERT INTO process_notification VALUES(?,?,?,?,?,?,0,?)",
                    (
                        self.identifier(),
                        row["workspace_id"],
                        uid,
                        row["id"],
                        kind,
                        encode(payload),
                        int(time.time()),
                    ),
                )

    def context(self, con, identity, row):
        ws = row["workspace_id"]
        batch = None
        coverage = True
        if row["passport_id"]:
            pids = [row["passport_id"]]
        else:
            batch = self.runs.scoped(con, ws, row["batch_id"])
            pids = [
                x[0]
                for x in con.execute(
                    "SELECT id FROM invoice_passports WHERE workspace_id=? AND "
                    "registration_id=? AND period=? AND purchase_import_id=? ORDER BY"
                    " id LIMIT 101",
                    (ws, row["registration_id"], row["period"], batch["purchase_import_id"]),
                )
            ]
            accepted = con.execute(
                "SELECT COUNT(*) FROM import_rows WHERE workspace_id=? AND "
                "import_id=? AND accepted=1 AND "
                "json_extract(canonical_json,'$.document_type')!='CREDIT_NOTE'",
                (ws, batch["purchase_import_id"]),
            ).fetchone()[0]
            bindings = [
                json.loads(x[0]).get("row_number")
                for x in con.execute(
                    "SELECT payload_json FROM passport_events WHERE workspace_id=? "
                    "AND action='PURCHASE_LINKED' AND passport_id IN (SELECT id FROM "
                    "invoice_passports WHERE workspace_id=? AND purchase_import_id=?)",
                    (ws, ws, batch["purchase_import_id"]),
                )
            ]
            coverage = (
                accepted > 0
                and (len(set(bindings)) == accepted or accepted == len(pids) == 1)
                and len(pids) <= 100
            )
        snapshots = [self.guidance.snapshot(con, identity, ws, pid) for pid in pids[:100]]
        bases = []
        checks = []
        titles = []
        for view, facts, signature in snapshots:
            f = facts["facts"] if facts["state"] == "CURRENT" else {}
            tax = suggestions(view, f, signature)
            reviews = [
                dict(x)
                for x in con.execute(
                    "SELECT * FROM tax_suggestion_review WHERE workspace_id=? AND "
                    "passport_id=? ORDER BY rowid DESC LIMIT 100",
                    (ws, view["id"]),
                )
            ]
            latest = {}
            for review in reviews:
                latest.setdefault(review["suggestion_id"], review)
            tax_ok = all(
                e["id"] in latest
                and latest[e["id"]]["fingerprint"] == signature
                and latest[e["id"]]["conclusion"] != "MORE_EVIDENCE"
                for e in tax
            )
            findings = view["findings"]
            approval = view["approval"]
            resolution = view["resolution"]
            basis = [
                digest(
                    {
                        "id": view["id"],
                        "document": view["filename"],
                        "extraction": view["extraction"],
                    }
                ),
                digest({"fields": view["fields"], "confirmed": view["confirmed"]}),
                digest(
                    {
                        "fields": view["fields"],
                        "po": findings.get("po_items"),
                        "receipt": findings.get("receipt_items"),
                    }
                ),
                view["source_signature"],
                signature,
                digest({"risk": signature, "approval": approval}),
                digest({"source": signature, "resolution": resolution}),
                view["source_signature"],
                digest({"source": signature, "reviews": latest}),
                digest(
                    {
                        "source": signature,
                        "approval": approval,
                        "resolution": resolution,
                        "reviews": latest,
                    }
                ),
            ]
            okay = [
                True,
                view["confirmed"] and findings.get("purchase_source_current", False),
                findings["po"] == findings["receipt"] == "MATCHED",
                bool(
                    findings.get("gst_source")
                    and findings["gst_source"]["state"] == "READY"
                    and findings["gst"] != "REVIEW"
                ),
                view["confirmed"],
                bool(approval and approval["state"] == "APPROVED"),
                findings["summary"] == "MATCHED"
                or resolution["state"] in {"ACKNOWLEDGED", "PROMISED", "RESOLVED", "ESCALATED"},
                findings["summary"] == "MATCHED",
                tax_ok,
                findings["summary"] == "MATCHED"
                and bool(approval and approval["state"] == "APPROVED")
                and tax_ok,
            ]
            bases.append(basis)
            checks.append(okay)
            titles.append(view["fields"].get("invoice_number") or view["filename"])
        batch_ok = not batch or (
            batch["state"] == "COMPLETED" and self.runs.sources_current(con, batch)
        )
        node_basis = [
            digest(
                {
                    "sources": [x[i] for x in bases],
                    "coverage": coverage,
                    "batch": dict(batch) if batch and i in {3, 9} else None,
                }
            )
            for i in range(len(STEPS))
        ]
        exit_checks = [
            bool(checks)
            and coverage
            and all(x[i] for x in checks)
            and (batch_ok if i in {3, 9} else True)
            for i in range(len(STEPS))
        ]
        signature = digest({"bases": node_basis, "exit": exit_checks})
        reasons = [
            "A saved invoice or covered batch is needed.",
            "Confirm the proposed invoice fields.",
            "Supply matching item-level order and delivery records.",
            "Choose a current GST statement and complete its comparison.",
            "Review the visible risk and missing-fact signals.",
            "Save an explicit payment decision using current evidence.",
            "Track the supplier response, or show that no correction is needed.",
            "Order, receipt, invoice and current GST evidence must align.",
            "Record a current CA review for each tax suggestion.",
            "All earlier steps, current approval and evidence must remain complete.",
        ]
        return {
            "fingerprint": signature,
            "bases": node_basis,
            "exit_checks": exit_checks,
            "reasons": reasons,
            "invoice_ids": pids[:100],
            "invoice_titles": titles,
            "invoice_group": digest(
                sorted(
                    (
                        str(v["fields"].get("supplier_gstin") or v["id"]),
                        str(v["fields"].get("invoice_number") or v["id"]).strip().upper(),
                        str(v["fields"].get("invoice_date") or ""),
                    )
                    for v, _, _ in snapshots
                )
            ),
            "coverage_complete": coverage,
            "tax_under_review": [v["gate"]["recorded_tax_under_review"] for v, _, _ in snapshots],
        }

    def refresh_row(self, con, identity, row, *, internal=False):
        ctx = self.context(con, None if internal else identity, row)
        nodes = con.execute(
            "SELECT * FROM node WHERE workspace_id=? AND run_id=? ORDER BY ordinal",
            (row["workspace_id"], row["id"]),
        ).fetchall()
        stale = next(
            (
                n["ordinal"]
                for n in nodes
                if n["state"] == "DONE"
                and (
                    n["fingerprint"] != ctx["bases"][n["ordinal"]]
                    or not ctx["exit_checks"][n["ordinal"]]
                )
            ),
            None,
        )
        if stale is not None:
            for n in nodes[stale:]:
                if n["state"] != "PENDING":
                    con.execute(
                        "UPDATE node SET state='STALE',version=version+1 WHERE id=?", (n["id"],)
                    )
                    self.event(
                        con,
                        identity,
                        row,
                        n,
                        "EVIDENCE_CHANGED",
                        n["state"],
                        "STALE",
                        ctx["fingerprint"],
                        "Relevant evidence changed. Reopen this step.",
                    )
            if row["state"] == "PROCESS_COMPLETED":
                self.event(
                    con,
                    identity,
                    row,
                    None,
                    "PROCESS_REOPENED",
                    "PROCESS_COMPLETED",
                    "IN_PROGRESS",
                    ctx["fingerprint"],
                    "Completion no longer has current evidence.",
                )
            con.execute(
                "UPDATE workflow_run SET state='IN_PROGRESS',version=version+1 WHERE id=?",
                (row["id"],),
            )
        if row["fingerprint"] != ctx["fingerprint"] or stale is not None:
            con.execute(
                "UPDATE workflow_run SET fingerprint=?,summary_json=?,updated_at=? WHERE id=?",
                (
                    ctx["fingerprint"],
                    encode(
                        {
                            "invoice_titles": ctx["invoice_titles"],
                            "coverage_complete": ctx["coverage_complete"],
                        }
                    ),
                    int(time.time()),
                    row["id"],
                ),
            )
        # Saved evidence completes data-processing steps. Risk acknowledgement and
        # final completion remain explicit human transitions.
        automatic = {
            "INTAKE",
            "CONFIRM",
            "COMMERCIAL",
            "GST",
            "PAYMENT",
            "CORRECTION",
            "RECHECK",
            "TAX",
        }
        current = con.execute(
            "SELECT * FROM node WHERE workspace_id=? AND run_id=? ORDER BY ordinal",
            (row["workspace_id"], row["id"]),
        ).fetchall()
        for n in current:
            if n["state"] == "DONE":
                continue
            if n["kind"] not in automatic or not ctx["exit_checks"][n["ordinal"]]:
                break
            now = int(time.time())
            con.execute(
                "UPDATE node SET state='DONE',version=version+1,fingerprint=?,"
                "output_json=? WHERE id=?",
                (
                    ctx["bases"][n["ordinal"]],
                    encode(
                        {
                            "automatic": True,
                            "reason": "Verified saved evidence satisfies this step",
                            "actor_id": identity.user_id,
                            "at": now,
                        }
                    ),
                    n["id"],
                ),
            )
            self.event(
                con,
                identity,
                row,
                n,
                "EVIDENCE_STEP_COMPLETED",
                n["state"],
                "DONE",
                ctx["fingerprint"],
                "Verified saved evidence satisfies this step. No new approval was made.",
            )
            con.execute("UPDATE workflow_run SET updated_at=? WHERE id=?", (now, row["id"]))
        return ctx

    def sync_invoice(self, identity, ws, pid):
        with self.store.transaction() as con:
            self.authorize(con, identity, ws)
            for row in con.execute(
                "SELECT * FROM workflow_run WHERE workspace_id=? AND passport_id=?", (ws, pid)
            ).fetchall():
                self.refresh_row(con, identity, row)

    def project(self, con, identity, row):
        ctx = self.context(con, identity, row)
        roles = set(self.business.roles(con, identity, row["workspace_id"]))
        membership = self.business.check(con, identity, row["workspace_id"])
        result = dict(row)
        result["summary"] = json.loads(result.pop("summary_json"))
        nodes = [
            dict(n)
            for n in con.execute(
                "SELECT * FROM node WHERE workspace_id=? AND run_id=? ORDER BY ordinal",
                (row["workspace_id"], row["id"]),
            )
        ]
        first_stale = next(
            (
                n["ordinal"]
                for n in nodes
                if n["state"] == "DONE"
                and (
                    n["fingerprint"] != ctx["bases"][n["ordinal"]]
                    or not ctx["exit_checks"][n["ordinal"]]
                )
            ),
            None,
        )
        for n in nodes:
            n["output"] = json.loads(n.pop("output_json"))
            if first_stale is not None and n["ordinal"] >= first_stale and n["state"] != "PENDING":
                n["state"] = "STALE"
            n["exit_ready"] = ctx["exit_checks"][n["ordinal"]]
            n["why"] = ctx["reasons"][n["ordinal"]]
            n["active"] = n["ordinal"] == 0 or all(
                p["state"] == "DONE" for p in nodes[: n["ordinal"]]
            )
            n["assignment_roles"] = sorted(NODE_ROLES[n["kind"]])
            n["can_assign"] = (
                bool(roles & {"CA", "CFO"}) and membership != "VIEWER" and n["state"] != "DONE"
            )
            n["can_update"] = (
                n["active"]
                and n["state"] != "DONE"
                and bool(roles & NODE_ROLES[n["kind"]])
                and (not n["assigned_to"] or n["assigned_to"] == identity.user_id)
            )
        if first_stale is not None:
            result["state"] = "IN_PROGRESS"
        result["fingerprint"] = ctx["fingerprint"]
        result["nodes"] = nodes
        result["invoice_ids"] = ctx["invoice_ids"]
        result["invoice_group"] = ctx["invoice_group"]
        result["coverage_complete"] = ctx["coverage_complete"]
        result["tax_under_review"] = ctx["tax_under_review"]
        result["events"] = [
            dict(e)
            for e in con.execute(
                "SELECT e.*,u.username FROM node_event e JOIN users u ON "
                "u.id=e.actor_id WHERE e.workspace_id=? AND e.run_id=? ORDER BY "
                "e.rowid DESC LIMIT 100",
                (row["workspace_id"], row["id"]),
            )
        ]
        result["edges"] = [
            dict(e)
            for e in con.execute(
                "SELECT * FROM edge WHERE workspace_id=? AND run_id=?",
                (row["workspace_id"], row["id"]),
            )
        ]
        return result

    def create(self, identity, ws, payload, key):
        with self.store.transaction() as con:
            self.authorize(con, identity, ws, mutation=True)
            previous = self.operation(con, identity, ws, "process-create", key, payload)
            if previous:
                return self.project(con, identity, self.row(con, ws, previous["id"]))
            source = (
                self.passports.row(con, ws, payload["passport_id"])
                if payload.get("passport_id")
                else self.runs.scoped(con, ws, payload["batch_id"])
            )
            existing = con.execute(
                "SELECT * FROM workflow_run WHERE workspace_id=? AND (passport_id=? OR batch_id=?)",
                (ws, payload.get("passport_id"), payload.get("batch_id")),
            ).fetchone()
            if existing:
                self.refresh_row(con, identity, existing)
                result = self.project(con, identity, self.row(con, ws, existing["id"]))
            else:
                self.quota(con, ws, "workflow_run", 200)
                template = con.execute(
                    "SELECT id FROM workflow_template WHERE workspace_id=? AND name=?",
                    (ws, "Invoice to reviewed completion"),
                ).fetchone()
                tid = template[0] if template else self.identifier()
                if not template:
                    con.execute(
                        "INSERT INTO workflow_template VALUES(?,?,?,?,1)",
                        (tid, ws, "Invoice to reviewed completion", encode(STEPS)),
                    )
                identifier = self.identifier()
                now = int(time.time())
                con.execute(
                    "INSERT INTO workflow_run VALUES(?,?,?,?,?,?,?,?,1,?,?,?,?,?)",
                    (
                        identifier,
                        ws,
                        source["registration_id"],
                        source["period"],
                        tid,
                        payload.get("passport_id"),
                        payload.get("batch_id"),
                        "IN_PROGRESS",
                        identity.user_id,
                        digest({}),
                        encode({}),
                        now,
                        now,
                    ),
                )
                ids = [self.identifier() for _ in STEPS]
                for i, (kind, title) in enumerate(STEPS):
                    con.execute(
                        "INSERT INTO node VALUES(?,?,?,?,?,?,?,1,NULL,NULL,NULL,?)",
                        (ids[i], ws, identifier, i, kind, title, "PENDING", encode({})),
                    )
                    if i:
                        con.execute(
                            "INSERT INTO edge VALUES(?,?,?,?)", (ws, identifier, ids[i - 1], ids[i])
                        )
                row = self.row(con, ws, identifier)
                ctx = self.refresh_row(con, identity, row)
                self.event(
                    con,
                    identity,
                    row,
                    None,
                    "PROCESS_CREATED",
                    "NONE",
                    "IN_PROGRESS",
                    ctx["fingerprint"],
                    "Created a source-bound review process.",
                )
                result = self.project(con, identity, self.row(con, ws, identifier))
            self.record(con, identity, ws, "process-create", key, payload, result)
            return result

    def listing(self, identity, ws, rid, period):
        with self.store.transaction(write=False) as con:
            self.authorize(con, identity, ws)
            self.passports.registration(con, ws, rid)
            return {
                "workflows": [
                    self.project(con, identity, r)
                    for r in con.execute(
                        "SELECT * FROM workflow_run WHERE workspace_id=? AND "
                        "registration_id=? AND period=? ORDER BY updated_at DESC LIMIT 50",
                        (ws, rid, period),
                    )
                ]
            }

    def detail(self, identity, ws, identifier):
        with self.store.transaction(write=False) as con:
            self.authorize(con, identity, ws)
            return self.project(con, identity, self.row(con, ws, identifier))

    def refresh(self, identity, ws, identifier, key):
        with self.store.transaction() as con:
            self.authorize(con, identity, ws)
            row = self.row(con, ws, identifier)
            previous = self.operation(con, identity, ws, "process-refresh:" + identifier, key, {})
            if previous:
                return self.project(con, identity, row)
            self.refresh_row(con, identity, row)
            result = self.project(con, identity, self.row(con, ws, identifier))
            self.record(con, identity, ws, "process-refresh:" + identifier, key, {}, result)
            return result

    def assign(self, identity, ws, nid, payload, key):
        with self.store.transaction() as con:
            self.authorize(con, identity, ws, mutation=True)
            require_role(self.business.access, con, identity, ws, {"CA", "CFO"})
            route = "node-assign:" + nid
            previous = self.operation(con, identity, ws, route, key, payload)
            if previous:
                return self.project(con, identity, self.row(con, ws, previous["id"]))
            node = self.node(con, ws, nid)
            row = self.row(con, ws, node["run_id"])
            self.refresh_row(con, identity, row)
            node = self.node(con, ws, nid)
            self.version(node, payload["expected_version"])
            member = next(
                (
                    m
                    for m in self.business.team_rows(con, ws)
                    if m["id"] == payload["user_id"] and m["active"]
                ),
                None,
            )
            if not member:
                raise APIError(404, "NOT_FOUND", "Active workspace member was not found.")
            if not set(member["roles"]) & NODE_ROLES[node["kind"]]:
                raise APIError(
                    403, "ASSIGNMENT_ROLE", "This member does not hold a role for this step."
                )
            if node["state"] == "DONE":
                raise APIError(409, "STEP_DONE", "Completed steps cannot be reassigned.")
            self.quota(con, ws, "assignment", 5000)
            con.execute(
                "UPDATE node SET "
                "assigned_to=?,due_on=?,state='ASSIGNED',version=version+1 WHERE "
                "id=?",
                (payload["user_id"], payload.get("due_on"), nid),
            )
            con.execute(
                "INSERT INTO assignment VALUES(?,?,?,?,?,?,?,?)",
                (
                    self.identifier(),
                    ws,
                    nid,
                    payload["user_id"],
                    identity.user_id,
                    payload.get("due_on"),
                    payload["note"],
                    int(time.time()),
                ),
            )
            ctx = self.context(con, identity, row)
            self.event(
                con,
                identity,
                row,
                node,
                "STEP_ASSIGNED",
                node["state"],
                "ASSIGNED",
                ctx["fingerprint"],
                payload["note"],
            )
            self.notify(
                con,
                row,
                [payload["user_id"]],
                "HANDOFF",
                {"node_id": nid, "title": node["title"], "note": payload["note"]},
            )
            self.refresh_row(con, identity, self.row(con, ws, row["id"]))
            result = self.project(con, identity, self.row(con, ws, row["id"]))
            self.record(con, identity, ws, route, key, payload, result)
            return result

    def transition(self, identity, ws, nid, payload, key):
        with self.store.transaction() as con:
            self.authorize(con, identity, ws)
            route = "node-transition:" + nid
            previous = self.operation(con, identity, ws, route, key, payload)
            if previous:
                return self.project(con, identity, self.row(con, ws, previous["id"]))
            node = self.node(con, ws, nid)
            row = self.row(con, ws, node["run_id"])
            ctx = self.refresh_row(con, identity, row)
            node = self.node(con, ws, nid)
            roles = self.business.roles(con, identity, ws)
            if not set(roles) & NODE_ROLES[node["kind"]]:
                raise APIError(403, "ROLE_FORBIDDEN", "Your role cannot complete this step.")
            if node["assigned_to"] and node["assigned_to"] != identity.user_id:
                raise APIError(
                    403, "ASSIGNED_ELSEWHERE", "This step belongs to another team member."
                )
            self.version(node, payload["expected_version"])
            if payload["fingerprint"] != ctx["fingerprint"]:
                raise APIError(409, "STALE_EVIDENCE", "Process evidence changed; refresh it first.")
            if node["state"] == "DONE":
                raise APIError(409, "STEP_DONE", "This step is already complete.")
            if (
                node["ordinal"]
                and con.execute(
                    "SELECT COUNT(*) FROM node WHERE run_id=? AND ordinal<? AND state!='DONE'",
                    (row["id"], node["ordinal"]),
                ).fetchone()[0]
            ):
                raise APIError(409, "PREDECESSOR_REQUIRED", "Complete earlier steps first.")
            target = payload["state"]
            if target == "DONE" and not ctx["exit_checks"][node["ordinal"]]:
                raise APIError(409, "EXIT_CHECK_FAILED", ctx["reasons"][node["ordinal"]])
            con.execute(
                "UPDATE node SET state=?,version=version+1,fingerprint=?,output_json=? WHERE id=?",
                (
                    target,
                    ctx["bases"][node["ordinal"]] if target == "DONE" else None,
                    encode(
                        {
                            "review_note": payload["note"],
                            "actor_id": identity.user_id,
                            "at": int(time.time()),
                        }
                    ),
                    nid,
                ),
            )
            self.event(
                con,
                identity,
                row,
                node,
                "STEP_" + target,
                node["state"],
                target,
                ctx["fingerprint"],
                payload["note"],
            )
            if target == "DONE" and node["kind"] == "COMPLETE":
                con.execute(
                    "UPDATE workflow_run SET "
                    "state='PROCESS_COMPLETED',version=version+1,updated_at=?,summary_json=?"
                    " WHERE id=?",
                    (
                        int(time.time()),
                        encode(
                            {
                                "invoice_titles": ctx["invoice_titles"],
                                "completed_by": identity.user_id,
                                "completed_at": int(time.time()),
                                "fingerprint": ctx["fingerprint"],
                                "outcome": "INTERNAL_REVIEW_COMPLETED_NOT_PAYMENT_OR_FILING",
                            }
                        ),
                        row["id"],
                    ),
                )
                self.event(
                    con,
                    identity,
                    row,
                    None,
                    "PROCESS_COMPLETED",
                    "IN_PROGRESS",
                    "PROCESS_COMPLETED",
                    ctx["fingerprint"],
                    payload["note"],
                )
                recipients = [m["id"] for m in self.business.team_rows(con, ws) if m["active"]]
                self.notify(
                    con,
                    row,
                    recipients,
                    "PROCESS_COMPLETED",
                    {
                        "summary": "Internal invoice review completed. No tax filing or bank "
                        "transfer is implied."
                    },
                )
            elif target == "DONE":
                next_node = con.execute(
                    "SELECT * FROM node WHERE run_id=? AND ordinal=?",
                    (row["id"], node["ordinal"] + 1),
                ).fetchone()
                if next_node and next_node["assigned_to"]:
                    self.notify(
                        con,
                        row,
                        [next_node["assigned_to"]],
                        "HANDOFF",
                        {"node_id": next_node["id"], "title": next_node["title"]},
                    )
            con.execute(
                "UPDATE workflow_run SET updated_at=? WHERE id=?", (int(time.time()), row["id"])
            )
            self.refresh_row(con, identity, self.row(con, ws, row["id"]))
            result = self.project(con, identity, self.row(con, ws, row["id"]))
            self.record(con, identity, ws, route, key, payload, result)
            return result

    def notifications(self, identity, ws):
        with self.store.transaction(write=False) as con:
            self.authorize(con, identity, ws)
            return {
                "notifications": [
                    dict(n) | {"payload": json.loads(n["payload_json"])}
                    for n in con.execute(
                        "SELECT * FROM process_notification WHERE workspace_id=? AND "
                        "recipient_id=? ORDER BY rowid DESC LIMIT 100",
                        (ws, identity.user_id),
                    )
                ]
            }

    def read_notification(self, identity, ws, nid, key):
        with self.store.transaction() as con:
            self.authorize(con, identity, ws)
            route = "notification-read:" + nid
            previous = self.operation(con, identity, ws, route, key, {})
            if previous:
                return previous
            row = con.execute(
                "SELECT * FROM process_notification WHERE workspace_id=? AND "
                "recipient_id=? AND id=?",
                (ws, identity.user_id, nid),
            ).fetchone()
            if not row:
                raise APIError(404, "NOT_FOUND", "Notification was not found.")
            con.execute("UPDATE process_notification SET read=1 WHERE id=?", (nid,))
            self.business.audit(con, identity, ws, "NOTIFICATION_READ", {"id": nid})
            result = {"id": nid, "read": True}
            self.record(con, identity, ws, route, key, {}, result)
            return result

    def scan(self, ws):
        # Internal monitor revalidates the recorded creator; it never invents a session or approval.
        with self.store.transaction() as con:
            cursor = self.scan_cursors.get(ws, "")
            rows = con.execute(
                "SELECT w.* FROM workflow_run w JOIN memberships m ON "
                "m.workspace_id=w.workspace_id AND m.user_id=w.created_by JOIN "
                "users u ON u.id=m.user_id WHERE w.workspace_id=? AND m.active=1 "
                "AND u.active=1 AND w.id>? ORDER BY w.id LIMIT 50",
                (ws, cursor),
            ).fetchall()
            for row in rows:
                actor = SimpleNamespace(user_id=row["created_by"])
                self.refresh_row(con, actor, row, internal=True)
            # Move only after successful processing, so every bounded run gets checked.
            self.scan_cursors[ws] = rows[-1]["id"] if len(rows) == 50 else ""
