---
phase: 16
plan: 06
subsystem: docs
tags: [docs, config, household-id]
requires: [16-01]
provides:
  - ".env.example HOUSEHOLD_ID block (operator-discoverable)"
  - "PROJECT.md Key Decisions row for Phase 16 contract"
  - "send.py docstring no longer references HOUSEHOLD_ID"
affects: [16-02, 16-03, 16-04, 16-05]
tech-stack:
  added: []
  patterns: []
key-files:
  created: []
  modified:
    - .env.example
    - src/robotina/gateway/send.py
    - .planning/PROJECT.md
decisions:
  - "Place HOUSEHOLD_ID under a new 'Gateway household identity (Phase 16+)' section between Telegram and Tavily — keeps gateway-related env vars grouped without disturbing existing section headers."
  - "Use `sys.exit(1)` (not RuntimeError) in the PROJECT.md decision text — resolves CONTEXT.md's loose 'RuntimeError at module import' wording per RESEARCH.md Open Q1; matches the actual gateway boot-guard pattern."
  - "Delete the stale `HOUSEHOLD_ID` docstring line from send.py rather than 'correct' it — RESEARCH.md Pitfall 3 confirmed the file's code path never reads the variable; documenting a non-existent dependency is worse than removing it."
metrics:
  duration: "~6 minutes"
  completed: 2026-05-15
  tasks: 3
  files_modified: 3
---

# Phase 16 Plan 06: Documentation & Cleanup Summary

**One-liner:** Operator-facing documentation (`.env.example`, `PROJECT.md`) and a stale-comment cleanup that close the docs surface of the Phase 16 empty-`household_id` fix — three zero-risk content edits with one automated test gate.

## What Was Built

Three content-only edits across docs and one source-file docstring:

1. **`.env.example`** — Added a new "Gateway household identity (Phase 16+)" section between the existing Telegram and Tavily blocks. Block contains a `REQUIRED` comment that names the failure mode (`sys.exit(1)` on missing/empty/whitespace), points to the two enforcement sites (`gateway/__init__.py::main`, `queue/task_types.py::NonEmptyHouseholdId`), and provides a placeholder `replace-with-your-household-uuid`. Closes **REQ-HID-6**.

2. **`src/robotina/gateway/send.py`** — Deleted the single stale docstring line `HOUSEHOLD_ID — used for Conversation lookup; defaults ""`. Per RESEARCH.md Pitfall 3, this file's code path never reads `HOUSEHOLD_ID`; the line was misleading and contradicted Phase 16's zero-default policy. No code changes — pure docstring fix. Closes **REQ-HID-7**.

3. **`.planning/PROJECT.md`** — Appended one row to the Key Decisions table recording the end-to-end `household_id` contract: gateway `sys.exit(1)` guard, Pydantic `NonEmptyHouseholdId` alias on 7 task-input models, tool constructor guards, and `queue_workflow` pre-write check. Closes **REQ-HID-8**.

### PROJECT.md row added (for the historical record)

```
| `household_id` is required and validated end-to-end (Phase 16) | A missing `HOUSEHOLD_ID` env var silently propagated as `""` through Conversation, IncomingMessageInput, WorkflowRun, and the household-manager-api tool, surfacing only as confusing 4xx responses from the backend. Phase 16 added defensive validation at four layers: gateway entrypoint (`sys.exit(1)` on missing/empty/whitespace), Pydantic task-input models (`NonEmptyHouseholdId` alias on 7 models), tool constructors (`HouseholdManagerApiTool`, `StartWorkflowTool` reject empty), and `queue_workflow` (raises ValueError before any DB write). | — Active |
```

## Test Transitions

| Test | Before | After | Notes |
| ---- | ------ | ----- | ----- |
| `tests/unit/test_env_example.py::test_env_example_exists` | GREEN | GREEN | File exists, no change required. |
| `tests/unit/test_env_example.py::test_household_id_documented` | RED (Wave 0) | **GREEN** | `^HOUSEHOLD_ID=` line now present. |
| `tests/unit/test_env_example.py::test_household_id_marked_required` | RED (Wave 0) | **GREEN** | Comment block above the line contains "REQUIRED". |

Run: `uv run pytest tests/unit/test_env_example.py -x -q` → `3 passed in 0.01s`.

## Commits

- `5ad5f2e` — `docs(16-06): document HOUSEHOLD_ID in .env.example` (Task 1, REQ-HID-6)
- `98ceb28` — `docs(16-06): remove stale HOUSEHOLD_ID reference from send.py docstring` (Task 2, REQ-HID-7)
- `5bb27eb` — `docs(16-06): record Phase 16 household_id validation Key Decision` (Task 3, REQ-HID-8)

## Confirmation: No `HOUSEHOLD_ID` reference remains in `send.py`

```
$ grep -c "HOUSEHOLD_ID" src/robotina/gateway/send.py
0
$ grep -c "TELEGRAM_BOT_TOKEN" src/robotina/gateway/send.py
2   # one in docstring "Env vars consumed", one in code (os.environ["..."])
$ grep -c "def send_message" src/robotina/gateway/send.py
1   # function signature untouched
```

## Deviations from Plan

None — plan executed exactly as written.

One process-level note (not a content deviation): during Task 2 commit, the working tree contained parallel-wave changes from plans 16-02, 16-04, and 16-05 (Wave 1 parallel work on `src/robotina/gateway/__init__.py`, `src/robotina/queue/workflow_runner.py`, `tests/test_workflow_runner.py`). The first attempt at the Task 2 commit accidentally absorbed those files because they had been staged before my edit. I caught it via `git show --stat HEAD` (which showed "4 files changed" instead of the expected "1 file changed"), did `git reset --soft HEAD~1` followed by selective `git reset HEAD <file>` to drop the non-owned files, and re-committed. The republished Task 2 commit (`98ceb28`) contains only the one-line docstring deletion in `src/robotina/gateway/send.py`. No work was lost; the parallel-wave files remained in the working tree for their respective executors to commit.

## Verification

All success criteria from the plan are satisfied:

- [x] **REQ-HID-6:** `grep -c "^HOUSEHOLD_ID=" .env.example` → `1`
- [x] **REQ-HID-7:** `! grep -i HOUSEHOLD_ID src/robotina/gateway/send.py` → exits 0
- [x] **REQ-HID-8:** `grep -c "household_id\` is required and validated end-to-end" .planning/PROJECT.md` → `1`
- [x] **Wave 0 env_example tests:** `uv run pytest tests/unit/test_env_example.py -x -q` → 3 passed
- [x] **Zero behavioral regression:** all three edits are content/documentation only; no executable code changed.

## Self-Check: PASSED

- File `/home/solanoe/code/robotina-gsd/.env.example`: FOUND (contains `HOUSEHOLD_ID=replace-with-your-household-uuid`)
- File `/home/solanoe/code/robotina-gsd/src/robotina/gateway/send.py`: FOUND (no `HOUSEHOLD_ID` reference)
- File `/home/solanoe/code/robotina-gsd/.planning/PROJECT.md`: FOUND (Key Decisions row present)
- Commit `5ad5f2e`: FOUND
- Commit `98ceb28`: FOUND
- Commit `5bb27eb`: FOUND
