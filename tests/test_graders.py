from agent_eval import GraderContext, make_grader
from agent_eval.graders.base import GRADER_FACTORIES, ONLINE_SAFE


def ctx(**kw) -> GraderContext:
    base = {"query": "q", "response": "r"}
    base.update(kw)
    return GraderContext(**base)


def test_registry_has_fifteen_graders():
    assert len(GRADER_FACTORIES) == 15


def test_online_safe_is_eight():
    assert ONLINE_SAFE == {
        "keyword", "tool_called", "min_length", "max_length",
        "no_refusal", "regex_match", "json_valid", "sentiment",
    }


def test_no_keyword_blocks_banned_tokens():
    g = make_grader("no_keyword", {"banned": ["secret"]})
    assert g(ctx(response="here is a SECRET token"))["passed"] is False
    assert g(ctx(response="clean text"))["passed"] is True


def test_min_length_accepts_min_or_min_chars():
    assert make_grader("min_length", {"min": 5})(ctx(response="abc"))["passed"] is False
    assert make_grader("min_length", {"min_chars": 2})(ctx(response="abc"))["passed"] is True


def test_regex_should_not_match_flips_semantics():
    g = make_grader("regex_match", {"pattern": r"OA-99", "should_match": False})
    assert g(ctx(response="OA 8 fracciones"))["passed"] is True
    assert g(ctx(response="usa el OA-99"))["passed"] is False


def test_json_valid_checks_keys():
    g = make_grader("json_valid", {"required_keys": ["score", "passed"]})
    assert g(ctx(response='{"score": 1.0, "passed": true}'))["passed"] is True
    assert g(ctx(response="{not json"))["passed"] is False


def test_expected_output_na_passes_through():
    r = make_grader("expected_output")(ctx(expected_output=None))
    assert r["passed"] is True and r["reason"].lower().startswith("n/a")


def test_tool_called_and_sequence():
    c = ctx(tool_calls=[{"name": "lookup"}, {"name": "finalize"}])
    assert make_grader("tool_called", {"tool": "lookup"})(c)["passed"] is True
    assert make_grader("tool_sequence", {"expected": ["lookup", "finalize"]})(c)["passed"] is True
    assert make_grader("tool_sequence", {"expected": ["finalize", "lookup"]})(c)["passed"] is False


def test_llm_rubric_uses_stub_judge():
    g = make_grader("llm_rubric", {"pass_threshold": 0.7, "rubric": "no fabrication"})
    bad = ctx(response="El OA-99 definitely aligns, plan listo.")
    assert g(bad)["passed"] is False
    good = ctx(response="No puedo confirmar el OA-99; uso el OA real.")
    assert g(good)["passed"] is True
