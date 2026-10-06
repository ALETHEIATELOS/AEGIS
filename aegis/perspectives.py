"""Perspectives: genuinely independent reasoning paths.

Research question 2: can AI systems maintain genuinely independent reasoning
paths?

A Perspective is one coherent line of reasoning about a case. Independence is
structural, not aspirational:

- Each perspective declares its own standpoint (the lens it reasons from).
- Each perspective binds to the specific evidence items it actually used
  (evidence_ids). Two perspectives may cite different evidence, the same
  evidence, or interpret the same evidence differently — and that difference
  is visible, not hidden in a shared prompt.
- Perspectives are produced by separate agent runs (see runtime.py) with no
  shared hidden state. The orchestrator passes each perspective agent only
  the case question and the evidence pool, never another perspective's
  reasoning — unless explicitly running a rebuttal pass.

Perspectives are immutable once formed. A change of mind is a new
perspective, not an edit.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Perspective(BaseModel):
    """One independent reasoning path over a case."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"px_{uuid4().hex[:12]}")
    name: str = Field(description="Short label, e.g. 'Financial conservatism' or 'Growth advocate'.")
    standpoint: str = Field(description="The lens this perspective reasons from. Declared up front.")
    evidence_ids: tuple[str, ...] = Field(
        default=(),
        description="The specific evidence items this perspective drew on. Independence is auditable here.",
    )
    reasoning: str = Field(description="The reasoning itself, in the perspective's own terms.")
    conclusion: str = Field(description="What this perspective concludes.")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0,
                               description="The perspective's own credence in its conclusion.")
    formed_by: str = Field(default="aegis", description="Which agent or process formed this perspective.")
    formed_at: datetime = Field(default_factory=_utcnow)

    def shares_evidence_with(self, other: "Perspective") -> set[str]:
        """The evidence items both perspectives drew on — overlap is data, not a flaw."""
        return set(self.evidence_ids) & set(other.evidence_ids)

    def evidence_overlap_ratio(self, other: "Perspective") -> float:
        """Fraction of this perspective's evidence shared with another (0.0–1.0).

        A research instrument: high overlap with divergent conclusions is
        exactly the signal that interpretation, not information, differs.
        """
        if not self.evidence_ids:
            return 0.0
        return len(self.shares_evidence_with(other)) / len(self.evidence_ids)
