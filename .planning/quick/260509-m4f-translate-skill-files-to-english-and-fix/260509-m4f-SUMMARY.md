---
phase: quick
plan: 260509-m4f
subsystem: agent/skills
tags: [skills, prompts, i18n, recipe-research, household-manager, null-handling]
dependency_graph:
  requires: []
  provides:
    - "Uniform JSON null-handling rule across recipe-research and household-manager skill bundles"
    - "English-only instruction prose in every skill .md file"
  affects:
    - "recipe-research-gather agent (prior contradictory null guidance fixed)"
    - "recipe-research-{ingredients,instructions,metadata} agents (null guidance now consistent)"
    - "household-manager request-producing flows (canonical null rule attached)"
tech_stack:
  added: []
  patterns:
    - "Single canonical null-handling paragraph reused across all skill files that document agent-produced JSON"
    - "English instructions / Spanish example values split (instructions in English, mimicked outputs in Argentine Spanish)"
key_files:
  created: []
  modified:
    - src/robotina/agent/skills/recipe-research/gather.md
    - src/robotina/agent/skills/recipe-research/ingredients.md
    - src/robotina/agent/skills/recipe-research/instructions.md
    - src/robotina/agent/skills/recipe-research/metadata.md
    - src/robotina/agent/skills/recipe-research/index.md
    - src/robotina/agent/skills/household-manager/shared.md
    - src/robotina/agent/skills/household-manager/recipes_create.md
    - src/robotina/agent/skills/household-manager/recipes_edit.md
    - src/robotina/agent/skills/household-manager/meal_plan.md
decisions:
  - "Use a single canonical null-handling paragraph in every production-side skill file (full-paragraph repetition rather than cross-references) so a small model with sliced context always sees the rule."
  - "Keep household-manager/{recipes_get,recipes_image,recipes_search,index}.md untouched — they document responses the agent reads, not request bodies it produces, so the canonical rule does not apply."
  - "Restore main-repo skill files when initial Edit/Write calls accidentally targeted them via absolute paths constructed from a drifted cwd; redo all edits inside the worktree to land them on the per-agent branch."
metrics:
  duration_seconds: 497
  duration_human: "~8 min"
  completed: 2026-05-09
  files_modified: 9
  tasks_completed: 3
---

# Quick Task 260509-m4f: Translate skill files to English and unify null-handling guidance Summary

One-liner: every skill `.md` file under `src/robotina/agent/skills/` now has English instruction prose with Spanish example values intact, and a single canonical "JSON output rules" paragraph replaces the previous contradictory null-handling guidance in `gather.md` (which said `no uses null`) versus the sibling files (`ingredients.md`, `metadata.md`) that already used `null` in their JSON examples.

## What changed

### recipe-research bundle (5 files)

- **gather.md** — Translated all instruction headings (`Objetivo`/`Proceso`/`Manejo de errores`/`Formato de salida`) and prose to English. Replaced the contradictory line `Incluye todos los campos que puedas extraer. Los campos faltantes se omiten (no uses null).` with the canonical "JSON output rules" paragraph. Spanish search-query examples (`"Pasta Bolognesa facil de preparar"`, etc.) and the directive to write Spanish queries are preserved.
- **ingredients.md** — Translated all prose to English. Preserved Spanish food/unit/note example values (`cebolla`, `aceite de oliva`, `unidad`, `cucharada`, `picada`). Added the canonical paragraph below the JSON example.
- **instructions.md** — Translated all prose to English. Preserved Spanish step-body placeholders (`"Paso 1 de la receta"`, `"Nombre de la receta en espanol"`). Added the canonical paragraph.
- **metadata.md** — Translated all prose to English. Replaced the Spanish `IMPORTANTE: Los campos de tiempo NUNCA deben ser null...` and trailing `Todos los campos de tiempo... nunca null` lines with English equivalents. Added the canonical paragraph above the narrower time-fields-must-be-numeric rule, ordered general-rule → narrower-constraint as the plan specified.
- **index.md** — Translated `Pasos` / `Importante` headings and bundle overview prose to English. Preserved the directive that all model-produced content (recipe names, ingredients, descriptions) must be Argentine Spanish.

### household-manager bundle (4 files)

These were already English-only on entry (confirmed by the audit grep). Added the canonical "JSON output rules" paragraph to the four files that document agent-produced request bodies:

