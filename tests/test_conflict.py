"""Research Q2/Q3: independent perspectives; disagreement without forced consensus."""

from aegis.conflict import Contradiction, ContradictionStatus, RiskFactor, RiskScenario
from aegis.perspectives import Perspective


def make_perspective(name, evidence_ids=(), confidence=0.6):
    return Perspective(
        name=name,
        standpoint=f"standpoint of {name}",
        evidence_ids=tuple(evidence_ids),
        reasoning=f"reasoning of {name}",
        conclusion=f"conclusion of {name}",
        confidence=confidence,
    )


def test_perspectives_bind_to_their_own_evidence():
    a = make_perspective("A", evidence_ids=["ev_1", "ev_2"])
    b = make_perspective("B", evidence_ids=["ev_2", "ev_3"])
    assert a.shares_evidence_with(b) == {"ev_2"}
    assert a.evidence_overlap_ratio(b) == 0.5
    # Same evidence, different conclusions: the divergence is interpretation, and it is visible.
    assert a.conclusion != b.conclusion


def test_contradiction_recorded_unresolved_by_default():
    a = make_perspective("A")
    b = make_perspective("B")
    cx = Contradiction(
        topic="Should we proceed?",
        positions={a.id: "yes, the upside dominates", b.id: "no, the downside dominates"},
    )
    assert cx.status == ContradictionStatus.UNRESOLVED
    assert cx.is_unresolved


def test_contradiction_resolution_requires_a_basis_and_preserves_history():
    a = make_perspective("A")
    b = make_perspective("B")
    cx = Contradiction(topic="t", positions={a.id: "yes", b.id: "no"})
    try:
        cx.resolve(actor="kai", resolution="")
        assert False, "should have raised"
    except ValueError:
        pass
    resolved = cx.resolve(actor="kai", resolution="new evidence ev_9 settled the factual dispute")
    assert resolved.status == ContradictionStatus.RESOLVED
    assert cx.status == ContradictionStatus.UNRESOLVED  # original record stands


def test_risk_score_is_deterministic():
    f = RiskFactor(name="supplier delay", likelihood=0.4, impact=0.8)
    assert f.score == 0.32
    assert f.severity() == "medium"
    assert RiskFactor(name="x", likelihood=0.9, impact=0.9).severity() == "high"


def test_scenario_uncertainty_propagation_is_transparent():
    s = RiskScenario(
        name="demand shock",
        assumptions=("recession in H2",),
        projected_outcome="revenue -30%",
        raw_probability=0.5,
        evidence_reliabilities=(0.9, 0.4),  # weakest link dominates
    )
    assert s.evidence_discount == 0.4
    assert s.adjusted_probability == 0.2
    assert s.adjusted_probability <= s.raw_probability
