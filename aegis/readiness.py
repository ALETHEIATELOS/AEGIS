"""Decision readiness: deterministic, LLM-free, auditable.

Research question 6 (partial): the readiness determination itself must be
deterministic. An LLM may produce the analysis; only explicit, inspectable
rules may declare a case READY_FOR_HUMAN_AUTHORITY.

The readiness check answers one question: is this case fit to be placed
before a human for a decision? It does NOT decide anything. Its output is
either:

- READY_FOR_HUMAN_AUTHORITY — the case may proceed to the decision gate, or
- NOT_READY — with explicit reasons, each one actionable.

Key doctrine: unresolved contradictions do NOT block readiness. What blocks
readiness is UNRECORDED contradiction — disagreement that exists but was
never written down. A human must see the dissent; the system must not
require the dissent to disappear first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ReadinessStatus(str, Enum):
    READY_FOR_HUMAN_AUTHORITY = "ready_for_human_authority"
    NOT_READY = "not_ready"


@dataclass(frozen=True)
class ReadinessPolicy:
    """The bar for readiness. Explicit, versionable, inspectable."""

    min_perspectives: int = 2
    require_synthesis: bool = True
    require_dissents_recorded: bool = True
    min_combined_confidence: float = 0.0
    min_evidence_items: int = 1


@dataclass(frozen=True)
class ReadinessResult:
    status: ReadinessStatus
    reasons: tuple[str, ...]
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    policy: ReadinessPolicy = field(default_factory=ReadinessPolicy)

    @property
    def is_ready(self) -> bool:
        return self.status == ReadinessStatus.READY_FOR_HUMAN_AUTHORITY


def assess_readiness(
    *,
    n_perspectives: int,
    has_synthesis: bool,
    n_evidence: int,
    unrecorded_contradictions: int,
    combined_confidence: float,
    policy: ReadinessPolicy | None = None,
) -> ReadinessResult:
    """Deterministic readiness assessment. Pure function — same inputs,
    same result, every time. No model calls, no hidden state."""
    policy = policy or ReadinessPolicy()
    reasons: list[str] = []

    if n_perspectives < policy.min_perspectives:
        reasons.append(
            f"only {n_perspectives} perspective(s); policy requires {policy.min_perspectives}"
        )
    if policy.require_synthesis and not has_synthesis:
        reasons.append("no synthesis produced")
    if n_evidence < policy.min_evidence_items:
        reasons.append(
            f"only {n_evidence} evidence item(s); policy requires {policy.min_evidence_items}"
        )
    if policy.require_dissents_recorded and unrecorded_contradictions > 0:
        reasons.append(
            f"{unrecorded_contradictions} known disagreement(s) never recorded as contradictions"
        )
    if combined_confidence < policy.min_combined_confidence:
        reasons.append(
            f"combined confidence {combined_confidence:.2f} below policy minimum "
            f"{policy.min_combined_confidence:.2f}"
        )

    if reasons:
        return ReadinessResult(status=ReadinessStatus.NOT_READY, reasons=tuple(reasons), policy=policy)
    return ReadinessResult(
        status=ReadinessStatus.READY_FOR_HUMAN_AUTHORITY,
        reasons=("all readiness criteria met",),
        policy=policy,
    )
