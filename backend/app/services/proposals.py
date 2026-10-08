"""Immutable, evidence-backed allocations; approval is never a bank instruction."""

import json
import time

from app.domain.imports import money_paise, money_string
from app.domain.workflows import allocations_within_balances
from app.errors import APIError
from app.services.imports import digest, encode
from app.services.runs import document_id
from app.services.workflows import WorkflowService


class ProposalService(WorkflowService):
    def __init__(self, runs, cases):
        super().__init__(runs)
        self.cases = cases

    def current(self, connection, row):
        snapshot = json.loads(row["snapshot_json"])
        run = self.runs.scoped(connection, row["workspace_id"], row["run_id"])
        if (
            run["state"] != "COMPLETED"
            or run["version"] != snapshot["run_version"]
            or not self.runs.sources_current(connection, run)
        ):
            return False
        for item in snapshot["balances"]:
            result = self.scoped(connection, "run_results", row["workspace_id"], item["result_id"])
            case = self.scoped(connection, "cases", row["workspace_id"], item["case_id"])
            if (
                result["version"] != item["result_version"]
                or case["version"] != item["case_version"]
                or not self.cases.sources_current(connection, case)
            ):
                return False
        return True

    def detail_row(self, connection, row):
        data = dict(row)
        data["snapshot"] = json.loads(data.pop("snapshot_json"))
        data.pop("created_by")
        data["stored_state"] = data["state"]
        data["sources_current"] = self.current(connection, row)
        if not data["sources_current"]:
            data["state"] = "STALE"
        data["timeline"] = [
            dict(event)
            for event in connection.execute(
                "SELECT * FROM proposal_events WHERE workspace_id=? AND proposal_id=? "
                "ORDER BY version,id",
                (row["workspace_id"], row["id"]),
            )
        ]
        return data

    def event(self, connection, identity, row, action, reason, request_id):
        connection.execute(
            "INSERT INTO proposal_events VALUES (?,?,?,?,?,?,?,?,?)",
            (
                self.identifier(),
                row["workspace_id"],
                row["id"],
                identity.user_id,
                action,
                reason,
                row["version"],
                request_id,
                int(time.time()),
            ),
        )

    def create(self, identity, workspace, payload, key, request_id):
        with self.store.transaction() as connection:
            self.authorize(connection, identity, workspace, mutation=True)
            cached = self.operation(connection, identity, workspace, "proposals", key, payload)
            if cached is not None:
                return cached
            self.limit(
                connection, "proposals", workspace, self.settings.max_proposals_per_workspace
            )
            run = self.runs.scoped(connection, workspace, payload["run_id"])
            self.version(run, payload["expected_run_version"])
            if run["state"] != "COMPLETED" or not self.runs.sources_current(connection, run):
                raise APIError(409, "STALE_SOURCE", "A current completed run is required.")
            observations = {item["document_id"]: item for item in payload["balance_observations"]}
            if len(observations) != len(payload["balance_observations"]):
                raise APIError(422, "DUPLICATE_BALANCE", "Record one balance per document.")
            balances, snapshots, provenance = (
                {},
                [],
                self.runs.detail_row(connection, run)["provenance"],
            )
            versions = payload["expected_result_versions"]
            for result_id, expected in versions.items():
                if expected <= 0:
                    raise APIError(422, "INVALID_VERSION", "Positive versions are required.")
                result = self.scoped(connection, "run_results", workspace, result_id)
                self.version(result, expected)
                if result["run_id"] != run["id"] or result["status"] not in {
                    "EXACT_MATCH",
                    "REVIEW_ACCEPTED",
                }:
                    raise APIError(
                        422,
                        "RESULT_NOT_ACCEPTED",
                        "Only accepted current results may be allocated.",
                    )
                canonical = json.loads(result["canonical_json"])
                if canonical["document_type"] == "CREDIT_NOTE":
                    raise APIError(
                        422, "CREDIT_NOTE_REVIEW", "Credit notes need separate adjustment review."
                    )
                document = document_id(result["purchase_import_id"], result["source_row_number"])
                observation = observations.get(document)
                if observation is None:
                    raise APIError(
                        422, "BALANCE_REQUIRED", "Recorded payment evidence is required."
                    )
                case = self.scoped(connection, "cases", workspace, observation["evidence_case_id"])
                self.version(case, observation["expected_case_version"])
                facts = json.loads(case["facts_json"])
                if (
                    not self.cases.sources_current(connection, case)
                    or case["purchase_document_id"] != document
                    or case["state"] not in {"REVIEW_READY", "CLOSED"}
                    or "PAYMENT_OBSERVATION" not in self.cases.evidence_kinds(connection, case)
                    or facts.get("amount_paid") is None
                    or facts.get("payment_observed_on") is None
                ):
                    raise APIError(
                        422, "BALANCE_REQUIRED", "A reviewed payment observation is required."
                    )
                gross = money_paise(canonical["gross_total"], "gross_total")
                paid = money_paise(facts["amount_paid"], "gross_total")
                if paid > gross:
                    raise APIError(
                        422, "BALANCE_EXCEEDED", "Recorded payment exceeds source gross."
                    )
                balances[document] = gross - paid
                snapshots.append(
                    {
                        "document_id": document,
                        "result_id": result_id,
                        "result_version": result["version"],
                        "case_id": case["id"],
                        "case_version": case["version"],
                        "observation_refs": facts["observation_refs"],
                        "gross_total": money_string(gross),
                        "amount_paid": money_string(paid),
                        "remaining_balance": money_string(gross - paid),
                        "payment_observed_on": facts["payment_observed_on"],
                        "invoice_number": canonical["invoice_number"],
                        "supplier_gstin": canonical["supplier_gstin"],
                    }
                )
                if case["provenance"] == "SYNTHETIC_DEMO":
                    provenance = "SYNTHETIC_DEMO"
            if set(observations) != set(balances):
                raise APIError(
                    422, "INVALID_BALANCE", "Balance documents must match selected results."
                )
            total = allocations_within_balances(payload["allocations"], balances)
            snapshot = {
                "run_id": run["id"],
                "run_version": run["version"],
                "currency": "INR",
                "provenance": provenance,
                "balances": snapshots,
                "allocations": payload["allocations"],
                "total_allocated": money_string(total),
                "instruction": "PROPOSAL_ONLY; human review required; no payment execution.",
            }
            now, identifier = int(time.time()), self.identifier()
            connection.execute(
                "INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    workspace,
                    run["id"],
                    encode(snapshot),
                    digest(snapshot),
                    "DRAFT",
                    1,
                    identity.user_id,
                    now,
                    now,
                ),
            )
            row = self.scoped(connection, "proposals", workspace, identifier)
            self.event(connection, identity, row, "CREATE", "Created reviewable draft.", request_id)
            response = self.detail_row(connection, row)
            self.record(connection, identity, workspace, "proposals", key, payload, response)
            return response

    def approve(self, identity, workspace, identifier, payload, key, request_id):
        route = f"proposals/{identifier}/approve"
        with self.store.transaction() as connection:
            self.authorize(connection, identity, workspace, mutation=True)
            cached = self.operation(connection, identity, workspace, route, key, payload)
            if cached is not None:
                return cached
            row = self.scoped(connection, "proposals", workspace, identifier)
            self.version(row, payload["expected_version"])
            if row["state"] != "DRAFT" or not self.current(connection, row):
                raise APIError(409, "PROPOSAL_NOT_CURRENT", "Only a current draft can be approved.")
            connection.execute(
                "UPDATE proposals SET state='APPROVED',version=version+1,updated_at=? "
                "WHERE workspace_id=? AND id=?",
                (int(time.time()), workspace, identifier),
            )
            row = self.scoped(connection, "proposals", workspace, identifier)
            self.event(connection, identity, row, "APPROVE", payload["reason"], request_id)
            response = self.detail_row(connection, row)
            self.record(connection, identity, workspace, route, key, payload, response)
            return response

    def detail(self, identity, workspace, identifier):
        with self.store.transaction(write=False) as connection:
            self.authorize(connection, identity, workspace)
            return self.detail_row(
                connection, self.scoped(connection, "proposals", workspace, identifier)
            )

    def list_proposals(self, identity, workspace, cursor, limit, registration=None, period=None):
        with self.store.transaction(write=False) as connection:
            self.authorize(connection, identity, workspace)
            rows = connection.execute(
                "SELECT p.* FROM proposals p JOIN runs r "
                "ON r.workspace_id=p.workspace_id AND r.id=p.run_id "
                "WHERE p.workspace_id=? AND p.id>? "
                "AND (? IS NULL OR r.registration_id=?) AND (? IS NULL OR r.period=?) "
                "ORDER BY p.id LIMIT ?",
                (workspace, cursor, registration, registration, period, period, limit + 1),
            ).fetchall()
            return {
                "proposals": [self.detail_row(connection, row) for row in rows[:limit]],
                "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None,
            }
