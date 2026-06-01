"""Immutable release bundles + Release Decision Records.

Governance you can't query is governance you don't have. A bundle is a frozen
identity: a new prompt revision, model upgrade, or tool-schema hash change is a
NEW bundle, never a mutation. An RDR records an approval chain and forbids
self-approval.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ReleaseBundle:
    agent_id: str
    bundle_tag: str                                   # "lesson-planner-v1.4.2"
    provider: str
    model: str
    code_sha: str | None = None
    prompt_version_id: str | None = None
    tool_schema_hashes: tuple[tuple[str, str], ...] = ()
    dataset_version_id: str | None = None
    policy_version_ids: tuple[str, ...] = ()
    compaction_config: tuple[tuple[str, str], ...] = ()
    notes: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=_now)

    @property
    def identity(self) -> tuple[str, str]:
        return (self.agent_id, self.bundle_tag)


class SelfApprovalError(Exception):
    """Raised when an approval chain has no distinct approver."""


@dataclass
class Approval:
    actor: str
    role: str
    decision: str            # approve | reject | comment
    note: str = ""
    decided_at: datetime = field(default_factory=_now)


@dataclass
class ReleaseDecisionRecord:
    bundle_id: str
    proposed_by: str
    approvals: list[Approval] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=_now)

    def add_approval(self, approval: Approval) -> None:
        if approval.decision == "approve" and approval.actor == self.proposed_by:
            raise SelfApprovalError(
                f"{approval.actor} proposed this bundle and cannot self-approve it"
            )
        self.approvals.append(approval)

    @property
    def is_approved(self) -> bool:
        rejected = any(a.decision == "reject" for a in self.approvals)
        approved_by_other = any(
            a.decision == "approve" and a.actor != self.proposed_by for a in self.approvals
        )
        return approved_by_other and not rejected
