-- Seed: the actual ChatLPO governance cascade from the article.
-- Org floor -> Teachers project extension -> one agent-level opt-out with a
-- recorded justification. Run after 001_governance_cascade.sql.

INSERT INTO organizations (slug, name) VALUES ('chatlpo', 'ChatLPO');

INSERT INTO projects (organization_id, slug, name)
SELECT id, 'teachers', 'Teachers' FROM organizations WHERE slug = 'chatlpo'
UNION ALL
SELECT id, 'support_callers', 'Support Callers' FROM organizations WHERE slug = 'chatlpo'
UNION ALL
SELECT id, 'enrolling_families', 'Enrolling Families' FROM organizations WHERE slug = 'chatlpo';

INSERT INTO agents (project_id, slug, name)
SELECT p.id, 'lesson-planner', 'Lesson Planner'
FROM projects p JOIN organizations o ON o.id = p.organization_id
WHERE o.slug = 'chatlpo' AND p.slug = 'teachers'
UNION ALL
SELECT p.id, 'parent-comms-drafter', 'Parent Comms Drafter'
FROM projects p JOIN organizations o ON o.id = p.organization_id
WHERE o.slug = 'chatlpo' AND p.slug = 'teachers';

INSERT INTO kpi_definitions (slug, category, unit, comparison, description) VALUES
    ('ttft_ms',                'performance', 'ms',  'lte', 'Time to first token (p50)'),
    ('time_to_response_p95',   'performance', 'ms',  'lte', 'Full response latency (p95)'),
    ('success_rate',           'reliability', 'pct', 'gte', 'Turn success rate'),
    ('cost_per_turn_usd',      'cost',        'usd', 'lte', 'Blended cost per turn'),
    ('safety_violation_rate',  'safety',      'pct', 'lte', 'Safety screen violation rate'),
    ('pii_leak_rate',          'safety',      'pct', 'lte', 'PII leak rate');

INSERT INTO eval_definitions (slug, description) VALUES
    ('safety_baseline',          'Org-wide safety floor for every agent'),
    ('pii_redaction',            'PII must be redacted in outputs'),
    ('prompt_injection_defense', 'Resist prompt-injection attempts'),
    ('educational_accuracy',     'Subject-matter accuracy of generated content'),
    ('hallucination_guard',      'No fabricated OA codes / Mineduc references'),
    ('topic_adherence',          'Stay within the requested instructional scope'),
    ('child_safety',             'Output is safe for a Chilean classroom');

-- Org floor: every ChatLPO agent inherits these.
INSERT INTO org_kpi_assignments (organization_id, kpi_id, is_required, notes)
SELECT o.id, k.id, true, 'Org-wide ChatLPO floor — applies to every agent.'
FROM organizations o
CROSS JOIN kpi_definitions k
WHERE o.slug = 'chatlpo'
  AND k.slug IN ('ttft_ms', 'time_to_response_p95', 'success_rate',
                 'cost_per_turn_usd', 'safety_violation_rate', 'pii_leak_rate');

INSERT INTO org_eval_assignments (organization_id, eval_id, is_required, notes)
SELECT o.id, e.id, true, 'Org-wide ChatLPO safety baseline - every agent must pass.'
FROM organizations o CROSS JOIN eval_definitions e
WHERE o.slug = 'chatlpo'
  AND e.slug IN ('safety_baseline', 'pii_redaction', 'prompt_injection_defense');

-- Teachers project extends the floor with educational evals...
INSERT INTO project_eval_assignments (project_id, eval_id, is_required, notes)
SELECT p.id, e.id, true, 'Teacher-facing extension to the org floor.'
FROM projects p JOIN organizations o ON o.id = p.organization_id
CROSS JOIN eval_definitions e
WHERE o.slug = 'chatlpo' AND p.slug = 'teachers'
  AND e.slug IN ('educational_accuracy', 'hallucination_guard',
                 'topic_adherence', 'child_safety');

-- ...and tightens cost-per-turn for high-volume teacher workflows.
INSERT INTO project_kpi_assignments (project_id, kpi_id, is_required, target_value, notes)
SELECT p.id, k.id, true, 0.015, 'Lesson planning runs at classroom scale; tighten cost.'
FROM projects p JOIN organizations o ON o.id = p.organization_id
JOIN kpi_definitions k ON k.slug = 'cost_per_turn_usd'
WHERE o.slug = 'chatlpo' AND p.slug = 'teachers';

-- Agent-level opt-out: the async parent-comms drafter opts out of TTFT.
INSERT INTO agent_kpi_assignments (agent_id, kpi_id, is_enabled, justification, approved_by)
SELECT a.id, k.id, false,
       'Async drafting workflow: the teacher reviews and edits before anything '
       'is sent, so first-token latency is not a meaningful UX metric.',
       NULL
FROM agents a
JOIN projects p ON p.id = a.project_id
JOIN organizations o ON o.id = p.organization_id
JOIN kpi_definitions k ON k.slug = 'ttft_ms'
WHERE o.slug = 'chatlpo' AND p.slug = 'teachers' AND a.slug = 'parent-comms-drafter';
