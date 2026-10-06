"""Research Q1: evidence provenance preserved through reasoning."""

import pytest
from pydantic import ValidationError

from aegis.evidence import Evidence, EvidenceKind


def make_evidence(**kwargs):
    defaults = dict(
        content="Q3 revenue was $4.2M.",
        kind=EvidenceKind.SUPPLIED_FACT,
        source="10-Q filing",
        reliability=0.9,
    )
    defaults.update(kwargs)
    return Evidence(**defaults)


def test_evidence_is_immutable():
    ev = make_evidence()
    with pytest.raises(ValidationError):
        ev.content = "changed"  # type: ignore[misc]


def test_provenance_chain_appends_without_mutating():
    ev = make_evidence()
    ev2 = ev.with_provenance("kai", "cited", detail="used in perspective px_1")
    assert len(ev.provenance) == 0          # original untouched
    assert len(ev2.provenance) == 1
    assert ev2.provenance[0].actor == "kai"
    assert ev2.provenance[0].action == "cited"


def test_derive_creates_child_with_lineage():
    parent = make_evidence()
    child = parent.derive(
        actor="kai",
        content="YoY growth is 12%.",
        kind=EvidenceKind.CALCULATED_RESULT,
        source="aegis computation",
        reliability=0.8,
        detail="computed from parent revenue figures",
    )
    assert child.kind == EvidenceKind.CALCULATED_RESULT
    assert parent.id != child.id
    assert any(e.action == "derived" and parent.id in e.detail for e in child.provenance)
    assert len(parent.provenance) == 0  # parent untouched


def test_reclassify_requires_a_reason():
    ev = make_evidence()
    with pytest.raises(ValueError, match="stated reason"):
        ev.reclassify(actor="kai", kind=EvidenceKind.ASSUMPTION, detail="")
    ev2 = ev.reclassify(actor="kai", kind=EvidenceKind.SUPPORTED_EVIDENCE,
                        detail="corroborated by second filing")
    assert ev2.kind == EvidenceKind.SUPPORTED_EVIDENCE
    assert ev.kind == EvidenceKind.SUPPLIED_FACT  # original untouched


def test_fingerprint_is_stable_and_content_sensitive():
    ev = make_evidence()
    # Same item, same fingerprint every time.
    assert ev.fingerprint() == ev.fingerprint()
    # Fingerprint includes the id, so two distinct items differ even with identical content.
    twin = Evidence(content=ev.content, kind=ev.kind, source=ev.source,
                    reliability=ev.reliability)
    assert twin.fingerprint() != ev.fingerprint()
