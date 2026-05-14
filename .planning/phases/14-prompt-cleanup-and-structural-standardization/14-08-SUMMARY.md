---
phase: 14-prompt-cleanup-and-structural-standardization
plan: 08
status: complete
commit: 7da223b
---

# Plan 14-08: Cleanup + Whole-Phase Smoke

## What landed

- `src/robotina/agent/prompts/hello-world/` deleted via `git rm -r` (clean diff).
- Whole-phase smoke verification passed (`OK 14-final`).

## Pre-deletion grep

Searched outside `.planning/` for any reference to `hello-world`:

| File | Reference | Disposition |
|------|-----------|-------------|
| `src/robotina/agent/agents.py:7` | docstring noting placeholder was removed in Phase 6 | doc-only, kept |
| `src/robotina/agent/workflows.py:11` | docstring noting `hello-world-2step` was removed in Phase 6 | doc-only, kept |
| `tests/test_workflow_runner.py:32` | test fixture using `"hello-world"` as a `task_type` string | unrelated to the prompt directory; kept |
| `tests/test_workflow_runner.py:429` | comment about removed integration tests | doc-only, kept |
| `tests/unit/test_agents_registry.py:78-81` | `test_hello_world_removed_from_registry` (asserts `KeyError` for `get_agent_config("hello-world")`) | load-bearing registry contract test, kept |

No live code path depends on `src/robotina/agent/prompts/hello-world/`. Deletion is safe.

## Final registry → prompt path table

| Task type | prompt_path |
|-----------|-------------|
| `handle-incoming-message`     | `src/robotina/agent/prompts/robotina/V003.md` |
| `recipe-research-gather`      | `src/robotina/agent/prompts/recipe-research-gather/V004.md` |
| `recipe-research-instructions`| `src/robotina/agent/prompts/recipe-research-instructions/V003.md` |
| `recipe-research-ingredients` | `src/robotina/agent/prompts/recipe-research-ingredients/V003.md` |
| `recipe-research-metadata`    | `src/robotina/agent/prompts/recipe-research-metadata/V003.md` |
| `recipe-load`                 | `src/robotina/agent/prompts/recipe-load/V004.md` |
| `acknowledge-add-recipe`      | `src/robotina/agent/prompts/acknowledge-add-recipe/V002.md` |

## Smoke output

```
OK 14-final
```

## Pre-existing cleanup flagged for future

- `overrides/anthropic.json` lacks a `recipe-load` entry while `openai.json` and `staging.ollama.json` have it. This pre-dates Phase 14 and is out of scope (CONTEXT.md scoped this phase to "prompt files, registry, and overrides" without mandating cross-override coverage parity). Suggested follow-up: add `recipe-load` to `anthropic.json` so the three overrides stay in sync, or document the intentional asymmetry.
- `overrides/openai.json` has a pre-existing uncommitted model upgrade (`gpt-4o-mini` → `gpt-4.1-mini`) in the user's working tree; left untouched by Phase 14 commits.

## Human verification owed (ROADMAP success criteria 4 and 5)

1. Smoke-test three Telegram inputs against the live agent:
   - "Hola" (chit-chat router → `queue`).
   - A meal-plan question (router → `household-manager-api` → `queue`).
   - "Agrega [some recipe]" (router → `start-workflow add-recipe` → full pipeline).
   Confirm behavior is identical to pre-phase.
2. Check LangWatch traces show the new prompt version filenames in run metadata (`V003.md`, `V004.md`, `V002.md`).

## Tests

`uv run pytest --ignore=tests/test_db_models.py --ignore=tests/test_gateway.py` — 171 passed.

DB-dependent tests (`tests/test_db_models.py` 4 tests, `tests/test_gateway.py` 6 tests + 6 errors) fail because local Postgres is not running. Pre-existing infra state, unrelated to Phase 14.
