CREATE TABLE IF NOT EXISTS memories (
    memory_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    provenance TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    allowed_audiences JSONB NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    last_confirmed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    superseded_by TEXT,
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    revision INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS memory_revisions (
    memory_id TEXT NOT NULL REFERENCES memories(memory_id),
    revision INTEGER NOT NULL,
    content TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL,
    change_reason TEXT NOT NULL,
    PRIMARY KEY (memory_id, revision)
);

CREATE TABLE IF NOT EXISTS memory_proposals (
    proposal_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    provenance TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    allowed_audiences JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected'))
);

CREATE TABLE IF NOT EXISTS memory_audit_events (
    event_id TEXT PRIMARY KEY,
    memory_id TEXT,
    event_type TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    detail JSONB NOT NULL
);
