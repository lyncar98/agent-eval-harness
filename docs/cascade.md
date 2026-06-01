# The standards cascade

```
Org      →  the floor. Every agent inherits these evals and KPIs.
 Project →  extends the floor; may tighten target values.
  Agent  →  may opt out of a specific check — with a written justification.
```

Governance you can't query is governance you don't have. The cascade lives in
data, not a binder: every assignment, override, and justification is a row you
can audit six months later.

## In code

```python
from agent_eval import Assignment, AgentOverride, resolve

effective = resolve(
    org=[Assignment("pii_redaction"), Assignment("cost_per_turn_usd", target_value=0.03)],
    project=[Assignment("cost_per_turn_usd", target_value=0.015)],  # tightens
    agent=[AgentOverride(
        "ttft_ms", is_enabled=False,
        justification="Async drafting workflow; first-token latency is not a UX metric.",
    )],
    comparison={"cost_per_turn_usd": "lte"},
)
```

- Project assignments **tighten** targets in the correct direction
  (`lte` → smaller is tighter; `gte` → larger is tighter).
- An agent opt-out (`is_enabled=False`) **must** carry a justification of at
  least 10 characters, or `resolve` raises `JustificationRequired`.

## In SQL

The same shape is enforced at the database in
[`schema/001_governance_cascade.sql`](../schema/001_governance_cascade.sql):

```sql
CONSTRAINT agent_kpi_override_justified CHECK (
    is_enabled = true
    OR length(trim(coalesce(justification, ''))) >= 10
)
```

and the effective set is materialized by the `agent_effective_kpis` view. The
ChatLPO floor + Teachers extension + the parent-comms TTFT opt-out are seeded in
[`schema/002_chatlpo_seed.sql`](../schema/002_chatlpo_seed.sql).
