"""Research Q6-partial: readiness is deterministic and LLM-free."""

from aegis.readiness import ReadinessPolicy, ReadinessStatus, assess_readiness


def ready_kwargs(**overrides):
    base = dict(
        n_perspectives=3,
        has_synthesis=True,
        n_evidence=5,
        unrecorded_contradictions=0,
        combined_confidence=0.7,
    )
    base.update(overrides)
    return base


def test_readiness_is_deterministic():
    r1 = assess_readiness(**ready_kwargs())
    r2 = assess_readiness(**ready_kwargs())
    assert r1.status == r2.status == ReadinessStatus.READY_FOR_HUMAN_AUTHORITY
    assert r1.reasons == r2.reasons


def test_each_criterion_blocks_with_actionable_reason():
    assert assess_readiness(**ready_kwargs(n_perspectives=1)).status == ReadinessStatus.NOT_READY
    r = assess_readiness(**ready_kwargs(n_perspectives=1))
    assert any("perspective" in reason for reason in r.reasons)

    assert assess_readiness(**ready_kwargs(has_synthesis=False)).status == ReadinessStatus.NOT_READY
    assert assess_readiness(**ready_kwargs(n_evidence=0)).status == ReadinessStatus.NOT_READY


def test_unrecorded_disagreement_blocks_but_recorded_dissent_does_not():
    # Known disagreement that was never written down: NOT READY.
    r = assess_readiness(**ready_kwargs(unrecorded_contradictions=2))
    assert r.status == ReadinessStatus.NOT_READY
    assert any("never recorded" in reason for reason in r.reasons)

    # Recorded-but-unresolved dissent does NOT block readiness.
    # The doctrine: the human must SEE the dissent; it need not disappear first.
    r2 = assess_readiness(**ready_kwargs(unrecorded_contradictions=0))
    assert r2.status == ReadinessStatus.READY_FOR_HUMAN_AUTHORITY


def test_policy_is_explicit_and_versionable():
    strict = ReadinessPolicy(min_perspectives=4, min_combined_confidence=0.8)
    r = assess_readiness(**ready_kwargs(), policy=strict)
    assert r.status == ReadinessStatus.NOT_READY
    assert r.policy.min_perspectives == 4
