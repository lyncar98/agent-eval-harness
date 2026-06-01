-- Offline eval runs and per-case items. Trials live as JSONB so a 3am on-call
-- can pull the exact failed trial and replay it.

CREATE TABLE eval_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    suite_slug      VARCHAR(128) NOT NULL,
    bundle_id       UUID REFERENCES release_bundles(id),
    trials_per_case INTEGER NOT NULL,
    required_passes INTEGER NOT NULL,
    -- Reporting metrics (computed over APPLICABLE cases only):
    pass_at_1       NUMERIC(5,4),
    pass_at_k       NUMERIC(5,4),
    pass_pow_k      NUMERIC(5,4),
    gate_pass_rate  NUMERIC(5,4),
    total_cases     INTEGER NOT NULL,
    applicable_cases INTEGER NOT NULL,
    approved        BOOLEAN NOT NULL DEFAULT false,
    decision_reason TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE eval_run_items (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id       UUID NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    case_id      VARCHAR(128) NOT NULL,
    case_type    VARCHAR(16) NOT NULL DEFAULT 'typical',
    applicable   BOOLEAN NOT NULL DEFAULT true,
    n_passed     INTEGER NOT NULL,
    required     INTEGER NOT NULL,
    item_passed  BOOLEAN NOT NULL,
    -- Each element: {trial_idx, passed, response, grader_results, tool_calls,
    --                transcript, latency_ms, tokens, cost_usd, error}
    trials       JSONB NOT NULL DEFAULT '[]',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX eval_run_items_run_idx ON eval_run_items (run_id);

-- Convenience: pull failed trials for replay.
CREATE OR REPLACE VIEW failed_trials AS
SELECT
    i.run_id, i.case_id, i.case_type,
    (t->>'trial_idx')::int  AS trial_idx,
    t->>'response'          AS response,
    t->'grader_results'     AS grader_results,
    t->'tool_calls'         AS tool_calls
FROM eval_run_items i
CROSS JOIN LATERAL jsonb_array_elements(i.trials) t
WHERE (t->>'passed')::boolean IS NOT TRUE;
