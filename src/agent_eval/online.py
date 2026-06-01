"""Online-eval consumer: the same suite, a judge-free deterministic subset.

The offline runner has the full grader registry. Live turns have no
``expected_output`` / ``reference_solution`` and we will not bill every prod
turn through an LLM judge, so the online consumer runs only the ``online_safe``
subset and SKIPS the rest. Same suite rows; cheaper, judge-free slice.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .context import GraderContext
from .graders.base import ONLINE_SAFE
from .suite import Suite


@dataclass
class OnlineResult:
    request_id: str
    sampled: bool
    bundle_id: str | None
    scored: list[dict] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    passed: bool = True


def run_online_checks(suite: Suite, payload: dict, *, bundle_id: str | None = None) -> OnlineResult:
    """Score a sampled ``chat_turn_completed`` payload against online-safe graders.

    Resolve ``bundle_id`` from the deployment in 'stable'/'rolling_out' state so
    each sample is attributed to the bundle that produced it.
    """
    ctx = GraderContext(
        query=payload.get("query", ""),
        response=payload.get("response", ""),
        tool_calls=payload.get("tool_calls", []),
        transcript=payload.get("transcript", []),
        latency_ms=payload.get("latency_ms", 0),
    )

    scored: list[dict] = []
    skipped: list[str] = []
    passed = True
    # Live turns have no case, so we use the suite-level graders only.
    for grader in suite.graders:
        if grader.name not in ONLINE_SAFE:
            skipped.append(grader.name)
            continue
        verdict = grader(ctx)
        scored.append(verdict)
        if grader.gating and not verdict["passed"]:
            passed = False

    return OnlineResult(
        request_id=payload.get("request_id", ""),
        sampled=True,
        bundle_id=bundle_id,
        scored=scored,
        skipped=skipped,
        passed=passed,
    )
