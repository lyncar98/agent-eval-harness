"""Code graders: deterministic, cheap, gating by default.

Each factory returns a configured :class:`Grader`. Factories whose checks need
only the chat-turn payload (no expected_* fields) are marked ``online_safe`` so
the online sampler can run them judge-free in production.
"""

from __future__ import annotations

import json
import re

from ..context import GraderContext
from .base import Grader, register, result


@register("no_keyword", "code")
def code_no_keyword(config: dict | None = None) -> Grader:
    """Banned-token guard (offline). Online, use regex_match(should_match=false)."""
    cfg = dict(config or {})

    def _run(ctx: GraderContext) -> dict:
        banned = cfg.get("banned", []) or []
        cs = cfg.get("case_sensitive", False)
        text = ctx.response if cs else ctx.response.lower()
        found = [k for k in banned if (k if cs else k.lower()) in text]
        if found:
            return result("no_keyword", "code", 0.0, False, f"Banned tokens present: {found}")
        return result("no_keyword", "code", 1.0, True, "No banned tokens present")

    return Grader("no_keyword", "code", _run, cfg)


@register("keyword", "code", online_safe=True)
def keyword(config: dict | None = None) -> Grader:
    """Required-token guard — all listed tokens MUST appear."""
    cfg = dict(config or {})

    def _run(ctx: GraderContext) -> dict:
        required = cfg.get("required", []) or []
        cs = cfg.get("case_sensitive", False)
        text = ctx.response if cs else ctx.response.lower()
        missing = [k for k in required if (k if cs else k.lower()) not in text]
        if missing:
            return result("keyword", "code", 0.0, False, f"Missing required tokens: {missing}")
        return result("keyword", "code", 1.0, True, "All required tokens present")

    return Grader("keyword", "code", _run, cfg, online_safe=True)


@register("min_length", "code", online_safe=True)
def min_length(config: dict | None = None) -> Grader:
    """Catch empty / evasive responses. Accepts ``min`` or ``min_chars``."""
    cfg = dict(config or {})

    def _run(ctx: GraderContext) -> dict:
        n = len((ctx.response or "").strip())
        floor = int(cfg.get("min", cfg.get("min_chars", 1)))
        passed = n >= floor
        return result("min_length", "code", 1.0 if passed else 0.0, passed,
                      f"length={n} (min {floor})")

    return Grader("min_length", "code", _run, cfg, online_safe=True)


@register("max_length", "code", online_safe=True)
def max_length(config: dict | None = None) -> Grader:
    """Catch runaway / padded responses. Accepts ``max`` or ``max_chars``."""
    cfg = dict(config or {})

    def _run(ctx: GraderContext) -> dict:
        n = len((ctx.response or "").strip())
        ceil = int(cfg.get("max", cfg.get("max_chars", 10_000)))
        passed = n <= ceil
        return result("max_length", "code", 1.0 if passed else 0.0, passed,
                      f"length={n} (max {ceil})")

    return Grader("max_length", "code", _run, cfg, online_safe=True)


@register("regex_match", "code", online_safe=True)
def regex_match(config: dict | None = None) -> Grader:
    """Assert (or forbid, via should_match=false) a regex over the response."""
    cfg = dict(config or {})

    def _run(ctx: GraderContext) -> dict:
        pattern = cfg.get("pattern", "")
        should_match = cfg.get("should_match", True)
        flags = re.IGNORECASE if cfg.get("ignore_case", True) else 0
        hit = re.search(pattern, ctx.response or "", flags) is not None
        passed = hit == bool(should_match)
        verb = "matched" if hit else "did not match"
        return result("regex_match", "code", 1.0 if passed else 0.0, passed,
                      f"/{pattern}/ {verb} (wanted match={should_match})")

    return Grader("regex_match", "code", _run, cfg, online_safe=True)


@register("json_valid", "code", online_safe=True)
def json_valid(config: dict | None = None) -> Grader:
    """Response (or a fenced block) must parse as JSON; optionally check keys."""
    cfg = dict(config or {})

    def _run(ctx: GraderContext) -> dict:
        raw = ctx.response or ""
        block = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", raw, re.DOTALL)
        candidate = block.group(1) if block else raw.strip()
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            return result("json_valid", "code", 0.0, False, f"Invalid JSON: {exc.msg}")
        for k in cfg.get("required_keys", []) or []:
            if isinstance(data, dict) and k not in data:
                return result("json_valid", "code", 0.0, False, f"Missing key: {k}")
        return result("json_valid", "code", 1.0, True, "Valid JSON")

    return Grader("json_valid", "code", _run, cfg, online_safe=True)


