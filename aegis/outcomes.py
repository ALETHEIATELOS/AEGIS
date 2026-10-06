"""Outcomes and observation: learning without corrupting history.

Research question 7: can AI systems learn from outcomes without corrupting
the historical decision record?

Yes, by separation:

- DecisionRecord (records.py) is frozen history. It is never edited, not
  even when the outcome proves it wrong. A wrong record is data.
- Outcome records what actually happened after a decision, observed by a
  named observer at a named time.
- Observation compares the outcome against what the synthesis expected and
  notes the divergence — in plain language, with no rewrite of the past.
- Lessons derived from observations live in EpistemicMemory (memory.py),
  which REFERENCES records by id. The reference graph goes one way:
  memory -> records. Records never point at lessons, so history cannot be
  retroactively reinterpreted by later learning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Outcome(BaseModel):
    """What actually happened after a decision. Observed, not predicted."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"oc_{uuid4().hex[:12]}")
    record_id: str = Field(description="The decision record this outcome follows from.")
    case_id: str
    description: str = Field(description="What happened, as observed.")
    observed_at: datetime = Field(default_factory=_utcnow)
    observer: str = Field(description="Who observed it — a named human or system.")


class Observation(BaseModel):
    """The comparison between what was expected and what happened.

    Divergence is stated plainly. The observation may propose a lesson, but
    the lesson itself is recorded in epistemic memory, not here.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"ob_{uuid4().hex[:12]}")
    outcome_id: str
    case_id: str
    expected: str = Field(description="What the synthesis led the decider to expect.")
    divergence: str = Field(description="How reality differed, stated plainly.")
    lesson_candidate: str = Field(
        default="", description="A proposed lesson, to be considered for epistemic memory."
    )
    observed_at: datetime = Field(default_factory=_utcnow)
