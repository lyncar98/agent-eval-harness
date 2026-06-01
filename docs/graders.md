# Graders

Every grader — code, model, or human-derived — is a configured callable with one
signature:

```python
grader(ctx: GraderContext) -> {"name", "family", "score", "passed", "reason", "gating"}
```

Graders are produced by **factory functions** so a suite can carry pre-configured
graders, and the same name can be instantiated from YAML via `make_grader`.

```python
from agent_eval.graders import min_length, code_no_keyword, llm_rubric

graders = [
    min_length(config={"min": 40}),
    code_no_keyword(config={"banned": ["OA-99-FAKE"]}),
    llm_rubric(config={"rubric": "...", "pass_threshold": 0.8}),
]
```

## Families

| Family | Cost | Reliability | Default role |
|---|---|---|---|
| `code` | cheap, deterministic | exact | gating |
| `model` (LLM-as-judge) | $$, slower | calibrated | gating **only** once trusted |
| `human` | expensive | ground truth | calibration source |

## The registry (15 graders)

### Code (deterministic)

| Name | Online-safe | What it checks |
|---|:--:|---|
| `no_keyword` | | banned tokens absent (offline; use `regex_match` online) |
| `keyword` | ✅ | required tokens present |
| `min_length` | ✅ | response not empty/evasive (`min` or `min_chars`) |
| `max_length` | ✅ | response not runaway (`max` or `max_chars`) |
| `regex_match` | ✅ | regex asserted or forbidden (`should_match`) |
| `json_valid` | ✅ | parses as JSON; optional `required_keys` |
| `no_refusal` | ✅ | not a refusal when an answer was expected |
| `sentiment` | ✅ | no hostile/dismissive tone |
| `expected_output` | | normalized exact match (offline) |
| `state_check` | | produced state ⊇ `expected_state` (outcome) |
| `tool_called` | ✅ | a specific tool was (not) invoked |
| `tool_sequence` | | ordered-subsequence trajectory (diagnostic by default) |

### Model (LLM-as-judge)

| Name | What it checks |
|---|---|
| `llm_rubric` | free-text rubric, with an explicit N/A "way out" |
| `llm_pairwise` | candidate vs reference solution |
| `groundedness` | claims supported by provided context |

The 8 **online-safe** graders form the deterministic, judge-free subset the
online sampler runs in production. The online consumer iterates the same suite
and **skips** anything outside that set.

## Outcome over trajectory

`tool_sequence` exists but is diagnostic by default (`gating=false`). Grade the
end state (`state_check`, output rubrics) and let the agent pick its path; assert
order only where the order *is* the policy.

## The judge "way out"

The rubric prompt instructs: *"If the rubric does not apply, set score=1.0,
passed=true, and explain in reason."* That N/A is a parser-level default so one
weird case can't crash a run. It is **not** a free pass: the runner detects N/A
reasons and excludes them from the denominator (see
[`design-decisions.md`](./design-decisions.md)).
