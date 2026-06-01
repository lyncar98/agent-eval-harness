from agent_eval import SLO, burn_rate, evaluate_slo, sampled_fraction, should_sample


def test_sampling_edges_and_replay():
    assert should_sample("x", 0.0) is False
    assert should_sample("x", 1.0) is True
    assert len({should_sample("req-42", 0.05) for _ in range(500)}) == 1


def test_sampled_fraction_close_to_rate():
    ids = [f"req-{i:07d}" for i in range(50_000)]
    assert abs(sampled_fraction(ids, 0.05) - 0.05) < 0.005


def test_burn_zero_when_beating_target():
    assert burn_rate(0.99, 0.98, "gte") == 0.0
    assert burn_rate(3000, 4000, "lte") == 0.0


def test_incident_opens_with_severity_and_duplicate_guard():
    slo = SLO(name="safety", metric="safety_violation_rate", target=0.005,
              comparison="lte", burn_alert_threshold=1.0)
    d = evaluate_slo(slo, observed=0.02)
    assert d.should_open is True and d.severity == "high" and d.category == "safety"
    assert evaluate_slo(slo, 0.02, has_open_incident=True).should_open is False
