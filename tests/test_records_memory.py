"""Research Q5 + Q7: reconstruct why a decision changed; learn without
corrupting history."""

import pytest

from aegis.authority import Actor, DecisionState
from aegis.evidence import Evidence, EvidenceKind
from aegis.memory import EpistemicMemory, Lesson, reconstruct
from aegis.outcomes import Observation, Outcome
from aegis.records import DecisionLog, DecisionRecord, actor_name_for_record


def make_record(case_id, fps, state=DecisionState.AUTHORIZED, authorized_by="wendy"):
    return DecisionRecord(
        case_id=case_id,
        question="Should we proceed?",
        state=state,
        recommendation="Proceed.",
        evidence_fingerprints=tuple(fps),
        authorized_by=authorized_by if state == DecisionState.AUTHORIZED else None,
    )


def test_log_is_append_only_and_chronological():
    log = DecisionLog()
    r1 = make_record("case_1", ["fp_a", "fp_b"])
    r2 = make_record("case_1", ["fp_a", "fp_b", "fp_c"])
    log.add(r1)
    log.add(r2)
    assert log.for_case("case_1") == [r1, r2]
    assert log.latest_for_case("case_1") == r2
    assert len(log) == 2
    with pytest.raises(TypeError):
        log.add("not a record")  # type: ignore[arg-type]


def test_reconstruct_explains_why_a_decision_changed():
    log = DecisionLog()
    log.add(make_record("case_1", ["fp_a", "fp_b"]))
    log.add(make_record("case_1", ["fp_a", "fp_c"]))  # fp_b out, fp_c in
    steps = reconstruct("case_1", log)
    assert len(steps) == 2
    assert steps[1]["evidence_added"] == ["fp_c"]
    assert steps[1]["evidence_removed"] == ["fp_b"]
    assert steps[1]["evidence_unchanged"] == ["fp_a"]


def test_learning_does_not_mutate_records():
    log = DecisionLog()
    record = make_record("case_1", ["fp_a"])
    log.add(record)

    outcome = Outcome(record_id=record.id, case_id="case_1",
                      description="Demand collapsed; the cautious case was right.",
                      observer="wendy")
    Observation(
        outcome_id=outcome.id, case_id="case_1",
        expected="Steady demand growth.",
        divergence="Demand fell 40% in Q1.",
        lesson_candidate="Weight demand-side evidence more heavily in cyclical domains.",
    )
    memory = EpistemicMemory()
    memory.add(Lesson(
        text="In cyclical domains, demand-side evidence deserves higher weight.",
        record_refs=(record.id,),
        outcome_refs=(outcome.id,),
        learned_by="wendy",
    ))

    # The record is untouched by everything learned after it.
    assert log.latest_for_case("case_1") == record
    assert record.evidence_fingerprints == ("fp_a",)
    assert len(memory.lessons_for_case("case_1", log)) == 1


def test_lessons_supersede_by_reference_not_edit():
    memory = EpistemicMemory()
    old = memory.add(Lesson(text="old lesson", learned_by="wendy"))
    new = memory.add(Lesson(text="corrected lesson", supersedes=(old.id,), learned_by="wendy"))
    assert old.text == "old lesson"  # the old lesson stands, unedited
    assert new.supersedes == (old.id,)
    assert len(memory) == 2


def test_authorized_record_must_name_a_human():
    with pytest.raises(ValueError, match="must name the human"):
        DecisionRecord(
            case_id="case_1", question="q", state=DecisionState.AUTHORIZED,
            recommendation="r", authorized_by=None,
        )
    with pytest.raises(ValueError, match="humans only"):
        actor_name_for_record(Actor.agent("aegis"))
    assert actor_name_for_record(Actor.human("wendy")) == "wendy"
