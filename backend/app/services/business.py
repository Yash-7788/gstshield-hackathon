"""Shared business facts and team authority over the existing memberships."""

import hashlib
import json
import secrets
import sqlite3
import time
from decimal import Decimal

from app.errors import APIError
from app.security.credential_receipts import credential_payload
from app.services.access import password_digest
from app.services.imports import digest, encode
from app.services.workflows import WorkflowService

EXECUTIVE_ROLES = [
    "CFO",
    "CMO",
    "CMA",
    "CA",
    "CEO",
    "COO",
    "CTO",
    "ACCOUNTS",
    "WAREHOUSE",
    "FOLLOWUP",
]


class BusinessService(WorkflowService):
    def __init__(self, passports):
        super().__init__(passports.runs)
        self.passports = passports

    def credential_binding(self, identity, ws, route, key, payload):
        with self.store.transaction(write=False) as con:
            self.check(con, identity, ws, owner=True)
        if not self.access.hash_slot.acquire(blocking=False):
            raise APIError(503, "ACCOUNT_BUSY", "Account setup is busy; retry.", retry_after=1)
        try:
            return credential_payload(ws, identity.user_id, route, key, digest(payload))
        finally:
            self.access.hash_slot.release()

    def check(self, con, identity, ws, *, owner=False):
        return self.access.require_membership(
            con, identity, ws, roles={"OWNER"} if owner else {"OWNER", "REVIEWER", "VIEWER"}
        )

    def roles(self, con, identity, ws):
        from app.security.roles import assigned_role

        return [assigned_role(self.access, con, identity, ws)]

    def portal(self, identity, ws):
        with self.store.transaction(write=False) as con:
            membership = self.check(con, identity, ws)
            return {
                "membership_role": membership,
                "roles": self.roles(con, identity, ws),
                "owner": membership == "OWNER",
                "financial_write": self.roles(con, identity, ws)[0]
                in {"CA", "CFO", "ACCOUNTS", "WAREHOUSE", "FOLLOWUP"},
                "team_management": membership == "OWNER",
                "user_id": identity.user_id,
                "username": identity.username,
                "account_limit": self.settings.max_local_users,
            }

    def audit(self, con, identity, ws, kind, facts):
        if (
            con.execute(
                "SELECT COUNT(*) FROM product_events WHERE workspace_id=?", (ws,)
            ).fetchone()[0]
            >= 10000
        ):
            raise APIError(409, "HISTORY_LIMIT", "Business history is full.")
        con.execute(
            "INSERT INTO product_events VALUES(?,?,?,?,?,?,?)",
            (
                self.identifier(),
                ws,
                identity.user_id,
                kind,
                digest(facts),
                encode(facts),
                int(time.time()),
            ),
        )

    def profile_row(self, con, ws, rid, period):
        self.passports.registration(con, ws, rid)
        row = con.execute(
            "SELECT * FROM business_profile WHERE workspace_id=? AND "
            "registration_id=? AND period=?",
            (ws, rid, period),
        ).fetchone()
        return {
            "profile": json.loads(row["value_json"]) if row else {},
            "version": row["version"] if row else 0,
            "updated_at": row["updated_at"] if row else None,
            "provenance": "USER_REPORTED",
            "registration_id": rid,
            "period": period,
        }

    def safe_profile(self, data, owner):
        result = json.loads(encode(data))
        employees = result["profile"].get("employees", [])
        salaries = [e.get("monthly_salary") for e in employees]
        total = (
            sum(Decimal(x) for x in salaries)
            if employees and all(x is not None for x in salaries)
            else None
        )
        result["profile"]["recorded_payroll_total"] = f"{total:.2f}" if total is not None else None
        result["profile"]["payroll_complete"] = (
            bool(employees)
            and total is not None
            and result["profile"].get("workforce_count") == len(employees)
        )
        if not owner:
            result["profile"].pop("employees", None)
        result["employee_details_visible"] = owner
        result["fingerprint"] = digest(data)
        return result

    def business(self, identity, ws, rid, period):
        with self.store.transaction(write=False) as con:
            membership = self.check(con, identity, ws)
            result = self.safe_profile(
                self.profile_row(con, ws, rid, period), membership == "OWNER"
            )
            role = self.roles(con, identity, ws)[0]
            if role == "CMO":
                permitted = {"business_name", "marketing_spend", "attributed_sales", "note"}
            elif role in {"CTO", "COO", "WAREHOUSE", "FOLLOWUP", "ACCOUNTS", "OBSERVER"}:
                permitted = {"business_name", "business_type", "note"}
            else:
                permitted = set(result["profile"])
            result["profile"] = {k: v for k, v in result["profile"].items() if k in permitted}
            return result

    def save_business(self, identity, ws, payload, key):
        with self.store.transaction() as con:
            self.check(con, identity, ws, owner=True)
            previous = self.operation(con, identity, ws, "business-save", key, payload)
            if previous:
                return previous
            data = self.profile_row(con, ws, payload["registration_id"], payload["period"])
            if data["version"] != payload["expected_version"]:
                raise APIError(
                    409, "VERSION_CONFLICT", "Business details changed; reload before saving."
                )
            profile = json.loads(encode(payload["profile"]))
            for field in [
                "monthly_revenue",
                "monthly_profit",
                "monthly_operating_cost",
                "annual_turnover",
                "loan_needed",
                "marketing_spend",
                "attributed_sales",
            ]:
                if profile.get(field) is not None:
                    profile[field] = f"{Decimal(profile[field]):.2f}"
            for field, value in profile.get("tax_paid", {}).items():
                if value is not None:
                    profile["tax_paid"][field] = f"{Decimal(value):.2f}"
            for employee in profile.get("employees", []):
                if employee.get("monthly_salary") is not None:
                    employee["monthly_salary"] = f"{Decimal(employee['monthly_salary']):.2f}"
            version = data["version"] + 1
            con.execute(
                "INSERT INTO business_profile VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(workspace_id,registration_id,period) DO UPDATE SET "
                "value_json=excluded.value_json,version=excluded.version,updated_by=excluded.updated_by,updated_at=excluded.updated_at",
                (
                    ws,
                    payload["registration_id"],
                    payload["period"],
                    encode(profile),
                    version,
                    identity.user_id,
                    int(time.time()),
                ),
            )
            self.audit(
                con,
                identity,
                ws,
                "BUSINESS_UPDATED",
                {
                    "registration_id": payload["registration_id"],
                    "period": payload["period"],
                    "version": version,
                    "profile_fingerprint": digest(profile),
                },
            )
            result = self.safe_profile(
                self.profile_row(con, ws, payload["registration_id"], payload["period"]), True
            )
            self.record(con, identity, ws, "business-save", key, payload, result)
            return result

    @staticmethod
    def single_role(roles):
        if len(roles) != 1 or roles[0] not in EXECUTIVE_ROLES:
            raise APIError(
                422, "ONE_ROLE_REQUIRED", "Assign exactly one preset role to each person."
            )

    def team_rows(self, con, ws):
        rows = con.execute(
            "SELECT u.id,u.username,u.active AS user_active,m.role AS membership_role,"
            "m.active,m.version AS membership_version,p.display_name,p.roles_json,p.version "
            "FROM memberships m JOIN users u ON u.id=m.user_id LEFT JOIN team_profile p "
            "ON p.workspace_id=m.workspace_id AND p.user_id=m.user_id WHERE "
            "m.workspace_id=? ORDER BY u.username LIMIT 100",
            (ws,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "username": r["username"],
                "display_name": r["display_name"] or r["username"],
                "roles": json.loads(r["roles_json"])
                if r["roles_json"]
                else ["OWNER"]
                if r["membership_role"] == "OWNER"
                else ["CA"]
                if r["membership_role"] == "REVIEWER"
                else ["OBSERVER"],
                "membership_role": r["membership_role"],
                "active": bool(r["active"] and r["user_active"]),
                "version": r["version"] or r["membership_version"],
            }
            for r in rows
        ]

    def team(self, identity, ws):
        with self.store.transaction(write=False) as con:
            self.check(con, identity, ws)
            return {
                "members": self.team_rows(con, ws),
                "account_limit": self.settings.max_local_users,
            }

    def create_member(self, identity, ws, payload, key):
        self.single_role(payload["roles"])
        password = payload["password"]
        safe_payload = {k: v for k, v in payload.items() if k != "password"}
        safe_payload["password_fingerprint"] = hashlib.sha256(password.encode()).hexdigest()
        safe_payload = self.credential_binding(identity, ws, "member-create", key, safe_payload)
        with self.store.transaction(write=False) as con:
            self.check(con, identity, ws, owner=True)
            previous = con.execute(
                "SELECT request_hash,response_json FROM workflow_operations "
                "WHERE workspace_id=? AND actor_id=? AND route=? AND key=?",
                (ws, identity.user_id, "member-create-v2", key),
            ).fetchone()
            if previous:
                if previous["request_hash"] != digest(safe_payload):
                    raise APIError(409, "IDEMPOTENCY_CONFLICT", "Request key already used.")
                return json.loads(previous["response_json"])
        if not self.access.hash_slot.acquire(blocking=False):
            raise APIError(503, "ACCOUNT_BUSY", "Account setup is busy; retry.", retry_after=1)
        try:
            salt = secrets.token_bytes(16)
            hashed = password_digest(password, salt)
            with self.store.transaction() as con:
                self.check(con, identity, ws, owner=True)
                previous = self.operation(con, identity, ws, "member-create-v2", key, safe_payload)
                if previous:
                    return previous
                if (
                    con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                    >= self.settings.max_local_users
                ):
                    raise APIError(409, "ACCOUNT_LIMIT", "Configured local account limit reached.")
                uid = self.identifier()
                try:
                    con.execute(
                        "INSERT INTO "
                        "users(id,username,salt,digest,algorithm,active,created_at) "
                        "VALUES(?,?,?,?,'scrypt-v1',1,?)",
                        (uid, payload["username"], salt, hashed, int(time.time())),
                    )
                except sqlite3.IntegrityError:
                    raise APIError(
                        409,
                        "ACCOUNT_CONFLICT",
                        "Choose a different account name or ask the operator to grant an "
                        "existing account.",
                    ) from None
                membership = (
                    "REVIEWER"
                    if {"CA", "CFO", "ACCOUNTS", "WAREHOUSE", "FOLLOWUP"} & set(payload["roles"])
                    else "VIEWER"
                )
                con.execute(
                    "INSERT INTO memberships(workspace_id,user_id,role,active) VALUES(?,?,?,1)",
                    (ws, uid, membership),
                )
                con.execute(
                    "INSERT INTO team_profile VALUES(?,?,?,?,1)",
                    (ws, uid, payload["display_name"], encode(payload["roles"])),
                )
                self.audit(
                    con, identity, ws, "MEMBER_CREATED", {"user_id": uid, "roles": payload["roles"]}
                )
                result = next(r for r in self.team_rows(con, ws) if r["id"] == uid)
                self.record(con, identity, ws, "member-create-v2", key, safe_payload, result)
                return result
        finally:
            self.access.hash_slot.release()

    def create_team(self, identity, ws, payload, key):
        members = payload["members"]
        for member in members:
            self.single_role(member["roles"])
        names = [member["username"] for member in members]
        if len(names) != len(set(names)):
            raise APIError(422, "ACCOUNT_CONFLICT", "Use a different username for each person.")
        safe_payload = {
            "members": [
                {
                    **{k: v for k, v in member.items() if k != "password"},
                    "password_fingerprint": hashlib.sha256(member["password"].encode()).hexdigest(),
                }
                for member in members
            ]
        }
        safe_payload = self.credential_binding(identity, ws, "team-setup", key, safe_payload)
        with self.store.transaction(write=False) as con:
            self.check(con, identity, ws, owner=True)
            previous = con.execute(
                "SELECT request_hash,response_json FROM workflow_operations "
                "WHERE workspace_id=? AND actor_id=? AND route=? AND key=?",
                (ws, identity.user_id, "team-setup-v2", key),
            ).fetchone()
            if previous:
                if previous["request_hash"] != digest(safe_payload):
                    raise APIError(409, "IDEMPOTENCY_CONFLICT", "Request key already used.")
                return json.loads(previous["response_json"])
            if (
                con.execute("SELECT COUNT(*) FROM users").fetchone()[0] + len(members)
                > self.settings.max_local_users
            ):
                raise APIError(409, "ACCOUNT_LIMIT", "Configured local account limit reached.")
            if any(
                con.execute("SELECT 1 FROM users WHERE username=?", (name,)).fetchone()
                for name in names
            ):
                raise APIError(
                    409,
                    "ACCOUNT_CONFLICT",
                    "One of these usernames already exists. Choose another username.",
                )
        if not self.access.hash_slot.acquire(blocking=False):
            raise APIError(503, "ACCOUNT_BUSY", "Account setup is busy; retry.", retry_after=1)
        try:
            prepared = []
            for member in members:
                salt = secrets.token_bytes(16)
                prepared.append((member, salt, password_digest(member["password"], salt)))
            with self.store.transaction() as con:
                self.check(con, identity, ws, owner=True)
                previous = self.operation(con, identity, ws, "team-setup-v2", key, safe_payload)
                if previous:
                    return previous
                if (
                    con.execute("SELECT COUNT(*) FROM users").fetchone()[0] + len(members)
                    > self.settings.max_local_users
                ):
                    raise APIError(409, "ACCOUNT_LIMIT", "Configured local account limit reached.")
                created = []
                for member, salt, hashed in prepared:
                    uid = self.identifier()
                    try:
                        con.execute(
                            "INSERT INTO users(id,username,salt,digest,algorithm,"
                            "active,created_at) "
                            "VALUES(?,?,?,?,'scrypt-v1',1,?)",
                            (uid, member["username"], salt, hashed, int(time.time())),
                        )
                    except sqlite3.IntegrityError:
                        raise APIError(
                            409,
                            "ACCOUNT_CONFLICT",
                            "One of these usernames already exists. Nothing was created; "
                            "correct the username and retry.",
                        ) from None
                    membership = (
                        "REVIEWER"
                        if {"CA", "CFO", "ACCOUNTS", "WAREHOUSE", "FOLLOWUP"} & set(member["roles"])
                        else "VIEWER"
                    )
                    con.execute(
                        "INSERT INTO memberships(workspace_id,user_id,role,active) VALUES(?,?,?,1)",
                        (ws, uid, membership),
                    )
                    con.execute(
                        "INSERT INTO team_profile VALUES(?,?,?,?,1)",
                        (ws, uid, member["display_name"], encode(member["roles"])),
                    )
                    self.audit(
                        con,
                        identity,
                        ws,
                        "MEMBER_CREATED",
                        {"user_id": uid, "roles": member["roles"]},
                    )
                    created.append(uid)
                self.audit(con, identity, ws, "TEAM_REGISTERED", {"user_ids": created})
                result = {
                    "members": [row for row in self.team_rows(con, ws) if row["id"] in created]
                }
                self.record(con, identity, ws, "team-setup-v2", key, safe_payload, result)
                return result
        finally:
            self.access.hash_slot.release()

    def update_member(self, identity, ws, uid, payload, key):
        self.single_role(payload["roles"])
        with self.store.transaction() as con:
            self.check(con, identity, ws, owner=True)
            route = "member-update:" + uid
            previous = self.operation(con, identity, ws, route, key, payload)
            if previous:
                return previous
            member = next((m for m in self.team_rows(con, ws) if m["id"] == uid), None)
            if member is None:
                raise APIError(404, "NOT_FOUND", "Team member was not found.")
            if member["membership_role"] == "OWNER":
                raise APIError(
                    403, "OWNER_MANAGED", "Owner access is managed by the local operator."
                )
            if member["version"] != payload["expected_version"]:
                raise APIError(409, "VERSION_CONFLICT", "Member changed; reload first.")
            version = member["version"] + 1
            membership = (
                "REVIEWER"
                if {"CA", "CFO", "ACCOUNTS", "WAREHOUSE", "FOLLOWUP"} & set(payload["roles"])
                else "VIEWER"
            )
            con.execute(
                "UPDATE memberships SET role=?,active=?,version=version+1 WHERE "
                "workspace_id=? AND user_id=?",
                (membership, int(payload["active"]), ws, uid),
            )
            con.execute(
                "INSERT INTO team_profile VALUES(?,?,?,?,?) ON CONFLICT(workspace_id,user_id) "
                "DO UPDATE SET roles_json=excluded.roles_json,version=excluded.version",
                (ws, uid, member["display_name"], encode(payload["roles"]), version),
            )
            self.audit(
                con,
                identity,
                ws,
                "MEMBER_UPDATED",
                {"user_id": uid, "roles": payload["roles"], "active": payload["active"]},
            )
            result = next(r for r in self.team_rows(con, ws) if r["id"] == uid)
            self.record(con, identity, ws, route, key, payload, result)
            return result

    def member_password(self, identity, ws, uid, payload, key):
        safe_payload = {
            "expected_version": payload["expected_version"],
            "password_fingerprint": hashlib.sha256(payload["password"].encode()).hexdigest(),
        }
        safe_payload = self.credential_binding(
            identity, ws, "member-password:" + uid, key, safe_payload
        )
        route = "member-password-v2:" + uid
        with self.store.transaction(write=False) as con:
            self.check(con, identity, ws, owner=True)
            member = next((row for row in self.team_rows(con, ws) if row["id"] == uid), None)
            if member is None:
                raise APIError(404, "NOT_FOUND", "Team member was not found.")
            if (
                member["membership_role"] == "OWNER"
                or con.execute(
                    "SELECT 1 FROM memberships WHERE user_id=? "
                    "AND (role='OWNER' OR workspace_id<>?)",
                    (uid, ws),
                ).fetchone()
            ):
                raise APIError(
                    403,
                    "ACCOUNT_SHARED",
                    "Accounts shared with another business or owner accounts require "
                    "the local operator to change their password.",
                )
            previous = self.operation(con, identity, ws, route, key, safe_payload)
            if previous:
                return previous
            if member["version"] != payload["expected_version"]:
                raise APIError(409, "VERSION_CONFLICT", "Member changed; reload first.")
        if not self.access.hash_slot.acquire(blocking=False):
            raise APIError(503, "ACCOUNT_BUSY", "Account setup is busy; retry.", retry_after=1)
        try:
            salt = secrets.token_bytes(16)
            hashed = password_digest(payload["password"], salt)
            with self.store.transaction() as con:
                self.check(con, identity, ws, owner=True)
                previous = self.operation(con, identity, ws, route, key, safe_payload)
                if previous:
                    return previous
                member = next((row for row in self.team_rows(con, ws) if row["id"] == uid), None)
                if member is None:
                    raise APIError(404, "NOT_FOUND", "Team member was not found.")
                if (
                    member["membership_role"] == "OWNER"
                    or con.execute(
                        "SELECT 1 FROM memberships WHERE user_id=? "
                        "AND (role='OWNER' OR workspace_id<>?)",
                        (uid, ws),
                    ).fetchone()
                ):
                    raise APIError(
                        403, "ACCOUNT_SHARED", "This account is managed outside this team."
                    )
                if member["version"] != payload["expected_version"]:
                    raise APIError(409, "VERSION_CONFLICT", "Member changed; reload first.")
                con.execute(
                    "UPDATE users SET salt=?,digest=?,version=version+1 WHERE id=?",
                    (salt, hashed, uid),
                )
                con.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
                con.execute(
                    "UPDATE team_profile SET version=version+1 WHERE workspace_id=? AND user_id=?",
                    (ws, uid),
                )
                con.execute(
                    "UPDATE memberships SET version=version+1 WHERE workspace_id=? AND user_id=?",
                    (ws, uid),
                )
                self.audit(
                    con,
                    identity,
                    ws,
                    "MEMBER_PASSWORD_CHANGED",
                    {"user_id": uid, "sessions_revoked": True},
                )
                result = {"user_id": uid, "password_updated": True}
                self.record(con, identity, ws, route, key, safe_payload, result)
                return result
        finally:
            self.access.hash_slot.release()

    def contributions(self, identity, ws, rid, period):
        with self.store.transaction(write=False) as con:
            self.check(con, identity, ws)
            self.passports.registration(con, ws, rid)
            return [
                dict(r)
                for r in con.execute(
                    "SELECT c.*,u.username FROM team_contribution c "
                    "JOIN users u ON u.id=c.actor_id WHERE c.workspace_id=? AND "
                    "c.registration_id=? AND c.period=? "
                    "ORDER BY c.created_at DESC,c.rowid DESC LIMIT 200",
                    (ws, rid, period),
                )
            ]

    def contribute(self, identity, ws, payload, key):
        with self.store.transaction() as con:
            roles = self.roles(con, identity, ws)
            if payload["role"] not in roles:
                raise APIError(403, "ROLE_FORBIDDEN", "Choose one of your approved team roles.")
            previous = self.operation(con, identity, ws, "team-contribution", key, payload)
            if previous:
                return previous
            self.passports.registration(con, ws, payload["registration_id"])
            if (
                con.execute(
                    "SELECT COUNT(*) FROM team_contribution WHERE workspace_id=?", (ws,)
                ).fetchone()[0]
                >= 2000
            ):
                raise APIError(409, "HISTORY_LIMIT", "Team update history is full.")
            identifier = self.identifier()
            con.execute(
                "INSERT INTO team_contribution VALUES(?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    ws,
                    payload["registration_id"],
                    payload["period"],
                    identity.user_id,
                    payload["role"],
                    payload["note"],
                    int(time.time()),
                ),
            )
            self.audit(
                con,
                identity,
                ws,
                "TEAM_UPDATE",
                {
                    "id": identifier,
                    "role": payload["role"],
                    "note_fingerprint": digest(payload["note"]),
                },
            )
            result = {"id": identifier, "saved": True}
            self.record(con, identity, ws, "team-contribution", key, payload, result)
            return result

    def owner_summary(self, identity, ws, rid, period):
        with self.store.transaction(write=False) as con:
            self.check(con, identity, ws)
        listing = self.passports.listing(identity, ws, rid, period)
        profile = self.business(identity, ws, rid, period)
        tasks = [
            {
                "passport_id": p["id"],
                "invoice": p["fields"].get("invoice_number", p["filename"]),
                "amount": p["gate"]["recorded_tax_under_review"],
                "reason": p["gate"]["reason"],
                "next_action": p["gate"]["recommendation"],
                "approval_state": p["approval"]["state"] if p["approval"] else "NOT_REVIEWED",
            }
            for p in listing["passports"]
            if not p["confirmed"]
            or p["findings"]["summary"] != "MATCHED"
            or not p["approval"]
            or p["approval"]["state"] == "STALE"
        ]
        unique = {}
        by_id = {p["id"]: p for p in listing["passports"]}
        for task in tasks:
            fields = by_id[task["passport_id"]]["fields"]
            invoice_key = (
                fields.get("supplier_gstin"),
                str(fields.get("invoice_number", task["passport_id"])).strip().upper(),
                fields.get("invoice_date"),
            )
            unique.setdefault(invoice_key, task)
        tasks = list(unique.values())
        return {
            "business": profile,
            "metrics": listing["metrics"],
            "priorities": tasks[:20],
            "missing_data": [
                k
                for k in [
                    "monthly_revenue",
                    "monthly_profit",
                    "monthly_operating_cost",
                    "workforce_count",
                ]
                if profile["profile"].get(k) is None
            ],
            "mode": "SAVED_FACTS_ONLY",
            "fingerprint": digest(
                {
                    "profile": profile["fingerprint"],
                    "invoices": [(p["id"], p["source_signature"]) for p in listing["passports"]],
                }
            ),
        }
