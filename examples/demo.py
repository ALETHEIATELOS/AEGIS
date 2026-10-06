"""End-to-end AEGIS demo: one consequential decision, fully governed.

Runs offline with Pydantic AI's test model. For a live run, pass a real
model name: AegisOrchestrator(model_name="openai:gpt-4o").

The demo walks the whole institutional pipeline:
  evidence -> perspectives -> conflict/risk -> synthesis -> readiness
  -> HUMAN AUTHORIZATION (simulated by the operator) -> record
  -> outcome -> observation -> epistemic memory
"""

from aegis.authority import Actor, DecisionState
from aegis.conflict import RiskAssessment, RiskFactor, RiskScenario
from aegis.domain import Case
from aegis.evidence import Evidence, EvidenceKind
from aegis.memory import EpistemicMemory, Lesson, reconstruct
from aegis.outcomes import Observation, Outcome
from aegis.records import DecisionLog, DecisionRecord
from aegis.runtime import AegisOrchestrator


def main() -> None:
    human = Actor.human("operator")
    log = DecisionLog()
    memory = EpistemicMemory()

    # 1. Evidence — immutable, provenance-chained.
    case = Case(
        question="Should we launch the new product line in Q1?",
        domain="product_strategy",
    )
    case.add_evidence(Evidence(
        content="Unit cost is $18 at 10k units.",
        kind=EvidenceKind.SUPPLIED_FACT, source="supplier quote", reliability=0.85,
    ).with_provenance("operator", "collected", "from Q4 supplier pack"))
    case.add_evidence(Evidence(
        content="Two competitors launched similar lines last quarter.",
        kind=EvidenceKind.SUPPORTED_EVIDENCE, source="market scan", reliability=0.7,
    ))
    case.add_evidence(Evidence(
        content="Demand will grow 20% next year.",
        kind=EvidenceKind.ASSUMPTION, source="analyst note", reliability=0.4,
    ))

    # 2-4. Perspectives, contradiction review, synthesis — agent-run, governed.
    orch = AegisOrchestrator(model_name="test")
    perspectives = orch.run_perspectives(
        case,
        standpoints=["financial conservatism", "growth optimism", "operational pragmatism"],
    )
    contradictions = orch.run_contradiction_review(case)

    case.risk_assessment = RiskAssessment(
        factors=(
            RiskFactor(name="demand shortfall", description="assumed growth does not materialize",
                       likelihood=0.45, impact=0.8,
                       evidence_ids=(case.evidence[2].id,)),
            RiskFactor(name="competitor response", likelihood=0.6, impact=0.5,
                       evidence_ids=(case.evidence[1].id,)),
        ),
        scenarios=(
            RiskScenario(name="soft launch", assumptions=("demand flat",),
                         projected_outcome="break-even in 9 months",
                         raw_probability=0.5, evidence_reliabilities=(0.4, 0.7)),
        ),
    )

    synthesis = orch.run_synthesis(case)
    print(f"--- synthesis {synthesis.id} ---")
    print(f"agreements: {list(synthesis.agreements)}")
    print(f"preserved dissents: {list(synthesis.preserved_dissents)}")
    print(f"combined confidence: {synthesis.combined_confidence:.2f}")
    print(f"recommendation: {synthesis.recommendation}")
    print(f"is_authorization: {synthesis.is_authorization}")

    # 5. Readiness — deterministic, LLM-free.
    readiness = case.assess_readiness()
    print(f"\nreadiness: {readiness.status.value}")
    for reason in readiness.reasons:
        print(f"  - {reason}")
    case.gate.advance(DecisionState.READY_FOR_HUMAN_AUTHORITY, Actor.agent("aegis"))

    # 6. THE GATE. Nothing before this line authorized anything.
    #    In production this is a human hand, not a script.
    case.gate.authorize(human, rationale="I accept the recommendation and own the consequences.")
    print(f"\ngate state: {case.gate.state.value} (by {human.identity})")

    record = DecisionRecord(
        case_id=case.id,
        question=case.question,
        state=case.gate.state,
        synthesis_id=synthesis.id,
        recommendation=synthesis.recommendation,
        evidence_fingerprints=tuple(e.fingerprint() for e in case.evidence),
        authorized_by=human.identity,
        authorization_rationale="I accept the recommendation and own the consequences.",
    )
    log.add(record)

    # 7. Outcome + observation, later. History is not rewritten.
    outcome = Outcome(record_id=record.id, case_id=case.id,
                      description="Launch beat break-even by 2 months.",
                      observer="operator")
    observation = Observation(
        outcome_id=outcome.id, case_id=case.id,
        expected="Break-even in 9 months under soft-launch scenario.",
        divergence="Faster by 2 months; competitor response was milder than feared.",
        lesson_candidate="Competitor-response risk was overstated for this segment.",
    )
    memory.add(Lesson(
        text=observation.lesson_candidate,
        record_refs=(record.id,), outcome_refs=(outcome.id,),
        learned_by="operator",
    ))

    # 8. Reconstruction: why did the decision stand as it does?
    print("\n--- reconstruction ---")
    for step in reconstruct(case.id, log):
        print(f"step {step['sequence']}: {step['state']} "
              f"(record {step['record_id']}, authorized by {step['authorized_by']})")

    print(f"\nperspectives: {len(perspectives)}, contradictions: {len(contradictions)}, "
          f"lessons in memory: {len(memory)}")
    print("done. recommendation ≠ authorization ≠ execution — the gate held.")


if __name__ == "__main__":
    main()
