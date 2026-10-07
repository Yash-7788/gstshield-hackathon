"""Shared workspace scope, bounded history and atomic idempotent commands."""

import json
from uuid import uuid4

from app.errors import APIError
from app.services.imports import digest, encode


class WorkflowService:
    def __init__(self, runs):
        self.runs = runs
        self.imports = runs.imports
        self.store = runs.store
        self.settings = runs.settings
        self.access = runs.access

    def authorize(self, connection, identity, workspace, *, mutation=False):
        self.runs.authorize(connection, identity, workspace, mutation=mutation)

    def scoped(self, connection, table, workspace, identifier):
        if table not in {"cases", "proposals", "artifacts", "run_results"}:
            raise ValueError("Unsupported resource")
        row = connection.execute(
            f"SELECT * FROM {table} WHERE workspace_id=? AND id=?", (workspace, identifier)
        ).fetchone()
        if row is None:
            raise APIError(404, "NOT_FOUND", "Resource was not found.")
        return row

    def operation(self, connection, identity, workspace, route, key, payload):
        row = connection.execute(
            "SELECT * FROM workflow_operations WHERE workspace_id=? AND actor_id=? "
            "AND route=? AND key=?",
            (workspace, identity.user_id, route, key),
        ).fetchone()
        if row:
            if row["request_hash"] != digest(payload):
                raise APIError(409, "IDEMPOTENCY_CONFLICT", "Request key already used.")
            return json.loads(row["response_json"])
        self.limit(connection, "workflow_operations", workspace, 1000)
        return None

    def record(self, connection, identity, workspace, route, key, payload, response):
        connection.execute(
            "INSERT INTO workflow_operations VALUES (?,?,?,?,?,?)",
            (workspace, identity.user_id, route, key, digest(payload), encode(response)),
        )

    def limit(self, connection, table, workspace, maximum):
        if table not in {"cases", "proposals", "artifacts", "workflow_operations"}:
            raise ValueError("Unsupported quota")
        if (
            connection.execute(
                f"SELECT count(*) FROM {table} WHERE workspace_id=?", (workspace,)
            ).fetchone()[0]
            >= maximum
        ):
            raise APIError(409, "WORKSPACE_LIMIT", "Workspace resource limit reached.")

    @staticmethod
    def version(row, expected):
        if row["version"] != expected:
            raise APIError(409, "VERSION_CONFLICT", "Resource changed; reload before editing.")

    @staticmethod
    def identifier():
        return str(uuid4())
