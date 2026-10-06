"""Conflict and risk: disagreement preserved, risk simulated.

Research question 3: can AI systems represent unresolved disagreement without
forcing premature consensus?
Research question 4 (partial): can uncertainty propagate through analysis
and simulation?

Two mechanisms:

1. Contradiction records. When perspectives disagree on a topic, the
   disagreement becomes a first-class, immutable record — not something to be
   "resolved" by averaging. A contradiction may be RESOLVED (with a recorded
   resolution) or remain UNRESOLVED. Unresolved contradictions are carried
   into synthesis as preserved dissent, and the readiness check requires them
   to be RECORDED, not resolved. Recording is the requirement; consensus is
   not.

2. Risk simulation. Risk factors (likelihood × impact, deterministic) and
   scenarios (projections under stated assumptions with probabilities
   adjusted by the reliability of the evidence they rest on). Uncertainty
   propagates explicitly: a scenario's probability is discounted by the
   weakest evidence it depends on, and that discount is visible.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContradictionStatus(str, Enum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"


class Contradiction(BaseModel):
    """A recorded disagreement between perspectives on a single topic."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"cx_{uuid4().hex[:12]}")
    topic: str = Field(description="What is disagreed about, stated neutrally.")
    positions: dict[str, str] = Field(
        description="perspective_id -> that perspective's position on the topic."
    )
    status: ContradictionStatus = ContradictionStatus.UNRESOLVED
    resolution: str = Field(
        default="",
        description="If resolved: how, and on what grounds. Empty while unresolved.",
    )
    recorded_at: datetime = Field(default_factory=_utcnow)
    recorded_by: str = Field(default="aegis")

    def resolve(self, *, actor: str, resolution: str) -> "Contradiction":
        """Resolve a contradiction — returns a NEW record; the unresolved
        record remains in history. Resolution requires a stated basis."""
        if not resolution:
            raise ValueError("Resolution requires a stated basis.")
        new = self.model_copy(update={
            "status": ContradictionStatus.RESOLVED,
            "resolution": resolution,
        })
        return new

    @property
    def is_unresolved(self) -> bool:
        return self.status == ContradictionStatus.UNRESOLVED


class RiskFactor(BaseModel):
    """One risk, scored deterministically. No model judgment in the score."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    likelihood: float = Field(ge=0.0, le=1.0, description="Probability the risk materializes.")
    impact: float = Field(ge=0.0, le=1.0, description="Severity if it materializes.")
    evidence_ids: tuple[str, ...] = Field(
        default=(), description="Evidence this assessment rests on."
    )

    @property
    def score(self) -> float:
        """Deterministic risk score: likelihood × impact."""
        return round(self.likelihood * self.impact, 4)

    def severity(self) -> str:
        s = self.score
        if s >= 0.5:
            return "high"
        if s >= 0.2:
            return "medium"
        return "low"


class RiskScenario(BaseModel):
    """A simulated future under stated assumptions.

    Uncertainty propagation: the scenario's stated probability is discounted
    by the minimum reliability of the evidence it depends on. The raw and
    adjusted probabilities are both kept — the adjustment is transparent, not
    hidden inside a model.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    assumptions: tuple[str, ...] = Field(description="What must hold for this scenario.")
    projected_outcome: str
    raw_probability: float = Field(ge=0.0, le=1.0)
    evidence_reliabilities: tuple[float, ...] = Field(
        default=(),
        description="Reliability of each evidence item the scenario depends on.",
    )

    @property
    def evidence_discount(self) -> float:
        """The weakest link: minimum evidence reliability, or 1.0 if none stated."""
        if not self.evidence_reliabilities:
            return 1.0
        return min(self.evidence_reliabilities)

    @property
    def adjusted_probability(self) -> float:
        """Probability after uncertainty propagation. Always ≤ raw."""
        return round(self.raw_probability * self.evidence_discount, 4)


class RiskAssessment(BaseModel):
    """The full risk picture for a case: factors + simulated scenarios."""

    model_config = ConfigDict(frozen=True)

    factors: tuple[RiskFactor, ...] = ()
    scenarios: tuple[RiskScenario, ...] = ()
    assessed_at: datetime = Field(default_factory=_utcnow)
    assessed_by: str = Field(default="aegis")

    def top_factors(self, n: int = 3) -> list[RiskFactor]:
        return sorted(self.factors, key=lambda f: f.score, reverse=True)[:n]

    def highest_adjusted_scenario(self) -> RiskScenario | None:
        if not self.scenarios:
            return None
        return max(self.scenarios, key=lambda s: s.adjusted_probability)
