"""Suite + case definition and YAML loader.

A suite carries its grading contract and a list of configured graders that apply
to every case (a case may override a grader of the same name). The *same* suite
drives the offline runner and the online sampler.

Gate field: ``required_passes``. The UI may display a fractional threshold
(0.667) because it reads well, but the release decision is integer:
``item_passed = n_passed >= required_passes``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .graders.base import Grader
from .registry import make_grader


@dataclass
class Case:
    id: str
    query: str
    case_type: str = "typical"            # typical | adversarial | edge
    expected_output: str | None = None
    reference_solution: str | None = None
    expected_state: dict | None = None
    expected_tool_calls: list[dict] | None = None
    checks: list[Grader] = field(default_factory=list)  # per-case overrides


@dataclass
class Suite:
    name: str
    trials_per_case: int = 3
    required_passes: int = 2
    graders: list[Grader] = field(default_factory=list)
    cases: list[Case] = field(default_factory=list)
    judge_provider: str | None = None
    judge_model: str | None = None

    @property
    def display_threshold(self) -> float:
        return round(self.required_passes / self.trials_per_case, 4)

    def graders_for(self, case: Case) -> list[Grader]:
        """Case-level graders override suite-level ones of the same name."""
        merged: dict[str, Grader] = {g.name: g for g in self.graders}
        for g in case.checks:
            merged[g.name] = g
        return list(merged.values())


def _parse_graders(raw: list | None) -> list[Grader]:
    out: list[Grader] = []
    for item in raw or []:
        if isinstance(item, str):
            out.append(make_grader(item))
            continue
        out.append(make_grader(
            item["name"],
            config=item.get("config", {}) or {},
            gating=item.get("gating", True),
        ))
    return out


def load_suite(path: str | Path) -> Suite:
    """Load a suite from YAML. Accepts ``graders`` or ``checks`` for the list,
    and ``required_passes`` or a fractional ``pass_threshold``."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    trials = int(data.get("trials_per_case", 3))

    if "required_passes" in data:
        required = int(data["required_passes"])
    else:
        threshold = float(data.get("pass_threshold", 0.667))
        required = max(1, math.ceil(threshold * trials))

    grader_spec = data.get("graders", data.get("checks"))

    cases = [
        Case(
            id=c["id"],
            query=c["query"],
            case_type=c.get("case_type", "typical"),
            expected_output=c.get("expected_output"),
            reference_solution=c.get("reference_solution"),
            expected_state=c.get("expected_state"),
            expected_tool_calls=c.get("expected_tool_calls"),
            checks=_parse_graders(c.get("checks", c.get("graders"))),
        )
        for c in data.get("cases", [])
    ]

    return Suite(
        name=data.get("name", data.get("slug", "suite")),
        trials_per_case=trials,
        required_passes=required,
        graders=_parse_graders(grader_spec),
        cases=cases,
        judge_provider=data.get("judge_provider"),
        judge_model=data.get("judge_model"),
    )
