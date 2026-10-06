"""Research Q6: recommendation, authorization, and execution are distinct states.

The load-bearing tests in AEGIS. If any of these fail, the architecture's
foundational principle is broken.
"""

import pytest

from aegis.authority import (
    Actor,
    AuthorityViolation,
    DecisionGate,
    DecisionState,
    IllegalTransition,
)


def ready_gate() -> DecisionGate:
    """Drive a gate through the analytical pipeline to READY_FOR_HUMAN_AUTHORITY."""
    sys = Actor.agent("aegis")
    gate = DecisionGate()
    for state in (DecisionState.EVIDENCE_COLLECTED, DecisionState.PERSPECTIVES_FORMED,
                  DecisionState.CONFLICT_ANALYZED, DecisionState.SYNTHESIZED,
                  DecisionState.READY_FOR_HUMAN_AUTHORITY):
        gate.advance(state, sys)
    return gate


def test_recommendation_is_not_authorization():
    gate = ready_gate()
    # READY_FOR_HUMAN_AUTHORITY means "fit to be placed before a human."
    # It authorizes nothing.
    assert gate.state == DecisionState.READY_FOR_HUMAN_AUTHORITY
    assert gate.state != DecisionState.AUTHORIZED


def test_agent_cannot_authorize():
    gate = ready_gate()
    with pytest.raises(AuthorityViolation):
        gate.authorize(Actor.agent("aegis"), rationale="the analysis is conclusive")
    with pytest.raises(AuthorityViolation):
        gate.execute(Actor.agent("aegis"))
    assert gate.state == DecisionState.READY_FOR_HUMAN_AUTHORITY  # unchanged


def test_only_human_authorizes_and_only_from_ready():
    gate = ready_gate()
    human = Actor.human("wendy")
    gate.authorize(human, rationale="I accept the recommendation and own the consequences.")
    assert gate.state == DecisionState.AUTHORIZED
    assert gate.state != DecisionState.EXECUTED  # authorized is not executed


def test_authorization_requires_a_stated_rationale():
    gate = ready_gate()
    with pytest.raises(ValueError, match="rationale"):
        gate.authorize(Actor.human("wendy"), rationale="")


def test_execution_only_from_authorized():
    gate = ready_gate()
    human = Actor.human("wendy")
    with pytest.raises(IllegalTransition):
        gate.execute(human, note="jumping the gun")
    gate.authorize(human, rationale="proceed")
    gate.execute(human, note="executed per authorization")
    assert gate.state == DecisionState.EXECUTED


def test_authorized_without_execution_stays_authorized():
    gate = ready_gate()
    gate.authorize(Actor.human("wendy"), rationale="proceed when ready")
    # The gate never executes on anyone's behalf.
    assert gate.state == DecisionState.AUTHORIZED


def test_illegal_transitions_are_closed():
    gate = DecisionGate()
    with pytest.raises(IllegalTransition):
        gate.advance(DecisionState.AUTHORIZED, Actor.agent("aegis"))  # must use authorize()
    with pytest.raises(IllegalTransition):
        gate.advance(DecisionState.EXECUTED, Actor.human("wendy"))    # must use execute()


def test_reject_and_hold_are_human_only():
    for method in ("reject", "hold"):
        gate = ready_gate()
        with pytest.raises(AuthorityViolation):
            getattr(gate, method)(Actor.agent("aegis"), rationale="x")
    gate = ready_gate()
    gate.hold(Actor.human("wendy"), rationale="waiting on counsel")
    assert gate.state == DecisionState.HELD
    # A held case can be released back for re-decision — by a human.
    gate.advance(DecisionState.READY_FOR_HUMAN_AUTHORITY, Actor.human("wendy"))


def test_supersession_retires_without_rewriting():
    gate = ready_gate()
    human = Actor.human("wendy")
    gate.authorize(human, rationale="v1 decision")
    gate.execute(human)
    gate.supersede(human, rationale="v2 case opened with new evidence")
    assert gate.state == DecisionState.SUPERSEDED
    assert len(gate.history) == 8  # every transition recorded, none erased


def test_system_actor_cannot_authorize_either():
    from aegis.authority import ActorKind
    gate = ready_gate()
    with pytest.raises(AuthorityViolation):
        gate.authorize(Actor(ActorKind.SYSTEM, "cron"), rationale="scheduled")
