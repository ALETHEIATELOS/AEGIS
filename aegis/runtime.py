"""Agent runtime: Pydantic AI agents governed by the AEGIS architecture.

Pydantic AI provides the agent runtime. AEGIS provides the institutional
intelligence architecture governing how those agents participate in
consequential decisions.

Three agent roles:

1. Perspective agents — one per standpoint. Each receives the case question
   and the evidence pool, NEVER another perspective's reasoning (unless
   explicitly running a rebuttal pass). Independence is enforced by what the
   orchestrator withholds, not by asking nicely.

2. Contrarian agent — reads the formed perspectives and records
   contradictions. Its job is to find disagreement, not to resolve it. New
   contradictions are recorded UNRESOLVED by default.

3. Synthesis agent — reads perspectives and contradictions and produces a
   synthesis draft: agreements, preserved dissents, recommendation. It is
   instructed, structurally and in prose, that its output is a
   recommendation and never an authorization.

The orchestrator runs the analytical pipeline and stops at the gate. It
never authorizes, never executes. Those transitions require a human hand on
DecisionGate.

Defaults to Pydantic AI's test model so the suite and demo run offline.
Pass any pydantic-ai model name (e.g. "openai:gpt-4o") for live runs.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent

from aegis.authority import Actor, ActorKind
from aegis.conflict import Contradiction
from aegis.domain import Case
from aegis.evidence import Evidence
from aegis.perspectives import Perspective
from aegis.synthesis import Synthesis, combine_confidence


# -- structured agent outputs ----------------------------------------------

class PerspectiveDraft(BaseModel):
    """What a perspective agent must return. Structured, citable, bounded."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Short label for this perspective.")
    reasoning: str = Field(description="The reasoning, in this perspective's own terms.")
    conclusion: str = Field(description="What this perspective concludes.")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(
        description="Ids of the evidence items (from the provided pool) this perspective relied on."
    )


class ContradictionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(description="What is disagreed about, stated neutrally.")
    positions: dict[str, str] = Field(
        description="perspective name -> that perspective's position on the topic."
    )


class ContradictionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contradictions: list[ContradictionDraft] = Field(default_factory=list)


class SynthesisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agreements: list[str] = Field(description="What the perspectives genuinely agree on.")
    recommendation: str = Field(description="The recommendation. Analysis only — never an authorization.")
    rationale: str = Field(default="")


# -- agent builders ----------------------------------------------------------

PERSPECTIVE_SYSTEM = """\
You are one independent perspective in an institutional decision process.
You receive a question and a pool of evidence. Another agent with a different
standpoint is analyzing the same question separately; you will never see
their reasoning, and they will never see yours.

Rules:
- Reason ONLY from the standpoint you are given.
- Cite evidence by its id. Never invent evidence. If the evidence is thin,
  say so and lower your confidence — do not fill gaps with imagination.
- Your output is analysis. You do not authorize anything. You do not decide.
"""

CONTRARIAN_SYSTEM = """\
You are the contrarian reviewer in an institutional decision process.
You receive several independently-formed perspectives on the same question.

Your job is to FIND disagreement, not to resolve it:
- Identify topics where perspectives genuinely disagree.
- State each side's position fairly, in neutral language.
- Do NOT pick a winner. Do NOT average positions. Do NOT force consensus.
- If perspectives agree, say nothing about that topic — agreement is the
  synthesis agent's business, not yours.
"""

SYNTHESIS_SYSTEM = """\
You are the synthesis agent in an institutional decision process.
You receive independent perspectives and a list of recorded contradictions.

Your job:
- State what the perspectives genuinely agree on. Do not manufacture agreement.
- Carry every unresolved contradiction forward as preserved dissent — name it
  explicitly so the human decider sees it.
- Produce a RECOMMENDATION with a rationale.
- Your recommendation is analysis, not authority. You do not authorize.
  You do not execute. Those acts belong to a human, outside this system.
"""


def build_perspective_agent(model_name: str = "test") -> Agent[None, PerspectiveDraft]:
    return Agent(model_name, output_type=PerspectiveDraft, system_prompt=PERSPECTIVE_SYSTEM)


def build_contrarian_agent(model_name: str = "test") -> Agent[None, ContradictionReport]:
    return Agent(model_name, output_type=ContradictionReport, system_prompt=CONTRARIAN_SYSTEM)


def build_synthesis_agent(model_name: str = "test") -> Agent[None, SynthesisDraft]:
    return Agent(model_name, output_type=SynthesisDraft, system_prompt=SYNTHESIS_SYSTEM)


def _format_evidence_pool(evidence: list[Evidence]) -> str:
    lines = []
    for e in evidence:
        lines.append(
            f"- [{e.id}] ({e.kind.value}, reliability={e.reliability:.2f}, source={e.source}): {e.content}"
        )
    return "\n".join(lines)


# -- orchestrator ------------------------------------------------------------

