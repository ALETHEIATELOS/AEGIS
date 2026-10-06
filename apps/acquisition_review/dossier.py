"""Decision dossier renderer: the human-readable output of a review."""

from __future__ import annotations

from aegis.domain import Case
from aegis.kaleidoscope import MinorityReport, Reframing, SensitivityResult
from aegis.perspectives import Perspective
from aegis.readiness import ReadinessResult
from aegis.synthesis import Synthesis


def render_dossier(*, case: Case, synthesis: Synthesis, readiness: ReadinessResult,
                   minority_report: MinorityReport,
                   sensitivity: list[SensitivityResult],
                   reframings: list[Reframing],
                   second_generation: list[Perspective]) -> str:
    L: list[str] = []
    add = L.append

    add(f"# Acquisition Review — Decision Dossier")
    add("")
    add(f"**Question:** {case.question}")
    add(f"**Case:** `{case.id}` · **Gate:** `{case.gate.state.value}`")
    add("")
    add("> This dossier is analysis, not authority. It declares the case "
        "READY FOR HUMAN AUTHORITY. Authorization is a human act, performed "
        "outside this system. READY ≠ AUTHORIZED ≠ EXECUTED.")
    add("")

    add("## Evidence")
    add("")
    add("| ID | Kind | Reliability | Source | Content |")
    add("|----|------|-------------|--------|---------|")
    for e in case.evidence:
        content = e.content.replace("|", "\\|").replace("\n", " ")
        add(f"| `{e.id}` | {e.kind.value} | {e.reliability:.2f} | {e.source} | {content} |")
    add("")

    add("## Perspectives")
    add("")
    gen1 = [p for p in case.perspectives if p.generation == 1]
    for p in gen1:
        add(f"### {p.name} (confidence {p.confidence:.2f})")
        add(f"*Standpoint:* {p.standpoint}")
        add("")
        add(p.reasoning)
        add("")
        add(f"**Conclusion:** {p.conclusion}")
        add("")
        if p.evidence_ids:
            add(f"Evidence cited: {', '.join(f'`{i}`' for i in p.evidence_ids)}")
            add("")

    if second_generation:
        add("## Rebuttal round — second-generation perspectives")
        add("")
        add("Each perspective below responded to a recorded contradiction, "
            "seeing the topic and positions only. First-generation "
            "perspectives are preserved above.")
        add("")
        for p in second_generation:
            add(f"### {p.name} — gen 2 (confidence {p.confidence:.2f})")
            add(f"*Responds to:* `{', '.join(p.responds_to)}`")
            add("")
            add(p.reasoning)
            add("")
            add(f"**Conclusion:** {p.conclusion}")
            add("")

    if case.contradictions:
        add("## Recorded contradictions")
        add("")
        for c in case.contradictions:
            name_by_id = {p.id: p.name for p in case.perspectives}
            add(f"### {c.topic} — `{c.status.value}`")
            for pid, pos in c.positions.items():
                add(f"- **{name_by_id.get(pid, pid)}**: {pos}")
            if c.resolution:
                add(f"\n*Resolution:* {c.resolution}")
            add("")

    if reframings:
        add("## Reframings — conclusions through foreign lenses")
        add("")
        name_by_id = {p.id: p.name for p in case.perspectives}
        for r in reframings:
            add(f"### {name_by_id.get(r.perspective_id, r.perspective_id)} "
                f"× {r.target_standpoint[:60]}")
            add("")
            add(r.reasoning)
            add("")
            add(f"**Reframed conclusion:** {r.reframed_conclusion}")
            add("")

    if case.risk_assessment and (case.risk_assessment.factors or case.risk_assessment.scenarios):
        ra = case.risk_assessment
        add("## Risk")
        add("")
        if ra.factors:
            add("| Risk | Likelihood × Impact | Severity |")
            add("|------|---------------------|----------|")
            for f in ra.top_factors(len(ra.factors)):
                add(f"| {f.name} | {f.likelihood:.2f} × {f.impact:.2f} = **{f.score:.2f}** | {f.severity()} |")
            add("")
        if ra.scenarios:
            add("### Scenarios (uncertainty-propagated)")
            add("")
            for s in ra.scenarios:
                add(f"- **{s.name}**: raw p={s.raw_probability:.2f} → "
                    f"adjusted p=**{s.adjusted_probability:.2f}** "
                    f"(evidence discount {s.evidence_discount:.2f}) — {s.projected_outcome}")
            add("")

    if sensitivity:
        add("## Sensitivity — what the recommendation hinges on")
        add("")
        add("| Evidence | Perspectives citing | Confidence without | Leverage |")
        add("|----------|---------------------|--------------------|----------|")
        ev_by_id = {e.id: e for e in case.evidence}
        for s in sensitivity[:8]:
            content = ev_by_id[s.evidence_id].content[:60].replace("|", "\\|")
            add(f"| `{s.evidence_id}` — {content}… | {s.perspectives_affected} "
                f"| {s.combined_confidence_without:.2f} | **{s.leverage:+.2f}** |")
        add("")
        add("*Positive leverage: removing this evidence weakens the synthesis. "
            "Negative: removing it strengthens it.*")
        add("")

    add("## Synthesis — recommendation (not authorization)")
    add("")
    if synthesis.agreements:
        add("**Agreements:**")
        for a in synthesis.agreements:
            add(f"- {a}")
        add("")
    add(f"**Recommendation:** {synthesis.recommendation}")
    if synthesis.recommendation_rationale:
        add("")
        add(synthesis.recommendation_rationale)
    add("")
    add(f"Combined confidence: **{synthesis.combined_confidence:.2f}** · "
        f"Dissents preserved: {len(synthesis.preserved_dissents)}")
    add("")

    add(minority_report.to_markdown())

    add("## Readiness")
    add("")
    add(f"**{readiness.status.value}**")
    for reason in readiness.reasons:
        add(f"- {reason}")
    add("")

    add("## Gate history")
    add("")
    if case.gate.history:
        for at, frm, to, actor, note in case.gate.history:
            add(f"- {at.isoformat()} — `{frm.value}` → `{to.value}` "
                f"by {actor.kind.value} '{actor.identity}'" + (f": {note}" if note else ""))
    else:
        add("*(no transitions yet)*")
    add("")

    add("---")
    add("**AWAITING HUMAN AUTHORIZATION.** Use "
        "`record_human_decision(result, name, 'authorize'|'reject'|'hold', rationale)` "
        "— or decide outside the system and record it. The dossier does not decide.")
    add("")
    return "\n".join(L)
