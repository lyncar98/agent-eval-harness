import pytest

from agent_eval import AgentOverride, Assignment, JustificationRequired, resolve


def test_org_floor_inherited():
    eff = {e.slug: e for e in resolve(
        org=[Assignment("pii_redaction"), Assignment("safety_baseline")],
    )}
    assert set(eff) == {"pii_redaction", "safety_baseline"}
    assert eff["pii_redaction"].source == "org"


def test_project_tightens_target_lower_is_better():
    eff = {e.slug: e for e in resolve(
        org=[Assignment("cost_per_turn_usd", target_value=0.03)],
        project=[Assignment("cost_per_turn_usd", target_value=0.015)],
        comparison={"cost_per_turn_usd": "lte"},
    )}
    assert eff["cost_per_turn_usd"].target_value == 0.015
    assert eff["cost_per_turn_usd"].source == "project"


def test_agent_optout_requires_justification():
    with pytest.raises(JustificationRequired):
        resolve(
            org=[Assignment("ttft_ms")],
            agent=[AgentOverride("ttft_ms", is_enabled=False, justification="too short")],
        )


def test_agent_optout_with_justification_removes_standard():
    eff = {e.slug: e for e in resolve(
        org=[Assignment("ttft_ms"), Assignment("success_rate")],
        agent=[AgentOverride(
            "ttft_ms", is_enabled=False,
            justification="Async drafting workflow; first-token latency is not a UX metric.",
        )],
    )}
    assert "ttft_ms" not in eff
    assert "success_rate" in eff
