---
phase: 14-prompt-cleanup-and-structural-standardization
plan: 02
status: complete
commit: 7ab3002
---

# Plan 14-02: acknowledge-add-recipe V001 → V002

## What landed

- `src/robotina/agent/prompts/acknowledge-add-recipe/V002.md` with the standardized skeleton.
- `AGENT_REGISTRY['acknowledge-add-recipe'].prompt_path` updated to V002.md.
- `tests/unit/test_agents_registry.py::test_acknowledge_add_recipe_registered` assertion updated.

## Behavioral parity

| V001 constraint | V002 location |
|-----------------|---------------|
| Brief 1–2 sentence Spanish acknowledgment | `## Process` step 1 |
| Mention data will be updated in the application | `## Process` step 2 |
| Single `queue` call, then stop | `## Process` step 3 + `## Rules` bullet |
| Warm, casual family-household tone | `## Rules` bullet |
| Plain text, no Markdown | `## Rules` bullet |
| No outcome / timeframe promises, no follow-up questions | `## Rules` bullets |
| No recipe details (added later by workflow) | `## Rules` bullet |
| Single language reminder | `## Rules` bullet (replaces the V001 top banner) |

The V001 example block ("Voy a buscar la receta de bocaditos de arroz...") is preserved as `### Example`.

## Override diffs

None expected; none observed. Override files unchanged.

## Tests

`uv run pytest tests/unit/test_agents_registry.py` — 17 passed.
