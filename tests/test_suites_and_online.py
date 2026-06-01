import pathlib

from agent_eval import load_suite, run_online_checks

SUITES = pathlib.Path(__file__).resolve().parents[1] / "suites"


def test_load_hallucination_suite():
    suite = load_suite(SUITES / "hallucination_guard_lesson_planner.yaml")
    assert suite.trials_per_case == 3
    assert suite.required_passes == 2
    assert suite.display_threshold == 0.6667
    assert {c.case_type for c in suite.cases} == {"typical", "adversarial", "edge"}


def test_online_skips_non_online_safe_graders():
    suite = load_suite(SUITES / "hallucination_guard_lesson_planner.yaml")
    res = run_online_checks(suite, {
        "request_id": "r1", "query": "q",
        "response": "Un plan de clase suficientemente largo para pasar min_length.",
    })
    assert "llm_rubric" in res.skipped
    assert any(v["name"] == "min_length" for v in res.scored)


def test_online_safety_suite_runs_deterministic_checks():
    suite = load_suite(SUITES / "safety_baseline.yaml")
    res = run_online_checks(suite, {
        "request_id": "r2", "query": "q",
        "response": "Respuesta útil y suficientemente larga para el chequeo.",
    })
    assert res.skipped == []     # all suite-level graders are online-safe
    assert res.passed is True


def test_quickstart_runs_and_shows_passk_below_gate():
    from agent_eval.examples.quickstart import CASES, build_suite
    from agent_eval.examples.agents import HALLUCINATION_SCRIPT, ScriptedAgent
    from agent_eval import run_suite

    report = run_suite(build_suite("stub"), ScriptedAgent(HALLUCINATION_SCRIPT), CASES)
    assert report.approved is True
    assert report.pass_pow_k < report.gate_pass_rate  # the whole point
