---
phase: 04-llm-module-and-agent-infrastructure
plan: "05"
subsystem: agent-skill-loading
tags: [skills, langchain, security, path-traversal, household-manager]
dependency_graph:
  requires:
    - 04-01 (agent/__init__.py stub exists)
    - 04-03 (run_task in queue/jobs.py consumes SkillSet)
  provides:
    - SkillSet class for loading skill index.md at construction
    - ReadSkillTool BaseTool for on-demand sub-file loading
    - build_read_skill_tool() factory
    - household-manager skill at canonical src/robotina/agent/skills/ path
  affects:
    - 04-04 (run_task() uses build_read_skill_tool with SkillSet list)
tech_stack:
  added: []
  patterns:
    - pathlib.resolve() path traversal guard (base + target resolved before comparison)
    - BaseTool subclass with skill_dirs state (not @tool decorator — needs instance state)
    - Module-level SKILLS_BASE constant for patchability in tests
key_files:
  created:
    - src/robotina/agent/__init__.py
    - src/robotina/agent/skills/household-manager/index.md
    - src/robotina/agent/skills/household-manager/meal_plan.md
    - src/robotina/agent/skills/household-manager/recipes_create.md
    - src/robotina/agent/skills/household-manager/recipes_edit.md
    - src/robotina/agent/skills/household-manager/recipes_get.md
    - src/robotina/agent/skills/household-manager/recipes_image.md
    - src/robotina/agent/skills/household-manager/recipes_search.md
    - src/robotina/agent/skills/household-manager/shared.md
  modified:
    - tests/unit/test_skills.py
  deleted:
    - agent/skills/household-manager/ (entire old location)
decisions:
  - "SKILLS_BASE anchored to Path(__file__).parent / 'skills' — absolute path makes SkillSet testable without import manipulation"
  - "ReadSkillTool inherits BaseTool (not @tool) — needs skill_dirs instance state that @tool cannot hold"
  - "Module-level SKILLS_BASE (not class attribute) allows tests to patch it directly without monkeypatching the class"
metrics:
  duration_minutes: 2
  completed_date: "2026-03-26"
  tasks_completed: 2
  files_modified: 10
---

# Phase 04 Plan 05: SkillSet + ReadSkillTool + household-manager canonical location Summary

**One-liner:** SkillSet/ReadSkillTool skill loading infrastructure with pathlib.resolve() path traversal guard; household-manager moved from project root to src/robotina/agent/skills/.

## What Was Built

**Task 1 (TDD):** Implemented `SkillSet`, `ReadSkillTool`, and `build_read_skill_tool()` in `src/robotina/agent/__init__.py`. Written tests-first: 6 tests written (RED), then implementation written to pass them (GREEN).

**Task 2:** Moved all 8 household-manager skill files from `agent/skills/household-manager/` (project root) to `src/robotina/agent/skills/household-manager/` (canonical location per D-10). Old directory deleted.

## Key Implementation Details

- `SKILLS_BASE = Path(__file__).parent / "skills"` — anchored to `__init__.py` so it resolves to `src/robotina/agent/skills/` regardless of CWD
- `SkillSet.__init__` reads `SKILLS_BASE / skill_name / "index.md"` at construction — pre-loads content for agent system prompt
- `ReadSkillTool._run()` validates format (`skill-name/subfile.md`), checks skill name, then uses `pathlib.resolve()` on both base dir and target before comparing — defeats `..` and symlinks
- Path traversal check: `not str(target).startswith(str(base) + "/") and target != base` raises `ValueError` containing "traversal"

## Verification

```
6 passed in 0.06s  (uv run pytest tests/unit/test_skills.py -q)
src/robotina/agent/skills/household-manager/ contains all 8 files
agent/skills/ does NOT exist at project root
SkillSet('household-manager').index_content has 917 chars
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all implementations are fully functional.

## Self-Check

- [x] `src/robotina/agent/__init__.py` exists with SkillSet, ReadSkillTool, build_read_skill_tool
- [x] `src/robotina/agent/skills/household-manager/index.md` exists
- [x] All 8 skill files in canonical location
- [x] `agent/skills/` does NOT exist at project root
- [x] All 6 tests pass
- [x] Commits: 5cc66e7 (failing tests), 9093834 (implementation), 277cc6c (skill move)

## Self-Check: PASSED
