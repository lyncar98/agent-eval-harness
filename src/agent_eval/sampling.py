"""Deterministic, idempotent online-eval sampling.

Sampling is a pure function of ``request_id`` — never ``random()``. Stream
replays (worker restart, consumer-group reset) hit the same id and sample to the
same outcome; combined with ``ON CONFLICT (request_id) DO NOTHING`` on the
samples table, the pipeline is idempotent (replaying ten times == once).
"""

from __future__ import annotations

import hashlib


def should_sample(request_id: str, rate: float) -> bool:
    """Whether this request falls in the sampled bucket for ``rate`` (clamped)."""
    if rate <= 0:
        return False
    if rate >= 1:
        return True
    digest = hashlib.sha256(request_id.encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:8], "big") / float(1 << 64)
    return bucket < rate


def sampled_fraction(request_ids: list[str], rate: float) -> float:
    if not request_ids:
        return 0.0
    return sum(1 for r in request_ids if should_sample(r, rate)) / len(request_ids)
