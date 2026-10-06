"""Research Q8: the same architecture generalizes across decision domains.

The machinery (evidence -> perspectives -> conflict -> synthesis ->
readiness -> gate) is domain-free. Domain knowledge lives in the evidence
and the standpoints, never in the pipeline.
"""

from aegis.authority import DecisionState
from aegis.domain import Case
from aegis.evidence import Evidence, EvidenceKind
from aegis.readiness import ReadinessStatus
from aegis.runtime import AegisOrchestrator


def run_domain_pipeline(domain: str, question: str, facts: list[str],
                        standpoints: list[str]) -> Case:
    case = Case(question=question, domain=domain)
    for i, fact in enumerate(facts):
        case.add_evidence(Evidence(
            content=fact, kind=EvidenceKind.SUPPLIED_FACT,
            source=f"{domain} source {i}", reliability=0.8,
        ))
    orch = AegisOrchestrator(model_name="test")
    orch.run_perspectives(case, standpoints=standpoints)
    orch.run_contradiction_review(case)
    orch.run_synthesis(case)
    return case


def test_same_pipeline_two_domains():
    investment = run_domain_pipeline(
        domain="investment_review",
        question="Should the fund take a position?",
        facts=["Drawdown risk is 12%.", "Correlation to book is 0.3."],
        standpoints=["risk management", "return maximization"],
    )
    vendor = run_domain_pipeline(
        domain="vendor_selection",
        question="Which supplier should we sign?",
        facts=["Bid A is 8% cheaper.", "Bid B has 99.9% SLA history."],
        standpoints=["cost discipline", "reliability engineering"],
    )
    for case in (investment, vendor):
        assert case.gate.state == DecisionState.SYNTHESIZED
        assert case.synthesis is not None
        assert case.synthesis.is_authorization is False
        assert case.assess_readiness().status == ReadinessStatus.READY_FOR_HUMAN_AUTHORITY
        # Domain travels with the case; the pipeline never needed to know it.
        assert case.domain in ("investment_review", "vendor_selection")
