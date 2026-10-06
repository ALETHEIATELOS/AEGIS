# AEGIS Architecture & Doctrine

This document is the technical companion to the README. It describes the
decision state machine, the authority boundary, and the design decisions
behind each module — the things a contributor must understand before
changing anything.

## The decision state machine

```
DRAFT
  → EVIDENCE_COLLECTED
  → PERSPECTIVES_FORMED
  → CONFLICT_ANALYZED
  → SYNTHESIZED
  → READY_FOR_HUMAN_AUTHORITY ─┬─→ AUTHORIZED ─┬─→ EXECUTED ──→ SUPERSEDED
                               ├─→ REJECTED ────┘
                               └─→ HELD ─→ READY_FOR_HUMAN_AUTHORITY (released)
                                        └→ SUPERSEDED
```

Everything left of `READY_FOR_HUMAN_AUTHORITY` is **analysis**: agents may
act there freely. Everything at and right of it is **authority**: only a
human actor may move the gate, and every move requires a stated rationale
(except `hold`, which requires one in practice and should always carry one).

`DecisionGate` (`aegis/authority.py`) enforces this as a closed transition
table. Key properties:

- `advance()` can move through analytical states but **refuses** to enter
  authority-bearing states — use `authorize()` / `reject()` / `hold()` /
  `execute()` / `supersede()`.
- `authorize()` requires `ActorKind.HUMAN`. Agents, tools, cron jobs, and
  the runtime itself get `AuthorityViolation`. There is no override flag.
- `execute()` requires state `AUTHORIZED`. An authorized-but-never-executed
  decision simply remains `AUTHORIZED` — the gate never executes on
  anyone's behalf.
- `supersede()` retires a decision without rewriting it. The old records
  stand; a new case begins at `DRAFT`.

## The authority boundary, precisely

Three confusions the architecture exists to prevent:

1. **"The analysis was conclusive, so we're authorized."**
   No. `READY_FOR_HUMAN_AUTHORITY` means "fit to be placed before a human."
   Conclusiveness is a property of analysis; authorization is an act by a
   person who owns the consequences.

2. **"The human clicked approve in the agent's UI, so the agent authorized it."**
   No. Authorization is attributed to the human identity on the transition,
   recorded in gate history and in the `DecisionRecord`. If the agent
   performed the click, the actor kind is `AGENT` and the gate refuses.

3. **"Authorization implies execution."**
   No. They are separate transitions, separately recorded, possibly by
   different humans at different times. `AUTHORIZED` without `EXECUTED` is
   a complete, stable, meaningful state.

## Module doctrine

### Evidence (`evidence.py`) — nothing is edited, ever

Immutability is not a performance choice; it is the audit trail. A
reclassification without a mandatory reason would be a silent rewrite of
what was known. Hence `reclassify()` requires `detail`, and `derive()`
embeds the parent id structurally — lineage survives even sloppy callers.

Fingerprints (`Evidence.fingerprint`) exist so decision records can bind
themselves to *exactly what was known*. Reconstruction diffs fingerprints,
not prose.

### Perspectives (`perspectives.py`, `runtime.py`) — independence by withholding

Independence is enforced by what the orchestrator withholds: a perspective
agent receives the question, its standpoint, and the evidence pool — never
another perspective's reasoning. (A rebuttal pass would be an explicit,
separate mechanism, not a default.)

Each perspective binds to `evidence_ids`. Overlap is measurable
(`evidence_overlap_ratio`), which makes "same evidence, different
conclusion" a visible, researchable signal rather than a suspicion.

### Conflict (`conflict.py`) — dissent is a record, not a bug

Contradictions default to `UNRESOLVED`. Resolution is allowed but requires
a stated basis and produces a *new* record — the unresolved record remains
in history.

The readiness check requires contradictions to be **recorded**, not
resolved. This is the single most important doctrinal choice in the
readiness module: the system must guarantee the human *sees* the dissent.
It must not require the dissent to disappear first.

Risk is deterministic: `RiskFactor.score = likelihood × impact`, and
`RiskScenario.adjusted_probability` discounts by the weakest evidence
reliability. Both the raw and adjusted numbers are kept — the adjustment
is transparent.

### Synthesis (`synthesis.py`) — the kaleidoscope, not the blender

