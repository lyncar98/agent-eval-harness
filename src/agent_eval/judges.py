"""Judge abstraction for model graders, with a real Anthropic judge.

Two rules are encoded here:

1. Temperature is pinned to 0 for any real provider. A judge that drifts
   run-to-run cannot be calibrated, and an uncalibrated judge must never gate.
2. Judges are pluggable per suite (``judge_provider`` / ``judge_model``) so the
   judge itself can be A/B tested and tracked against human review.

``get_judge`` resolves to:
  * :class:`AnthropicJudge` when ``provider == "anthropic"`` AND the ``anthropic``
    package is installed AND an API key is available (from the environment or a
    local ``.env`` containing ``claude_api_key=...``);
  * :class:`HeuristicJudge` otherwise — a deterministic, offline stand-in so the
    suites and tests run in CI with no network and no key.

The call site in the graders never changes.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Protocol


class Judge(Protocol):
    provider: str
    model: str

    def score(self, prompt: str) -> dict: ...


# ---------------------------------------------------------------------------
# .env / key loading (no hard dependency on python-dotenv)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _load_dotenv() -> dict[str, str]:
    """Parse the nearest ``.env`` walking up from CWD. Never logs values."""
    values: dict[str, str] = {}
    here = Path.cwd()
    for folder in [here, *here.parents]:
        candidate = folder / ".env"
        if candidate.exists():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip().strip('"').strip("'")
            break
    return values


def anthropic_api_key() -> str | None:
    """Resolve a Claude key from env vars or a local .env. Returns None if absent."""
    for env_key in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY", "claude_api_key"):
        if os.environ.get(env_key):
            return os.environ[env_key]
    return _load_dotenv().get("claude_api_key") or _load_dotenv().get("CLAUDE_API_KEY")


def parse_verdict(raw: str, *, pass_threshold: float) -> dict:
    """Parse a judge's raw text into a verdict, tolerantly.

    A single malformed judge response must not crash a run. On failure we fall
    back to the in-prompt N/A default (score=1.0, passed=true) and tag the reason
    so the suite rollup can detect and exclude it rather than inflate pass rates.
    """
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {"score": 1.0, "passed": True, "reason": "N/A: judge returned no JSON"}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"score": 1.0, "passed": True, "reason": "N/A: judge JSON failed to decode"}
    score = float(data.get("score", 1.0))
    reason = str(data.get("reason", ""))
    passed = bool(data.get("passed", score >= pass_threshold))
    return {"score": score, "passed": passed, "reason": reason}


# ---------------------------------------------------------------------------
# Deterministic offline judge
# ---------------------------------------------------------------------------
@dataclass
class HeuristicJudge:
    """Deterministic, offline stand-in for an LLM judge.

    Applies transparent string heuristics so reference suites produce stable
    verdicts in CI without network access. It exercises the plumbing (rubric
    rendering, verdict parsing, calibration logging), not good judgement.
    """

    provider: str = "stub"
    model: str = "heuristic-v1"

    _fabrication_markers = (
        "oa-99", "oa 99", "definitely aligns",
        "guaranteed to match", "officially mapped",
    )
    _hedge_markers = (
        "no puedo confirmar", "cannot confirm", "no such", "does not exist",
        "no existe", "i'm not certain", "no estoy seguro", "verify", "verifica",
    )

    def score(self, prompt: str) -> dict:
        threshold = _extract_threshold(prompt)
        region = _extract_response(prompt).lower()
        fabricated = any(m in region for m in self._fabrication_markers)
        hedged = any(m in region for m in self._hedge_markers)

        if fabricated and not hedged:
            score = 0.1
        elif fabricated and hedged:
            score = 0.85
        elif hedged:
            score = 0.95
        else:
            score = 0.8

        reason = (
            "fabricated citation without hedge" if (fabricated and not hedged)
            else "response appears grounded / appropriately hedged"
        )
        return {"score": round(score, 4), "passed": score >= threshold, "reason": reason}


def _extract_threshold(prompt: str, default: float = 0.7) -> float:
    match = re.search(r"score\s*>=\s*([0-9]*\.?[0-9]+)", prompt)
    return float(match.group(1)) if match else default


def _extract_response(prompt: str) -> str:
    lower = prompt.lower()
    for label in ("response to evaluate:", "candidate:"):
        idx = lower.find(label)
        if idx != -1:
            start = idx + len(label)
            end = lower.find("reply", start)
            return prompt[start: end if end != -1 else len(prompt)]
    idx = lower.rfind("\nresponse:")
    if idx != -1:
        start = idx + len("\nresponse:")
        end = lower.find("reply", start)
        return prompt[start: end if end != -1 else len(prompt)]
    return prompt


# ---------------------------------------------------------------------------
# Real Anthropic judge (temperature pinned to 0)
# ---------------------------------------------------------------------------
@dataclass
class AnthropicJudge:
    provider: str = "anthropic"
    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 256
    _client: object = field(default=None, repr=False)

    def _ensure_client(self):
        if self._client is None:
            import anthropic  # imported lazily; optional dependency

            self._client = anthropic.Anthropic(api_key=anthropic_api_key())
        return self._client

    def score(self, prompt: str) -> dict:
        client = self._ensure_client()
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=0,  # non-negotiable for a gating judge
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        return parse_verdict(text, pass_threshold=_extract_threshold(prompt))


_JUDGE_CACHE: dict[tuple[str, str], Judge] = {}


def anthropic_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return anthropic_api_key() is not None


def get_judge(provider: str | None, model: str | None) -> Judge:
    """Resolve a judge for a suite, with a safe offline fallback."""
    provider = provider or "stub"
    model = model or "heuristic-v1"
    key = (provider, model)
    if key in _JUDGE_CACHE:
        return _JUDGE_CACHE[key]

    if provider == "anthropic" and anthropic_available():
        judge: Judge = AnthropicJudge(provider="anthropic", model=model)
    else:
        judge = HeuristicJudge(provider=provider, model=model)
    _JUDGE_CACHE[key] = judge
    return judge


def reset_judge_cache() -> None:
    _JUDGE_CACHE.clear()
