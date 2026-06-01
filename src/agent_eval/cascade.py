"""The standards cascade: org -> project -> agent.

The governance contract is three sentences, and the third is enforced, not
suggested:

  1. Org-level assignments are the FLOOR; every agent inherits them.
  2. Project-level assignments EXTEND the floor and may TIGHTEN target values.
  3. An agent may OPT OUT of a specific assignment only with a written
     justification of at least :data:`MIN_JUSTIFICATION_CHARS` characters.

This is the in-memory mirror of the SQL cascade in ``schema/``. ``resolve_*``
returns the effective set an agent must satisfy, raising
:class:`JustificationRequired` if an opt-out lacks a justification.
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_JUSTIFICATION_CHARS = 10


class JustificationRequired(ValueError):
    """Raised when an agent opt-out has no (sufficient) justification."""


@dataclass
class Assignment:
    """An org/project assignment of a KPI or eval, with an optional target."""

    slug: str
    is_required: bool = True
    target_value: float | None = None


@dataclass
class AgentOverride:
    """An agent-level override. ``is_enabled=False`` is an opt-out."""

    slug: str
    is_enabled: bool = True
    target_value: float | None = None
    justification: str | None = None
    approved_by: str | None = None

    def validate(self) -> None:
        if not self.is_enabled:
            text = (self.justification or "").strip()
            if len(text) < MIN_JUSTIFICATION_CHARS:
                raise JustificationRequired(
                    f"opt-out of '{self.slug}' needs a justification of >= "
                    f"{MIN_JUSTIFICATION_CHARS} characters (got {len(text)})"
                )


@dataclass
class EffectiveStandard:
    slug: str
    is_required: bool
    target_value: float | None
    source: str            # 'org' | 'project' | 'agent'


def _tighter(comparison: str, a: float | None, b: float | None) -> float | None:
    """Return the more demanding of two targets. ``a`` (more specific) wins ties."""
    if a is None:
        return b
    if b is None:
        return a
    if comparison == "gte":      # higher is better -> tighter = larger
        return max(a, b)
    return min(a, b)             # lower is better -> tighter = smaller


def resolve(
    org: list[Assignment],
    project: list[Assignment] | None = None,
    agent: list[AgentOverride] | None = None,
    *,
    comparison: dict[str, str] | None = None,
) -> list[EffectiveStandard]:
    """Resolve the cascade into the effective standards for one agent.

    ``comparison`` maps a slug to 'gte'/'lte' so target tightening picks the
    correct direction; defaults to 'lte' (lower-is-better) when unspecified.
    """
    project = project or []
    agent = agent or []
    comparison = comparison or {}

    effective: dict[str, EffectiveStandard] = {}
    for a in org:
        effective[a.slug] = EffectiveStandard(a.slug, a.is_required, a.target_value, "org")

    for a in project:
        comp = comparison.get(a.slug, "lte")
        if a.slug in effective:
            cur = effective[a.slug]
            effective[a.slug] = EffectiveStandard(
                a.slug,
                cur.is_required or a.is_required,
                _tighter(comp, a.target_value, cur.target_value),
                "project" if a.target_value is not None else cur.source,
            )
        else:
            effective[a.slug] = EffectiveStandard(a.slug, a.is_required, a.target_value, "project")

    for o in agent:
        o.validate()
        if not o.is_enabled:
            effective.pop(o.slug, None)
            continue
        comp = comparison.get(o.slug, "lte")
        cur = effective.get(o.slug)
        base_required = cur.is_required if cur else True
        base_target = cur.target_value if cur else None
        effective[o.slug] = EffectiveStandard(
            o.slug,
            base_required,
            _tighter(comp, o.target_value, base_target),
            "agent" if o.target_value is not None else (cur.source if cur else "agent"),
        )

    return sorted(effective.values(), key=lambda e: e.slug)
