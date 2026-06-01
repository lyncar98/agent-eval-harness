"""agent-eval-harness: production-grade evaluation for LLM agents.

Public API (as documented in the README):

    from agent_eval import GraderContext, Suite, run_suite
    from agent_eval.graders import code_no_keyword, llm_rubric, min_length
"""

from .calibration import CalibrationRecord, GraderTrust, compute_trust, trust_band
from .cascade import (
    Assignment,
    AgentOverride,
    EffectiveStandard,
    JustificationRequired,
    resolve,
)
from .context import GraderContext
from .graders.base import GRADER_FACTORIES, GRADER_FAMILY, ONLINE_SAFE, Grader
from .judges import (
    AnthropicJudge,
    HeuristicJudge,
    Judge,
    anthropic_available,
    get_judge,
    parse_verdict,
)
from .online import OnlineResult, run_online_checks
from .registry import make_grader
from .release import (
    Approval,
    ReleaseBundle,
    ReleaseDecisionRecord,
    SelfApprovalError,
)
from .runner import RunItem, RunReport, TrialResult, run_suite
from .sampling import sampled_fraction, should_sample
from .slo import SLO, IncidentDecision, burn_rate, evaluate_slo
from .suite import Case, Suite, load_suite

__version__ = "0.1.0"

__all__ = [
    "GraderContext",
    "Suite",
    "Case",
    "load_suite",
    "run_suite",
    "RunReport",
    "RunItem",
    "TrialResult",
    "Grader",
    "make_grader",
    "GRADER_FACTORIES",
    "GRADER_FAMILY",
    "ONLINE_SAFE",
    "Judge",
    "HeuristicJudge",
    "AnthropicJudge",
    "get_judge",
    "anthropic_available",
    "parse_verdict",
    "Assignment",
    "AgentOverride",
    "EffectiveStandard",
    "JustificationRequired",
    "resolve",
    "CalibrationRecord",
    "GraderTrust",
    "compute_trust",
    "trust_band",
    "OnlineResult",
    "run_online_checks",
    "ReleaseBundle",
    "ReleaseDecisionRecord",
    "Approval",
    "SelfApprovalError",
    "SLO",
    "IncidentDecision",
    "burn_rate",
    "evaluate_slo",
    "sampled_fraction",
    "should_sample",
]
