"""Model graders: LLM-as-judge. Untrusted until calibrated; must run at temp 0.

The rubric prompt gives the judge an explicit "way out": if the rubric does not
apply, return score=1.0, passed=true and say so. That N/A is a parser-level
default, not a free pass — the suite rollup detects N/A reasons and excludes
them from the denominator (see :mod:`agent_eval.runner`).
"""

from __future__ import annotations

import json

from ..context import GraderContext
from ..judges import get_judge, parse_verdict
from .base import Grader, register, result

_RUBRIC_PROMPT = """\
You are an impartial evaluator. Score the response against the rubric.

Rubric:
{rubric}

User query:
{query}
{reference_block}

Response to evaluate:
{response}

Reply with ONLY a JSON object on a single line:
{{"score": <0.0..1.0>, "passed": <true|false>, "reason": "<one-sentence justification>"}}

The "passed" field MUST be true iff score >= {pass_threshold}.
If the rubric does not apply, set score=1.0, passed=true, and explain in "reason".
"""


@register("llm_rubric", "model")
def llm_rubric(config: dict | None = None) -> Grader:
    """Score a response against a free-text rubric via a (pinned) judge."""
    cfg = dict(config or {})

    def _run(ctx: GraderContext) -> dict:
        threshold = float(cfg.get("pass_threshold", 0.7))
        reference_block = (
            f"\nReference solution (a known-good answer):\n{ctx.reference_solution}\n"
            if ctx.reference_solution else ""
        )
        prompt = _RUBRIC_PROMPT.format(
            rubric=cfg.get("rubric", ""),
            query=ctx.query,
            reference_block=reference_block,
            response=ctx.response,
            pass_threshold=threshold,
        )
        judge = get_judge(ctx.judge_provider, ctx.judge_model)
        v = parse_verdict(json.dumps(judge.score(prompt)), pass_threshold=threshold)
        return result("llm_rubric", "model", v["score"], v["passed"], v["reason"])

    return Grader("llm_rubric", "model", _run, cfg)


@register("llm_pairwise", "model")
def llm_pairwise(config: dict | None = None) -> Grader:
    """Compare the response against the reference; pass if as good or better."""
    cfg = dict(config or {})

    def _run(ctx: GraderContext) -> dict:
        if not ctx.reference_solution:
            return result("llm_pairwise", "model", 1.0, True, "N/A: no reference_solution")
        threshold = float(cfg.get("pass_threshold", 0.7))
        prompt = (
            "Compare candidate vs reference for the query. Score 1.0 if candidate "
            "is as good or better, lower otherwise.\n"
            f"Query:\n{ctx.query}\nReference:\n{ctx.reference_solution}\n"
            f"Candidate:\n{ctx.response}\n"
            f'Reply ONLY JSON: {{"score":<0..1>,"passed":<bool>,"reason":"..."}} '
            f"passed iff score >= {threshold}"
        )
        judge = get_judge(ctx.judge_provider, ctx.judge_model)
        v = parse_verdict(json.dumps(judge.score(prompt)), pass_threshold=threshold)
        return result("llm_pairwise", "model", v["score"], v["passed"], v["reason"])

    return Grader("llm_pairwise", "model", _run, cfg)


@register("groundedness", "model")
def groundedness(config: dict | None = None) -> Grader:
    """Judge whether claims are grounded in provided context."""
    cfg = dict(config or {})

    def _run(ctx: GraderContext) -> dict:
        threshold = float(cfg.get("pass_threshold", 0.7))
        prompt = (
            "Judge whether every claim in the response is supported by the context. "
            "Unsupported claims should lower the score.\n"
            f"Context:\n{cfg.get('context', '')}\nResponse:\n{ctx.response}\n"
            f'Reply ONLY JSON: {{"score":<0..1>,"passed":<bool>,"reason":"..."}} '
            f"passed iff score >= {threshold}"
        )
        judge = get_judge(ctx.judge_provider, ctx.judge_model)
        v = parse_verdict(json.dumps(judge.score(prompt)), pass_threshold=threshold)
        return result("groundedness", "model", v["score"], v["passed"], v["reason"])

    return Grader("groundedness", "model", _run, cfg)
