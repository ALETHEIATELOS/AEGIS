# The Foundation: LIQUIDITYLAB/pydantic-ai

AEGIS is the institutional-intelligence layer. It is not an agent
framework. The agent framework it builds on is Pydantic AI — specifically
the archived, read-only fork:

- **Repository:** `https://github.com/LIQUIDITYLAB/pydantic-ai`
- **Pinned commit:** `721c78d6014f197c595a9c2a83789aa4dbf6d008` (`main`, 2026-10-05)
- **Status:** public archive — readable by everyone, changeable by no one
- **Upstream:** `pydantic/pydantic-ai` (the fork point's upstream)

## The relationship, precisely

```
LIQUIDITYLAB/pydantic-ai          AEGIS
(clean agent foundation)          (institutional intelligence layer)
  Agents, models, tools,             Evidence, perspectives, conflict,
  types, streaming, evals  ───────▶  synthesis, readiness, the gate,
                                     records, outcomes, memory
```

Pydantic AI provides the agent runtime: how agents call models, how tools
work, how types flow. AEGIS provides the governance: how those agents
participate in consequential decisions without ever granting themselves
authority.

AEGIS **does not modify** the foundation. Not a patch, not a fork of a
file, not a monkeypatch at import time. If AEGIS needs something the
foundation doesn't do, that need is expressed as an issue against the
architecture — never as a change to the foundation. The boundary is the
product: the day AEGIS edits the foundation is the day "clean foundation"
stops meaning anything.

## The API surface AEGIS depends on

Deliberately small — the smaller the surface, the stronger the pin:

- `Agent(model, output_type=..., system_prompt=...)` — typed agents with
  structured output (`aegis/runtime.py`: perspective, contrarian,
  synthesis, rebuttal, reframing agents)
- `agent.run_sync(prompt)` / `result.output` — the single call path
- `model="test"` (`TestModel`) — offline runs for the suite and demos

That's it. AEGIS does not depend on tools, streaming, evals, voice, or
any model-specific integration. If a future AEGIS needs more surface, this
document gets updated first.

## Verification

2026-10-06: the full AEGIS suite (**52 tests**) was run against the fork
installed from git at the pinned commit — **all green**. The verification
environment is kept at `~/workspace/aegis/.venv-foundation`
(`pydantic-ai-slim` + `pydantic-graph` built from the fork; everything else
from PyPI). Re-run any time with:

```bash
.venv-foundation/bin/python -m pytest -q
```

## Install note

`pyproject.toml` depends on PyPI `pydantic-ai` (the stable distribution
channel — this is what Render installs on deploy). The fork is the
**reference implementation** the project is verified against, not the
install source: dev-versioned git builds are fragile as a deployment
input, and the archive exists to be read, not to be a package index. If
the reference ever needs to become the install source, that's a deliberate
decision recorded here first — not a quiet edit to a dependency line.
