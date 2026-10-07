"""Additive local invoice evidence, decisions and append-only event records."""

PASSPORT_SCHEMA = (
    """CREATE TABLE invoice_passports (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, registration_id TEXT NOT NULL,
        period TEXT NOT NULL, filename TEXT NOT NULL, mime_type TEXT NOT NULL,
        content BLOB, sha256 TEXT NOT NULL, extraction_json TEXT NOT NULL,
        fields_json TEXT NOT NULL, confirmed INTEGER NOT NULL CHECK(confirmed IN (0,1)),
        purchase_import_id TEXT, version INTEGER NOT NULL CHECK(version>0),
        created_by TEXT NOT NULL REFERENCES users(id), created_at INTEGER NOT NULL,
        UNIQUE(workspace_id,id),
        FOREIGN KEY(workspace_id,registration_id) REFERENCES registrations(workspace_id,id),
        FOREIGN KEY(workspace_id,purchase_import_id) REFERENCES imports(workspace_id,id)
    ) STRICT""",
    """CREATE INDEX passport_scope ON invoice_passports
        (workspace_id,registration_id,period,created_at,id)""",
    """CREATE TABLE passport_evidence (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, passport_id TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('PO','RECEIPT','CLOCKS','PORTAL')),
        payload_json TEXT NOT NULL, created_by TEXT NOT NULL REFERENCES users(id),
        created_at INTEGER NOT NULL,
        FOREIGN KEY(workspace_id,passport_id) REFERENCES invoice_passports(workspace_id,id)
    ) STRICT""",
    """CREATE TABLE passport_events (
        sequence INTEGER PRIMARY KEY, id TEXT NOT NULL UNIQUE, workspace_id TEXT NOT NULL,
        passport_id TEXT NOT NULL, actor_id TEXT NOT NULL REFERENCES users(id),
        action TEXT NOT NULL, payload_json TEXT NOT NULL, created_at INTEGER NOT NULL,
        FOREIGN KEY(workspace_id,passport_id) REFERENCES invoice_passports(workspace_id,id)
    ) STRICT""",
    """CREATE TABLE passport_decisions (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, passport_id TEXT NOT NULL,
        decision TEXT NOT NULL, amount_paise INTEGER NOT NULL CHECK(amount_paise>=0),
        reason TEXT NOT NULL, source_signature TEXT NOT NULL,
        snapshot_json TEXT NOT NULL, approved_by TEXT NOT NULL REFERENCES users(id),
        created_at INTEGER NOT NULL,
        FOREIGN KEY(workspace_id,passport_id) REFERENCES invoice_passports(workspace_id,id)
    ) STRICT""",
)
