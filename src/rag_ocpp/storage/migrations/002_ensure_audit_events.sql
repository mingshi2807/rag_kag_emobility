-- Ensure privacy-preserving enterprise audit trail exists on legacy databases.
-- Do not store raw prompts, source chunks, generated answers, secrets, or full query text.

CREATE TABLE IF NOT EXISTS audit_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type      TEXT NOT NULL,
    surface         TEXT NOT NULL,
    action          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'success',
    actor_id        TEXT,
    session_id      TEXT,
    correlation_id  TEXT,
    resource_type   TEXT,
    resource_id     TEXT,
    latency_ms      INT,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_events_type_created
    ON audit_events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_events_surface_created
    ON audit_events(surface, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_events_correlation
    ON audit_events(correlation_id);
CREATE INDEX IF NOT EXISTS audit_events_resource
    ON audit_events(resource_type, resource_id);