- **shared.md** — New `## JSON output rules` subsection between `## Pagination` and `## Filtering reference lists`. This is the canonical home; per-page restatements reference it.
- **recipes_create.md** — Added at the top, scoped to "every request body documented on this page".
- **recipes_edit.md** — Added at the top; the paragraph explicitly says the table column `Set null to clear` means the JSON literal `null`.
- **meal_plan.md** — Added at the top, even though most meal-plan request fields are required, to keep the rule uniformly visible.

### household-manager bundle — files NOT touched

`recipes_get.md`, `recipes_image.md`, `recipes_search.md`, and `index.md` document responses the agent reads (not request bodies it produces). Per the plan's task 2 step 2, the canonical paragraph does not apply to them. They were checked for stray Spanish prose during the audit grep and found clean.

## Verification

All four phase-level grep gates pass:

```
$ grep -rEi 'no uses null|Los campos faltantes|NUNCA deben' src/robotina/agent/skills/
(no output)

$ grep -rF '260509-m4f' src/robotina/agent/skills/
(no output)

$ for f in <8 production-side skill files>; do grep -q "JSON output rules" $f || echo MISSING $f; done
(no MISSING)

$ grep -E '^(# |## |### )(Objetivo|Proceso|Manejo|Construir|Buscar|Extraer|Formato|Pasos|Importante)' src/robotina/agent/skills/recipe-research/*.md
(no output)
```

`uv run pytest tests/` was run from the worktree:

```
10 failed, 146 passed, 2 warnings, 6 errors in 5.47s
```

Every failure is `sqlalchemy.exc.OperationalError: connection to server at "localhost"... port 5432 failed: Connection refused` from `tests/test_db_models.py` and `tests/test_gateway.py`. These are pre-existing infrastructure failures (Postgres not running locally) unrelated to skill-file content — skill `.md` files are read by the LLM at runtime and are not imported by any test. No test asserts on skill-file prose. **No new failures introduced by this change.**

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 3 — Blocking issue] Edit/Write tool calls initially targeted the main repo instead of the worktree**

- **Found during:** Task 1 commit step.
- **Issue:** The first round of Write/Edit calls used absolute paths under `/home/solanoe/code/robotina-gsd/src/...`, which resolves to the **main repo's** working tree. The worktree (where the per-agent commit must land) lives at `/home/solanoe/code/robotina-gsd/.claude/worktrees/agent-a34d92694737c23a6/src/...`. Result: edits applied to the wrong working tree; `git status` inside the worktree showed `nothing to commit, working tree clean` while the main repo had 9 dirty skill files plus unrelated dirty state.
- **Fix:**
  1. Restored the main-repo skill files to HEAD via `git checkout --` so the main repo carries no stray edits from this task.
  2. Re-Read each file at its absolute **worktree** path to satisfy the Edit/Write read-first invariant.
  3. Re-applied every edit using absolute paths rooted at the worktree (verified via `git rev-parse --show-toplevel` inside the worktree).
  4. Re-ran the verification block; all gates passed.
- **Files affected:** all 9 skill files (final commit landed on the worktree branch as intended).
- **Commit:** `94d8e0e` (the recovered, correct commit).
- **Root cause / preventive note:** the per-task commit protocol's "absolute-path safety" rule (#3099) anticipates exactly this failure: paths constructed from prior `pwd` output in an orchestrator context resolve to the main repo. For future executions, prefer relative paths from inside the worktree, or always recompute absolute paths from `git rev-parse --show-toplevel` run **inside** the target worktree.

### No other deviations

The plan's translation rule (English instructions / Spanish example values), null-handling rule (canonical paragraph + narrower time-fields constraint in metadata.md), and scope guardrails (no schema changes, no Python edits, no quick-task ID inside skill files) were followed exactly. No architectural decisions were required.

## Authentication gates

None. This task was 100% file edits with no external auth.

## Known stubs

None. The skill files do not introduce data-source stubs.

## Threat flags

None. Skill files are static prompt content; they do not expand the threat surface (no new endpoints, auth paths, file access patterns, or schema changes at trust boundaries).

## Self-Check: PASSED

Verified the commit and modified files exist:

- Commit `94d8e0e` in `git log --all` on branch `worktree-agent-a34d92694737c23a6`: FOUND.
- All 9 modified skill files present at the listed paths in the worktree (each Read in this task).
- `git diff --name-only HEAD~1 HEAD` returns exactly the 9 listed files; no deletions.
- All four phase-level verification grep gates return the expected results.
- Worktree `git status` is clean post-commit.

## Commit

`94d8e0e fix(skills): translate recipe-research skill files to English and unify null-handling guidance`

Branch: `worktree-agent-a34d92694737c23a6` (will be merged back to main by the orchestrator).
