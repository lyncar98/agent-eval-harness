from agent_eval import Case, Suite, make_grader, run_suite
from agent_eval.runner import MIN_APPLICABLE_FRACTION


class FlakyAgent:
    def __init__(self, script):
        self.script = script
        self.counts = {}

    def create_session(self):
        return self

    def run(self, case):
        seq = self.script[case.id]
        i = self.counts.get(case.id, 0)
        self.counts[case.id] = i + 1
        return {"response": seq[min(i, len(seq) - 1)]}


def make_suite(required_passes=2):
    return Suite(
        name="t",
        trials_per_case=3,
        required_passes=required_passes,
        graders=[make_grader("keyword", {"required": ["ok"]})],
        cases=[Case(id="stable", query="q"), Case(id="flaky", query="q")],
    )


def test_pass_metrics_differ_for_flaky_case():
    agent = FlakyAgent({"stable": ["ok a", "ok b", "ok c"],
                        "flaky":  ["ok yes", "nope", "ok yes"]})
    report = run_suite(make_suite(), agent)
    assert report.pass_at_1 == 1.0
    assert report.pass_at_k == 1.0
    assert report.pass_pow_k == 0.5    # only 'stable' is all-pass
    assert report.gate_pass_rate == 1.0
    assert report.approved is True


def test_strict_gate_fails_flaky_case():
    agent = FlakyAgent({"stable": ["ok a", "ok b", "ok c"],
                        "flaky":  ["ok yes", "nope", "ok yes"]})
    report = run_suite(make_suite(required_passes=3), agent)
    assert report.gate_pass_rate == 0.5
    assert report.approved is False


def test_na_only_suite_fails_as_insufficient_applicable():
    suite = Suite(
        name="na", trials_per_case=2, required_passes=1,
        graders=[make_grader("expected_output")],
        cases=[Case(id="a", query="q"), Case(id="b", query="q")],
    )

    class A:
        def create_session(self):
            return self

        def run(self, case):
            return {"response": "anything"}

    report = run_suite(suite, A())
    assert report.applicable_cases == 0
    assert report.approved is False
    assert "insufficient applicable" in report.reason
    assert MIN_APPLICABLE_FRACTION > 0
