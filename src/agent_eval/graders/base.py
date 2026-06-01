"""Grader primitive + registry.

Every grader — code, model, or human-derived — is a configured callable with one
shape::

    grader(ctx: GraderContext) -> {"name", "family", "score", "passed", "reason"}

Graders are produced by *factory functions* (``min_length(config=...)``) so a
suite can carry pre-configured graders directly, and the same factory name can
be looked up from YAML. The orchestrator never branches on the grader family.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..context import GraderContext

RunFn = Callable[[GraderContext], dict]


@dataclass
class Grader:
    """A configured, callable grader."""

    name: str
    family: str                       # code | model | human
    run: RunFn
    config: dict = field(default_factory=dict)
    online_safe: bool = False
    gating: bool = True

    def __call__(self, ctx: GraderContext) -> dict:
        verdict = self.run(ctx)
        verdict.setdefault("name", self.name)
        verdict.setdefault("family", self.family)
        verdict["gating"] = self.gating
        return verdict


def result(name: str, family: str, score: float, passed: bool, reason: str) -> dict:
    return {
        "name": name,
        "family": family,
        "score": round(float(score), 4),
        "passed": bool(passed),
        "reason": reason,
    }


# name -> factory(config) -> Grader
GRADER_FACTORIES: dict[str, Callable[..., Grader]] = {}
GRADER_FAMILY: dict[str, str] = {}
# Subset runnable on a bare chat-turn payload (no expected_* fields, no judge).
ONLINE_SAFE: set[str] = set()


def register(name: str, family: str, *, online_safe: bool = False):
    """Register a grader factory under ``name``."""

    def deco(factory: Callable[..., Grader]) -> Callable[..., Grader]:
        GRADER_FACTORIES[name] = factory
        GRADER_FAMILY[name] = family
        if online_safe:
            ONLINE_SAFE.add(name)
        factory.grader_name = name        # type: ignore[attr-defined]
        factory.grader_family = family    # type: ignore[attr-defined]
        return factory

    return deco
