"""Suite runner: isolated trials, three pass metrics, integer gate, N/A rollup.

For each case we run ``k`` isolated trials (a fresh session per trial so memory
or tool state from one attempt cannot contaminate the next), grade every trial
with the suite's gating graders, then report three metrics over applicable cases:

  pass@1   - did the FIRST trial pass?     (what users actually experience)
  pass@k   - did ANY trial pass?           (capability somewhere in the dist.)
  pass^k   - did EVERY trial pass?         (consistency / the trust metric)

The release gate is separate and integer-based::

    item_passed = n_passed >= suite.required_passes

N/A is not a free pass: graders whose reason marks them N/A are excluded at the
rollup layer. A case with no applicable gating verdict drops from the
denominator, and if too few cases remain the run fails as "insufficient
applicable cases" rather than quietly approving.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol

from .context import GraderContext
from .suite import Case, Suite

MIN_APPLICABLE_FRACTION = 0.6


def is_na(verdict: dict) -> bool:
    return str(verdict.get("reason", "")).strip().lower().startswith("n/a")


class AgentSession(Protocol):
    def run(self, case: Case) -> dict: ...


class Agent(Protocol):
    def create_session(self) -> AgentSession: ...


@dataclass
class TrialResult:
    trial_idx: int
    passed: bool
    response: str
    grader_results: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    transcript: list[dict] = field(default_factory=list)
    latency_ms: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    error: str | None = None
    applicable: bool = True


@dataclass
class RunItem:
    case_id: str
    case_type: str
    applicable: bool
    n_passed: int
    required: int
    item_passed: bool
    trials: list[TrialResult]


@dataclass
class RunReport:
    suite_name: str
    total_cases: int
    applicable_cases: int
    pass_at_1: float
    pass_at_k: float
    pass_pow_k: float
    gate_pass_rate: float
    approved: bool
    reason: str
    items: list[RunItem]


def _grade_trial(suite: Suite, case: Case, trial_idx: int, output: dict) -> TrialResult:
    ctx = GraderContext(
        query=case.query,
        response=output.get("response", ""),
        expected_output=case.expected_output,
        expected_tool_calls=case.expected_tool_calls,
        reference_solution=case.reference_solution,
        expected_state=case.expected_state,
        tool_calls=output.get("tool_calls", []),
        transcript=output.get("transcript", []),
        latency_ms=output.get("latency_ms", 0),
        judge_provider=suite.judge_provider,
        judge_model=suite.judge_model,
    )

    gating_passed = True
    had_applicable = False
    results: list[dict] = []
    for grader in suite.graders_for(case):
        if grader.name == "state_check":
            grader.config["produced_state"] = output.get("state", {})
        verdict = grader(ctx)
        results.append(verdict)
        if grader.gating and not is_na(verdict):
            had_applicable = True
            gating_passed = gating_passed and verdict["passed"]

    return TrialResult(
        trial_idx=trial_idx,
        passed=gating_passed and had_applicable,
        response=ctx.response,
        grader_results=results,
        tool_calls=ctx.tool_calls,
        transcript=ctx.transcript,
        latency_ms=output.get("latency_ms", 0),
        tokens=output.get("tokens", 0),
        cost_usd=output.get("cost_usd", 0.0),
        error=output.get("error"),
        applicable=had_applicable,
    )


def run_suite(suite: Suite, agent: Agent, cases: list[Case] | None = None) -> RunReport:
    """Run every case ``k`` times, score, and decide whether to approve.

    ``cases`` defaults to ``suite.cases``; pass an explicit list to reuse one
    suite definition across different case sets.
    """
    cases = cases if cases is not None else suite.cases
    k = suite.trials_per_case
    required = suite.required_passes

    items: list[RunItem] = []
    pass_at_1 = pass_at_k = pass_pow_k = gate_passes = applicable_cases = 0

    for case in cases:
        trials: list[TrialResult] = []
        for trial_idx in range(k):
            session = agent.create_session()  # isolation per trial
            start = time.perf_counter()
            output = session.run(case)
            output.setdefault("latency_ms", int((time.perf_counter() - start) * 1000))
            trials.append(_grade_trial(suite, case, trial_idx, output))

        case_applicable = any(t.applicable for t in trials)
        n_passed = sum(1 for t in trials if t.passed)
        item_passed = case_applicable and n_passed >= required

        if case_applicable:
            applicable_cases += 1
            if trials[0].passed:
                pass_at_1 += 1
            if any(t.passed for t in trials):
                pass_at_k += 1
            if all(t.passed for t in trials):
                pass_pow_k += 1
            if item_passed:
                gate_passes += 1

        items.append(RunItem(
            case_id=case.id, case_type=case.case_type, applicable=case_applicable,
            n_passed=n_passed, required=required, item_passed=item_passed, trials=trials,
        ))

    total = len(cases)
    denom = applicable_cases or 1
    enough = applicable_cases > 0 and applicable_cases >= MIN_APPLICABLE_FRACTION * max(total, 1)

    if not enough:
        approved, reason = False, (
            f"insufficient applicable cases: {applicable_cases}/{total} "
            f"(min fraction {MIN_APPLICABLE_FRACTION})"
        )
    else:
        approved = gate_passes == applicable_cases
        reason = ("all applicable cases met the gate" if approved
                  else f"{applicable_cases - gate_passes} applicable case(s) failed the gate")

    return RunReport(
        suite_name=suite.name,
        total_cases=total,
        applicable_cases=applicable_cases,
        pass_at_1=round(pass_at_1 / denom, 4),
        pass_at_k=round(pass_at_k / denom, 4),
        pass_pow_k=round(pass_pow_k / denom, 4),
        gate_pass_rate=round(gate_passes / denom, 4),
        approved=approved,
        reason=reason,
        items=items,
    )
