"""Decision records: append-only, immutable, reconstructable.

Research question 5: can the system reconstruct WHY a decision changed when
evidence or models change?
Research question 7 (partial): records must survive learning — history is
never rewritten.

A DecisionRecord is frozen at creation. It captures:
- the case and the question,
- the synthesis it rests on,
- fingerprints of the exact evidence set behind it,
- the state it records (authorized, rejected, executed, ...),
- who authorized it (if anyone) and their stated rationale.

The DecisionLog is append-only: records are added, never edited or deleted.
When a decision changes, a NEW record is appended. Reconstruction
(memory.py) replays the log chronologically and diffs evidence fingerprints
between consecutive records — so "why did the decision change?" is answered
by "what evidence changed, and what did the new synthesis conclude?"
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from aegis.authority import Actor, ActorKind, DecisionState


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DecisionRecord(BaseModel):
    """One immutable point in a case's decision history."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"dr_{uuid4().hex[:12]}")
    case_id: str
    question: str = Field(description="The question this record answers, as posed at the time.")
    state: DecisionState
    synthesis_id: str | None = Field(default=None)
    recommendation: str = Field(default="")
    evidence_fingerprints: tuple[str, ...] = Field(
        default=(),
        description="Fingerprints (see evidence.Evidence.fingerprint) of the exact "
                    "evidence set behind this record. The basis of reconstruction.",
    )
    authorized_by: str | None = Field(
        default=None, description="Human identity that authorized, if any. Never an agent."
    )
    authorization_rationale: str = Field(default="")
    recorded_at: datetime = Field(default_factory=_utcnow)

    def model_post_init(self, __context) -> None:  # noqa: N805
        if self.state == DecisionState.AUTHORIZED and not self.authorized_by:
            raise ValueError("An AUTHORIZED record must name the human who authorized it.")


class DecisionLog:
    """Append-only log of decision records for all cases.

    Add is the only write operation. There is no update, no delete.
    """

    def __init__(self):
        self._records: list[DecisionRecord] = []

    def add(self, record: DecisionRecord) -> DecisionRecord:
        if not isinstance(record, DecisionRecord):
            raise TypeError("Only DecisionRecord instances may enter the log.")
        self._records.append(record)
        return record

    def for_case(self, case_id: str) -> list[DecisionRecord]:
        """Chronological records for one case — the raw material of reconstruction."""
        return [r for r in self._records if r.case_id == case_id]

    def latest_for_case(self, case_id: str) -> DecisionRecord | None:
        records = self.for_case(case_id)
        return records[-1] if records else None

    def __len__(self) -> int:
        return len(self._records)


def actor_name_for_record(actor: Actor) -> str:
    """Render an actor for a record, enforcing the human-authority rule.

    Convenience guard: records should never attribute authorization to a
    non-human. The gate already enforces this; this is defense in depth.
    """
    if actor.kind is not ActorKind.HUMAN:
        raise ValueError(
            f"Decision records attribute authority to humans only; "
            f"got {actor.kind.value} '{actor.identity}'."
        )
    return actor.identity
