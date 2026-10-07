"""Versioned import schema. Sources are private BLOBs included in SQLite backups."""

IMPORT_SCHEMA = (
    """CREATE TABLE import_files (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, registration_id TEXT NOT NULL,
        original_name TEXT NOT NULL, content BLOB NOT NULL,
        size_bytes INTEGER NOT NULL CHECK(size_bytes>0 AND size_bytes=length(content)),
        sha256 TEXT NOT NULL CHECK(length(sha256)=64),
        uploaded_by TEXT NOT NULL REFERENCES users(id),
        created_at INTEGER NOT NULL, UNIQUE(workspace_id,id),
        FOREIGN KEY(workspace_id,registration_id) REFERENCES registrations(workspace_id,id)
    ) STRICT""",
    """CREATE TABLE imports (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, registration_id TEXT NOT NULL,
        file_id TEXT NOT NULL, file_sha256 TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('PURCHASE','PORTAL_2B')), period TEXT NOT NULL,
        adapter_version TEXT NOT NULL, sheet_name TEXT, mapping_json TEXT NOT NULL,
        mapping_hash TEXT NOT NULL, provenance TEXT NOT NULL
        CHECK(provenance IN ('USER_PROVIDED','SYNTHETIC_DEMO')),
        state TEXT NOT NULL CHECK(state IN
        ('RECEIVED','PARSING','AWAITING_CONFIRMATION','READY','FAILED','SUPERSEDED')),
        version INTEGER NOT NULL DEFAULT 1 CHECK(version>0),
        accepted_rows INTEGER NOT NULL DEFAULT 0 CHECK(accepted_rows>=0),
        rejected_rows INTEGER NOT NULL DEFAULT 0 CHECK(rejected_rows>=0),
        duplicate_rows INTEGER NOT NULL DEFAULT 0 CHECK(duplicate_rows>=0),
        errors_json TEXT NOT NULL DEFAULT '[]', columns_json TEXT NOT NULL DEFAULT '[]',
        generated_at TEXT, supersedes_import_id TEXT, derived_from_import_id TEXT,
        created_by TEXT NOT NULL REFERENCES users(id), created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL, UNIQUE(workspace_id,id),
        FOREIGN KEY(workspace_id,registration_id) REFERENCES registrations(workspace_id,id),
        FOREIGN KEY(workspace_id,file_id) REFERENCES import_files(workspace_id,id),
        FOREIGN KEY(workspace_id,supersedes_import_id) REFERENCES imports(workspace_id,id),
        FOREIGN KEY(workspace_id,derived_from_import_id) REFERENCES imports(workspace_id,id)
    ) STRICT""",
    """CREATE UNIQUE INDEX imports_content_unique ON imports
        (workspace_id,registration_id,kind,period,file_sha256,mapping_hash,adapter_version,
        ifnull(supersedes_import_id,''),ifnull(derived_from_import_id,''))""",
    """CREATE TABLE import_rows (
        workspace_id TEXT NOT NULL, import_id TEXT NOT NULL, row_number INTEGER NOT NULL,
        original_json TEXT NOT NULL, canonical_json TEXT, errors_json TEXT NOT NULL,
        accepted INTEGER NOT NULL CHECK(accepted IN (0,1)),
        duplicate INTEGER NOT NULL CHECK(duplicate IN (0,1)),
        taxable_value INTEGER, igst INTEGER, cgst INTEGER, sgst INTEGER, cess INTEGER,
        other_charges INTEGER, round_off INTEGER, gross_total INTEGER, total_tax INTEGER,
        PRIMARY KEY(workspace_id,import_id,row_number),
        FOREIGN KEY(workspace_id,import_id) REFERENCES imports(workspace_id,id)
    ) STRICT""",
    """CREATE TABLE jobs (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, import_id TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind='IMPORT'),
        state TEXT NOT NULL CHECK(state IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')),
        error_code TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
        UNIQUE(workspace_id,id), UNIQUE(import_id),
        FOREIGN KEY(workspace_id,import_id) REFERENCES imports(workspace_id,id)
    ) STRICT""",
    """CREATE TABLE import_operations (
        workspace_id TEXT NOT NULL, actor_id TEXT NOT NULL REFERENCES users(id),
        route TEXT NOT NULL, key TEXT NOT NULL, request_hash TEXT NOT NULL,
        import_id TEXT NOT NULL,
        PRIMARY KEY(workspace_id,actor_id,route,key),
        FOREIGN KEY(workspace_id,import_id) REFERENCES imports(workspace_id,id)
    ) STRICT""",
    """CREATE TABLE import_events (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, import_id TEXT NOT NULL,
        actor_id TEXT NOT NULL REFERENCES users(id), action TEXT NOT NULL,
        request_id TEXT NOT NULL, created_at INTEGER NOT NULL,
        FOREIGN KEY(workspace_id,import_id) REFERENCES imports(workspace_id,id)
    ) STRICT""",
)
