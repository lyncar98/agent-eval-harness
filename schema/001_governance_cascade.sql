-- Governance cascade: org -> project -> agent.
--
-- The contract is three sentences, and the third one is a CHECK constraint,
-- not a culture deck:
--   1. Org-level KPIs and evals are the FLOOR; every agent inherits them.
--   2. Project-level assignments EXTEND the floor (and may tighten targets).
--   3. An agent may OPT OUT of a specific KPI/eval only with a written
--      justification of at least 10 characters.
--
-- Postgres dialect. Requires uuid-ossp (or swap for gen_random_uuid()).

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE organizations (
    id    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug  VARCHAR(64) UNIQUE NOT NULL,
    name  TEXT NOT NULL
);

CREATE TABLE projects (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id  UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    slug             VARCHAR(64) NOT NULL,
    name             TEXT NOT NULL,
    UNIQUE (organization_id, slug)
);

CREATE TABLE agents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    slug        VARCHAR(64) NOT NULL,
    name        TEXT NOT NULL,
    UNIQUE (project_id, slug)
);

CREATE TABLE platform_users (
    id     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email  TEXT UNIQUE,
    name   TEXT
);

CREATE TABLE kpi_definitions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug        VARCHAR(64) UNIQUE NOT NULL,   -- ttft_ms, success_rate, ...
    category    VARCHAR(32) NOT NULL,          -- performance|cost|safety|quality
    unit        VARCHAR(32),
    comparison  VARCHAR(8) NOT NULL DEFAULT 'lte',  -- gte|lte ("better" direction)
    description TEXT
);

CREATE TABLE eval_definitions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug        VARCHAR(64) UNIQUE NOT NULL,   -- safety_baseline, pii_redaction, ...
    description TEXT
);

CREATE TABLE org_kpi_assignments (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id  UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    kpi_id           UUID NOT NULL REFERENCES kpi_definitions(id),
    is_required      BOOLEAN NOT NULL DEFAULT true,
    target_value     NUMERIC,
    notes            TEXT,
    UNIQUE (organization_id, kpi_id)
);

CREATE TABLE org_eval_assignments (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id  UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    eval_id          UUID NOT NULL REFERENCES eval_definitions(id),
    is_required      BOOLEAN NOT NULL DEFAULT true,
    notes            TEXT,
    UNIQUE (organization_id, eval_id)
);

CREATE TABLE project_kpi_assignments (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kpi_id        UUID NOT NULL REFERENCES kpi_definitions(id),
    is_required   BOOLEAN NOT NULL DEFAULT true,
    target_value  NUMERIC,
    notes         TEXT,
    UNIQUE (project_id, kpi_id)
);

CREATE TABLE project_eval_assignments (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    eval_id      UUID NOT NULL REFERENCES eval_definitions(id),
    is_required  BOOLEAN NOT NULL DEFAULT true,
    notes        TEXT,
    UNIQUE (project_id, eval_id)
);

-- Agent overrides — opt-out is allowed ONLY with a justification >= 10 chars.
CREATE TABLE agent_kpi_assignments (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id       UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    kpi_id         UUID NOT NULL REFERENCES kpi_definitions(id),
    is_enabled     BOOLEAN NOT NULL DEFAULT true,
    target_value   NUMERIC,
    justification  TEXT,
    approved_by    UUID REFERENCES platform_users(id),
    UNIQUE (agent_id, kpi_id),
    CONSTRAINT agent_kpi_override_justified CHECK (
        is_enabled = true
        OR length(trim(coalesce(justification, ''))) >= 10
    )
);

CREATE TABLE agent_eval_assignments (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id       UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    eval_id        UUID NOT NULL REFERENCES eval_definitions(id),
    is_enabled     BOOLEAN NOT NULL DEFAULT true,
    justification  TEXT,
    approved_by    UUID REFERENCES platform_users(id),
    UNIQUE (agent_id, eval_id),
    CONSTRAINT agent_eval_override_justified CHECK (
        is_enabled = true
        OR length(trim(coalesce(justification, ''))) >= 10
    )
);

-- Effective KPIs per agent: org floor + project extension minus justified
-- opt-outs; tightest target wins via COALESCE precedence agent>project>org.
CREATE OR REPLACE VIEW agent_effective_kpis AS
SELECT
    a.id                                            AS agent_id,
    k.id                                            AS kpi_id,
    k.slug                                          AS kpi_slug,
    k.category,
    COALESCE(ak.target_value, pk.target_value, ok.target_value) AS target_value,
    COALESCE(ak.is_enabled, true)                   AS is_enabled
FROM agents a
JOIN projects p           ON p.id = a.project_id
JOIN organizations o      ON o.id = p.organization_id
JOIN org_kpi_assignments ok ON ok.organization_id = o.id
JOIN kpi_definitions k    ON k.id = ok.kpi_id
LEFT JOIN project_kpi_assignments pk ON pk.project_id = p.id AND pk.kpi_id = k.id
LEFT JOIN agent_kpi_assignments  ak ON ak.agent_id   = a.id AND ak.kpi_id  = k.id
WHERE COALESCE(ak.is_enabled, true) = true;
