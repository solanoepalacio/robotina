---
phase: 16
plan: 03
subsystem: agent-tools
tags: [pydantic, langchain, tools, python, validation, household_id, REQ-HID-3]
wave: 2
dependency_graph:
  requires: [16-01, 16-02]
  provides:
    - "Construction-time non-empty household_id validation on HouseholdManagerApiTool"
    - "Construction-time non-empty household_id validation on StartWorkflowTool"
    - "Removal of literal '' default on StartWorkflowTool.household_id (Pitfall 5 closed)"
    - "Removal of silent shared_context.get('household_id', '') fallback (Pitfall 4 closed)"
  affects:
    - src/robotina/agent/tools/household_manager_api.py
    - src/robotina/agent/tools/start_workflow.py
    - tests/unit/test_household_manager_api_tool.py
    - tests/unit/test_start_workflow_tool.py
tech_stack:
  added: []
  patterns:
    - "Apply NonEmptyHouseholdId Annotated alias to pydantic-based BaseTool subclass fields"
    - "Pydantic-native validation at tool construction (raises ValidationError, not bespoke ValueError)"
    - "Bracket-form dict access (shared_context['household_id']) to remove silent '' masks"
key_files:
  created: []
  modified:
    - src/robotina/agent/tools/household_manager_api.py
    - src/robotina/agent/tools/start_workflow.py
    - tests/unit/test_household_manager_api_tool.py
    - tests/unit/test_start_workflow_tool.py
decisions:
  - "Use pydantic-native NonEmptyHouseholdId (from 16-02) rather than model_validator — cleaner, matches the project pattern, and ValidationError is a ValueError subclass so any caller expecting ValueError still works."
  - "Remove the '= \"\"' default on StartWorkflowTool.household_id entirely (per Pitfall 5). Caller (jobs.py:148) already passes household_id at every construction site, so this is safe."
  - "Bracket-form shared_context['household_id'] in _run (Pitfall 4). The line above (setdefault) guarantees the key is present unless an explicit empty was forced, and that path falls through to queue_workflow's raise (16-04)."
  - "chat_id / user_id / platform defaults on StartWorkflowTool left as '' — out of Phase 16 scope (they have their own coverage paths)."
metrics:
  duration_seconds: 158
  completed_at: 2026-05-15T18:58:07Z
  tasks_completed: 2
  commits: 4
  files_modified: 4
requirements:
  - REQ-HID-3
---

# Phase 16 Plan 03: Tool Constructor Validation Summary

Third defensive layer (after gateway boot guard and task-input Pydantic models) for the empty-string `household_id` propagation bug — `HouseholdManagerApiTool` and `StartWorkflowTool` now reject empty / whitespace-only `household_id` at construction via the `NonEmptyHouseholdId` alias, and the two known silent-fallback paths in `StartWorkflowTool` (literal `""` default + `.get("household_id", "")`) are eliminated.

## Outcome

Both Pydantic-based `BaseTool` subclasses that carry `household_id` now fail loudly at `__init__` rather than storing an empty string and propagating it. The bracket-form `shared_context["household_id"]` in `StartWorkflowTool._run` removes the last masking site identified in 16-RESEARCH.md (Pitfalls 4 + 5).

REQ-HID-3 fully covered.

## What Changed

### Source edits

**`src/robotina/agent/tools/household_manager_api.py`** (2 edits)
- Add `from robotina.queue.task_types import NonEmptyHouseholdId`
- Change class field `household_id: str` → `household_id: NonEmptyHouseholdId` (line ~221)

**`src/robotina/agent/tools/start_workflow.py`** (3 edits)
- Add `from robotina.queue.task_types import NonEmptyHouseholdId`
- Change class field `household_id: str = ""` → `household_id: NonEmptyHouseholdId` — **literal `""` default REMOVED** (Pitfall 5)
- In `_run()`, change `household_id = shared_context.get("household_id", "")` → `household_id = shared_context["household_id"]` — **silent fallback REMOVED** (Pitfall 4)

### Test edits (append-only)

**`tests/unit/test_household_manager_api_tool.py`** — appended 3 functions:
- `test_constructor_rejects_empty_household_id` — `household_id=""` → `pydantic.ValidationError`
- `test_constructor_rejects_whitespace_household_id` — `household_id="   "` → `pydantic.ValidationError`
- `test_constructor_accepts_non_empty_household_id` — regression guard with `"hh-1"`

