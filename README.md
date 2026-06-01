# agent-eval-harness

> Production-grade evaluation for LLM agents. A grader registry (code / model / human), `pass@1` / `pass@k` / `pass^k` consistency scoring, calibrated LLM judges, and an org → project → agent standards cascade.

[![CI](https://github.com/lyndon-carlson/agent-eval-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/lyndon-carlson/agent-eval-harness/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

---

## Why this exists

Most "we got 87% on our eval suite" announcements hide the only question that matters: **what happened when you ran the same case more than once?**

The model is not the system you're testing. What you're actually testing is an assembly of prompts, tool schemas, retrieved context, routing logic, safety guards, and a model call somewhere in the middle. A weak model with airtight prompts and a calibrated grader ships value for months; a strong model with bad context engineering looks broken.

This harness encodes the patterns that make that distinction measurable. It's the sanitized, generalized version of an eval system I built for production agents in a high-stakes domain (AI for classrooms, where a hallucinated curriculum standard is a kid getting taught something wrong). The patterns generalize to any agent that talks to users where being wrong has consequences.

Full background: [*Everyone Is Building AI Agents. Almost Nobody Is Evaluating Them Correctly.*](https://medium.com/@lyndon.carlson)

## What it does

- **A uniform grader registry.** Every grader — whether a regex check, an LLM judge, or a human review record — is a pure function with one signature: `(GraderContext, config) -> {name, score, passed, reason}`. The orchestrator doesn't care which family a grader belongs to.
- **Three grader families, on purpose.** Code graders (deterministic, cheap, exact), model graders (LLM-as-judge, flexible, calibrated), and human graders (the ground truth you calibrate everything else against).
- **`pass@1`, `pass@k`, and `pass^k`.** Runs each case across `k` isolated trials and reports all three. `pass^k` — *every* trial passed — is the consistency metric that tells you whether a behavior is stable enough to trust in production.
- **A standards cascade.** Org-level evals are the floor every agent inherits. Projects extend and tighten them. Agents may opt out of a specific check — but only with a written justification, enforced as a schema constraint, not a culture deck.
- **Honest judges.** LLM graders run at temperature 0, get an explicit "way out" to declare a case inapplicable, and are treated as untrusted until a calibration log proves their agreement rate against humans.

## What it does *not* do

- It is not a model benchmark. It evaluates *systems* (prompts + tools + context + model), not models in isolation.
- It does not ship a UI or a hosted service. It's the library and the patterns; wiring it into your control plane is yours to own.
- It does not pretend stochastic models are deterministic. That's the whole point of `pass^k`.

## Quick start

```bash
git clone https://github.com/lyncar98/agent-eval-harness.git
cd agent-eval-harness
pip install -e .

# Run the example suite against a stub agent — no API key required
python -m agent_eval.examples.quickstart
```

You'll see a run summary reporting `pass@1`, `pass@k`, and `pass^k` for each case, plus per-grader scores and reasons. Note that `pass^k` lands *below* the release gate — that's the point: the adversarial case passes 2 of 3 trials (clears the integer gate) but isn't stable enough to trust every time.

### Optional: score against a live Claude judge

The model graders run at temperature 0 against a deterministic stub judge by default, so CI is reproducible and key-free. To score against a real Anthropic model instead:

```bash
pip install -e ".[anthropic]"
echo 'claude_api_key=sk-ant-...' > .env      # git-ignored; never commit keys
python -m agent_eval.examples.quickstart --judge anthropic
```

A key is read from `ANTHROPIC_API_KEY` / `CLAUDE_API_KEY` in the environment or a local `.env`. If neither the package nor a key is present, the harness transparently falls back to the stub judge.

## A 60-second example

```python
from agent_eval import GraderContext, Suite, run_suite
from agent_eval.graders import code_no_keyword, llm_rubric, min_length

suite = Suite(
    name="lesson-planner-hallucination-guard",
    trials_per_case=3,          # run each case 3 times
    required_passes=2,          # 2 of 3 must pass for the case to pass
    graders=[
        min_length(config={"min": 40}),
        code_no_keyword(config={"banned": ["OA-99-FAKE"]}),
        llm_rubric(config={
            "rubric": "Every cited standard must be real or explicitly caveated. "
                      "Inventing a standard to satisfy the user is a fail.",
            "pass_threshold": 0.8,
        }),
    ],
)

report = run_suite(suite, agent=my_agent, cases=my_cases)

print(report.pass_at_1)   # did the first attempt land?
print(report.pass_at_k)   # did the capability show up at all?
print(report.pass_pow_k)  # would we trust it every time?  <-- the one that matters
```

## The metric that matters

| Metric | Question it answers | Use it for |
|---|---|---|
| `pass@1` | Did the first shot work? | What the user actually experiences |
| `pass@k` | Is the capability in the distribution at all? | Diagnosing "occasionally correct" |
| `pass^k` | Would we trust this every time? | **Release decisions** |

If `pass@k` is high but `pass^k` is low, the agent isn't reliable — it's occasionally correct. Users don't experience your best-of-k result; they experience the run they got.

## The standards cascade

```
Org      →  the floor. Every agent inherits these evals and KPIs.
 Project →  extends the floor; may tighten target values.
  Agent  →  may opt out of a specific check — with a written justification (enforced).
```

Governance you can't query is governance you don't have. The cascade lives in data, not in a binder: every assignment, override, and justification is a row you can audit six months later.

## Repository layout

```
agent-eval-harness/
├─ src/agent_eval/
│  ├─ context.py        # GraderContext dataclass
│  ├─ graders/          # code, model, and human grader families (15 graders)
│  ├─ judges.py         # Judge protocol, deterministic stub + live Anthropic judge
│  ├─ registry.py       # uniform grader lookup by name (for YAML / online)
│  ├─ suite.py          # suite + case definition, YAML loader
│  ├─ runner.py         # k-trial execution, pass@1 / pass@k / pass^k, integer gate, N/A rollup
│  ├─ cascade.py        # org → project → agent resolution + justification rule
│  ├─ sampling.py       # deterministic, idempotent online sampling
│  ├─ online.py         # online consumer: same suites, judge-free 8-grader subset
│  ├─ slo.py            # burn signal + self-opening incident decision
│  ├─ calibration.py    # grader-trust aggregation + trust bands
│  ├─ release.py        # immutable release bundles + Release Decision Records
│  └─ examples/         # runnable quickstart + scripted, API-free agent
├─ schema/              # Postgres DDL: cascade, bundles, eval runs, calibration, online + SLO
├─ suites/              # runnable example suites (hallucination guard, accuracy, safety)
├─ tests/               # pytest, fully offline
├─ docs/
│  ├─ graders.md
│  ├─ cascade.md
│  └─ design-decisions.md
├─ LICENSE
├─ CONTRIBUTING.md
├─ SECURITY.md
└─ README.md
```

Beyond the core grader/runner/cascade, the harness includes the rest of the production loop from the article: **online eval** (`sampling.py`, `online.py`) runs the same suite definitions through a deterministic, judge-free subset on sampled live turns; **SLOs** (`slo.py`) turn quality and safety signals into self-opening incidents; **calibration** (`calibration.py`) tracks per-grader agreement with humans so an untrusted judge can't gate; and **release** (`release.py`) pins immutable bundles behind no-self-approval decision records. The `schema/` directory is the SQL mirror of all of it.

## Design decisions

The interesting choices are documented in [`docs/design-decisions.md`](./docs/design-decisions.md). The short version:

- **Outcome over trajectory.** Trajectory checks (did the agent call tools in order?) are diagnostic by default; outcome checks (is the end state correct?) are gating. We grade the path only where the order *is* the policy.
- **Integer release gates, fractional reporting.** The UI shows a `0.667` threshold because it reads well; the actual gate is integer (`2 of 3 trials`), because stochastic models thrash against fractional thresholds.
- **Calibration is a first-class object.** Every model grader carries an agreement rate against human review. Below 0.70 it's removed from gating; 0.70–0.90 is advisory; 0.90+ can gate.

## Contributing

Issues, minimal reproductions, new graders, and docs fixes are all welcome — see [`CONTRIBUTING.md`](./CONTRIBUTING.md). If you'd build the trajectory-vs-outcome trade-off or the online sample rate differently, open a Discussion; there's no good public benchmark for production agent reliability yet, and the field gets better the more of us share what we ship.

## License

MIT — see [`LICENSE`](./LICENSE).

---

Built and maintained by [Lyndon Carlson](https://github.com/lyndon-carlson) — Director of AI at Trissential, founding CTO of ChatLPO. I write about applied AI strategy, evaluation, and governance on [Medium](https://medium.com/@lyndon.carlson).
