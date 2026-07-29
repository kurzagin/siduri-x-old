CREATE TABLE IF NOT EXISTS stream_sessions (
    session_id TEXT PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('planned', 'active', 'ended', 'failed'))
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    session_id TEXT,
    correlation_id TEXT,
    privacy_class TEXT NOT NULL,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS audit_events_session_idx ON audit_events (session_id, occurred_at);
