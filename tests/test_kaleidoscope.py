"""Kaleidoscope v0.2: reframing, rebuttal, sensitivity, minority report."""

from aegis.conflict import Contradiction
from aegis.domain import Case
from aegis.evidence import Evidence, EvidenceKind
from aegis.kaleidoscope import (
    Rebuttal,
    build_minority_report,
    contradiction_exposure,
    second_generation,
    sensitivity_analysis,
)
from aegis.perspectives import Perspective
from aegis.runtime import AegisOrchestrator
from aegis.synthesis import combine_confidence


def make_case() -> Case:
    case = Case(question="Should we proceed?", domain="test")
    for i, content in enumerate(["revenue is strong", "costs are rising", "market is flat"]):
        case.add_evidence(Evidence(content=content, kind=EvidenceKind.SUPPLIED_FACT,
                                   source=f"src{i}", reliability=0.8))
    return case


def add_perspective(case: Case, name: str, ev_indexes: list[int], confidence: float) -> Perspective:
    ev_ids = tuple(case.evidence[i].id for i in ev_indexes)
    p = Perspective(name=name, standpoint=f"{name} lens", evidence_ids=ev_ids,
                    reasoning=f"{name} reasoning", conclusion=f"{name} conclusion",
                    confidence=confidence)
    case.add_perspective(p)
    return p


def test_sensitivity_is_deterministic_and_correct():
    case = make_case()
    add_perspective(case, "A", [0], 0.9)
    add_perspective(case, "B", [0, 1], 0.5)
    add_perspective(case, "C", [1, 2], 0.8)

    r1 = sensitivity_analysis(case)
    r2 = sensitivity_analysis(case)
    assert [r.evidence_id for r in r1] == [r.evidence_id for r in r2]  # deterministic

    baseline = combine_confidence([0.9, 0.5, 0.8])
    by_ev = {r.evidence_id: r for r in r1}
    ev_a, ev_b, ev_c = (case.evidence[i].id for i in range(3))

    # ev_a cited by A(0.9), B(0.5): without -> [0.8]
    assert by_ev[ev_a].perspectives_affected == 2
    assert by_ev[ev_a].combined_confidence_without == combine_confidence([0.8])
    assert by_ev[ev_a].combined_confidence_with == baseline
    # removing the low-confidence B strengthens the synthesis -> negative leverage
    assert by_ev[ev_a].leverage < 0

    # ev_c cited only by C(0.8): without -> geomean(0.9, 0.5) < baseline
    assert by_ev[ev_c].perspectives_affected == 1
    assert by_ev[ev_c].leverage > 0  # load-bearing: removing it weakens the synthesis

    # sorted by absolute leverage, most load-bearing first
    leverages = [abs(r.leverage) for r in r1]
    assert leverages == sorted(leverages, reverse=True)


def test_sensitivity_empty_case():
    assert sensitivity_analysis(Case(question="q", domain="d")) == []


def test_rebuttal_round_produces_gen2_with_bounded_exposure():
    case = make_case()
    a = add_perspective(case, "A", [0], 0.8)
    b = add_perspective(case, "B", [1], 0.6)
    cx = case.add_contradiction(Contradiction(
        topic="timing", positions={a.id: "now", b.id: "later"}))

    orch = AegisOrchestrator(model_name="test")
    gen2 = orch.run_rebuttal_round(case)

    assert len(gen2) == 2  # one rebuttal per involved perspective
    assert len(case.perspectives) == 4  # gen 1 kept
    name_by_id = {p.id: p.name for p in case.perspectives if p.generation == 1}
    for g in gen2:
        assert g.generation == 2
        assert g.responds_to == (cx.id,)
        assert g.name in (a.name, b.name)


def test_second_generation_holds_or_revises():
    case = make_case()
    base = add_perspective(case, "A", [0], 0.8)
    held = Rebuttal(contradiction_id="cx_1", perspective_id=base.id,
                    exposed_to=("Topic: t",), response="I hold.",
                    conclusion_held=True, new_confidence=0.85)
    g = second_generation(base, rebuttal=held, reasoning="r", formed_by="t")
    assert g.conclusion == base.conclusion
    assert g.confidence == 0.85
    assert g.generation == 2

    revised = Rebuttal(contradiction_id="cx_1", perspective_id=base.id,
                       exposed_to=("Topic: t",), response="Fair point.",
                       conclusion_held=False, revised_conclusion="new view",
                       new_confidence=0.5)
    g2 = second_generation(base, rebuttal=revised, reasoning="r", formed_by="t")
    assert g2.conclusion == "new view"


def test_contradiction_exposure_is_bounded():
    case = make_case()
    a = add_perspective(case, "A", [0], 0.8)
    b = add_perspective(case, "B", [1], 0.6)
    cx = Contradiction(topic="timing", positions={a.id: "now", b.id: "later"})
    exposure = contradiction_exposure(cx, {a.id: "A", b.id: "B"})
    text = "\n".join(exposure)
    assert "timing" in text and "now" in text and "later" in text
    # Full reasoning is NOT exposed — only topic + positions.
    assert a.reasoning not in text and b.reasoning not in text


def test_reframing_records():
    case = make_case()
    a = add_perspective(case, "A", [0], 0.8)
    b = add_perspective(case, "B", [1], 0.6)
    orch = AegisOrchestrator(model_name="test")
    reframings = orch.run_reframing(case, pairs=[(a.id, b.standpoint)])
    assert len(reframings) == 1
    r = reframings[0]
    assert r.perspective_id == a.id
    assert r.original_conclusion == a.conclusion
    assert r.target_standpoint == b.standpoint
    assert r.reframed_conclusion  # the test model fills something


def test_minority_report_names_dissent():
    case = make_case()
    a = add_perspective(case, "A", [0], 0.8)
    b = add_perspective(case, "B", [1], 0.6)
    case.add_contradiction(Contradiction(
        topic="Should we proceed now?", positions={a.id: "yes", b.id: "no"}))
    report = build_minority_report(case)
    assert len(report.dissents) == 1
    d = report.dissents[0]
    assert d.positions == {"A": "yes", "B": "no"}
    assert set(d.evidence_ids) == {case.evidence[0].id, case.evidence[1].id}
    md = report.to_markdown()
    assert "# Minority Report" in md and "Should we proceed now?" in md
