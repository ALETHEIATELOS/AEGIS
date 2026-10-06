# Live Model Runs

AEGIS runs fully offline by default (Pydantic AI's test model). For live
runs — real perspectives, real rebuttals, real synthesis prose — point the
orchestrator at a real model.

## Setup

```bash
export AEGIS_MODEL="openai:gpt-4o"   # any Pydantic AI model string
export OPENAI_API_KEY="…"            # the provider's key
python -m apps.acquisition_review --evidence apps/acquisition_review/sample_evidence.json --out dossier.md
```

Or pass the model explicitly — explicit always wins over the environment:

```python
from aegis.runtime import AegisOrchestrator
orch = AegisOrchestrator(model_name="anthropic:claude-sonnet-4-5")
```

Model strings follow [Pydantic AI's model naming](https://ai.pydantic.dev/models/):
`openai:gpt-4o`, `anthropic:claude-sonnet-4-5`, `google-gla:gemini-2.5-pro`,
`groq:llama-3.3-70b-versatile`, etc. The key lives in the environment, never
in the repo.

## What changes with a live model — and what doesn't

**Changes:** the prose. Perspectives reason better, the contrarian finds
sharper disagreements, reframings bite harder, the synthesis reads like it
was written by someone who did the work.

**Does not change:** the governance. The readiness check is still
deterministic and LLM-free. The gate still refuses non-human authorization.
Records are still append-only. A live model makes the analysis smarter; it
does not move the authority boundary one millimeter. That is the entire
point of the architecture: upgrade the minds, keep the constitution.

## Cost and latency notes

A full review with rebuttal + reframing makes roughly
`(standpoints) + 1 + (contradictions × perspectives) + (perspectives × standpoints) + 1`
model calls — for the default 4 standpoints, expect on the order of 15–25
calls. With `--no-reframing` and `--no-rebuttal` it drops to ~6. Size the
model to the stakes: a fast model for perspective drafts, a strong model
for synthesis, if you want to split them (construct separate
orchestrators — the agents are independent objects).

## Verification status

Live runs are wired and code-reviewed but **not live-verified in this
environment** — no provider API keys are configured here. The test suite
and the demo exercise the identical code path with the test model. First
live run should be treated as a shakedown: compare the dossier against a
test-model run of the same evidence and confirm the structure (not the
prose) is identical.
