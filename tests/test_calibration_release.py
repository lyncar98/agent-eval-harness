import dataclasses

import pytest

from agent_eval import (
    Approval,
    CalibrationRecord,
    ReleaseBundle,
    ReleaseDecisionRecord,
    SelfApprovalError,
    compute_trust,
    trust_band,
)


def test_trust_bands():
    assert trust_band(None) == "unreviewed"
    assert trust_band(0.5) == "needs_recalibration"
    assert trust_band(0.8) == "watch"
    assert trust_band(0.95) == "trusted"


def test_model_grader_loses_gating_below_threshold():
    records = [
        CalibrationRecord("llm_rubric", "model", True, False),
        CalibrationRecord("llm_rubric", "model", True, True),
        CalibrationRecord("regex_match", "code", True, True),
    ]
    trust = {t.grader_name: t for t in compute_trust(records)}
    assert trust["llm_rubric"].agreement_rate == 0.5
    assert trust["llm_rubric"].may_gate is False
    assert trust["regex_match"].may_gate is True  # code may always gate


def test_bundle_immutable_and_no_self_approval():
    b = ReleaseBundle(agent_id="a", bundle_tag="lp-v1.0.0",
                      provider="anthropic", model="claude-3-5-haiku-latest")
    with pytest.raises(dataclasses.FrozenInstanceError):
        b.model = "claude-3-5-sonnet-latest"  # type: ignore[misc]

    rdr = ReleaseDecisionRecord(bundle_id=b.id, proposed_by="alice")
    with pytest.raises(SelfApprovalError):
        rdr.add_approval(Approval(actor="alice", role="eng", decision="approve"))
    rdr.add_approval(Approval(actor="bob", role="curriculum", decision="approve"))
    assert rdr.is_approved is True
