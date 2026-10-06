"""Research Q4/Q6-partial: synthesis preserves dissent, propagates uncertainty,
and can never be an authorization."""

import pytest

from aegis.synthesis import Synthesis, combine_confidence, synthesize


def test_combine_confidence_properties():
    # Never exceeds the most confident input; a weak link drags the combination down.
    assert combine_confidence([0.9, 0.9]) <= 0.9
    assert combine_confidence([0.9, 0.2]) < 0.9
    assert combine_confidence([]) == 0.0
    # Deterministic: same inputs, same output.
    assert combine_confidence([0.7, 0.8, 0.6]) == combine_confidence([0.7, 0.8, 0.6])


def test_synthesize_preserves_dissent():
    s = synthesize(
        case_id="case_1",
        perspective_conclusions=[("px_a", 0.8), ("px_b", 0.6)],
        agreements=["costs are known"],
        dissent_ids=["cx_1", "cx_2"],
        recommendation="Proceed with caution.",
        rationale="Costs known; demand disputed.",
    )
    assert set(s.preserved_dissents) == {"cx_1", "cx_2"}
    assert s.agreements == ("costs are known",)
    assert s.is_authorization is False
    assert 0.0 < s.combined_confidence <= 0.8


def test_synthesis_can_never_be_an_authorization():
    with pytest.raises(ValueError, match="never be an authorization"):
        Synthesis(
            case_id="case_1",
            perspective_ids=("px_a",),
            combined_confidence=0.9,
            recommendation="Go.",
            is_authorization=True,
        )
