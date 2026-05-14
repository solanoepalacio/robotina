---
phase: 14-prompt-cleanup-and-structural-standardization
plan: 04
status: complete
commit: 5d6b5bf
---

# Plan 14-04: recipe-research-instructions V002 → V003

Standardized skeleton applied; no behavioral change. `## Output` defers to `RecipeResearchInstructionsOutput`. The majority-consensus heuristic, single-action step constraint, and Argentine Spanish vocabulary requirement are preserved verbatim in `## Process` + `## Rules`. Registry test assertion synced.

`uv run pytest tests/unit/test_agents_registry.py` — 17 passed.
