"""Additive schema 6: durable channel records; original business tables stay intact."""

WHATSAPP_SCHEMA = (
    """CREATE TABLE wa_links (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
        user_version INTEGER NOT NULL, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        registration_id TEXT NOT NULL, period TEXT NOT NULL, phone TEXT NOT NULL,
        active INTEGER NOT NULL CHECK(active IN (0,1)), version INTEGER NOT NULL CHECK(version>0),
        consent_alerts INTEGER NOT NULL DEFAULT 0 CHECK(consent_alerts IN (0,1)),
        last_inbound INTEGER NOT NULL, created_at INTEGER NOT NULL,
        FOREIGN KEY(workspace_id,registration_id) REFERENCES registrations(workspace_id,id))
        STRICT""",
    "CREATE UNIQUE INDEX wa_phone_active ON wa_links(phone) WHERE active=1",
    "CREATE UNIQUE INDEX wa_user_active ON wa_links(user_id) WHERE active=1",
    """CREATE TABLE wa_codes (
        code_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
        user_version INTEGER NOT NULL, workspace_id TEXT NOT NULL REFERENCES workspaces(id),
        registration_id TEXT NOT NULL, period TEXT NOT NULL, expires_at INTEGER NOT NULL,
        FOREIGN KEY(workspace_id,registration_id) REFERENCES registrations(workspace_id,id))
        STRICT""",
    """CREATE TABLE wa_events (
        event_key TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('TEXT','DOCUMENT','STATUS')),
        phone TEXT NOT NULL, payload TEXT NOT NULL, link_id TEXT REFERENCES wa_links(id),
        link_version INTEGER, state TEXT NOT NULL CHECK(state IN
        ('QUEUED','PROCESSING','DONE','FAILED')),
        error_code TEXT, received_at INTEGER NOT NULL) STRICT""",
    "CREATE INDEX wa_events_queue ON wa_events(state,received_at,event_key)",
    """CREATE TABLE wa_intents (
        link_id TEXT PRIMARY KEY REFERENCES wa_links(id), link_version INTEGER NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('PURCHASE','PORTAL_2B')),
        expires_at INTEGER NOT NULL, event_key TEXT UNIQUE REFERENCES wa_events(event_key))
        STRICT""",
    """CREATE TABLE wa_outbox (
        id TEXT PRIMARY KEY, logical_key TEXT NOT NULL UNIQUE,
        link_id TEXT REFERENCES wa_links(id), link_version INTEGER, phone TEXT NOT NULL,
        body TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN
          ('QUEUED','ATTEMPTED','ACKNOWLEDGED','DELIVERED','READ','FAILED','UNKNOWN','CANCELLED')),
        provider_id TEXT UNIQUE, error_code TEXT, created_at INTEGER NOT NULL,
        attempted_at INTEGER, updated_at INTEGER NOT NULL) STRICT""",
    "CREATE INDEX wa_outbox_queue ON wa_outbox(state,created_at,id)",
    """CREATE TABLE wa_watches (
        logical_key TEXT PRIMARY KEY, link_id TEXT NOT NULL REFERENCES wa_links(id),
        link_version INTEGER NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('IMPORT','ARTIFACT')),
        resource_id TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('PENDING','DONE')),
        created_at INTEGER NOT NULL) STRICT""",
    """CREATE TABLE wa_capabilities (
        token_hash TEXT PRIMARY KEY, link_id TEXT NOT NULL REFERENCES wa_links(id),
        link_version INTEGER NOT NULL, artifact_id TEXT NOT NULL REFERENCES artifacts(id),
        expires_at INTEGER NOT NULL, downloads INTEGER NOT NULL DEFAULT 0 CHECK(downloads>=0),
        revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1))) STRICT""",
    """CREATE TABLE wa_rates (
        bucket TEXT PRIMARY KEY, expires_at INTEGER NOT NULL, count INTEGER NOT NULL
        CHECK(count>0)) STRICT""",
    """CREATE TABLE wa_budget (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), used INTEGER NOT NULL CHECK(used>=0))
        STRICT""",
    "INSERT INTO wa_budget VALUES (1,0)",
    """CREATE TABLE wa_consent_codes (
        code_hash TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
        user_id TEXT NOT NULL REFERENCES users(id), user_version INTEGER NOT NULL,
        action_id TEXT NOT NULL, draft_id TEXT NOT NULL REFERENCES action_events(id),
        action_version INTEGER NOT NULL, phone TEXT NOT NULL, expires_at INTEGER NOT NULL,
        FOREIGN KEY(workspace_id,action_id) REFERENCES business_actions(workspace_id,id)) STRICT""",
    """CREATE TABLE wa_recipients (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
        user_id TEXT NOT NULL REFERENCES users(id), user_version INTEGER NOT NULL,
        action_id TEXT NOT NULL, draft_id TEXT NOT NULL REFERENCES action_events(id),
        action_version INTEGER NOT NULL, phone TEXT NOT NULL, verified_at INTEGER NOT NULL,
        last_inbound INTEGER NOT NULL, active INTEGER NOT NULL CHECK(active IN (0,1)),
        FOREIGN KEY(workspace_id,action_id) REFERENCES business_actions(workspace_id,id)) STRICT""",
    "CREATE UNIQUE INDEX wa_recipient_draft ON wa_recipients(workspace_id,draft_id) WHERE active=1",
    """CREATE TABLE wa_followups (
        outbox_id TEXT PRIMARY KEY REFERENCES wa_outbox(id), recipient_id TEXT NOT NULL
        REFERENCES wa_recipients(id),
        workspace_id TEXT NOT NULL, action_id TEXT NOT NULL, draft_id TEXT NOT NULL REFERENCES
        action_events(id),
        actor_id TEXT NOT NULL REFERENCES users(id), source_signature TEXT NOT NULL,
        FOREIGN KEY(workspace_id,action_id) REFERENCES business_actions(workspace_id,id)) STRICT""",
    """CREATE TABLE wa_delivery_events (
        id TEXT PRIMARY KEY, outbox_id TEXT NOT NULL REFERENCES wa_outbox(id),
        state TEXT NOT NULL, created_at INTEGER NOT NULL,
        UNIQUE(outbox_id,state)) STRICT""",
)
