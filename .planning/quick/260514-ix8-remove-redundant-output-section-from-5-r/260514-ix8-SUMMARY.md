---
quick_id: 260514-ix8
description: Remove redundant Output section from 5 recipe research prompts
date: 2026-05-14
status: complete
commit: 0bd4062
---

# Quick Task 260514-ix8 — Summary

## What changed

Removed the `## Output` section from each of the 5 artifact-producing recipe agent prompts:

- `src/robotina/agent/prompts/recipe-research-gather/V004.md`
- `src/robotina/agent/prompts/recipe-research-instructions/V003.md`
- `src/robotina/agent/prompts/recipe-research-ingredients/V003.md`
- `src/robotina/agent/prompts/recipe-research-metadata/V003.md`
- `src/robotina/agent/prompts/recipe-load/V004.md`

Each prompt now ends at its `## Rules` section.

## Why

The output schema is enforced at the API level by `response_format_model` bindings in `src/robotina/agent/agents.py`. `LLMBackend.create_agent()` passes the Pydantic class as `response_format=` to `langchain.agents.create_agent`, which derives a JSON schema and binds it to the LLM:

- Anthropic / OpenAI → `ProviderStrategy` (provider-native structured output)
- Ollama → `ToolStrategy` (schema wrapped as a tool the model must call)

The model receives the schema regardless of what the prompt says. The prompt-level Output sections only re-pointed developers at `src/robotina/queue/task_types.py` ("refer to it; do not re-describe fields here") — that's a developer-facing comment in a file meant exclusively for the agent. See `.planning/decisions/response-format-adoption.md` (Phase 11) for the schema-binding rationale.

## Verification

```
$ grep -l "^## Output" src/robotina/agent/prompts/recipe-research-gather/V004.md \
    src/robotina/agent/prompts/recipe-research-instructions/V003.md \
    src/robotina/agent/prompts/recipe-research-ingredients/V003.md \
    src/robotina/agent/prompts/recipe-research-metadata/V003.md \
    src/robotina/agent/prompts/recipe-load/V004.md
# (no output — all clean)
```

No code changes — `agents.py` and `task_types.py` were untouched. Schema bindings remain correct; runtime behavior is unchanged.

## Out of scope (intentionally not touched)

- Older prompt versions (`V001`–`V003`) — historical, will not be loaded by the runtime.
- Non-artifact-producing prompts (`robotina`, `acknowledge-add-recipe`) — no `response_format_model`.

## Commit

`0bd4062` — refactor(prompts): remove redundant Output section from 5 recipe agents (260514-ix8)