**`tests/unit/test_start_workflow_tool.py`** — appended 3 functions:
- `test_constructor_rejects_empty_household_id` — explicit `household_id=""`
- `test_constructor_requires_household_id_no_default` — omitted entirely, proves Pitfall 5 is closed
- `test_constructor_accepts_non_empty_household_id` — regression guard with `"h1"`

## Verification

### grep audits

| Check | Command | Result |
|-------|---------|--------|
| New import in household_manager_api.py | `grep -c 'from robotina.queue.task_types import NonEmptyHouseholdId' src/robotina/agent/tools/household_manager_api.py` | `1` ✓ |
| New field in household_manager_api.py | `grep -cE '^\s+household_id: NonEmptyHouseholdId$' src/robotina/agent/tools/household_manager_api.py` | `1` ✓ |
| Old `household_id: str` removed | `grep -cE '^\s+household_id: str$' src/robotina/agent/tools/household_manager_api.py` | `0` ✓ |
| New import in start_workflow.py | `grep -c 'from robotina.queue.task_types import NonEmptyHouseholdId' src/robotina/agent/tools/start_workflow.py` | `1` ✓ |
| New field in start_workflow.py | `grep -cE '^\s+household_id: NonEmptyHouseholdId$' src/robotina/agent/tools/start_workflow.py` | `1` ✓ |
| `household_id: str = ""` default REMOVED | `grep -cE 'household_id: str = ""' src/robotina/agent/tools/start_workflow.py` | `0` ✓ |
| `.get("household_id", "")` fallback REMOVED | `grep -cE 'shared_context\.get\(.household_id.' src/robotina/agent/tools/start_workflow.py` | `0` ✓ |
| Bracket form present | `grep -cE 'shared_context\[.household_id.\]' src/robotina/agent/tools/start_workflow.py` | `1` ✓ |
| Plan-level negative grep | `grep -nE 'household_id: str(\s*=\|\s*$)' src/robotina/agent/tools/{start_workflow,household_manager_api}.py` | (no matches) ✓ |

### pytest

| Command | Result |
|---------|--------|
| `uv run pytest tests/unit/test_household_manager_api_tool.py -x -q` | 19 passed (16 pre-existing + 3 new) |
| `uv run pytest tests/unit/test_start_workflow_tool.py -x -q` | 12 passed (9 pre-existing + 3 new) |
| `uv run pytest tests/unit/test_household_manager_api_tool.py tests/unit/test_start_workflow_tool.py -x -q` | 31 passed |
| `uv run pytest tests/unit -x -q -k "household_id"` | 34 passed, 99 deselected |
| `uv run pytest tests/unit -q` (full unit suite regression check) | **133 passed** — no regressions |

### Test-count delta

| File | Pre-plan tests | Post-plan tests | Delta |
|------|----------------|------------------|-------|
| `tests/unit/test_household_manager_api_tool.py` | 16 | 19 | +3 |
| `tests/unit/test_start_workflow_tool.py` | 9 | 12 | +3 |
| **Total** | **25** | **31** | **+6** |

## Commits

| Hash | Type | Message |
|------|------|---------|
| `6edbfbb` | test | `test(16-03): add failing tests — HouseholdManagerApiTool must reject empty household_id` |
| `13450bf` | feat | `feat(16-03): HouseholdManagerApiTool rejects empty household_id at construction` |
| `8bee618` | test | `test(16-03): add failing tests — StartWorkflowTool must reject empty household_id` |
| `19a0475` | feat | `feat(16-03): StartWorkflowTool requires non-empty household_id; remove silent fallbacks` |

TDD RED → GREEN gate sequence observed on both tasks (test commit before implementation commit).

## Deviations from Plan

None — plan executed exactly as written.

## TDD Gate Compliance

- Task 1 (HouseholdManagerApiTool): RED commit `6edbfbb` (test-only) followed by GREEN commit `13450bf` (source).
- Task 2 (StartWorkflowTool): RED commit `8bee618` (test-only) followed by GREEN commit `19a0475` (source).
- No REFACTOR commits needed — implementation already minimal.

## Known Stubs

None. All edits replaced existing code with stronger validation; no placeholders introduced.

## Threat Flags

None. This plan removes attack surface (silent tenant-id empty bypass) — it does not add new boundaries.

## Self-Check: PASSED

- [x] All 4 modified files exist on disk
- [x] All 4 commits (`6edbfbb`, `13450bf`, `8bee618`, `19a0475`) exist in `git log --all`
- [x] All 9 grep acceptance criteria pass (Task 1 + Task 2)
- [x] `uv run pytest tests/unit -q` returns 133 passed, 0 failed
- [x] Two TDD RED→GREEN sequences observed in commit log
