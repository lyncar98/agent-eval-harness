"""Uniform grader lookup by name.

Lets YAML suites (and the online consumer) instantiate graders by string name
with a config dict, sharing the exact same factories used in Python.
"""

from __future__ import annotations

from . import graders as _graders  # noqa: F401  (ensures factories are registered)
from .graders.base import GRADER_FACTORIES, GRADER_FAMILY, ONLINE_SAFE, Grader

__all__ = ["make_grader", "GRADER_FACTORIES", "GRADER_FAMILY", "ONLINE_SAFE"]


def make_grader(name: str, config: dict | None = None, *, gating: bool = True) -> Grader:
    """Instantiate a registered grader by name. Raises KeyError if unknown."""
    if name not in GRADER_FACTORIES:
        raise KeyError(f"unknown grader '{name}'. Known: {sorted(GRADER_FACTORIES)}")
    grader = GRADER_FACTORIES[name](config=config or {})
    grader.gating = gating
    return grader