@register("no_refusal", "code", online_safe=True)
def no_refusal(config: dict | None = None) -> Grader:
    """Heuristic refusal detector for turns that should have been answered."""
    cfg = dict(config or {})

    def _run(ctx: GraderContext) -> dict:
        markers = cfg.get("markers") or [
            "i can't help", "i cannot help", "i can't assist", "i cannot assist",
            "as an ai", "no puedo ayudar", "lo siento, no puedo",
        ]
        text = (ctx.response or "").lower()
        hit = next((m for m in markers if m in text), None)
        if hit:
            return result("no_refusal", "code", 0.0, False, f"Refusal marker: '{hit}'")
        return result("no_refusal", "code", 1.0, True, "No refusal markers")

    return Grader("no_refusal", "code", _run, cfg, online_safe=True)


@register("sentiment", "code", online_safe=True)
def sentiment(config: dict | None = None) -> Grader:
    """Tiny lexicon sentiment floor — flags hostile / dismissive tone."""
    cfg = dict(config or {})

    def _run(ctx: GraderContext) -> dict:
        negative = set(cfg.get("negative") or
                       ["stupid", "idiot", "useless", "shut up", "estúpido", "inútil"])
        text = (ctx.response or "").lower()
        hits = [w for w in negative if w in text]
        passed = not hits
        return result("sentiment", "code", 1.0 if passed else 0.0, passed,
                      "neutral/positive tone" if passed else f"negative tone: {hits}")

    return Grader("sentiment", "code", _run, cfg, online_safe=True)


@register("expected_output", "code")
def expected_output(config: dict | None = None) -> Grader:
    """Normalized exact-match against a known answer (offline only)."""
    cfg = dict(config or {})

    def _run(ctx: GraderContext) -> dict:
        if ctx.expected_output is None:
            return result("expected_output", "code", 1.0, True,
                          "N/A: no expected_output for this case")

        def norm(s: str) -> str:
            return re.sub(r"\s+", " ", s.strip().lower())

        passed = norm(ctx.response) == norm(ctx.expected_output)
        return result("expected_output", "code", 1.0 if passed else 0.0, passed,
                      "exact match" if passed else "did not match expected_output")

    return Grader("expected_output", "code", _run, cfg)


@register("state_check", "code")
def state_check(config: dict | None = None) -> Grader:
    """Outcome grader: produced state must be a superset of expected_state.

    The produced state is threaded in via config['produced_state'] by the runner.
    """
    cfg = dict(config or {})

    def _run(ctx: GraderContext) -> dict:
        if not ctx.expected_state:
            return result("state_check", "code", 1.0, True, "N/A: no expected_state")
        produced = cfg.get("produced_state") or {}
        mismatches = {
            k: (v, produced.get(k))
            for k, v in ctx.expected_state.items()
            if produced.get(k) != v
        }
        passed = not mismatches
        return result("state_check", "code", 1.0 if passed else 0.0, passed,
                      "state matches" if passed else f"state mismatch: {mismatches}")

    return Grader("state_check", "code", _run, cfg)


@register("tool_called", "code", online_safe=True)
def tool_called(config: dict | None = None) -> Grader:
    """Assert a specific tool was (or was not) invoked."""
    cfg = dict(config or {})

    def _run(ctx: GraderContext) -> dict:
        name = cfg.get("tool", "")
        should = cfg.get("should_call", True)
        called = name in [tc.get("name") for tc in ctx.tool_calls]
        passed = called == bool(should)
        return result("tool_called", "code", 1.0 if passed else 0.0, passed,
                      f"tool '{name}' {'called' if called else 'not called'} (wanted={should})")

    return Grader("tool_called", "code", _run, cfg, online_safe=True)


@register("tool_sequence", "code")
def tool_sequence(config: dict | None = None) -> Grader:
    """Trajectory check — diagnostic by default.

    Assert ``expected`` tools appear as an ordered subsequence of actual calls.
    Pass ``gating=true`` on the suite check only where order IS the policy.
    """
    cfg = dict(config or {})

    def _run(ctx: GraderContext) -> dict:
        expected = cfg.get("expected") or [
            tc.get("name") for tc in (ctx.expected_tool_calls or [])
        ]
        actual = [tc.get("name") for tc in ctx.tool_calls]
        it = iter(actual)
        ok = all(any(e == a for a in it) for e in expected)
        return result("tool_sequence", "code", 1.0 if ok else 0.0, ok,
                      f"expected subsequence {expected} in {actual}: {ok}")

    return Grader("tool_sequence", "code", _run, cfg)
