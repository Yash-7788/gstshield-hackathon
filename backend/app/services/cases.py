"""Durable evidence cases with explicit transitions and versioned observation history."""

import json
import re
import time

from app.domain.imports import money_paise, money_string
from app.domain.workflows import missing_facts, validate_facts
from app.errors import APIError
from app.services.imports import encode
from app.services.runs import document_id
from app.services.workflows import WorkflowService


class CaseService(WorkflowService):
    def source_gross(self, connection, case):
        result = self.scoped(connection, "run_results", case["workspace_id"], case["result_id"])
        return money_paise(json.loads(result["canonical_json"])["gross_total"], "gross_total")

    def events(self, connection, row):
        return [
            dict(item)
            for item in connection.execute(
                "SELECT * FROM case_events WHERE workspace_id=? AND case_id=? ORDER BY version,id",
                (row["workspace_id"], row["id"]),
            )
        ]

    def evidence_kinds(self, connection, row):
        refs = set(json.loads(row["facts_json"])["observation_refs"])
        facts = json.loads(row["facts_json"])
        fields = {
            "PAYMENT_OBSERVATION": ("amount_paid", "payment_observed_on"),
            "ACCEPTANCE_OBSERVATION": (
                "acceptance_date",
                "agreed_credit_days",
                "supplier_classification",
            ),
            "FILING_OBSERVATION": (
                "supplier_return_period",
                "supplier_return_status",
                "filing_observed_on",
            ),
            "IRN_OBSERVATION": ("irn", "applicability"),
        }
        kinds = set()
        for event in self.events(connection, row):
            saved = json.loads(event["facts_json"])
            if event["id"] in refs and all(
                saved.get(name) == facts.get(name) for name in fields.get(event["kind"], ())
            ):
                kinds.add(event["kind"])
        return kinds

    def detail_row(self, connection, row):
        data = dict(row)
        data["amount"] = money_string(data["amount"])
        data["facts"] = json.loads(data.pop("facts_json"))
        data.pop("created_by")
        data["missing_facts"] = missing_facts(
            row["kind"], data["facts"], self.evidence_kinds(connection, row)
        )
        irn = data["facts"].get("irn")
        data["irn_observation"] = (
            "NOT_PROVIDED"
            if not irn
            else "FORMAT_ONLY"
            if re.fullmatch(r"[0-9a-fA-F]{64}", irn)
            else "FORMAT_INVALID"
        )
        data["timeline"] = self.events(connection, row)
        for event in data["timeline"]:
            event["facts"] = json.loads(event.pop("facts_json"))
            raw = event.pop("evidence_json")
            event["evidence_source"] = json.loads(raw) if raw else None
        return data

    def event(
        self,
        connection,
        identity,
        row,
        kind,
        reason,
        request_id,
        *,
        import_id=None,
        evidence_source=None,
        facts=None,
        from_state=None,
        identifier=None,
    ):
        connection.execute(
            "INSERT INTO case_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                identifier or self.identifier(),
                row["workspace_id"],
                row["id"],
                identity.user_id,
                kind,
                import_id,
                encode(evidence_source) if evidence_source else None,
                reason,
                encode(facts or {}),
                row["provenance"],
                from_state or row["state"],
                row["state"],
                row["version"],
                request_id,
                int(time.time()),
            ),
        )

    def check_refs(self, connection, row, facts):
        allowed = {
            event["id"]
            for event in self.events(connection, row)
            if event["kind"] not in {"CREATE", "TRANSITION", "NOTE"}
        }
        if not set(facts["observation_refs"]).issubset(allowed):
            raise APIError(422, "INVALID_EVIDENCE", "Observation must belong to this case.")

    def create(self, identity, workspace, payload, key, request_id):
        with self.store.transaction() as connection:
            self.authorize(connection, identity, workspace, mutation=True)
            cached = self.operation(connection, identity, workspace, "cases", key, payload)
            if cached is not None:
                return cached
            self.limit(connection, "cases", workspace, self.settings.max_cases_per_workspace)
            result = self.scoped(connection, "run_results", workspace, payload["result_id"])
            run = self.runs.scoped(connection, workspace, result["run_id"])
            if (
                run["registration_id"] != payload["registration_id"]
                or document_id(result["purchase_import_id"], result["source_row_number"])
                != payload["purchase_document_id"]
            ):
                raise APIError(422, "CASE_CONTEXT", "Case must refer to its source document.")
            gross = money_paise(json.loads(result["canonical_json"])["gross_total"], "gross_total")
            case_amount = money_paise(payload["amount"], "gross_total")
            if case_amount > gross:
                raise APIError(422, "CASE_AMOUNT", "Case amount exceeds recorded source gross.")
            facts = validate_facts(payload["kind"], payload["facts"], gross)
            if facts["observation_refs"]:
                raise APIError(422, "INVALID_EVIDENCE", "Add observations after creating the case.")
            provenance = self.runs.detail_row(connection, run)["provenance"]
            now, identifier = int(time.time()), self.identifier()
            connection.execute(
                "INSERT INTO cases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    workspace,
                    payload["registration_id"],
                    result["id"],
                    payload["purchase_document_id"],
                    payload["kind"],
                    case_amount,
                    "INR",
                    encode(facts),
                    provenance,
                    "OPEN",
                    1,
                    identity.user_id,
                    now,
                    now,
                ),
            )
            row = self.scoped(connection, "cases", workspace, identifier)
            self.event(connection, identity, row, "CREATE", "Created for human review.", request_id)
            response = self.detail_row(connection, row)
            self.record(connection, identity, workspace, "cases", key, payload, response)
            return response

    def mutate(
        self, identity, workspace, identifier, payload, key, request_id, *, transition=False
    ):
        route = f"cases/{identifier}/" + ("transition" if transition else "evidence")
        with self.store.transaction() as connection:
            self.authorize(connection, identity, workspace, mutation=True)
            cached = self.operation(connection, identity, workspace, route, key, payload)
            if cached is not None:
                return cached
            row = self.scoped(connection, "cases", workspace, identifier)
            self.version(row, payload["expected_version"])
            if len(self.events(connection, row)) >= self.settings.max_case_events:
                raise APIError(409, "EVIDENCE_LIMIT", "Case history limit reached.")
            facts, state, provenance = (
                json.loads(row["facts_json"]),
                row["state"],
                row["provenance"],
            )
            event_id, import_id = self.identifier(), None
            evidence_source = None
            if transition:
                permitted = {
                    "OPEN": {"EVIDENCE_REQUIRED"},
                    "EVIDENCE_REQUIRED": {"REVIEW_READY"},
                    "REVIEW_READY": {"CLOSED", "EVIDENCE_REQUIRED"},
                    "CLOSED": {"OPEN"},
                }
                target = payload["state"]
                if target not in permitted[state]:
                    raise APIError(409, "INVALID_TRANSITION", "Case transition is not permitted.")
                if target == "REVIEW_READY" and missing_facts(
                    row["kind"], facts, self.evidence_kinds(connection, row)
                ):
                    raise APIError(
                        409, "EVIDENCE_REQUIRED", "Required facts or evidence are missing."
                    )
                state, event_kind = target, "TRANSITION"
            else:
                if state == "CLOSED":
                    raise APIError(409, "CASE_CLOSED", "Reopen the case before adding evidence.")
                event_kind, import_id = payload["event_kind"], payload["import_id"]
                if import_id:
                    imported = self.imports.scoped(
                        connection, identity, workspace, import_id, mutation=True
                    )
                    if imported["registration_id"] != row["registration_id"]:
                        raise APIError(422, "EVIDENCE_CONTEXT", "Evidence registration differs.")
                    evidence_source = {
                        name: imported[name]
                        for name in (
                            "id",
                            "version",
                            "file_sha256",
                            "adapter_version",
                            "provenance",
                        )
                    }
                    if imported["provenance"] == "SYNTHETIC_DEMO":
                        provenance = "SYNTHETIC_DEMO"
                if event_kind == "DOCUMENT" and not import_id:
                    raise APIError(422, "EVIDENCE_REQUIRED", "Document evidence needs an import.")
                facts = validate_facts(
                    row["kind"], facts | payload["facts_patch"], self.source_gross(connection, row)
                )
                self.check_refs(connection, row, facts)
                if event_kind != "NOTE":
                    if len(facts["observation_refs"]) >= 20:
                        raise APIError(
                            409, "EVIDENCE_LIMIT", "Observation reference limit reached."
                        )
                    facts["observation_refs"].append(event_id)
                if state == "REVIEW_READY":
                    state = "EVIDENCE_REQUIRED"
            connection.execute(
                "UPDATE cases SET facts_json=?,state=?,provenance=?,version=version+1,"
                "updated_at=? WHERE workspace_id=? AND id=?",
                (encode(facts), state, provenance, int(time.time()), workspace, identifier),
            )
            updated = self.scoped(connection, "cases", workspace, identifier)
            self.event(
                connection,
                identity,
                updated,
                event_kind,
                payload["reason"],
                request_id,
                import_id=import_id,
                evidence_source=evidence_source,
                facts=facts,
                from_state=row["state"],
                identifier=event_id,
            )
            response = self.detail_row(connection, updated)
            self.record(connection, identity, workspace, route, key, payload, response)
            return response

    def detail(self, identity, workspace, identifier):
        with self.store.transaction(write=False) as connection:
            self.authorize(connection, identity, workspace)
            return self.detail_row(
                connection, self.scoped(connection, "cases", workspace, identifier)
            )

    def list_cases(self, identity, workspace, cursor, limit, registration=None, period=None):
        with self.store.transaction(write=False) as connection:
            self.authorize(connection, identity, workspace)
            rows = connection.execute(
                "SELECT c.* FROM cases c JOIN run_results rr "
                "ON rr.workspace_id=c.workspace_id AND rr.id=c.result_id "
                "JOIN runs r ON r.workspace_id=rr.workspace_id AND r.id=rr.run_id "
                "WHERE c.workspace_id=? AND c.id>? "
                "AND (? IS NULL OR c.registration_id=?) AND (? IS NULL OR r.period=?) "
                "ORDER BY c.id LIMIT ?",
                (workspace, cursor, registration, registration, period, period, limit + 1),
            ).fetchall()
            return {
                "cases": [self.detail_row(connection, row) for row in rows[:limit]],
                "next_cursor": rows[limit - 1]["id"] if len(rows) > limit else None,
            }
