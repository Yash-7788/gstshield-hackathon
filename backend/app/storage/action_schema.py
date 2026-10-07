"""Additive schema 5: durable business actions and bounded automated observations."""

ACTION_SCHEMA = (
    """CREATE TABLE business_actions (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, registration_id TEXT NOT NULL,
        period TEXT NOT NULL, document_id TEXT NOT NULL, kind TEXT NOT NULL
            CHECK(kind IN ('INVOICE_REVIEW','MSME_REVIEW','RULE37_REVIEW','RULE37A_REVIEW',
                'IRN_REVIEW','NOTICE_REVIEW')),
        case_id TEXT, run_id TEXT NOT NULL, result_id TEXT NOT NULL,
        source_json TEXT NOT NULL, signature TEXT NOT NULL CHECK(length(signature)=64),
        state TEXT NOT NULL CHECK(state IN ('OPEN','AWAITING_SUPPLIER','EVIDENCE_REQUIRED',
            'REVIEW_REQUIRED','CLOSED')),
        version INTEGER NOT NULL CHECK(version>0), assigned_to TEXT REFERENCES users(id),
        due_at INTEGER, reminded_at INTEGER, outcome_json TEXT,
        created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
        UNIQUE(workspace_id,id),
        CHECK((kind='INVOICE_REVIEW' AND case_id IS NULL)
            OR (kind!='INVOICE_REVIEW' AND case_id IS NOT NULL)),
        FOREIGN KEY(workspace_id,registration_id) REFERENCES registrations(workspace_id,id),
        FOREIGN KEY(workspace_id,case_id) REFERENCES cases(workspace_id,id),
        FOREIGN KEY(workspace_id,run_id) REFERENCES runs(workspace_id,id),
        FOREIGN KEY(workspace_id,result_id,run_id) REFERENCES run_results(workspace_id,id,run_id))
        STRICT""",
    """CREATE UNIQUE INDEX actions_identity ON business_actions
        (workspace_id,registration_id,period,document_id,kind,ifnull(case_id,''))""",
    "CREATE INDEX actions_due ON business_actions(workspace_id,state,due_at,id)",
    """CREATE TABLE action_events (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, action_id TEXT NOT NULL,
        actor_id TEXT REFERENCES users(id), kind TEXT NOT NULL, reason TEXT NOT NULL,
        snapshot_json TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0),
        request_id TEXT NOT NULL, created_at INTEGER NOT NULL,
        UNIQUE(action_id,version),
        FOREIGN KEY(workspace_id,action_id) REFERENCES business_actions(workspace_id,id)) STRICT""",
    "CREATE INDEX action_events_scope ON action_events(workspace_id,action_id,version)",
    """CREATE TABLE action_checkpoints (
        workspace_id TEXT NOT NULL REFERENCES workspaces(id), kind TEXT NOT NULL
            CHECK(kind IN ('RUN','CASE')), source_id TEXT NOT NULL,
        version INTEGER NOT NULL CHECK(version>0), attempted_at INTEGER NOT NULL, error_code TEXT,
        PRIMARY KEY(workspace_id,kind,source_id)) STRICT""",
    """CREATE TABLE automation_status (
        workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id), checked_at INTEGER NOT NULL,
        error_code TEXT) STRICT""",
)
