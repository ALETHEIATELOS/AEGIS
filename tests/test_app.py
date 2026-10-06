"""Acquisition review app: full pipeline to a decision dossier."""

import pytest

from aegis.authority import Actor, AuthorityViolation, DecisionState
from aegis.readiness import ReadinessStatus
from apps.acquisition_review.__main__ import main as cli_main
from apps.acquisition_review.review import (
    load_evidence_file,
    record_human_decision,
    run_acquisition_review,
)

SAMPLE = "apps/acquisition_review/sample_evidence.json"


def test_intake_loads_evidence_risks_scenarios():
    evidence, risks, scenarios, question = load_evidence_file(SAMPLE)
    assert len(evidence) == 8
    assert "Harborline Logistics" in question
    assert len(risks) == 3
    assert len(scenarios) == 2
    # intake provenance recorded
    assert any(e.action == "collected" for e in evidence[0].provenance)


def test_full_review_reaches_the_gate_with_dossier():
    result = run_acquisition_review(SAMPLE, model_name="test",
                                    with_reframing=False)  # keep the test fast
    assert result.readiness.status == ReadinessStatus.READY_FOR_HUMAN_AUTHORITY
    assert result.case.gate.state == DecisionState.READY_FOR_HUMAN_AUTHORITY
    assert result.synthesis.is_authorization is False
    d = result.dossier_markdown
    for section in ("## Evidence", "## Perspectives", "## Synthesis",
                    "# Minority Report", "## Readiness",
                    "AWAITING HUMAN AUTHORIZATION"):
        assert section in d, f"dossier missing: {section}"
    assert "Harborline" in d


def test_app_authorization_is_human_only():
    result = run_acquisition_review(SAMPLE, model_name="test",
                                    with_rebuttal=False, with_reframing=False)
    with pytest.raises(AuthorityViolation):
        result.case.gate.authorize(Actor.agent("aegis"), rationale="the analysis is conclusive")
    record = record_human_decision(result, "wendy", "authorize",
                                   rationale="Thesis confirmed; I own the downside.")
    assert result.case.gate.state == DecisionState.AUTHORIZED
    assert record.authorized_by == "wendy"
    assert len(result.log) == 1


def test_cli_writes_dossier_file(tmp_path):
    out = tmp_path / "dossier.md"
    rc = cli_main(["--evidence", SAMPLE, "--model", "test",
                   "--no-rebuttal", "--no-reframing", "--out", str(out)])
    assert rc == 0
    text = out.read_text()
    assert "# Acquisition Review" in text
    assert "AWAITING HUMAN AUTHORIZATION" in text
