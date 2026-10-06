"""Evidence: immutable items with a full provenance chain.

Research question 1: can AI systems preserve evidence provenance throughout
probabilistic reasoning?

Every piece of evidence in AEGIS is frozen at creation. Nothing about an
evidence item can be edited in place — derivations, reclassifications, and
reliability updates all produce NEW evidence items whose provenance chain
records exactly what happened, who did it, and why. The original remains
untouched, so any downstream reasoning can be audited back to what was known
and when.

Evidence classification mirrors the institutional doctrine:
- SUPPLIED_FACT: asserted by a party or source; taken as given for analysis.
- CALCULATED_RESULT: produced by computation from other evidence.
- SUPPORTED_EVIDENCE: corroborated by at least one independent source.
- ASSUMPTION: treated as true for analysis but unverified.
- UNKNOWN: a known gap — we know we do not know this.
- UNRESOLVED: disputed or contradictory across sources.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceKind(str, Enum):
    SUPPLIED_FACT = "supplied_fact"
    CALCULATED_RESULT = "calculated_result"
    SUPPORTED_EVIDENCE = "supported_evidence"
    ASSUMPTION = "assumption"
    UNKNOWN = "unknown"
    UNRESOLVED = "unresolved"


class ProvenanceEntry(BaseModel):
    """One link in an evidence item's chain of custody."""

    model_config = ConfigDict(frozen=True)

    actor: str = Field(description="Who performed the action (human, agent, or system name).")
    action: str = Field(description="What happened: collected, derived, reclassified, cited, ...")
    at: datetime = Field(default_factory=_utcnow)
    detail: str = Field(default="", description="Why — the reason for the action.")


class Evidence(BaseModel):
    """A single, immutable unit of evidence with full provenance."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"ev_{uuid4().hex[:12]}")
    content: str = Field(description="The evidence itself, as stated.")
    kind: EvidenceKind
    source: str = Field(description="Where this came from: a document, a person, a system, a computation.")
    reliability: float = Field(default=0.5, ge=0.0, le=1.0,
                               description="Credence in this item, 0.0–1.0. Always explicit, never implicit.")
    collected_at: datetime = Field(default_factory=_utcnow)
    provenance: tuple[ProvenanceEntry, ...] = Field(
        default=(), description="Ordered chain of custody, oldest first. Immutable once recorded."
    )

    def with_provenance(self, actor: str, action: str, detail: str = "") -> "Evidence":
        """Return a new Evidence with an appended provenance entry.

        The original is untouched — provenance is a chain, not a log that can
        be rewritten.
        """
        entry = ProvenanceEntry(actor=actor, action=action, detail=detail)
        return self.model_copy(update={"provenance": self.provenance + (entry,)})

    def derive(self, *, actor: str, content: str, kind: EvidenceKind,
               source: str, reliability: float, detail: str = "") -> "Evidence":
        """Derive a NEW evidence item from this one (e.g. a calculation).

        The new item's provenance starts with a link back to this item, so
        calculated results always carry their lineage.
        """
        child = Evidence(
            content=content,
            kind=kind,
            source=source,
            reliability=reliability,
        )
        seed = ProvenanceEntry(
            actor=actor,
            action="derived",
            # Lineage is structural: the parent id is always present, so a
            # derived item can never lose track of what it came from.
            detail=f"derived from {self.id}" + (f": {detail}" if detail else ""),
        )
        return child.model_copy(update={"provenance": self.provenance + (seed,)})

    def reclassify(self, *, actor: str, kind: EvidenceKind, detail: str) -> "Evidence":
        """Reclassify an item — returns a new item, preserving the original.

        Reclassification is itself evidence-handling that must be auditable,
        so the reason is mandatory.
        """
        if not detail:
            raise ValueError("Reclassification requires a stated reason (detail).")
        new = self.model_copy(update={"kind": kind})
        return new.with_provenance(actor, "reclassified",
                                   f"{self.kind.value} -> {kind.value}: {detail}")

    def fingerprint(self) -> str:
        """Stable content hash used by decision records for reconstruction.

        Records store fingerprints, not just ids, so a decision can be
        re-examined later against exactly what was known at the time.
        """
        h = hashlib.sha256()
        for part in (self.id, self.content, self.kind.value, self.source):
            h.update(part.encode("utf-8"))
        return h.hexdigest()[:16]

    def provenance_summary(self) -> list[str]:
        return [f"{e.at.isoformat()} — {e.actor}: {e.action}"
                + (f" ({e.detail})" if e.detail else "")
                for e in self.provenance]
