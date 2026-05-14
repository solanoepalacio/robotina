---
phase: 14-prompt-cleanup-and-structural-standardization
plan: 07
status: complete
commit: 14dcf47
---

# Plan 14-07: recipe-load V003 → V004

## What landed

- `src/robotina/agent/prompts/recipe-load/V004.md` with the standardized skeleton.
- `AGENT_REGISTRY['recipe-load'].prompt_path` updated to V004.md.
- Registry test assertion synced (V003 → V004; the V002 → V003 sync from plan 14-01 is also captured by this final state).

## Hallucination guardrail preserved

V003's "The only failure mode that matters" prose is reorganized into `## Rules` while preserving the load-bearing phrasing: "A real `recipe_id` looks like a UUID … in the JSON the API just returned. If you find yourself typing a UUID that wasn't in the response, stop — you are about to hallucinate."

## Field-mapping table preserved

The snake_case → camelCase table for `servingsQty`, `servingsUnit`, `prepTime`, `cookTime`, `totalTime`, `sourceUrl` is preserved verbatim inside `## Process` step 2.

## Skeleton deviation

`## Process` step 2 contains a Markdown table inline with the numbered list. This is a deliberate deviation from the "single-action numbered steps" convention because the field-mapping table is load-bearing for the agent's behavior and inlining it keeps the operator's eye on the renaming during step execution. Alternative would have been a `## Field Mapping` subsection, but the skeleton has no `## Field Mapping` slot and the rename rule belongs to step 2 conceptually.

## Behavioral parity

| V003 section | V004 location |
|--------------|---------------|
| `# The only failure mode that matters` | `## Rules` (hallucination guardrail, paraphrased) |
| `# Inputs you already have` | `## Inputs` |
| `# Tools` (with both `household-manager-api` and `read-skill`) | `## Tools` |
| `# Field mapping (input → API)` | `## Process` step 2 (table preserved) |
| `# Resolving ingredient names` | `## Process` steps 3 and 4 |
| `# Building and sending the request` | `## Process` steps 5 and 6 |
| `# Filling the output` | `## Process` step 7 |
| `# If POST fails` | `## Process` step 8 + `## Rules` bullet |

## Pre-existing scope note

`overrides/anthropic.json` has no `recipe-load` entry. This pre-existing gap is out of scope for Phase 14 (CONTEXT.md scoped this phase to "prompt files, registry, and overrides" without mandating cross-override coverage). Flagged in plan 14-08's smoke summary for future cleanup.

## Tests

`uv run pytest tests/unit/test_agents_registry.py` — 17 passed.
