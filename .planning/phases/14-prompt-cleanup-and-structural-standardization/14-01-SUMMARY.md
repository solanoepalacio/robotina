---
phase: 14-prompt-cleanup-and-structural-standardization
plan: 01
status: complete
commit: a30e03f
---

# Plan 14-01: robotina V002 → V003

## What landed

- New `src/robotina/agent/prompts/robotina/V003.md` adopting the standardized skeleton — **Role / Inputs / Tools / Process / Rules / Output**.
- `AGENT_REGISTRY['handle-incoming-message'].prompt_path` updated to V003.md.
- `tests/unit/test_agents_registry.py` assertions for handle-incoming-message updated to V003.md.

## Skeleton convention adopted

The six standardized section headers establish the convention for plans 14-02..14-07:

1. `## Role` — one-paragraph description of what the agent does.
2. `## Inputs` — what arrives in the user message (workflow shared_context, prior step outputs).
3. `## Tools` — bullet list with short per-tool description.
4. `## Process` — numbered, single-action steps.
5. `## Rules` — bullet constraints (language, schema, behavioral guardrails).
6. `## Output` — short paragraph either pointing to the Pydantic response model in `src/robotina/queue/task_types.py` (for agents WITH `response_format_model`) or describing the terminating tool call (for agents WITHOUT).

## Removed prose

- The V002 top banner `> **IMPORTANT: You MUST always respond to the user in Spanish...`. The Spanish-output rule now appears once, inside `## Rules`.
- The V002 `## Failure modes to avoid` section. Its WRONG/RIGHT examples were duplicates of guidance already in `## Rules` and `## Process`. Eliminated as a dedup target.

## Behavioral parity check

Every V002 behavioral constraint maps to a V003 line:

| V002 constraint | V003 location |
|-----------------|---------------|
| Every turn ends in a tool call (`queue` or `start-workflow`) | `## Rules` bullet |
| Routing question and Yes/No decision | `## Process` step 2 |
| Plain assistant text is never delivered | `## Rules` bullet |
| For `start-workflow` requests do NOT additionally call `queue` | `## Tools` description of `start-workflow` |
| `household-manager-api` is intermediate (does not terminate the turn) | `## Tools` description of `household-manager-api` |
| Pass only task-specific fields in `shared_context`; `reply_context` / `household_id` are injected | `## Process` step 4 + `## Inputs` bullet |
| Read the `household-manager` skill before the first API call | `## Tools` description |
| Ambiguous → clarify via `queue` in Spanish | `## Rules` bullet |
| Don't enumerate workflow type names in reasoning | `## Rules` bullet |

The `queue` / `start-workflow` example sections are preserved as `### Examples — direct reply` and `### Examples — multi-step task` subsections — kept for operator pattern-matching.

## Override file diffs

Expected: none. All three `overrides/*.json` files already lack `prompt_path` keys for `handle-incoming-message` (registry is the single source of truth for prompt paths). Confirmed by smoke check before commit.

`overrides/openai.json` has a pre-existing uncommitted diff (`gpt-4o-mini` → `gpt-4.1-mini` model upgrade) unrelated to Phase 14 — left untouched in this commit, not included in the staged tree.

## Test suite status

- `uv run pytest --ignore=tests/test_db_models.py --ignore=tests/test_gateway.py` → 171 passed.
- DB-dependent tests (`tests/test_db_models.py`, `tests/test_gateway.py`) fail because local Postgres is not running — pre-existing infra state, unrelated to Phase 14.

## Pre-existing test sync

`test_recipe_load_registered` asserted `recipe-load/V002.md` but the registry has carried `V003.md` since a prior phase (likely Phase 11). The mismatch failed before any Phase 14 edit. Synced the assertion to `V003.md` in this commit so the unit suite is green during the phase. Plan 14-07 will bump the assertion again to `V004.md` when it lands `recipe-load/V004.md`.
