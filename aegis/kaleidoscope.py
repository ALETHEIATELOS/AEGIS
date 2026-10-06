"""The computational kaleidoscope, pushed further.

v0.1 turned the evidence through independent perspectives once. v0.2 adds
four mechanisms that deepen the kaleidoscope without weakening the
governance around it:

1. Reframing — a perspective's conclusion re-expressed through ANOTHER
   standpoint's lens. Not a new opinion: the same conclusion, stress-tested
   against a foreign value system. "What does the growth case look like to
   someone who only cares about downside?" Recorded as an immutable
   Reframing with full provenance.

2. Structured rebuttal — the explicit, named mechanism by which a
   perspective may respond to a recorded contradiction. Bounded exposure:
   the rebutting agent sees the contradiction's topic and the positions
   taken on THAT topic — never another perspective's full reasoning.
   Rebuttals produce second-generation perspectives; the first generation is
   kept. The audit trail shows the disagreement evolving, not being edited.

3. Sensitivity analysis — deterministic and LLM-free: for each evidence
   item, recompute the synthesis's combined confidence excluding every
   perspective that cited it. The delta is the item's leverage — which
   evidence the recommendation hinges on. This is research question 5 made
   operational: change the evidence, see exactly what moves.

4. Minority report — a formal document built from unresolved
   contradictions. Each dissent is stated with its supporting perspectives
   and the evidence they cited, rendered as markdown for the human decider.
   Dissent gets typography, not a footnote.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from aegis.conflict import Contradiction
from aegis.domain import Case
from aegis.perspectives import Perspective
from aegis.synthesis import combine_confidence


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Reframing(BaseModel):
    """One conclusion, re-expressed through a foreign standpoint."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"rf_{uuid4().hex[:12]}")
    perspective_id: str = Field(description="The perspective being reframed.")
    original_conclusion: str
    target_standpoint: str = Field(description="The foreign lens applied.")
    reframed_conclusion: str = Field(
        description="The same conclusion, stress-tested against the foreign lens."
    )
    reasoning: str = Field(description="How the conclusion survives — or fails — the reframe.")
    created_at: datetime = Field(default_factory=_utcnow)
    created_by: str = Field(default="aegis")


