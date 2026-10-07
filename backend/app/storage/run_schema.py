"""Additive v3 schema: immutable runs, unique assignments and atomic review history."""

RUN_SCHEMA = (
    """CREATE TABLE runs (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, registration_id TEXT NOT NULL,
        period TEXT NOT NULL, purchase_import_id TEXT NOT NULL, portal_import_id TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK(revision>0), version INTEGER NOT NULL CHECK(version>0),
        state TEXT NOT NULL CHECK(state IN ('QUEUED','RUNNING','COMPLETED','FAILED','SUPERSEDED')),
        policy_json TEXT NOT NULL, sources_json TEXT NOT NULL, summary_json TEXT,
        superseded_by_run_id TEXT, created_by TEXT NOT NULL REFERENCES users(id),
        created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
        UNIQUE(workspace_id,id), UNIQUE(workspace_id,registration_id,period,revision),
        UNIQUE(workspace_id,id,purchase_import_id,portal_import_id),
        UNIQUE(workspace_id,id,portal_import_id),
        CHECK((state IN ('COMPLETED','SUPERSEDED') AND summary_json IS NOT NULL)
            OR (state NOT IN ('COMPLETED','SUPERSEDED') AND summary_json IS NULL)),
        FOREIGN KEY(workspace_id,registration_id) REFERENCES registrations(workspace_id,id),
        FOREIGN KEY(workspace_id,purchase_import_id) REFERENCES imports(workspace_id,id),
        FOREIGN KEY(workspace_id,portal_import_id) REFERENCES imports(workspace_id,id),
        FOREIGN KEY(workspace_id,superseded_by_run_id) REFERENCES runs(workspace_id,id)
    ) STRICT""",
    """CREATE TABLE run_jobs (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, run_id TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL CHECK(kind='RUN'),
        state TEXT NOT NULL CHECK(state IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')),
        lease TEXT, error_code TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
        UNIQUE(workspace_id,id),
        CHECK((state='RUNNING' AND lease IS NOT NULL)
            OR (state<>'RUNNING' AND lease IS NULL)),
        FOREIGN KEY(workspace_id,run_id) REFERENCES runs(workspace_id,id)
    ) STRICT""",
    "CREATE INDEX run_queue ON run_jobs(state,created_at,id)",
    """CREATE TABLE run_results (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, run_id TEXT NOT NULL,
        purchase_import_id TEXT NOT NULL, portal_import_id TEXT NOT NULL,
        source_row_number INTEGER NOT NULL,
        status TEXT NOT NULL CHECK(status IN (
            'EXACT_MATCH','FUZZY_SUGGESTION','AMOUNT_MISMATCH','MISSING_IN_SNAPSHOT',
            'AMBIGUOUS','EVIDENCE_INCOMPLETE','REVIEW_ACCEPTED','REJECTED')),
        version INTEGER NOT NULL CHECK(version>0), canonical_json TEXT NOT NULL,
        reasons_json TEXT NOT NULL, assigned_portal_row INTEGER,
        UNIQUE(workspace_id,id), UNIQUE(workspace_id,id,run_id),
        UNIQUE(run_id,source_row_number),
        UNIQUE(run_id,assigned_portal_row),
        CHECK((status IN ('EXACT_MATCH','REVIEW_ACCEPTED') AND assigned_portal_row IS NOT NULL)
            OR (status NOT IN ('EXACT_MATCH','REVIEW_ACCEPTED') AND assigned_portal_row IS NULL)),
        FOREIGN KEY(workspace_id,run_id) REFERENCES runs(workspace_id,id),
        FOREIGN KEY(workspace_id,purchase_import_id,source_row_number)
            REFERENCES import_rows(workspace_id,import_id,row_number),
        FOREIGN KEY(workspace_id,portal_import_id,assigned_portal_row)
            REFERENCES import_rows(workspace_id,import_id,row_number),
        FOREIGN KEY(workspace_id,run_id,purchase_import_id,portal_import_id)
            REFERENCES runs(workspace_id,id,purchase_import_id,portal_import_id)
    ) STRICT""",
    """CREATE TABLE run_candidates (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, run_id TEXT NOT NULL,
        result_id TEXT NOT NULL,
        portal_import_id TEXT NOT NULL, portal_row_number INTEGER NOT NULL,
        score TEXT NOT NULL, rank INTEGER NOT NULL CHECK(rank>0),
        eligible INTEGER NOT NULL CHECK(eligible IN (0,1)), original_invoice_number TEXT NOT NULL,
        invoice_date TEXT NOT NULL, differences_json TEXT NOT NULL, reasons_json TEXT NOT NULL,
        UNIQUE(result_id,portal_row_number), UNIQUE(result_id,rank),
        UNIQUE(workspace_id,result_id,id),
        FOREIGN KEY(workspace_id,run_id) REFERENCES runs(workspace_id,id),
        FOREIGN KEY(workspace_id,result_id,run_id)
            REFERENCES run_results(workspace_id,id,run_id),
        FOREIGN KEY(workspace_id,portal_import_id,portal_row_number)
            REFERENCES import_rows(workspace_id,import_id,row_number),
        FOREIGN KEY(workspace_id,run_id,portal_import_id)
            REFERENCES runs(workspace_id,id,portal_import_id)
    ) STRICT""",
    """CREATE TABLE run_events (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, run_id TEXT NOT NULL,
        result_id TEXT, actor_id TEXT NOT NULL REFERENCES users(id),
        action TEXT NOT NULL, reason TEXT, candidate_id TEXT REFERENCES run_candidates(id),
        result_version INTEGER, request_id TEXT NOT NULL, created_at INTEGER NOT NULL,
        FOREIGN KEY(workspace_id,run_id) REFERENCES runs(workspace_id,id),
        FOREIGN KEY(workspace_id,result_id,run_id)
            REFERENCES run_results(workspace_id,id,run_id),
        FOREIGN KEY(workspace_id,result_id,candidate_id)
            REFERENCES run_candidates(workspace_id,result_id,id)
    ) STRICT""",
    """CREATE TABLE run_operations (
        workspace_id TEXT NOT NULL, actor_id TEXT NOT NULL REFERENCES users(id),
        route TEXT NOT NULL, key TEXT NOT NULL, request_hash TEXT NOT NULL,
        response_json TEXT NOT NULL,
        PRIMARY KEY(workspace_id,actor_id,route,key),
        FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
    ) STRICT""",
)
