-- Grader calibration: treat every model grader as untrusted until proven.
-- A human marks a trial pass/fail; we log agreement PER GRADER (not per trial),
-- so disagreement is attributed to the rubric judge, not the regex that was fine.

CREATE TABLE eval_grader_calibrations (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_item_id   UUID NOT NULL REFERENCES eval_run_items(id) ON DELETE CASCADE,
    trial_idx     INTEGER NOT NULL DEFAULT 0,
    grader_name   VARCHAR(64) NOT NULL,
    grader_kind   VARCHAR(16) NOT NULL,            -- code|model|human
    grader_score  NUMERIC(5,4) NOT NULL,
    grader_passed BOOLEAN NOT NULL,
    human_passed  BOOLEAN NOT NULL,
    agrees        BOOLEAN GENERATED ALWAYS AS (grader_passed = human_passed) STORED,
    reviewer_id   UUID REFERENCES platform_users(id),
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX grader_calib_name_idx ON eval_grader_calibrations (grader_name);

-- Trust = agreement rate with humans. Control plane sorts ASC so the
-- least-trusted judges sit at the top of the Grader Trust tab.
CREATE OR REPLACE VIEW eval_grader_trust AS
SELECT
    grader_name, grader_kind,
    COUNT(*)                                        AS reviews_total,
    COUNT(*) FILTER (WHERE agrees)                  AS reviews_agreed,
    (COUNT(*) FILTER (WHERE agrees))::numeric
        / NULLIF(COUNT(*), 0)::numeric              AS agreement_rate,
    MAX(created_at)                                 AS last_reviewed_at
FROM eval_grader_calibrations
GROUP BY grader_name, grader_kind;

-- Trust bands, applied as policy:
--   < 0.70  -> needs recalibration (removed from gating immediately)
--   0.70-0.90 -> watch (advisory; humans still call the trial)
--   >= 0.90 -> trusted (may gate)
CREATE OR REPLACE VIEW eval_grader_trust_banded AS
SELECT
    *,
    CASE
        WHEN agreement_rate IS NULL THEN 'unreviewed'
        WHEN agreement_rate < 0.70 THEN 'needs_recalibration'
        WHEN agreement_rate < 0.90 THEN 'watch'
        ELSE 'trusted'
    END AS trust_band,
    (agreement_rate >= 0.90) AS may_gate
FROM eval_grader_trust;
