-- Online eval samples, SLO definitions, and self-opening incidents.

-- Idempotency anchor: ON CONFLICT (request_id) DO NOTHING on insert means a
-- stream replay produces the same rows whether it runs once or ten times.
CREATE TABLE online_eval_samples (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id  VARCHAR(128) UNIQUE NOT NULL,
    agent_id    UUID REFERENCES agents(id) ON DELETE SET NULL,
    bundle_id   UUID REFERENCES release_bundles(id),   -- stable|rolling_out at sample time
    suite_slug  VARCHAR(128) NOT NULL,
    passed      BOOLEAN NOT NULL,
    scored      JSONB NOT NULL DEFAULT '[]',           -- online-safe grader verdicts
    skipped     JSONB NOT NULL DEFAULT '[]',           -- checks not runnable online
    sampled_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE slo_definitions (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id             UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    name                 VARCHAR(128) NOT NULL,
    metric               VARCHAR(64) NOT NULL,         -- ttft_ms, success_rate, ...
    category             VARCHAR(32),
    target               NUMERIC NOT NULL,
    comparison           VARCHAR(8) NOT NULL DEFAULT 'lte',  -- gte|lte
    window_minutes       INTEGER NOT NULL DEFAULT 60,   -- room for MWMBR later
    burn_alert_threshold NUMERIC NOT NULL DEFAULT 1.0,
    is_enabled           BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE incidents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id    UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    severity    VARCHAR(8) NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
    category    VARCHAR(32) NOT NULL,
    title       TEXT NOT NULL,
    detail      TEXT,
    state       VARCHAR(16) NOT NULL DEFAULT 'open'
        CHECK (state IN ('open', 'mitigated', 'resolved')),
    opened_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- Duplicate guard: don't open a second incident for the same agent+title while
-- a matching one is still open or mitigated.
CREATE UNIQUE INDEX one_open_incident_per_signal
    ON incidents (agent_id, title)
    WHERE state IN ('open', 'mitigated');
