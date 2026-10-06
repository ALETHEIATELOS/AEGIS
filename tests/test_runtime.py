"""Research Q2/Q3/Q8 (runtime): the full pipeline with Pydantic AI test models.

Runs fully offline (model="test"). Asserts structure and governance, not
model prose: perspectives formed independently, contradictions recorded
unresolved, synthesis preserves dissent, pipeline stops at the gate.
"""

from aegis.authority import Actor, DecisionState
from aegis.domain import Case
from aegis.evidence import Evidence, EvidenceKind
from aegis.readiness import ReadinessStatus
from aegis.runtime import AegisOrchestrator


def build_case() -> Case:
    case = Case(
        question="Should we launch the new product line in Q1?",
        domain="product_strategy",
    )
    case.add_evidence(Evidence(
        content="Unit cost is $18 at 10k units.",
        kind=EvidenceKind.SUPPLIED_FACT, source="supplier quote", reliability=0.85,
    ))
    case.add_evidence(Evidence(
        content="Two competitors launched similar lines last quarter.",
        kind=EvidenceKind.SUPPORTED_EVIDENCE, source="market scan", reliability=0.7,
    ))
    case.add_evidence(Evidence(
        content="Demand will grow 20% next year.",
        kind=EvidenceKind.ASSUMPTION, source="analyst note", reliability=0.4,
    ))
    return case


def test_full_pipeline_stops_at_the_gate():
    case = build_case()
    orch = AegisOrchestrator(model_name="test")

    perspectives = orch.run_perspectives(
        case, standpoints=["financial conservatism", "growth optimism", "operational pragmatism"]
    )
    assert len(perspectives) == 3
    assert case.gate.state == DecisionState.PERSPECTIVES_FORMED
    # Each perspective declares its standpoint and cites real evidence.
    evidence_ids = {e.id for e in case.evidence}
    for p in perspectives:
        assert p.standpoint
        assert set(p.evidence_ids) <= evidence_ids

    orch.run_contradiction_review(case)
    assert case.gate.state == DecisionState.CONFLICT_ANALYZED
    # Contradictions found are recorded UNRESOLVED — the contrarian finds, not resolves.
    for c in case.contradictions:
        assert c.is_unresolved

    synthesis = orch.run_synthesis(case)
    assert case.gate.state == DecisionState.SYNTHESIZED
    assert synthesis.is_authorization is False
    # Unresolved dissent is carried into the synthesis, not hidden.
    assert set(synthesis.preserved_dissents) == {c.id for c in case.unresolved_contradictions()}

    readiness = case.assess_readiness()
    assert readiness.status == ReadinessStatus.READY_FOR_HUMAN_AUTHORITY
    case.gate.advance(DecisionState.READY_FOR_HUMAN_AUTHORITY, Actor.agent("aegis"))

    # The orchestrator cannot cross the gate. A human must.
    assert case.gate.state == DecisionState.READY_FOR_HUMAN_AUTHORITY
    case.gate.authorize(Actor.human("wendy"), rationale="I own this decision.")
    assert case.gate.state == DecisionState.AUTHORIZED


def test_perspective_agents_do_not_see_each_other():
    # Structural independence: each run receives the question + evidence pool
    # only. (Verified by construction in runtime.py; here we assert the
    # outputs carry no cross-references.)
    case = build_case()
    orch = AegisOrchestrator(model_name="test")
    perspectives = orch.run_perspectives(case, standpoints=["A-lens", "B-lens"])
    other_names = {p.name for p in perspectives}
    for p in perspectives:
        for other in other_names - {p.name}:
            assert other not in p.reasoning