class AegisOrchestrator:
    """Runs the analytical pipeline: evidence -> perspectives -> conflict ->
    synthesis -> readiness. Stops at the gate. Never authorizes, never executes."""

    def __init__(self, model_name: str = "test", agent_name: str = "aegis"):
        self.model_name = model_name
        self.agent_name = agent_name
        self._actor = Actor(ActorKind.AGENT, agent_name)
        self.perspective_agent = build_perspective_agent(model_name)
        self.contrarian_agent = build_contrarian_agent(model_name)
        self.synthesis_agent = build_synthesis_agent(model_name)

    def run_perspectives(self, case: Case, standpoints: list[str]) -> list[Perspective]:
        """Run one independent perspective agent per standpoint.

        Each agent sees the question, its standpoint, and the evidence pool —
        nothing else. Provenance records which evidence each perspective cited.
        """
        from aegis.authority import DecisionState
        pool = _format_evidence_pool(case.evidence)
        formed: list[Perspective] = []
        for standpoint in standpoints:
            prompt = (
                f"Question: {case.question}\n\n"
                f"Your standpoint: {standpoint}\n\n"
                f"Evidence pool:\n{pool}\n\n"
                "Form your perspective now."
            )
            result = self.perspective_agent.run_sync(prompt)
            draft: PerspectiveDraft = result.output
            # Keep only evidence ids that actually exist in the case.
            valid_ids = tuple(eid for eid in draft.evidence_ids
                              if eid in {e.id for e in case.evidence})
            perspective = Perspective(
                name=draft.name,
                standpoint=standpoint,
                evidence_ids=valid_ids,
                reasoning=draft.reasoning,
                conclusion=draft.conclusion,
                confidence=draft.confidence,
                formed_by=self.agent_name,
            )
            case.add_perspective(perspective)
            for eid in valid_ids:
                item = case.evidence_by_id(eid)
                idx = case.evidence.index(item)
                case.evidence[idx] = item.with_provenance(
                    self.agent_name, "cited",
                    detail=f"cited by perspective {perspective.id} ({perspective.name})",
                )
            formed.append(perspective)
        if case.gate.state == DecisionState.EVIDENCE_COLLECTED:
            case.gate.advance(DecisionState.PERSPECTIVES_FORMED, self._actor,
                              note=f"{len(formed)} independent perspectives formed")
        return formed

    def run_contradiction_review(self, case: Case) -> list[Contradiction]:
        """Run the contrarian agent over the formed perspectives.

        New contradictions are recorded UNRESOLVED. The contrarian finds
        disagreement; it does not resolve it.
        """
        from aegis.authority import DecisionState
        perspectives_text = "\n\n".join(
            f"Perspective '{p.name}' (id {p.id}, standpoint: {p.standpoint}):\n"
            f"Reasoning: {p.reasoning}\nConclusion: {p.conclusion} "
            f"(confidence {p.confidence:.2f})"
            for p in case.perspectives
        )
        name_to_id = {p.name: p.id for p in case.perspectives}
        result = self.contrarian_agent.run_sync(
            f"Question: {case.question}\n\nPerspectives:\n{perspectives_text}\n\n"
            "Record the contradictions you find."
        )
        report: ContradictionReport = result.output
        recorded: list[Contradiction] = []
        for draft in report.contradictions:
            positions = {name_to_id.get(name, name): pos
                         for name, pos in draft.positions.items()}
            contradiction = Contradiction(
                topic=draft.topic,
                positions=positions,
                recorded_by=self.agent_name,
            )
            case.add_contradiction(contradiction)
            recorded.append(contradiction)
        if case.gate.state == DecisionState.PERSPECTIVES_FORMED:
            case.gate.advance(DecisionState.CONFLICT_ANALYZED, self._actor,
                              note=f"{len(recorded)} contradiction(s) recorded")
        return recorded

    def run_synthesis(self, case: Case) -> Synthesis:
        """Run the synthesis agent. Output is a recommendation — never an
        authorization. Unresolved contradictions are carried as preserved dissent."""
        from aegis.authority import DecisionState
        perspectives_text = "\n\n".join(
            f"Perspective '{p.name}' (id {p.id}): {p.conclusion} "
            f"(confidence {p.confidence:.2f})"
            for p in case.perspectives
        )
        contradictions_text = "\n".join(
            f"- [{c.id}] {c.topic} ({c.status.value}): "
            + "; ".join(f"{pid}: {pos}" for pid, pos in c.positions.items())
            for c in case.contradictions
        ) or "(none recorded)"
        result = self.synthesis_agent.run_sync(
            f"Question: {case.question}\n\nPerspectives:\n{perspectives_text}\n\n"
            f"Recorded contradictions:\n{contradictions_text}\n\n"
            "Produce the synthesis."
        )
        draft: SynthesisDraft = result.output
        dissent_ids = [c.id for c in case.unresolved_contradictions()]
        synthesis = Synthesis(
            case_id=case.id,
            perspective_ids=tuple(p.id for p in case.perspectives),
            agreements=tuple(draft.agreements),
            preserved_dissents=tuple(dissent_ids),
            combined_confidence=combine_confidence([p.confidence for p in case.perspectives]),
            recommendation=draft.recommendation,
            recommendation_rationale=draft.rationale,
            synthesized_by=self.agent_name,
        )
        case.synthesis = synthesis
        if case.gate.state == DecisionState.CONFLICT_ANALYZED:
            case.gate.advance(DecisionState.SYNTHESIZED, self._actor,
                              note=f"synthesis {synthesis.id} produced")
        return synthesis
