"""Synthesis: recommendation that preserves dissent.

The computational kaleidoscope: the same evidence turned through multiple
independent perspectives, then combined WITHOUT forcing consensus.

A Synthesis:
- states what the perspectives AGREE on,
- carries UNRESOLVED contradictions forward as preserved dissent (not as a
  problem to hide, but as part of the recommendation's context),
- propagates uncertainty deterministically from perspective confidences,
- produces a RECOMMENDATION — and marks, structurally, that a
  recommendation is not an authorization.

The synthesis never authorizes. It cannot. Authorization lives in
authority.py and requires a human actor. A synthesis that tried to
authorize would be a category error, and the types make it one: there is
simply no authorization field on a Synthesis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def combine_confidence(confidences: list[float]) -> float:
    """Deterministic uncertainty propagation across perspectives.

    Uses the geometric mean: agreement among several moderately-confident
    perspectives yields moderate combined confidence; a single low-confidence
    perspective drags the combination down. This is a research default, not a
    theorem — it is chosen because it is transparent, monotonic, and never
    exceeds the most confident input.
    """
    if not confidences:
        return 0.0
    product = 1.0
    for c in confidences:
        product *= max(c, 1e-9)
    return round(product ** (1.0 / len(confidences)), 4)


class Synthesis(BaseModel):
    """The combined view: agreements, preserved dissent, propagated
    uncertainty, and a recommendation that is explicitly NOT an authorization.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"sy_{uuid4().hex[:12]}")
    case_id: str
    perspective_ids: tuple[str, ...] = Field(description="Perspectives considered.")
    agreements: tuple[str, ...] = Field(
        default=(), description="What the perspectives genuinely agree on."
    )
    preserved_dissents: tuple[str, ...] = Field(
        default=(),
        description="Contradiction ids carried forward UNRESOLVED. Dissent is part of the output.",
    )
    combined_confidence: float = Field(ge=0.0, le=1.0)
    recommendation: str = Field(description="What is recommended — analysis, not authority.")
    recommendation_rationale: str = Field(default="")
    # Structural marker: a synthesis is analysis. This field exists so the
    # distinction is in the data, not just in the documentation.
    is_authorization: bool = Field(default=False, frozen=True)
    synthesized_at: datetime = Field(default_factory=_utcnow)
    synthesized_by: str = Field(default="aegis")

    def model_post_init(self, __context) -> None:  # noqa: N805
        if self.is_authorization:
            raise ValueError("A Synthesis can never be an authorization. "
                             "Authorization requires a human actor (see authority.py).")


def synthesize(*, case_id: str, perspective_conclusions: list[tuple[str, float]],
               agreements: list[str], dissent_ids: list[str],
               recommendation: str, rationale: str = "",
               synthesized_by: str = "aegis") -> Synthesis:
    """Build a Synthesis from perspective outputs. Pure function, no LLM.

    perspective_conclusions: list of (perspective_id, confidence).
    """
    ids = [pid for pid, _ in perspective_conclusions]
    confidences = [c for _, c in perspective_conclusions]
    return Synthesis(
        case_id=case_id,
        perspective_ids=tuple(ids),
        agreements=tuple(agreements),
        preserved_dissents=tuple(dissent_ids),
        combined_confidence=combine_confidence(confidences),
        recommendation=recommendation,
        recommendation_rationale=rationale,
        synthesized_by=synthesized_by,
    )
