"""AEGIS web service: landing page + acquisition review API."""

from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import aegis
from apps.acquisition_review import run_review_from_intake

_SAMPLE_PATH = (
    Path(__file__).resolve().parent.parent / "acquisition_review" / "sample_evidence.json"
)


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("landing.html", version=aegis.__version__)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "version": aegis.__version__})

    @app.get("/api/sample")
    def sample():
        """The sample intake file — the shape POST /api/review expects."""
        return jsonify(json.loads(_SAMPLE_PATH.read_text()))

    @app.post("/api/review")
    def review():
        """Run an acquisition review. Body: {"intake": {...}, "model": null,
        "with_rebuttal": true, "with_reframing": true}.

        The service stops at the gate: the response declares
        READY_FOR_HUMAN_AUTHORITY. Authorization is a human act, outside
        this system.
        """
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "JSON body required"}), 400
        intake = body.get("intake")
        if not isinstance(intake, dict):
            return jsonify({"error": "'intake' must be a JSON object (see GET /api/sample)"}), 400
        try:
            result = run_review_from_intake(
                intake,
                model_name=body.get("model"),  # None -> $AEGIS_MODEL -> test model
                with_rebuttal=bool(body.get("with_rebuttal", True)),
                with_reframing=bool(body.get("with_reframing", True)),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001 — surfaced as 500, message only
            return jsonify({"error": f"review failed: {exc}"}), 500

        case = result.case
        return jsonify({
            "case_id": case.id,
            "question": case.question,
            "gate_state": case.gate.state.value,
            "readiness": result.readiness.status.value,
            "recommendation": result.synthesis.recommendation,
            "combined_confidence": result.synthesis.combined_confidence,
            "agreements": list(result.synthesis.agreements),
            "dissents": len(result.minority_report.dissents),
            "perspectives": [
                {"name": p.name, "conclusion": p.conclusion,
                 "confidence": p.confidence, "generation": p.generation}
                for p in case.perspectives
            ],
            "sensitivity": [
                {"evidence_id": s.evidence_id, "leverage": s.leverage,
                 "perspectives_affected": s.perspectives_affected}
                for s in result.sensitivity
            ],
            "minority_report_markdown": result.minority_report.to_markdown(),
            "dossier_markdown": result.dossier_markdown,
        })

    return app
