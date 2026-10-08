"""Additive v8 business, team and source-bound process storage."""

PRODUCT_SCHEMA = (
    """CREATE TABLE business_profile (
        workspace_id TEXT NOT NULL, registration_id TEXT NOT NULL, period TEXT NOT NULL,
        value_json TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0),
        updated_by TEXT NOT NULL REFERENCES users(id), updated_at INTEGER NOT NULL,
        PRIMARY KEY(workspace_id,registration_id,period),
                FOREIGN KEY(workspace_id,registration_id) REFERENCES
        registrations(workspace_id,id)) STRICT""",
    """CREATE TABLE team_profile (
        workspace_id TEXT NOT NULL, user_id TEXT NOT NULL, display_name TEXT NOT NULL,
        roles_json TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0),
        PRIMARY KEY(workspace_id,user_id),
        FOREIGN KEY(workspace_id,user_id) REFERENCES memberships(workspace_id,user_id)) STRICT""",
    """CREATE TABLE product_events (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        actor_id TEXT NOT NULL REFERENCES users(id), kind TEXT NOT NULL,
        fingerprint TEXT NOT NULL CHECK(length(fingerprint)=64),
        payload_json TEXT NOT NULL, created_at INTEGER NOT NULL) STRICT""",
    "CREATE INDEX product_event_scope ON product_events(workspace_id,created_at,id)",
    """CREATE TABLE team_contribution (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, registration_id TEXT NOT NULL,
        period TEXT NOT NULL, actor_id TEXT NOT NULL, role TEXT NOT NULL,
        note TEXT NOT NULL, created_at INTEGER NOT NULL,
        FOREIGN KEY(workspace_id,registration_id) REFERENCES registrations(workspace_id,id),
        FOREIGN KEY(workspace_id,actor_id) REFERENCES memberships(workspace_id,user_id)) STRICT""",
    """CREATE TABLE workflow_template (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        name TEXT NOT NULL, nodes_json TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0),
        UNIQUE(workspace_id,id)) STRICT""",
    """CREATE TABLE workflow_run (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, registration_id TEXT NOT NULL,
        period TEXT NOT NULL, template_id TEXT NOT NULL, passport_id TEXT, batch_id TEXT,
        state TEXT NOT NULL CHECK(state IN ('IN_PROGRESS','PROCESS_COMPLETED')),
        version INTEGER NOT NULL CHECK(version>0), created_by TEXT NOT NULL REFERENCES users(id),
        fingerprint TEXT NOT NULL CHECK(length(fingerprint)=64),
        summary_json TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
        UNIQUE(workspace_id,id), UNIQUE(workspace_id,passport_id), UNIQUE(workspace_id,batch_id),
        CHECK((passport_id IS NOT NULL)+(batch_id IS NOT NULL)=1),
        FOREIGN KEY(workspace_id,registration_id) REFERENCES registrations(workspace_id,id),
        FOREIGN KEY(workspace_id,template_id) REFERENCES workflow_template(workspace_id,id),
        FOREIGN KEY(workspace_id,passport_id) REFERENCES invoice_passports(workspace_id,id),
        FOREIGN KEY(workspace_id,batch_id) REFERENCES runs(workspace_id,id)) STRICT""",
    """CREATE TABLE node (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, run_id TEXT NOT NULL,
        ordinal INTEGER NOT NULL CHECK(ordinal>=0), kind TEXT NOT NULL, title TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN
        ('PENDING','ASSIGNED','IN_PROGRESS','BLOCKED','DONE','STALE')),
        version INTEGER NOT NULL CHECK(version>0), assigned_to TEXT, due_on TEXT,
        fingerprint TEXT, output_json TEXT NOT NULL,
        UNIQUE(workspace_id,id), UNIQUE(run_id,ordinal),
        FOREIGN KEY(workspace_id,run_id) REFERENCES workflow_run(workspace_id,id),
                FOREIGN KEY(workspace_id,assigned_to) REFERENCES
        memberships(workspace_id,user_id)) STRICT""",
    """CREATE TABLE edge (
                workspace_id TEXT NOT NULL, run_id TEXT NOT NULL, from_node TEXT NOT NULL,
        to_node TEXT NOT NULL,
        PRIMARY KEY(from_node,to_node),
        FOREIGN KEY(workspace_id,run_id) REFERENCES workflow_run(workspace_id,id),
        FOREIGN KEY(workspace_id,from_node) REFERENCES node(workspace_id,id),
        FOREIGN KEY(workspace_id,to_node) REFERENCES node(workspace_id,id)) STRICT""",
    """CREATE TABLE node_event (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, run_id TEXT NOT NULL, node_id TEXT,
        actor_id TEXT NOT NULL REFERENCES users(id), kind TEXT NOT NULL,
        from_state TEXT NOT NULL, to_state TEXT NOT NULL, fingerprint TEXT NOT NULL,
        note TEXT NOT NULL, created_at INTEGER NOT NULL,
        FOREIGN KEY(workspace_id,run_id) REFERENCES workflow_run(workspace_id,id),
        FOREIGN KEY(workspace_id,node_id) REFERENCES node(workspace_id,id)) STRICT""",
    "CREATE INDEX node_event_scope ON node_event(workspace_id,run_id,created_at,id)",
    """CREATE TABLE assignment (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
        assigned_to TEXT NOT NULL, actor_id TEXT NOT NULL REFERENCES users(id),
        due_on TEXT, note TEXT NOT NULL, created_at INTEGER NOT NULL,
        FOREIGN KEY(workspace_id,node_id) REFERENCES node(workspace_id,id),
                FOREIGN KEY(workspace_id,assigned_to) REFERENCES
        memberships(workspace_id,user_id)) STRICT""",
    """CREATE TABLE process_notification (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, recipient_id TEXT NOT NULL,
        run_id TEXT NOT NULL, kind TEXT NOT NULL, payload_json TEXT NOT NULL,
        read INTEGER NOT NULL CHECK(read IN (0,1)), created_at INTEGER NOT NULL,
        FOREIGN KEY(workspace_id,recipient_id) REFERENCES memberships(workspace_id,user_id),
        FOREIGN KEY(workspace_id,run_id) REFERENCES workflow_run(workspace_id,id)) STRICT""",
    """CREATE TABLE invoice_review_facts (
        workspace_id TEXT NOT NULL, passport_id TEXT NOT NULL, facts_json TEXT NOT NULL,
        version INTEGER NOT NULL CHECK(version>0), source_signature TEXT NOT NULL,
        updated_by TEXT NOT NULL REFERENCES users(id), updated_at INTEGER NOT NULL,
        PRIMARY KEY(workspace_id,passport_id),
                FOREIGN KEY(workspace_id,passport_id) REFERENCES
        invoice_passports(workspace_id,id)) STRICT""",
    """CREATE TABLE tax_suggestion_review (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, passport_id TEXT NOT NULL,
        suggestion_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                conclusion TEXT NOT NULL CHECK(conclusion IN
        ('ACTION_REVIEWED','NOT_APPLICABLE','MORE_EVIDENCE')),
                note TEXT NOT NULL, reviewed_by TEXT NOT NULL REFERENCES users(id), created_at
        INTEGER NOT NULL,
                FOREIGN KEY(workspace_id,passport_id) REFERENCES
        invoice_passports(workspace_id,id)) STRICT""",
)