class Rebuttal(BaseModel):
    """A perspective's bounded response to a contradiction.

    The rebutting perspective saw the topic and the positions on that topic
    only — the exposure is recorded here so the bound is auditable.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"rb_{uuid4().hex[:12]}")
    contradiction_id: str
    perspective_id: str = Field(description="The perspective responding.")
    exposed_to: tuple[str, ...] = Field(
        description="Exactly what the rebutting agent was shown: topic + positions, nothing more."
    )
    response: str
    conclusion_held: bool = Field(description="True if the perspective holds its conclusion.")
    revised_conclusion: str = Field(
        default="", description="If revised: the new conclusion. Empty if held."
    )
    new_confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=_utcnow)
    created_by: str = Field(default="aegis")


class SensitivityResult(BaseModel):
    """How much the synthesis depends on one evidence item. Deterministic."""

    model_config = ConfigDict(frozen=True)

    evidence_id: str
    combined_confidence_with: float = Field(description="Combined confidence with all perspectives.")
    combined_confidence_without: float = Field(
        description="Combined confidence excluding perspectives that cited this item."
    )
    perspectives_affected: int

    @property
    def leverage(self) -> float:
        """The drop (or rise) in confidence if this evidence were removed.

        Positive leverage: the evidence supports the conclusion — removing it
        weakens the synthesis. Negative leverage: the evidence was cited by
        low-confidence perspectives — removing it strengthens the synthesis.
        Either way, the human sees what the recommendation hinges on.
        """
        return round(self.combined_confidence_with - self.combined_confidence_without, 4)


def sensitivity_analysis(case: Case) -> list[SensitivityResult]:
    """Deterministic sensitivity analysis over the case's evidence.

    Pure function, no model calls. For each evidence item, recompute the
    geometric-mean confidence without the perspectives that cited it.
    Sorted by absolute leverage, most load-bearing first.
    """
    if not case.perspectives:
        return []
    all_confidences = [p.confidence for p in case.perspectives]
    baseline = combine_confidence(all_confidences)
    results: list[SensitivityResult] = []
    for item in case.evidence:
        citing = [p for p in case.perspectives if item.id in p.evidence_ids]
        remaining = [p.confidence for p in case.perspectives if item.id not in p.evidence_ids]
        results.append(SensitivityResult(
            evidence_id=item.id,
            combined_confidence_with=baseline,
            combined_confidence_without=combine_confidence(remaining),
            perspectives_affected=len(citing),
        ))
    return sorted(results, key=lambda r: abs(r.leverage), reverse=True)


class DissentEntry(BaseModel):
    """One unresolved dissent, with its supporters and their evidence."""

    model_config = ConfigDict(frozen=True)

    contradiction_id: str
    topic: str
    positions: dict[str, str] = Field(description="perspective name -> position on the topic.")
    evidence_ids: tuple[str, ...] = Field(description="Evidence cited by the dissenting perspectives.")


class MinorityReport(BaseModel):
    """The formal minority report: every unresolved dissent, stated fully.

    This is the document the human decider reads alongside the
    recommendation. It exists because a synthesis that buries dissent is a
    synthesis that cannot be trusted.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"mr_{uuid4().hex[:12]}")
    case_id: str
    dissents: tuple[DissentEntry, ...]
    generated_at: datetime = Field(default_factory=_utcnow)
    generated_by: str = Field(default="aegis")

    def to_markdown(self) -> str:
        lines = ["# Minority Report", "",
                 f"Case `{self.case_id}` — {len(self.dissents)} unresolved dissent(s).",
                 "",
                 "> Dissent is part of the output. A recommendation that hides "
                 "disagreement cannot be trusted.",
                 ""]
        for i, d in enumerate(self.dissents, 1):
            lines.append(f"## Dissent {i}: {d.topic}")
            lines.append("")
            for name, position in d.positions.items():
                lines.append(f"- **{name}**: {position}")
            if d.evidence_ids:
                lines.append("")
                lines.append(f"Evidence cited: {', '.join(f'`{e}`' for e in d.evidence_ids)}")
            lines.append("")
        return "\n".join(lines)


def build_minority_report(case: Case,
                          name_by_id: dict[str, str] | None = None) -> MinorityReport:
    """Build the minority report from the case's unresolved contradictions."""
    name_by_id = name_by_id or {p.id: p.name for p in case.perspectives}
    evidence_by_perspective = {p.id: p.evidence_ids for p in case.perspectives}
    dissents: list[DissentEntry] = []
    for c in case.unresolved_contradictions():
        positions = {name_by_id.get(pid, pid): pos for pid, pos in c.positions.items()}
        ev_ids = tuple(sorted({e for pid in c.positions for e in evidence_by_perspective.get(pid, ())}))
        dissents.append(DissentEntry(
            contradiction_id=c.id,
            topic=c.topic,
            positions=positions,
            evidence_ids=ev_ids,
        ))
    return MinorityReport(case_id=case.id, dissents=tuple(dissents))


def second_generation(base: Perspective, *, rebuttal: Rebuttal,
                      reasoning: str, formed_by: str) -> Perspective:
    """Produce a second-generation perspective from a rebuttal.

    The first generation is kept — this is a new perspective that responds
    to a contradiction, not an edit of the old one.
    """
    conclusion = rebuttal.revised_conclusion if not rebuttal.conclusion_held else base.conclusion
    return Perspective(
        name=base.name,
        standpoint=base.standpoint,
        evidence_ids=base.evidence_ids,
        reasoning=reasoning,
        conclusion=conclusion,
        confidence=rebuttal.new_confidence,
        formed_by=formed_by,
        generation=2,
        responds_to=(rebuttal.contradiction_id,),
    )


def contradiction_exposure(contradiction: Contradiction,
                           name_by_id: dict[str, str]) -> tuple[str, ...]:
    """The bounded exposure for a rebuttal: topic + positions, nothing more.

    Returns human-readable lines. This is the entire informational content a
    rebutting agent is permitted to see about other perspectives.
    """
    lines = [f"Topic: {contradiction.topic}"]
    for pid, pos in contradiction.positions.items():
        lines.append(f"- {name_by_id.get(pid, pid)}: {pos}")
    return tuple(lines)
