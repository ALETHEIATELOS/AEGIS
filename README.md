# AEGIS — Institutional Intelligence Infrastructure

AEGIS is a research and engineering stack for building evidence-bound,
multi-perspective AI decision systems.

AEGIS separates AI execution from institutional intelligence. It is designed to
preserve evidence, independent reasoning, disagreement, uncertainty, decision
state, human authority, outcomes, and epistemic memory across consequential
decision processes.

## The one principle everything else hangs on

> **AI-generated analysis, recommendation, authorization, and execution are
> distinct states.**
>
> `READY FOR HUMAN AUTHORITY ≠ AUTHORIZED ≠ EXECUTED`
>
> Technical connectivity does not establish authority. No model, agent, tool,
> or runtime may grant itself authority.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                                    # deterministic core, no API keys needed
python examples/demo.py                   # full decision lifecycle, end to end

# Domain application: acquisition review -> decision dossier
python -m apps.acquisition_review --evidence apps/acquisition_review/sample_evidence.json

# Web service (landing page + review API), local:
pip install -e ".[web]"
gunicorn "apps.web.app:create_app()" --bind 0.0.0.0:8000
```

The agent runtime (`aegis/runtime.py`) uses
[Pydantic AI](https://ai.pydantic.dev/). It defaults to Pydantic AI's test
model, so the demo and the test suite run fully offline. Point it at a real
model to run live perspectives:

```python
from aegis.runtime import AegisOrchestrator
orchestrator = AegisOrchestrator(model_name="openai:gpt-4o")  # or any pydantic-ai model
```

## Architecture

```
                    AEGIS
       Institutional Intelligence Layer
                         │
       ┌─────────────────┼─────────────────┐
       │                 │                 │
   Evidence         Perspectives       Governance
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │
                  Conflict / Risk
                         │
                     Synthesis
                         │
                Decision Readiness
                         │
                  Decision Gate
                         │
                  Human Authority
                         │
                  Decision Record
                         │
                      Outcome
                         │
                    Observation
                         │
                 Epistemic Memory
                         ▼
                  Agent Runtime
                         │
                   Pydantic AI
```

Each layer is a typed, importable module in `aegis/`:

| Module | Responsibility |
|---|---|
| `evidence.py` | Immutable evidence items with a provenance chain — who touched what, when, and why |
| `perspectives.py` | Independent reasoning paths, each bound to the evidence it actually used |
| `conflict.py` | Unresolved disagreement preserved as a first-class record; deterministic risk factors and scenarios |
| `kaleidoscope.py` | **v0.2:** reframing, structured rebuttal rounds, deterministic sensitivity analysis, minority reports |
| `synthesis.py` | Recommendation that **preserves dissent** and propagates uncertainty — never forces consensus |
| `readiness.py` | Deterministic, LLM-free readiness check: `READY_FOR_HUMAN_AUTHORITY` or `NOT_READY` with reasons |
| `authority.py` | The decision gate: explicit state machine; **only a human actor can authorize**; only `AUTHORIZED` can execute |
| `records.py` | Append-only, immutable decision records with evidence fingerprints for reconstruction |
| `outcomes.py` | Observed outcomes and divergence notes, kept separate from the records they describe |
| `memory.py` | Epistemic memory: lessons reference records but never mutate them |
| `domain.py` | Domain-agnostic `Case` envelope — the same architecture across decision domains |
| `runtime.py` | Pydantic AI agents (perspective, contrarian, synthesis, rebuttal, reframing) and the orchestrator |
| `apps/acquisition_review/` | **v0.2:** domain application — JSON evidence intake, full pipeline, decision dossier markdown |
| `apps/web/` | **v0.3:** Flask web service — project landing page + `POST /api/review`; deployable via `render.yaml` |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full doctrine,
including the decision state machine and the authority boundary.

## Origins

AEGIS builds upon the institutional intelligence architecture developed through AletheiaTelos.

AletheiaTelos established the initial architecture around:

* Evidence
* Independent Perspectives
* Computational Kaleidoscope
* Conflict and Coexistence
* Risk Simulation
* Contrarian Review
* Decision Readiness
* Decision Gates
* Human Authority
* Decision Records
* Outcomes
* Observation
* Epistemic Memory

AEGIS is the new implementation layer for researching and extending these ideas using modern typed AI infrastructure.

## Runtime foundation

Pydantic AI provides the agent runtime. AEGIS provides the institutional
intelligence architecture governing how those agents participate in
consequential decisions.

## The 8 research questions, mapped to code

1. **Evidence provenance through probabilistic reasoning** → `evidence.py`:
   every item carries an immutable chain-of-custody; `derive()` returns a new
   item, never a mutation.
2. **Genuinely independent reasoning paths** → `perspectives.py` +
   `runtime.py`: each perspective agent runs with its own evidence selection
   and no shared hidden state.
3. **Unresolved disagreement without forced consensus** →
   `conflict.py`: contradictions are recorded `UNRESOLVED` and carried into
   the synthesis as preserved dissent.
4. **Uncertainty propagation** → `synthesis.py` + `conflict.py`: perspective
   confidences combine deterministically; risk scenarios carry probabilities
   adjusted by evidence reliability.
5. **Reconstructing why a decision changed** → `records.py` + `memory.py`:
   records store evidence fingerprints; `reconstruct()` replays the
   chronological record so a changed decision is explainable by diffing.
6. **Recommendation ≠ authorization ≠ execution** → `authority.py`: a
   deterministic state machine enforces the distinction; an agent attempting
   to authorize raises `AuthorityViolation`.
7. **Learning from outcomes without corrupting history** → `outcomes.py` +
   `memory.py`: outcomes and lessons are append-only and reference records;
   records are frozen.
8. **Generalizing across domains** → `domain.py`: the `Case` envelope is
   domain-agnostic; see the tests for the same pipeline run in two domains.

## Repository boundary

AEGIS is a new implementation and research stack. Reference architectures may
inform its development, but source repositories remain separate. AEGIS does
not modify or replace:

* AletheiaTelos source repositories
* the clean Pydantic AI foundation
* TYR application repositories

## Status

**v0.3.0** — the web service:

- **`apps/web/`**: Flask service with a project landing page (the public
  face — suitable for a custom domain), `GET /health`, `GET /api/sample`,
  and `POST /api/review`, which runs the full acquisition-review pipeline
  and returns the dossier, sensitivity analysis, and minority report as
  JSON. Stops at the gate, like everything else here.
- **`render.yaml`**: Blueprint — Render dashboard → New → Blueprint →
  select the repo, then attach a custom domain under the service's
  Settings → Custom Domains. `AEGIS_MODEL` defaults to `test`; set a live
  model plus provider key to go live.

**v0.2.0** — the deepened kaleidoscope and the first domain application
(reframing, structured rebuttal with bounded exposure, sensitivity
analysis, minority reports; `apps/acquisition_review`; `AEGIS_MODEL`;
46 tests).

**v0.1.0** — the foundational institutional-intelligence layer: typed
domain core, deterministic readiness and authority gates, Pydantic AI
runtime wiring, end-to-end demo.
