"""The single object every grader receives.

Live production turns only populate ``query``, ``response``, ``tool_calls``,
``transcript``, and ``latency_ms``. The ``expected_*`` and ``reference_solution``
fields exist only for offline cases — which is exactly why expectation-based and
judge-based graders cannot run on a live turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GraderContext:
    query: str
    response: str
    expected_output: str | None = None
    expected_tool_calls: list[dict] | None = None
    reference_solution: str | None = None      # prove the task is solvable
    expected_state: dict | None = None          # outcome, not transcript
    tool_calls: list[dict] = field(default_factory=list)
    transcript: list[dict] = field(default_factory=list)
    latency_ms: int = 0
    judge_provider: str | None = None
    judge_model: str | None = None
