"""Grader trust: treat every model grader as untrusted until calibrated.

Humans review trials and mark them pass/fail; we log agreement PER GRADER (not
per trial), so a disagreement is attributed to the rubric judge that was wrong,
not the regex that was fine. Agreement rate is the trust score, and trust gates
whether a model grader may gate.
"""

from __future__ import annotations

from dataclasses import dataclass

NEEDS_RECALIBRATION = 0.70
TRUSTED = 0.90


@dataclass
class CalibrationRecord:
    grader_name: str
    grader_kind: str          # code | model | human
    grader_passed: bool
    human_passed: bool

    @property
    def agrees(self) -> bool:
        return self.grader_passed == self.human_passed


@dataclass
class GraderTrust:
    grader_name: str
    grader_kind: str
    reviews_total: int
    reviews_agreed: int
    agreement_rate: float
    trust_band: str
    may_gate: bool


def trust_band(agreement_rate: float | None) -> str:
    if agreement_rate is None:
        return "unreviewed"
    if agreement_rate < NEEDS_RECALIBRATION:
        return "needs_recalibration"
    if agreement_rate < TRUSTED:
        return "watch"
    return "trusted"


def compute_trust(records: list[CalibrationRecord]) -> list[GraderTrust]:
    """Aggregate per-grader trust, least-trusted first.

    Code graders are deterministic and always allowed to gate; only model
    graders must earn (and can lose) gating rights through agreement.
    """
    by_grader: dict[str, list[CalibrationRecord]] = {}
    for r in records:
        by_grader.setdefault(r.grader_name, []).append(r)

    out: list[GraderTrust] = []
    for name, rs in by_grader.items():
        total = len(rs)
        agreed = sum(1 for r in rs if r.agrees)
        rate = agreed / total if total else None
        kind = rs[0].grader_kind
        may_gate = kind == "code" or (rate is not None and rate >= TRUSTED)
        out.append(GraderTrust(
            grader_name=name,
            grader_kind=kind,
            reviews_total=total,
            reviews_agreed=agreed,
            agreement_rate=round(rate, 4) if rate is not None else 0.0,
            trust_band=trust_band(rate),
            may_gate=may_gate,
        ))

    out.sort(key=lambda g: g.agreement_rate)
    return out
