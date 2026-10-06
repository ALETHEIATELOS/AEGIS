"""AEGIS domain application: acquisition review.

A complete, domain-specific decision pipeline built on the AEGIS
institutional-intelligence layer — the same architecture, pointed at
acquisitions. Domain knowledge lives here (standpoints, evidence intake,
dossier format); the machinery (evidence, perspectives, conflict,
synthesis, readiness, gate) stays domain-free in aegis/.

Usage:
    python -m apps.acquisition_review --evidence apps/acquisition_review/sample_evidence.json
    python -m apps.acquisition_review --evidence deal.json --model openai:gpt-4o --out dossier.md

The app stops at the gate: it produces a decision dossier and declares the
case READY_FOR_HUMAN_AUTHORITY. Authorization is a human act, performed
outside the app.
"""

from apps.acquisition_review.review import (
    ReviewResult,
    load_evidence_data,
    run_acquisition_review,
    run_review_from_intake,
)

__all__ = ["ReviewResult", "load_evidence_data", "run_acquisition_review", "run_review_from_intake"]
