"""Expensive scoped credential receipts; preserve retry history without cheap verifiers."""

import hashlib

from app.services.access import password_digest
from app.services.imports import digest, encode


def credential_payload(workspace, actor, route, key, inner_hash):
    salt = hashlib.sha256(encode([workspace, actor, route, key]).encode()).digest()[:16]
    return {"credential_binding_v2": password_digest(inner_hash, salt).hex()}


def upgrade_receipts(store, workspace):
    """Offline, workspace-scoped migration. Preserve keys and exact response history."""
    with store.transaction(write=False) as con:
        rows = con.execute(
            "SELECT * FROM workflow_operations WHERE workspace_id=? AND "
            "(route IN ('member-create','team-setup') OR route LIKE 'member-password:%')",
            (workspace,),
        ).fetchall()
    changed = 0
    for row in rows:
        binding = credential_payload(
            workspace, row["actor_id"], row["route"], row["key"], row["request_hash"]
        )
        new_route = (
            "member-password-v2:" + row["route"].split(":", 1)[1]
            if row["route"].startswith("member-password:")
            else row["route"] + "-v2"
        )
        with store.transaction() as con:
            changed += con.execute(
                "UPDATE workflow_operations SET route=?,request_hash=? WHERE workspace_id=? "
                "AND actor_id=? AND route=? AND key=? AND request_hash=?",
                (
                    new_route,
                    digest(binding),
                    workspace,
                    row["actor_id"],
                    row["route"],
                    row["key"],
                    row["request_hash"],
                ),
            ).rowcount
    return changed
