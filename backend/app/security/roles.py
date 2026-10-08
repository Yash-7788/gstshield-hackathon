"""One assigned staff role and server-enforced tool access, independent of UI labels."""

import json

from app.errors import APIError

STAFF = {"CA", "CFO", "CMA", "CMO", "CEO", "COO", "CTO", "ACCOUNTS", "WAREHOUSE", "FOLLOWUP"}
INVOICES = {"CA", "CFO", "ACCOUNTS", "WAREHOUSE", "FOLLOWUP"}


def assigned_role(access, con, identity, ws):
    membership = access.require_membership(con, identity, ws)
    if membership == "OWNER":
        return "OWNER"
    row = con.execute(
        "SELECT roles_json FROM team_profile WHERE workspace_id=? AND user_id=?",
        (ws, identity.user_id),
    ).fetchone()
    roles = json.loads(row[0]) if row else ["CA"] if membership == "REVIEWER" else ["OBSERVER"]
    if len(roles) != 1 or roles[0] not in STAFF | {"OBSERVER"}:
        return "ROLE_SETUP_REQUIRED"
    return roles[0]


def actor_role(con, actor, ws):
    """Current persisted authority for workers; never fabricate a browser session."""
    row = con.execute(
        "SELECT m.role,p.roles_json FROM memberships m JOIN users u ON u.id=m.user_id "
        "LEFT JOIN team_profile p ON p.workspace_id=m.workspace_id AND p.user_id=m.user_id "
        "WHERE m.workspace_id=? AND m.user_id=? AND m.active=1 AND u.active=1",
        (ws, actor),
    ).fetchone()
    if not row:
        return None
    if row["role"] == "OWNER":
        return "OWNER"
    roles = (
        json.loads(row["roles_json"])
        if row["roles_json"]
        else (["CA"] if row["role"] == "REVIEWER" else ["OBSERVER"])
    )
    return roles[0] if len(roles) == 1 and roles[0] in STAFF | {"OBSERVER"} else None


def require_role(access, con, identity, ws, permitted):
    role = assigned_role(access, con, identity, ws)
    if role not in permitted:
        raise APIError(
            403,
            "ROLE_FORBIDDEN",
            "This tool belongs to another team role. Ask your owner to check your assigned role.",
        )
    return role


def permitted_roles(suffix, mutation):
    parts = suffix.strip("/").split("/")
    head = parts[0]
    all_roles = STAFF | {"OWNER", "OBSERVER", "ROLE_SETUP_REQUIRED"}
    if head == "registrations":
        return {"OWNER"} if mutation else all_roles
    if head == "product":
        tool = parts[1] if len(parts) > 1 else ""
        if tool in {"portal", "team", "contributions", "notifications", "workflows", "nodes"}:
            if not mutation:
                return all_roles
            if tool == "team":
                return {"OWNER"}
            if tool == "contributions":
                return STAFF
            if tool == "notifications":
                return all_roles
            return {"CA", "CFO", "ACCOUNTS", "WAREHOUSE", "FOLLOWUP"}
        if tool == "gst-statement":
            return {"CA"}
        if tool == "business":
            return {"OWNER"} if mutation else all_roles - {"ROLE_SETUP_REQUIRED"}
        if tool == "owner-summary":
            return {"OWNER", "CEO", "CA", "CFO"}
        if tool == "assistants":
            return {parts[2]} & STAFF if len(parts) > 2 else set()
        if tool in {"schemes", "competitors"}:
            return {"OWNER", "CEO", "CFO", "CMA", "CA"}
        if tool == "tax-suggestions":
            return {"CA"}
        if tool == "invoices":
            return {"CA"} if mutation else {"CA", "CFO", "OWNER"}
        return set()
    if head == "command-center":
        return all_roles if "glossary" in parts else INVOICES
    if head == "passports":
        if not mutation:
            return INVOICES
        action = parts[-1]
        if action in {"approve", "clocks", "demo-bank-payment", "scenario", "intelligence"}:
            return {"CA", "CFO"}
        if action in {"resolution", "supplier-invite", "supplier-send"}:
            return {"CA", "FOLLOWUP"}
        if action in {"evidence", "evidence-documents"}:
            return {"CA", "WAREHOUSE"}
        if action in {"documents", "from-source", "confirm", "retry-extraction", "remove"}:
            return {"CA", "ACCOUNTS"}
        if action in {"refresh", "watch"}:
            return INVOICES
        return {"CA"}
    if head == "artifacts" and parts[-1] == "cleanup":
        return {"OWNER"}
    if head == "jobs":
        return {"CA", "CFO", "ACCOUNTS"} if not mutation else set()
    if head == "imports":
        return {"CA", "ACCOUNTS"} if mutation else {"CA", "CFO", "ACCOUNTS"}
    if head in {
        "runs",
        "results",
        "cases",
        "reports",
        "artifacts",
        "actions",
        "proposals",
        "payment-proposals",
    }:
        return (
            {"CA", "CFO"}
            if head in {"proposals", "payment-proposals", "actions", "reports", "artifacts"}
            else {"CA"}
            if mutation
            else {"CA", "CFO"}
        )
    if head == "whatsapp":
        return {"CA", "FOLLOWUP"}
    return set()


def enforce_request(access, identity, ws, suffix, mutation):
    with access.store.transaction(write=False) as con:
        require_role(access, con, identity, ws, permitted_roles(suffix, mutation))
