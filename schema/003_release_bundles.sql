-- Immutable release bundles, Release Decision Records, and deployments.
-- A bundle is a row. An RDR is a row. A deployment is a state machine in SQL.

CREATE TABLE release_bundles (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id           UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    bundle_tag         VARCHAR(128) NOT NULL,          -- "lesson-planner-v1.4.2"
    code_sha           VARCHAR(64),
    prompt_version_id  UUID,
    tool_schema_hashes JSONB NOT NULL DEFAULT '[]',    -- [{tool, hash}, ...]
    dataset_version_id UUID,
    policy_version_ids JSONB NOT NULL DEFAULT '[]',
    provider           VARCHAR(32) NOT NULL,
    model              VARCHAR(64) NOT NULL,           -- exact id, e.g. gpt-5-mini
    compaction_config  JSONB NOT NULL DEFAULT '{}',
    notes              TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Identity is (agent, tag). A bundle never mutates: any behavior-affecting
    -- change (prompt rev, model upgrade, new tool-schema hash) is a NEW row.
    UNIQUE (agent_id, bundle_tag)
);

-- Block in-place mutation at the database. New revision => new bundle.
CREATE OR REPLACE FUNCTION reject_bundle_update() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'release_bundles are immutable; create a new bundle instead';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_release_bundles_immutable
    BEFORE UPDATE ON release_bundles
    FOR EACH ROW EXECUTE FUNCTION reject_bundle_update();

CREATE TABLE release_decision_records (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bundle_id    UUID NOT NULL REFERENCES release_bundles(id) ON DELETE CASCADE,
    proposed_by  UUID NOT NULL REFERENCES platform_users(id),
    approvals    JSONB NOT NULL DEFAULT '[]',          -- [{actor, role, decision, note, decided_at}]
    eval_run_id  UUID,
    state        VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending', 'approved', 'rejected')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- No self-approval: there must be an approve from someone other than the proposer.
CREATE OR REPLACE VIEW rdr_self_approval_audit AS
SELECT
    r.id AS rdr_id, r.bundle_id, r.state,
    bool_or((a->>'decision') = 'approve' AND (a->>'actor')::uuid <> r.proposed_by)
        AS has_independent_approval
FROM release_decision_records r
LEFT JOIN LATERAL jsonb_array_elements(r.approvals) a ON true
GROUP BY r.id, r.bundle_id, r.state, r.proposed_by;

CREATE TABLE deployments (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id    UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    bundle_id   UUID NOT NULL REFERENCES release_bundles(id),
    state       VARCHAR(16) NOT NULL DEFAULT 'candidate'
        CHECK (state IN ('candidate', 'rolling_out', 'stable', 'rolled_back', 'retired')),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- At most one actively-serving bundle per agent (stable or rolling_out).
CREATE UNIQUE INDEX one_active_deployment_per_agent
    ON deployments (agent_id)
    WHERE state IN ('stable', 'rolling_out');
