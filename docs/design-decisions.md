# Design decisions

The short version of the choices that matter.

## pass@1 / pass@k / pass^k

Running a case once tells you nothing about consistency. We run `k` **isolated**
trials per case (fresh session each, so state can't leak between attempts) and
report all three:

| Metric | Question | Use it for |
|---|---|---|
| `pass@1` | did the first shot work? | what the user actually experiences |
| `pass@k` | is the capability in the distribution at all? | diagnosing "occasionally correct" |
| `pass^k` | would we trust it every time? | **release decisions** |

If `pass@k` is high but `pass^k` is low, the agent isn't reliable — it's
occasionally correct.

## Integer release gates, fractional reporting

The UI shows a `0.667` threshold because it reads well. The actual gate is
integer: `item_passed = n_passed >= required_passes` (e.g. 2 of 3). Stochastic
models thrash against fractional thresholds; integers are honest about what the
gate means.

## N/A is not a free pass

LLM judges get an explicit "way out": *if the rubric doesn't apply, pass and say
so.* That keeps a single weird case from crashing a run. But the gating decision
is made one layer up, in the runner, where an N/A verdict is **excluded from the
denominator**. A case with no applicable gating verdict is dropped; if too few
applicable cases remain (`MIN_APPLICABLE_FRACTION`), the whole run fails as
*"insufficient applicable cases"* instead of quietly approving. So a rubric that
N/As 40% of cases shows up loudly, not silently.

## Calibration is a first-class object

Every model grader carries an agreement rate against human review, logged **per
grader** so disagreement is attributed to the rubric judge, not the regex that
was fine. Bands: `< 0.70` removed from gating; `0.70–0.90` advisory; `0.90+` may
gate. Code graders may always gate.

## Online eval: deterministic, idempotent, judge-free

Sampling is a pure function of `request_id` (SHA-256 bucket), so stream replays
sample identically and — with `ON CONFLICT (request_id) DO NOTHING` — the
pipeline is idempotent. The online consumer runs only the 8 `online_safe`
graders (no judge cost, no per-case expected fields) and skips the rest, driven
by the *same* suite definition as the offline run.

## Immutable bundles

A release bundle is a frozen identity. A new prompt revision, model upgrade, or
tool-schema hash is a **new bundle**, never a mutation — the only way to get a
stable diff between releases and trace a regression to what changed. A Release
Decision Record records the approval chain and forbids self-approval.

## `burn_rate` is honestly named in prose, not in the symbol

It computes the normalized distance from target inside one window — a
budget-overshoot ratio, not Google-SRE MWMBR. It catches sustained breaches
well; it under-reacts to short spikes and over-reacts on tiny low-traffic
denominators. `window_minutes` is already in the schema, so a second window is
an additive change.
