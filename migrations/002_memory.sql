-- Siduri's authoritative single-user memory schema for Supabase Postgres.
-- The local orchestrator connects directly; RLS blocks Supabase client roles.

CREATE TABLE IF NOT EXISTS memories (
    memory_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    provenance TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    allowed_audiences JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    last_confirmed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    superseded_by TEXT,
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    revision INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS memory_revisions (
    memory_id TEXT NOT NULL REFERENCES memories(memory_id) ON DELETE CASCADE,
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
    allowed_audiences JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected'))
);

CREATE TABLE IF NOT EXISTS memory_audit_events (
    event_id TEXT PRIMARY KEY,
    memory_id TEXT,
    event_type TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    detail JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS source_events (
    event_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS memory_proposal_claims (
    proposal_id TEXT PRIMARY KEY REFERENCES memory_proposals(proposal_id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    value TEXT,
    claim_type TEXT NOT NULL CHECK (claim_type IN ('semantic', 'preference', 'episodic', 'relationship')),
    source_event_id TEXT REFERENCES source_events(event_id)
);

CREATE TABLE IF NOT EXISTS versioned_claims (
    claim_id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    value TEXT NOT NULL,
    claim_type TEXT NOT NULL CHECK (claim_type IN ('semantic', 'preference', 'episodic', 'relationship')),
    source_event_id TEXT NOT NULL REFERENCES source_events(event_id),
    provenance TEXT NOT NULL,
    authority TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed', 'rejected', 'session_only', 'superseded', 'revoked')),
    sensitivity TEXT NOT NULL,
    allowed_audiences JSONB NOT NULL DEFAULT '[]'::jsonb,
    user_confirmation TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    asserted_at TIMESTAMPTZ NOT NULL,
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    supersedes TEXT REFERENCES versioned_claims(claim_id),
    replaces TEXT REFERENCES versioned_claims(claim_id),
    schema_version INTEGER NOT NULL DEFAULT 1,
    search_document TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', coalesce(subject, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(predicate, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(value, '')), 'B')
    ) STORED
);

CREATE INDEX IF NOT EXISTS versioned_claims_current_lookup_idx
    ON versioned_claims (subject, predicate, status, asserted_at DESC);
CREATE INDEX IF NOT EXISTS versioned_claims_search_idx
    ON versioned_claims USING GIN (search_document);

CREATE TABLE IF NOT EXISTS behavioral_directives (
    directive_id TEXT PRIMARY KEY,
    memory_class TEXT NOT NULL CHECK (memory_class IN ('identity', 'relationship', 'behavioral')),
    domain TEXT NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    value TEXT NOT NULL,
    activation TEXT NOT NULL CHECK (activation IN ('always', 'always_when_scope_matches', 'retrieval_only', 'session_only', 'disabled')),
    scope JSONB NOT NULL,
    behavior JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed', 'rejected', 'session_only', 'superseded', 'revoked')),
    source_type TEXT NOT NULL,
    source_event_id TEXT NOT NULL REFERENCES source_events(event_id),
    confirmed_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    supersedes_id TEXT REFERENCES behavioral_directives(directive_id),
    sensitivity TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS behavioral_directives_active_lookup_idx
    ON behavioral_directives (status, activation, domain, subject, predicate, created_at DESC);

-- No policies are intentionally created. Supabase's anon/authenticated API
-- roles receive no rows; the trusted local orchestrator uses the database URL.
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_proposal_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE versioned_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE behavioral_directives ENABLE ROW LEVEL SECURITY;

-- Embeddings can be added later without changing claim identity:
-- CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;
-- ALTER TABLE versioned_claims ADD COLUMN embedding extensions.vector(<chosen_dimensions>);
