"""SLO evaluation and self-opening incidents.

Honest naming: ``burn_rate`` computes the normalized distance from target inside
the current window — a budget-overshoot ratio, not a Google-SRE multi-window
multi-burn-rate (MWMBR) signal. It catches sustained breaches well; it
under-reacts to short spikes and over-reacts on tiny denominators in low-traffic
windows. ``window_minutes`` is in the schema, so adding a second window is
additive, not a redesign.
"""

from __future__ import annotations

from dataclasses import dataclass


def burn_rate(observed: float, target: float, comparison: str) -> float:
    """How far over budget we are. 0.0 == on or beating target."""
    if comparison == "gte":
        if observed >= target:
            return 0.0
        denom = (1.0 - target) or 1e-9
        return max(0.0, (target - observed) / denom)
    if observed <= target:
        return 0.0
    denom = target or 1e-9
    return max(0.0, (observed - target) / denom)


@dataclass
class SLO:
    name: str
    metric: str
    target: float
    comparison: str               # 'gte' | 'lte'
    burn_alert_threshold: float
    window_minutes: int = 60
    category: str | None = None


@dataclass
class IncidentDecision:
    should_open: bool
    severity: str | None
    category: str | None
    title: str | None
    detail: str | None
    burn: float


_METRIC_CATEGORY = {
    "ttft_ms": "performance",
    "time_to_response_p95": "performance",
    "success_rate": "reliability",
    "cost_per_turn_usd": "cost",
    "safety_violation_rate": "safety",
    "pii_leak_rate": "safety",
}


def category_for_metric(metric: str) -> str:
    return _METRIC_CATEGORY.get(metric, "quality")


def evaluate_slo(slo: SLO, observed: float, *, has_open_incident: bool = False) -> IncidentDecision:
    """Compute burn and decide whether to open an incident (with duplicate guard)."""
    burn = burn_rate(observed, slo.target, slo.comparison)
    if burn < slo.burn_alert_threshold or has_open_incident:
        return IncidentDecision(False, None, None, None, None, round(burn, 4))

    severity = "high" if burn >= slo.burn_alert_threshold * 2 else "medium"
    category = slo.category or category_for_metric(slo.metric)
    detail = (
        f"metric={slo.metric} observed={observed:.4f} target={slo.target} "
        f"burn={burn:.2f} (threshold {slo.burn_alert_threshold})"
    )
    return IncidentDecision(True, severity, category, f"SLO burn: {slo.name}", detail, round(burn, 4))
