"""The domain-agnostic Case envelope.

Research question 8: can the architecture generalize across consequential
decision domains?

The Case is deliberately free of domain content. It holds a question, the
evidence, the perspectives, the contradictions, the risk assessment, the
synthesis, and the decision gate — the institutional machinery is identical
whether the domain is investment review, vendor selection, hiring, or
anything else consequential. Domain knowledge lives in the evidence and in
the standpoints the perspectives are given, never in the machinery.

A Case is a working envelope (mutable while the case is open); everything
it produces that matters — perspectives, contradictions, syntheses,
records — is immutable and also lands in the DecisionLog.
"""

from __future__ import annotations

from uuid import uuid4

from aegis.authority import DecisionGate, DecisionState
from aegis.conflict import Contradiction, RiskAssessment
from aegis.evidence import Evidence
from aegis.perspectives import Perspective
from aegis.readiness import ReadinessPolicy, ReadinessResult, assess_readiness
from aegis.synthesis import Synthesis


class Case:
    """One consequential decision, from question to record."""

    def __init__(self, question: str, domain: str, case_id: str | None = None):
        self.id = case_id or f"case_{uuid4().hex[:12]}"
        self.question = question
        self.domain = domain
        self.evidence: list[Evidence] = []
        self.perspectives: list[Perspective] = []
        self.contradictions: list[Contradiction] = []
        self.risk_assessment: RiskAssessment | None = None
        self.synthesis: Synthesis | None = None
        self.gate = DecisionGate()

    # -- evidence --------------------------------------------------------

    def add_evidence(self, item: Evidence) -> Evidence:
        self.evidence.append(item)
        if self.gate.state == DecisionState.DRAFT:
            from aegis.authority import Actor, ActorKind
            self.gate.advance(DecisionState.EVIDENCE_COLLECTED,
                              Actor(ActorKind.SYSTEM, "aegis"),
                              note=f"evidence collected: {item.id}")
        return item

    def evidence_by_id(self, evidence_id: str) -> Evidence:
        for item in self.evidence:
            if item.id == evidence_id:
                return item
        raise KeyError(f"Unknown evidence id: {evidence_id}")

    # -- perspectives -----------------------------------------------------

    def add_perspective(self, perspective: Perspective) -> Perspective:
        unknown = [eid for eid in perspective.evidence_ids
                   if eid not in {e.id for e in self.evidence}]
        if unknown:
            raise ValueError(
                f"Perspective {perspective.id} cites unknown evidence: {unknown}. "
                "Perspectives may only cite evidence in the case."
            )
        self.perspectives.append(perspective)
        return perspective

    # -- conflict ----------------------------------------------------------

    def add_contradiction(self, contradiction: Contradiction) -> Contradiction:
        perspective_ids = {p.id for p in self.perspectives}
        unknown = [pid for pid in contradiction.positions if pid not in perspective_ids]
        if unknown:
            raise ValueError(
                f"Contradiction {contradiction.id} references unknown perspectives: {unknown}."
            )
        self.contradictions.append(contradiction)
        return contradiction

    def unresolved_contradictions(self) -> list[Contradiction]:
        return [c for c in self.contradictions if c.is_unresolved]

    # -- readiness ----------------------------------------------------------

    def assess_readiness(self, policy: ReadinessPolicy | None = None,
                         known_unrecorded: int = 0) -> ReadinessResult:
        """Run the deterministic readiness check against current case state.

        known_unrecorded: disagreements the operators know about that were
        never recorded as contradictions. Honesty input — the check trusts
        it, which is why recording dissent is a discipline, not just a type.
        """
        return assess_readiness(
            n_perspectives=len(self.perspectives),
            has_synthesis=self.synthesis is not None,
            n_evidence=len(self.evidence),
            unrecorded_contradictions=known_unrecorded,
            combined_confidence=self.synthesis.combined_confidence if self.synthesis else 0.0,
            policy=policy,
        )