The synthesis turns the same evidence through multiple perspectives and
combines them *without forcing consensus*: agreements are stated,
contradictions are carried as `preserved_dissents`, uncertainty propagates
via geometric-mean confidence combination.

`Synthesis.is_authorization` is frozen `False`, and constructing one with
`True` raises. The distinction between recommendation and authorization is
in the types, not just the docs.

### Readiness (`readiness.py`) — the LLM-free checkpoint

`assess_readiness()` is a pure function. Same inputs → same result, every
time, with no model in the loop. The policy (`ReadinessPolicy`) is explicit
and versionable so the bar itself can be audited and argued about.

### Records, outcomes, memory (`records.py`, `outcomes.py`, `memory.py`)

The reference graph goes one way: **memory → records → evidence**.
Lessons reference records; records reference evidence fingerprints; nothing
points backward. This is what makes "learning without corrupting history"
structural rather than aspirational.

`reconstruct()` replays a case's records chronologically and diffs evidence
fingerprints between consecutive records — the mechanical answer to "why
did the decision change?"

### Kaleidoscope v0.2 (`kaleidoscope.py`, `runtime.py`) — deeper turns, same constitution

Four mechanisms deepen the kaleidoscope without touching the authority boundary:

- **Reframing.** A conclusion stress-tested through a foreign standpoint.
  Recorded as an immutable `Reframing` — the original conclusion is kept
  alongside, so the audit shows what was tested, not just the result.
- **Structured rebuttal.** The *only* path by which a perspective engages
  another's reasoning — and the exposure is bounded to topic + positions.
  `contradiction_exposure()` returns exactly what the rebutting agent saw;
  the bound is auditable because it is data. Rebuttals yield
  second-generation perspectives (`generation=2`, `responds_to` set); gen 1
  is never edited.
- **Sensitivity analysis.** Pure function: for each evidence item,
  recompute combined confidence without the perspectives that cited it.
  `leverage` tells the human what the recommendation hinges on — including
  negative leverage, where removing weak evidence *strengthens* the case.
- **Minority report.** Built only from unresolved contradictions, rendered
  as markdown for the decider. If there is no dissent, the report says so
  plainly rather than inventing any.

Rebuttal rounds are analytical sub-steps: they happen between
`CONFLICT_ANALYZED` and `SYNTHESIZED` and are recorded in provenance and
perspective generations, not as new gate states. The state machine is
unchanged.

### Domain (`domain.py`) — the envelope is empty on purpose

`Case` carries no domain logic. If you find yourself adding domain-specific
fields to `Case`, stop: that knowledge belongs in evidence content and in
standpoints. The day `Case` needs a domain field is the day the
generalization claim (research question 8) has failed.

### Domain applications (`apps/`)

Apps are thin: domain standpoints, evidence intake, dossier format. If an
app needs a new concept that isn't domain knowledge (a new reasoning
mechanism, a new gate behavior), that concept belongs in `aegis/` — the
app was the wrong place the moment it needed it. The acquisition review
app also demonstrates the intended lifecycle beyond the dossier:
`record_human_decision()` (human act) → `DecisionRecord` → `record_outcome()`
→ lesson in epistemic memory, history untouched.

## Guardrails for contributors

1. **Never add an authorization path for non-human actors.** Not a flag,
   not an env var, not a "trusted agent" role. The boundary is the product.
2. **Never mutate a frozen record.** New information → new record.
3. **Never let the readiness check call a model.** Deterministic means
   deterministic.
4. **Never let a perspective agent see another perspective's reasoning**
   except through an explicit, named rebuttal mechanism.
5. **Keep the reference graph one-way** (memory → records → evidence).
6. **Uncertainty must propagate visibly.** Any new combination rule keeps
   both inputs and output inspectable, like `adjusted_probability` does.
7. **Rebuttal exposure stays bounded.** The only thing a rebutting
   perspective may see of another is what `contradiction_exposure()`
   returns: topic + positions. Never widen that channel casually — it is
   the load-bearing wall of perspective independence.

## Running the suite

```bash
pip install -e ".[dev]"
pytest
```

The suite runs fully offline (Pydantic AI test model). Tests assert
structure and governance — state machines, immutability, authority
boundaries — not model prose.
