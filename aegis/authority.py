"""The decision gate and human authority.

Research question 6: maintain a deterministic distinction between
recommendation, authorization, and execution.

The doctrine, enforced by this module:

    READY FOR HUMAN AUTHORITY ≠ AUTHORIZED ≠ EXECUTED

- A case becomes READY_FOR_HUMAN_AUTHORITY through the deterministic
  readiness check (readiness.py). That is analytical readiness — it means
  "fit to be placed before a human." It authorizes nothing.
- AUTHORIZED happens only through DecisionGate.authorize(), which requires
  an Actor of kind HUMAN. An agent, a tool, or the runtime itself attempting
  to authorize raises AuthorityViolation. Technical connectivity does not
  establish authority.
- EXECUTED happens only through DecisionGate.execute(), which requires the
  case to already be AUTHORIZED. Authorization and execution are separate
  transitions, separately recorded, possibly by different humans at
  different times.

The state machine is explicit and closed: illegal transitions raise
IllegalTransition. There is no back door.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum


class ActorKind(str, Enum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


class Actor:
    """Who is acting. The kind is load-bearing: only HUMAN can authorize."""

    __slots__ = ("kind", "identity")

    def __init__(self, kind: ActorKind, identity: str):
        self.kind = kind
        self.identity = identity

    @classmethod
    def human(cls, identity: str) -> "Actor":
        return cls(ActorKind.HUMAN, identity)

    @classmethod
    def agent(cls, identity: str) -> "Actor":
        return cls(ActorKind.AGENT, identity)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Actor(kind={self.kind.value}, identity={self.identity!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Actor) and self.kind == other.kind and self.identity == other.identity


class DecisionState(str, Enum):
    DRAFT = "draft"
    EVIDENCE_COLLECTED = "evidence_collected"
    PERSPECTIVES_FORMED = "perspectives_formed"
    CONFLICT_ANALYZED = "conflict_analyzed"
    SYNTHESIZED = "synthesized"
    READY_FOR_HUMAN_AUTHORITY = "ready_for_human_authority"
    AUTHORIZED = "authorized"
    REJECTED = "rejected"
    HELD = "held"
    EXECUTED = "executed"
    SUPERSEDED = "superseded"


# The closed transition table. Anything not listed here is illegal.
_TRANSITIONS: dict[DecisionState, frozenset[DecisionState]] = {
    DecisionState.DRAFT: frozenset({DecisionState.EVIDENCE_COLLECTED}),
    DecisionState.EVIDENCE_COLLECTED: frozenset({DecisionState.PERSPECTIVES_FORMED}),
    DecisionState.PERSPECTIVES_FORMED: frozenset({DecisionState.CONFLICT_ANALYZED}),
    DecisionState.CONFLICT_ANALYZED: frozenset({DecisionState.SYNTHESIZED}),
    DecisionState.SYNTHESIZED: frozenset({DecisionState.READY_FOR_HUMAN_AUTHORITY}),
    DecisionState.READY_FOR_HUMAN_AUTHORITY: frozenset({
        DecisionState.AUTHORIZED, DecisionState.REJECTED, DecisionState.HELD,
    }),
    DecisionState.HELD: frozenset({
        DecisionState.READY_FOR_HUMAN_AUTHORITY,  # released back for re-decision
        DecisionState.SUPERSEDED,
    }),
    DecisionState.AUTHORIZED: frozenset({DecisionState.EXECUTED, DecisionState.SUPERSEDED}),
    DecisionState.REJECTED: frozenset({DecisionState.SUPERSEDED}),
    DecisionState.EXECUTED: frozenset({DecisionState.SUPERSEDED}),
    DecisionState.SUPERSEDED: frozenset(),
}


class IllegalTransition(Exception):
    """Raised when a state transition is not in the closed transition table."""


class AuthorityViolation(Exception):
    """Raised when a non-human actor attempts an authority-bearing action.

    This is the load-bearing exception in AEGIS. No model, agent, tool, or
    runtime may grant itself authority.
    """


class DecisionGate:
    """Enforces the decision state machine and the human-authority boundary.

    The gate is deliberately dumb: it knows states, transitions, and actor
    kinds. It contains no model, no judgment, no discretion. Judgment lives
    in the human; analysis lives in the agents; the gate lives in between
    and cannot be argued with.
    """

    def __init__(self, initial: DecisionState = DecisionState.DRAFT):
        self._state = initial
        self._history: list[tuple[datetime, DecisionState, DecisionState, Actor, str]] = []

    @property
    def state(self) -> DecisionState:
        return self._state

    @property
    def history(self):
        return tuple(self._history)

    def _transition(self, to: DecisionState, actor: Actor, note: str = "") -> None:
        allowed = _TRANSITIONS[self._state]
        if to not in allowed:
            raise IllegalTransition(
                f"Cannot transition from {self._state.value} to {to.value}. "
                f"Allowed: {sorted(s.value for s in allowed) or 'none (terminal state)'}."
            )
        self._history.append((datetime.now(timezone.utc), self._state, to, actor, note))
        self._state = to

    # -- analytical pipeline (no authority involved) -------------------------

    def advance(self, to: DecisionState, actor: Actor, note: str = "") -> None:
        """Advance through the analytical states up to READY_FOR_HUMAN_AUTHORITY.

        Refuses to cross the authority boundary: use authorize()/reject()/
        hold() for those transitions.
        """
        if to in (DecisionState.AUTHORIZED, DecisionState.REJECTED,
                  DecisionState.HELD, DecisionState.EXECUTED):
            raise IllegalTransition(
                f"{to.value} is an authority-bearing state; use the dedicated "
                "gate method (authorize/reject/hold/execute)."
            )
        self._transition(to, actor, note)

    # -- authority-bearing transitions ----------------------------------------

    def authorize(self, actor: Actor, rationale: str = "") -> None:
        """AUTHORIZE a ready case. Human actors only.

        This is the moment authority is exercised. Everything before it was
        analysis; everything after it is consequence.
        """
        self._require_human(actor, "authorize")
        if not rationale:
            raise ValueError("Authorization requires a stated rationale.")
        self._transition(DecisionState.AUTHORIZED, actor, rationale)

    def reject(self, actor: Actor, rationale: str = "") -> None:
        self._require_human(actor, "reject")
        if not rationale:
            raise ValueError("Rejection requires a stated rationale.")
        self._transition(DecisionState.REJECTED, actor, rationale)

    def hold(self, actor: Actor, rationale: str = "") -> None:
        self._require_human(actor, "hold")
        self._transition(DecisionState.HELD, actor, rationale)

    def execute(self, actor: Actor, note: str = "") -> None:
        """EXECUTE an authorized decision. Only from AUTHORIZED.

        Execution is a separate act from authorization, separately recorded.
        An authorized decision that is never executed simply remains
        AUTHORIZED — the gate will not execute on anyone's behalf.
        """
        self._require_human(actor, "execute")
        self._transition(DecisionState.EXECUTED, actor, note)

    def supersede(self, actor: Actor, rationale: str = "") -> None:
        """Supersede a terminal or held decision with a new case.

        Supersession retires the old decision without rewriting it — the
        record stands, and the new case begins at DRAFT elsewhere.
        """
        self._require_human(actor, "supersede")
        self._transition(DecisionState.SUPERSEDED, actor, rationale)

    @staticmethod
    def _require_human(actor: Actor, action: str) -> None:
        if actor.kind is not ActorKind.HUMAN:
            raise AuthorityViolation(
                f"Only a human actor may {action}. "
                f"Attempted by {actor.kind.value} '{actor.identity}'. "
                "Technical connectivity does not establish authority."
            )
