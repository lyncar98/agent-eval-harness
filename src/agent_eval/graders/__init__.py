"""Grader families exposed as factory functions.

Import a grader and configure it inline::

    from agent_eval.graders import min_length, code_no_keyword, llm_rubric

    suite_graders = [
        min_length(config={"min": 40}),
        code_no_keyword(config={"banned": ["OA-99-FAKE"]}),
        llm_rubric(config={"rubric": "...", "pass_threshold": 0.8}),
    ]
"""

from .base import (
    GRADER_FACTORIES,
    GRADER_FAMILY,
    ONLINE_SAFE,
    Grader,
    register,
    result,
)
from .code import (
    code_no_keyword,
    expected_output,
    json_valid,
    keyword,
    max_length,
    min_length,
    no_refusal,
    regex_match,
    sentiment,
    state_check,
    tool_called,
    tool_sequence,
)
from .model import groundedness, llm_pairwise, llm_rubric

__all__ = [
    "Grader",
    "register",
    "result",
    "GRADER_FACTORIES",
    "GRADER_FAMILY",
    "ONLINE_SAFE",
    # code
    "code_no_keyword",
    "keyword",
    "min_length",
    "max_length",
    "regex_match",
    "json_valid",
    "no_refusal",
    "sentiment",
    "expected_output",
    "state_check",
    "tool_called",
    "tool_sequence",
    # model
    "llm_rubric",
    "llm_pairwise",
    "groundedness",
]
