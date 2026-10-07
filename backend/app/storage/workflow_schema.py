"""Additive workflow tables; previous schema definitions remain immutable."""

WORKFLOW_SCHEMA = (
    """CREATE TABLE cases (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        registration_id TEXT NOT NULL, result_id TEXT NOT NULL,
        purchase_document_id TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('MSME_REVIEW','RULE37_REVIEW','RULE37A_REVIEW',
            'IRN_REVIEW','NOTICE_REVIEW')),
        amount INTEGER NOT NULL CHECK(amount>=0), currency TEXT NOT NULL CHECK(currency='INR'),
        facts_json TEXT NOT NULL, provenance TEXT NOT NULL
            CHECK(provenance IN ('USER_PROVIDED','SYNTHETIC_DEMO')),
        state TEXT NOT NULL CHECK(state IN ('OPEN','EVIDENCE_REQUIRED','REVIEW_READY','CLOSED')),
        version INTEGER NOT NULL CHECK(version>0), created_by TEXT NOT NULL REFERENCES users(id),
        created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
        UNIQUE(workspace_id,id),
        FOREIGN KEY(workspace_id,registration_id) REFERENCES registrations(workspace_id,id),
        FOREIGN KEY(workspace_id,result_id) REFERENCES run_results(workspace_id,id)) STRICT""",
    """CREATE TABLE case_events (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, case_id TEXT NOT NULL,
        actor_id TEXT NOT NULL REFERENCES users(id), kind TEXT NOT NULL,
        import_id TEXT, evidence_json TEXT, note TEXT NOT NULL, facts_json TEXT NOT NULL,
        provenance TEXT NOT NULL CHECK(provenance IN ('USER_PROVIDED','SYNTHETIC_DEMO')),
        from_state TEXT NOT NULL, to_state TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0),
        request_id TEXT NOT NULL, created_at INTEGER NOT NULL,
        FOREIGN KEY(workspace_id,case_id) REFERENCES cases(workspace_id,id),
        FOREIGN KEY(workspace_id,import_id) REFERENCES imports(workspace_id,id)) STRICT""",
    "CREATE INDEX case_events_scope ON case_events(workspace_id,case_id,created_at,id)",
    """CREATE TABLE proposals (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, run_id TEXT NOT NULL,
        snapshot_json TEXT NOT NULL,
        snapshot_sha256 TEXT NOT NULL CHECK(length(snapshot_sha256)=64),
        state TEXT NOT NULL CHECK(state IN ('DRAFT','APPROVED','EXPORTED')),
        version INTEGER NOT NULL CHECK(version>0), created_by TEXT NOT NULL REFERENCES users(id),
        created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
        UNIQUE(workspace_id,id),
        FOREIGN KEY(workspace_id,run_id) REFERENCES runs(workspace_id,id)) STRICT""",
    """CREATE TABLE proposal_events (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, proposal_id TEXT NOT NULL,
        actor_id TEXT NOT NULL REFERENCES users(id), action TEXT NOT NULL,
        reason TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0),
        request_id TEXT NOT NULL, created_at INTEGER NOT NULL,
        FOREIGN KEY(workspace_id,proposal_id) REFERENCES proposals(workspace_id,id)) STRICT""",
    """CREATE TABLE artifacts (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        kind TEXT NOT NULL CHECK(kind IN ('RECONCILIATION_PDF','EVIDENCE_PDF','PROPOSAL_CSV',
            'ROW_ERRORS_CSV')),
        run_id TEXT, case_id TEXT, proposal_id TEXT, import_id TEXT,
        snapshot_json TEXT NOT NULL,
        snapshot_sha256 TEXT NOT NULL CHECK(length(snapshot_sha256)=64),
        filename TEXT NOT NULL, mime_type TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('PENDING','READY','FAILED','EXPIRED')),
        content BLOB, sha256 TEXT, size_bytes INTEGER CHECK(size_bytes>=0), error_code TEXT,
        expires_at INTEGER NOT NULL, created_by TEXT NOT NULL REFERENCES users(id),
        created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
        UNIQUE(workspace_id,id),
        CHECK((run_id IS NOT NULL)+(case_id IS NOT NULL)+(proposal_id IS NOT NULL)
            +(import_id IS NOT NULL)=1),
        CHECK((state='READY' AND content IS NOT NULL AND sha256 IS NOT NULL
            AND length(sha256)=64 AND size_bytes=length(content))
            OR (state!='READY' AND content IS NULL)),
        FOREIGN KEY(workspace_id,run_id) REFERENCES runs(workspace_id,id),
        FOREIGN KEY(workspace_id,case_id) REFERENCES cases(workspace_id,id),
        FOREIGN KEY(workspace_id,proposal_id) REFERENCES proposals(workspace_id,id),
        FOREIGN KEY(workspace_id,import_id) REFERENCES imports(workspace_id,id)) STRICT""",
    """CREATE TABLE artifact_jobs (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, artifact_id TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL CHECK(kind='ARTIFACT'),
        state TEXT NOT NULL CHECK(state IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')),
        error_code TEXT, lease TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
        CHECK((state='RUNNING' AND lease IS NOT NULL) OR (state!='RUNNING' AND lease IS NULL)),
        FOREIGN KEY(workspace_id,artifact_id) REFERENCES artifacts(workspace_id,id)) STRICT""",
    "CREATE INDEX artifact_jobs_queue ON artifact_jobs(state,created_at,id)",
    """CREATE TABLE workflow_operations (
        workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        actor_id TEXT NOT NULL REFERENCES users(id), route TEXT NOT NULL, key TEXT NOT NULL,
        request_hash TEXT NOT NULL, response_json TEXT NOT NULL,
        PRIMARY KEY(workspace_id,actor_id,route,key)) STRICT""",
)
