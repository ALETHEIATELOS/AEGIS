"""The acquisition review pipeline: evidence in, decision dossier out."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from aegis.authority import Actor, DecisionState
from aegis.conflict import RiskAssessment, RiskFactor, RiskScenario
from aegis.domain import Case
from aegis.evidence import Evidence, EvidenceKind
from aegis.kaleidoscope import MinorityReport, Reframing, SensitivityResult
from aegis.memory import EpistemicMemory, Lesson
from aegis.outcomes import Observation, Outcome
from aegis.perspectives import Perspective
from aegis.readiness import ReadinessResult
from aegis.records import DecisionLog, DecisionRecord
from aegis.runtime import AegisOrchestrator
from aegis.synthesis import Synthesis
from apps.acquisition_review.dossier import render_dossier
from apps.acquisition_review.standpoints import QUESTION_TEMPLATE, STANDPOINTS


@dataclass
class ReviewResult:
    """Everything the review produced. The dossier is the deliverable."""

    case: Case
    synthesis: Synthesis
    readiness: ReadinessResult
    minority_report: MinorityReport
    sensitivity: list[SensitivityResult]
    reframings: list[Reframing]
    second_generation: list[Perspective]
    dossier_markdown: str
    log: DecisionLog = field(default_factory=DecisionLog)
    memory: EpistemicMemory = field(default_factory=EpistemicMemory)


def load_evidence_file(path: str | Path) -> tuple[list[Evidence], list[RiskFactor], list[RiskScenario], str]:
    """Load a review intake file.

    JSON shape:
    {
      "target": "Harborline Logistics",
      "terms": "…",                       # optional, folded into the question
      "evidence": [
        {"content": "…", "kind": "supplied_fact", "source": "…", "reliability": 0.8}
      ],
      "risks": [                          # optional
        {"name": "…", "description": "…", "likelihood": 0.4, "impact": 0.8}
      ],
      "scenarios": [                      # optional
        {"name": "…", "assumptions": ["…"], "projected_outcome": "…",
         "raw_probability": 0.5, "evidence_reliabilities": [0.8]}
      ]
    }
    """
    data = json.loads(Path(path).read_text())
    target = data.get("target", "the target")
    terms = data.get("terms", "")
    question = QUESTION_TEMPLATE.format(target=target)
    if terms:
        question += f" Proposed terms: {terms}"

    evidence = []
    for item in data.get("evidence", []):
        evidence.append(Evidence(
            content=item["content"],
            kind=EvidenceKind(item.get("kind", "supplied_fact")),
            source=item.get("source", "intake file"),
            reliability=float(item.get("reliability", 0.5)),
        ).with_provenance("operator", "collected", detail=f"from {path}"))

    risks = [RiskFactor(
        name=r["name"],
        description=r.get("description", ""),
        likelihood=float(r.get("likelihood", 0.5)),
        impact=float(r.get("impact", 0.5)),
    ) for r in data.get("risks", [])]

    scenarios = [RiskScenario(
        name=s["name"],
        assumptions=tuple(s.get("assumptions", [])),
        projected_outcome=s.get("projected_outcome", ""),
        raw_probability=float(s.get("raw_probability", 0.5)),
        evidence_reliabilities=tuple(s.get("evidence_reliabilities", ())),
    ) for s in data.get("scenarios", [])]

    return evidence, risks, scenarios, question


def run_acquisition_review(
    evidence_path: str | Path,
    *,
    model_name: str | None = None,
    with_rebuttal: bool = True,
    with_reframing: bool = True,
    standpoints: list[str] | None = None,
) -> ReviewResult:
    """Run the full acquisition review. Stops at the gate — the dossier
    declares READY_FOR_HUMAN_AUTHORITY; authorization happens outside."""
    evidence, risks, scenarios, question = load_evidence_file(evidence_path)
    case = Case(question=question, domain="acquisition_review")
    for item in evidence:
        case.add_evidence(item)

    orch = AegisOrchestrator(model_name=model_name)
    orch.run_perspectives(case, standpoints=standpoints or STANDPOINTS)
    orch.run_contradiction_review(case)

    gen2: list[Perspective] = []
    if with_rebuttal and case.unresolved_contradictions():
        gen2 = orch.run_rebuttal_round(case)

    reframings: list[Reframing] = []
    if with_reframing:
        reframings = orch.run_reframing(case)

    if risks or scenarios:
        case.risk_assessment = RiskAssessment(factors=tuple(risks), scenarios=tuple(scenarios))

    synthesis = orch.run_synthesis(case)
    sensitivity = orch.analyze_sensitivity(case)
    minority_report = orch.minority_report(case)

    readiness = case.assess_readiness()
    if readiness.is_ready:
        case.gate.advance(DecisionState.READY_FOR_HUMAN_AUTHORITY,
                          Actor.agent("aegis"),
                          note="acquisition review complete; awaiting human authorization")

    log = DecisionLog()
    memory = EpistemicMemory()
    dossier = render_dossier(
        case=case, synthesis=synthesis, readiness=readiness,
        minority_report=minority_report, sensitivity=sensitivity,
        reframings=reframings, second_generation=gen2,
    )
    return ReviewResult(
        case=case, synthesis=synthesis, readiness=readiness,
        minority_report=minority_report, sensitivity=sensitivity,
        reframings=reframings, second_generation=gen2,
        dossier_markdown=dossier, log=log, memory=memory,
    )


def record_human_decision(result: ReviewResult, human_name: str,
                          decision: str, rationale: str) -> DecisionRecord:
    """Authorize / reject / hold the reviewed case — a human act, outside
    the pipeline. decision: 'authorize' | 'reject' | 'hold'."""
    human = Actor.human(human_name)
    gate = result.case.gate
    if decision == "authorize":
        gate.authorize(human, rationale=rationale)
    elif decision == "reject":
        gate.reject(human, rationale=rationale)
    elif decision == "hold":
        gate.hold(human, rationale=rationale)
    else:
        raise ValueError(f"Unknown decision: {decision}")
    record = DecisionRecord(
        case_id=result.case.id,
        question=result.case.question,
        state=gate.state,
        synthesis_id=result.synthesis.id,
        recommendation=result.synthesis.recommendation,
        evidence_fingerprints=tuple(e.fingerprint() for e in result.case.evidence),
        authorized_by=human_name if decision == "authorize" else None,
        authorization_rationale=rationale if decision == "authorize" else "",
    )
    result.log.add(record)
    return record


def record_outcome(result: ReviewResult, record: DecisionRecord, *,
                   description: str, observer: str,
                   expected: str, divergence: str,
                   lesson: str, learned_by: str) -> Outcome:
    """After the fact: observe the outcome and bank the lesson — without
    touching the record."""
    outcome = Outcome(record_id=record.id, case_id=result.case.id,
                      description=description, observer=observer)
    result.memory.add(Lesson(
        text=lesson,
        record_refs=(record.id,), outcome_refs=(outcome.id,),
        learned_by=learned_by,
    ))
    Observation(
        outcome_id=outcome.id, case_id=result.case.id,
        expected=expected, divergence=divergence, lesson_candidate=lesson,
    )
    return outcome
