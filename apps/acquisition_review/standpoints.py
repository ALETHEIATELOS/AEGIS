"""Domain standpoints for acquisition review.

The standpoints are the domain. Everything else — evidence handling,
perspectives, contradiction, synthesis, readiness, the gate — is the
domain-free AEGIS machinery.
"""

STANDPOINTS: list[str] = [
    "financial underwriting: cash flows, leverage, and returns. "
    "Skeptical of projections; trusts audited numbers over narratives; "
    "asks what the downside case pays.",

    "operational diligence: can this business actually run after close. "
    "Management depth, customer concentration, systems, integration risk; "
    "distrusts synergy math that has no owner.",

    "risk and downside: what kills this deal. Hunts for the single point "
    "of failure, the regulatory tripwire, the liability hiding in the "
    "footnotes. Comfortable being the unpopular voice.",

    "strategic fit: why this target, why now. Tests the thesis against "
    "alternatives — build, partner, or walk away. A good deal at the wrong "
    "time is the wrong deal.",
]

QUESTION_TEMPLATE = "Should we acquire {target} at the proposed terms?"
