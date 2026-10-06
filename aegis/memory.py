"""Epistemic memory: what the institution has learned, without rewriting history.

Research question 5 (reconstruction) and 7 (learning without corruption)
meet here.

EpistemicMemory is an append-only journal of Lessons. Each lesson:
- states what was learned, in plain language,
- references the decision records and outcomes it was learned FROM (by id),
- is stamped with when it was learned and by whom.

Lessons never modify records. A lesson that turns out to be wrong is not
edited either — a new lesson supersedes it by reference, the same way a new
decision record supersedes an old one. The institution's memory is a
growing, auditable chain, not a mutable wiki.

reconstruct() answers "why did this decision change?": it replays a case's
decision records chronologically and diffs the evidence fingerprints
between consecutive records, showing exactly what new, removed, or changed
evidence underlies each new decision.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from aegis.records import DecisionLog, DecisionRecord


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Lesson(BaseModel):
    """One thing the institution has learned. Immutable; supersede, don't edit."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"ln_{uuid4().hex[:12]}")
    text: str = Field(description="The lesson, stated plainly.")
    record_refs: tuple[str, ...] = Field(
        default=(), description="Decision records this lesson was learned from."
    )
    outcome_refs: tuple[str, ...] = Field(default=())
    supersedes: tuple[str, ...] = Field(
        default=(), description="Earlier lesson ids this lesson replaces. The old ones remain."
    )
    learned_at: datetime = Field(default_factory=_utcnow)
    learned_by: str = Field(default="aegis")


class EpistemicMemory:
    """Append-only institutional memory."""

    def __init__(self):
        self._lessons: list[Lesson] = []

    def add(self, lesson: Lesson) -> Lesson:
        if not isinstance(lesson, Lesson):
            raise TypeError("Only Lesson instances may enter epistemic memory.")
        self._lessons.append(lesson)
        return lesson

    def lessons_for_case(self, case_id: str, log: DecisionLog) -> list[Lesson]:
        """Lessons learned from a case's records."""
        record_ids = {r.id for r in log.for_case(case_id)}
        return [ln for ln in self._lessons if set(ln.record_refs) & record_ids]

    def __len__(self) -> int:
        return len(self._lessons)


def reconstruct(case_id: str, log: DecisionLog) -> list[dict]:
    """Replay a case's decision history and explain each change.

    Returns a chronological list of steps. Each step after the first shows
    which evidence fingerprints were added or removed relative to the
    previous record — the mechanical answer to "why did the decision
    change?", grounded in what was known at each point.
    """
    records: list[DecisionRecord] = log.for_case(case_id)
    steps: list[dict] = []
    previous_fps: set[str] = set()
    for i, record in enumerate(records):
        current_fps = set(record.evidence_fingerprints)
        step = {
            "sequence": i + 1,
            "record_id": record.id,
            "state": record.state.value,
            "recommendation": record.recommendation,
            "authorized_by": record.authorized_by,
            "recorded_at": record.recorded_at.isoformat(),
        }
        if i > 0:
            step["evidence_added"] = sorted(current_fps - previous_fps)
            step["evidence_removed"] = sorted(previous_fps - current_fps)
            step["evidence_unchanged"] = sorted(current_fps & previous_fps)
        previous_fps = current_fps
        steps.append(step)
    return steps
