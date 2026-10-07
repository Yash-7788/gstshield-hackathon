"""Local operator provisioned identities and bounded, revocable browser sessions."""

import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.errors import APIError
from app.storage.local import LocalStore

HASH_N = 32768
HASH_R = 8
HASH_P = 3
ROLES = {"OWNER", "REVIEWER", "VIEWER"}


def username_value(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,63}", value):
        raise ValueError("Username must be 3-64 lowercase ASCII letters, digits or ._-.")
    return value


def name_value(value: str) -> str:
    if not value.strip() or len(value) > 100 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("Display name must contain 1-100 characters without control characters.")
    return value.strip()


def password_value(value: str) -> str:
    if not 12 <= len(value) <= 128 or len(value.encode("utf-8")) > 512:
        raise ValueError("Password must be 12-128 characters (at most 512 UTF-8 bytes).")
    return value


def password_digest(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=HASH_N,
        r=HASH_R,
        p=HASH_P,
        maxmem=64 * 1024 * 1024,
        dklen=32,
    )


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def csrf_value(token: str) -> str:
    return hmac.new(token.encode("ascii"), b"gstshield-csrf-v1", hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class Identity:
    user_id: str
    username: str
    expires_at: int
    session_hash: str = field(repr=False)
    csrf_token: str = field(repr=False)


@dataclass(frozen=True)
class LinkedIdentity(Identity):
    """Constructed only from a verified active phone link, never a browser request body."""

    link_id: str = ""
    link_version: int = 0


class AccessService:
    def __init__(self, store: LocalStore):
        self.store = store
        self.settings = store.settings
        self.hash_slot = threading.BoundedSemaphore(1)
        self.clock = time.time

    def provision(self, username: str, password: str, workspace_name: str) -> tuple[str, str]:
        username_value(username)
        password_value(password)
        workspace_name = name_value(workspace_name)
        salt = secrets.token_bytes(16)
        digest = password_digest(password, salt)
        user_id, workspace_id = str(uuid4()), str(uuid4())
        now = int(self.clock())
        try:
            with self.store.transaction() as connection:
                if (
                    connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                    >= self.settings.max_local_users
                ):
                    raise APIError(409, "ACCOUNT_LIMIT", "Local account limit reached.")
                if (
                    connection.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]
                    >= self.settings.max_local_workspaces
                ):
                    raise APIError(409, "WORKSPACE_LIMIT", "Local workspace limit reached.")
                connection.execute(
                    (
                        "INSERT INTO users "
                        "(id,username,salt,digest,algorithm,active,created_at) VALUES "
                        "(?,?,?,?,'scrypt-v1',1,?)"
                    ),
                    (user_id, username, salt, digest, now),
                )
                connection.execute(
                    "INSERT INTO workspaces (id,name,created_at) VALUES (?,?,?)",
                    (workspace_id, workspace_name, now),
                )
                connection.execute(
                    "INSERT INTO memberships (workspace_id,user_id,role,active) "
                    "VALUES (?,?,'OWNER',1)",
                    (workspace_id, user_id),
                )
        except sqlite3.IntegrityError:
            raise APIError(409, "ACCOUNT_CONFLICT", "Account already exists.") from None
        return user_id, workspace_id

    def reset_password(self, username: str, password: str) -> None:
        username_value(username)
        password_value(password)
        salt = secrets.token_bytes(16)
        digest = password_digest(password, salt)
        with self.store.transaction() as connection:
            row = connection.execute(
                "SELECT id FROM users WHERE username=?", (username,)
            ).fetchone()
            if row is None:
                raise APIError(404, "NOT_FOUND", "Account was not found.")
            connection.execute(
                "UPDATE users SET salt=?,digest=?,active=1,version=version+1 WHERE id=?",
                (salt, digest, row[0]),
            )
            connection.execute("DELETE FROM sessions WHERE user_id=?", (row[0],))

    def grant(self, username: str, workspace_id: str, role: str, *, active: bool = True) -> None:
        username_value(username)
        workspace_id = str(UUID(workspace_id))
        if role not in ROLES:
            raise ValueError("Invalid membership role.")
        with self.store.transaction() as connection:
            user = connection.execute(
                "SELECT id FROM users WHERE username=?", (username,)
            ).fetchone()
            workspace = connection.execute(
                "SELECT id FROM workspaces WHERE id=?", (workspace_id,)
            ).fetchone()
            if user is None or workspace is None:
                raise APIError(404, "NOT_FOUND", "Account or workspace was not found.")
            connection.execute(
                (
                    "INSERT INTO memberships (workspace_id,user_id,role,active) VALUES (?,?,?,?) "
                    "ON CONFLICT(workspace_id,user_id) DO UPDATE SET "
                    "role=excluded.role,active=excluded.active,version=memberships.version+1"
                ),
                (workspace_id, user[0], role, int(active)),
            )

    def add_registration(self, workspace_id: str, gstin: str, display_name: str) -> str:
        workspace_id = str(UUID(workspace_id))
        display_name = name_value(display_name)
        # Structural input check only; official status and checksum verification are deferred.
        if not re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]", gstin):
            raise ValueError("GSTIN must use the 15-character structural format.")
        identifier = str(uuid4())
        try:
            with self.store.transaction() as connection:
                if (
                    connection.execute(
                        "SELECT id FROM workspaces WHERE id=?", (workspace_id,)
                    ).fetchone()
                    is None
                ):
                    raise APIError(404, "NOT_FOUND", "Workspace was not found.")
                if (
                    connection.execute(
                        "SELECT COUNT(*) FROM registrations WHERE workspace_id=?", (workspace_id,)
                    ).fetchone()[0]
                    >= self.settings.max_registrations_per_workspace
                ):
                    raise APIError(409, "REGISTRATION_LIMIT", "Registration limit reached.")
                connection.execute(
                    (
                        "INSERT INTO registrations "
                        "(id,workspace_id,gstin,display_name,created_at) VALUES "
                        "(?,?,?,?,?)"
                    ),
                    (identifier, workspace_id, gstin, display_name, int(self.clock())),
                )
        except sqlite3.IntegrityError:
            raise APIError(
                409, "REGISTRATION_CONFLICT", "Registration already exists in this workspace."
            ) from None
        return identifier

    def rate(self, connection, bucket: str, limit: int, seconds: int) -> None:
        now = int(self.clock())
        # All current windows expire within 60 seconds. Bound retained operational rows.
        connection.execute("DELETE FROM rate_windows WHERE start <= ?", (now - 60,))
        row = connection.execute(
            "SELECT start,count FROM rate_windows WHERE bucket=?", (bucket,)
        ).fetchone()
        if row is not None and now - row[0] < seconds:
            if row[1] >= limit:
                raise APIError(
                    429,
                    "RATE_LIMITED",
                    "Request limit reached.",
                    retry_after=max(1, row[0] + seconds - now),
                )
            connection.execute("UPDATE rate_windows SET count=count+1 WHERE bucket=?", (bucket,))
        else:
            connection.execute(
                (
                    "INSERT INTO rate_windows VALUES (?,?,1) ON CONFLICT(bucket) DO "
                    "UPDATE SET start=excluded.start,count=1"
                ),
                (bucket, now),
            )

    def login(self, username: str, password: str) -> tuple[str, Identity]:
        username_value(username)
        password_value(password)
        with self.store.transaction() as connection:
            self.rate(connection, "login:global", 30, 60)
            self.rate(connection, "login:" + hashlib.sha256(username.encode()).hexdigest(), 5, 60)
            row = connection.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not self.hash_slot.acquire(blocking=False):
            raise APIError(503, "AUTH_BUSY", "Sign-in is busy; retry shortly.", retry_after=1)
        try:
            salt = row["salt"] if row else b"gstshield-dummy!!"
            digest = password_digest(password, salt)
        finally:
            self.hash_slot.release()
        if row is None or not row["active"] or not hmac.compare_digest(digest, row["digest"]):
            raise APIError(401, "INVALID_CREDENTIALS", "Username or password is incorrect.")
        token = secrets.token_urlsafe(32)
        now = int(self.clock())
        with self.store.transaction() as connection:
            current = connection.execute(
                "SELECT active,version FROM users WHERE id=?", (row["id"],)
            ).fetchone()
            if current is None or not current["active"] or current["version"] != row["version"]:
                raise APIError(401, "INVALID_CREDENTIALS", "Username or password is incorrect.")
            connection.execute(
                "DELETE FROM sessions WHERE expires_at<=? OR user_id=?", (now, row["id"])
            )
            if (
                connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
                >= self.settings.max_active_demo_sessions
            ):
                raise APIError(503, "SESSION_LIMIT", "Local session limit reached.", retry_after=60)
            connection.execute(
                "INSERT INTO sessions VALUES (?,?,?,?)",
                (token_digest(token), row["id"], now, now + self.settings.session_ttl_seconds),
            )
        return token, Identity(
            row["id"],
            row["username"],
            now + self.settings.session_ttl_seconds,
            token_digest(token),
            csrf_value(token),
        )

    def identity(self, token: str, *, mutation: bool = False) -> Identity:
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise APIError(401, "AUTH_REQUIRED", "Sign-in is required.")
        hashed = token_digest(token)
        with self.store.transaction() as connection:
            row = connection.execute(
                (
                    "SELECT u.id,u.username,s.expires_at FROM sessions s JOIN users u "
                    "ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND "
                    "u.active=1"
                ),
                (hashed, int(self.clock())),
            ).fetchone()
            if row is None:
                raise APIError(401, "AUTH_REQUIRED", "Sign-in is required.")
            self.rate(
                connection,
                ("mutation:" if mutation else "read:") + hashed,
                self.settings.mutation_requests_per_minute
                if mutation
                else self.settings.read_requests_per_minute,
                60,
            )
        return Identity(row["id"], row["username"], row["expires_at"], hashed, csrf_value(token))

    def require_membership(self, connection, identity: Identity, workspace_id: str, *, roles=ROLES):
        if isinstance(identity, LinkedIdentity):
            row = connection.execute(
                "SELECT m.role FROM wa_links l JOIN memberships m ON m.user_id=l.user_id "
                "AND m.workspace_id=l.workspace_id JOIN users u ON u.id=l.user_id "
                "WHERE l.id=? AND l.user_id=? AND l.workspace_id=? AND l.active=1 "
                "AND l.version=? AND u.active=1 AND u.version=l.user_version AND m.active=1",
                (identity.link_id, identity.user_id, workspace_id, identity.link_version),
            ).fetchone()
            if row is None:
                raise APIError(404, "NOT_FOUND", "Resource was not found.")
            if row["role"] not in roles:
                raise APIError(403, "ROLE_FORBIDDEN", "Your role does not permit this operation.")
            return row["role"]
        row = connection.execute(
            "SELECT m.role FROM memberships m JOIN sessions s ON s.user_id=m.user_id "
            "JOIN users u ON u.id=m.user_id WHERE m.workspace_id=? AND m.user_id=? "
            "AND m.active=1 AND u.active=1 AND s.token_hash=? AND s.expires_at>?",
            (workspace_id, identity.user_id, identity.session_hash, int(self.clock())),
        ).fetchone()
        if row is None:
            raise APIError(404, "NOT_FOUND", "Resource was not found.")
        if row["role"] not in roles:
            raise APIError(403, "ROLE_FORBIDDEN", "Your role does not permit this operation.")
        return row["role"]

    def workspaces(self, identity: Identity) -> list[dict]:
        with self.store.transaction(write=False) as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT w.id,w.name,m.role,w.created_at,w.version FROM workspaces w "
                    "JOIN memberships m ON m.workspace_id=w.id JOIN users u ON u.id=m.user_id "
                    "JOIN sessions s ON s.user_id=m.user_id WHERE m.user_id=? AND m.active=1 "
                    "AND u.active=1 AND s.token_hash=? AND s.expires_at>? ORDER BY w.id",
                    (identity.user_id, identity.session_hash, int(self.clock())),
                ).fetchall()
            ]

    def registrations(self, identity: Identity, workspace_id: str) -> list[dict]:
        with self.store.transaction(write=False) as connection:
            self.require_membership(connection, identity, workspace_id)
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM registrations WHERE workspace_id=? ORDER BY id", (workspace_id,)
                ).fetchall()
            ]

    def logout(self, identity: Identity) -> None:
        with self.store.transaction() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash=?", (identity.session_hash,))
