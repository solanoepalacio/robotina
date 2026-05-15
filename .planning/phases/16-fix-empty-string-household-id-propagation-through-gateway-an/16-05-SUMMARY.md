---
phase: 16
plan: 05
subsystem: gateway
tags:
  - python
  - gateway
  - config
  - household_id
  - fail-fast
requirements:
  - REQ-HID-5
dependency-graph:
  requires:
    - 16-01 (autouse `_set_household_id` conftest fixture so handler bracket-form read is safe in tests)
  provides:
    - Gateway refuses to boot when `HOUSEHOLD_ID` is unset/empty/whitespace (SPEC R1)
    - Handler.py reads `HOUSEHOLD_ID` via bracket form (no silent `""` default)
  affects:
    - 16-02 (downstream Pydantic guard now backstopped by gateway entrypoint guard)
    - 16-04 (queue_workflow guard now backstopped by gateway entrypoint guard)
tech-stack:
  added: []
  patterns:
    - Fail-fast in entrypoint `main()` via `sys.exit(1)` with stderr message naming the env var (RESEARCH Pattern 2)
    - Per-message bracket-form env read for defense-in-depth (RESEARCH Pattern 4)
key-files:
  created: []
  modified:
    - src/robotina/gateway/__init__.py
    - src/robotina/gateway/handler.py
decisions:
  - "`HOUSEHOLD_ID` is required end-to-end; the gateway entrypoint is the single fail-fast point (SPEC R1), with handler bracket-form read as a paranoia backstop."
metrics:
  duration_seconds: 326
  duration_minutes: 5
  completed_at: "2026-05-15T18:52:00Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 16 Plan 05: Gateway Dual-Guard for HOUSEHOLD_ID Summary

Dual-guard adopted: fail-fast `sys.exit(1)` in `gateway/__init__.py::main()` plus bracket-form `os.environ["HOUSEHOLD_ID"]` read in `handler.py::handle_message`. Wave 0 boot tests (`test_gateway_boot.py`) flipped from RED to GREEN; existing gateway tests still pass via the autouse `_set_household_id` conftest fixture from plan 16-01.

## What Was Implemented

### Task 1 — gateway/__init__.py fail-fast guard

Two changes to `src/robotina/gateway/__init__.py`:

1. Added `import sys` to the top-of-file import block.
2. Inserted a fail-fast guard inside `main()` between `logging.basicConfig(...)` and `token = os.environ["TELEGRAM_BOT_TOKEN"]`:

```python
household_id = os.environ.get("HOUSEHOLD_ID", "").strip()
if not household_id:
    sys.stderr.write(
        "FATAL: HOUSEHOLD_ID environment variable is unset or empty.\n"
        "  The gateway refuses to start because every Conversation and "
        "WorkflowRun row would otherwise carry an empty household_id.\n"
        "  Set HOUSEHOLD_ID in your .env file (see .env.example) and retry.\n"
    )
    sys.exit(1)
```

The guard uses `.get(...).strip()` (not bracket form) because SPEC R1 requires that **unset, empty, and whitespace-only** all produce the same failure outcome — bracket form would only catch "unset" via `KeyError` and would not catch `""` or `"   "`. The strip-then-check is the only idiom that handles all three uniformly.

Docstring updated to document HOUSEHOLD_ID alongside TELEGRAM_BOT_TOKEN. Boot log line now includes `household_id=%s` so operators can confirm the active value at startup.

### Task 2 — handler.py bracket-form read + docstring fix

Two changes to `src/robotina/gateway/handler.py`:

1. Replaced `household_id = os.environ.get("HOUSEHOLD_ID", "")` at line 43 with `household_id = os.environ["HOUSEHOLD_ID"]`. The bracket form raises `KeyError` if the env var is unset — a clean, named failure mode if any caller imports `handle_message` and runs it without going through `main()`.
2. Updated the module docstring (line 11 area) so HOUSEHOLD_ID is documented as `REQUIRED for Conversation; KeyError on missing (Phase 16, REQ-HID-5)` instead of the previous `defaults ""` wording. Added cross-reference to the entrypoint guard.

The autouse `_set_household_id` fixture in `tests/conftest.py` (plan 16-01) injects `HOUSEHOLD_ID=test-household` for every test, so the bracket-form read does not break unrelated gateway tests.

## Wave 0 Test Transition

`tests/unit/test_gateway_boot.py` (added in plan 16-01) drives this plan:

| Test | Before 16-05 | After 16-05 |
|------|--------------|-------------|
| `test_main_exits_on_missing_household_id` | RED (process tries to start Telegram polling, fails on invalid token, stderr contains traceback but not "HOUSEHOLD_ID" as an env-var name) | GREEN (exit 1, stderr mentions HOUSEHOLD_ID) |
| `test_main_exits_on_empty_household_id` | RED | GREEN |
| `test_main_exits_on_whitespace_household_id` | RED | GREEN |
| `test_main_boots_with_valid_household_id` | RED | GREEN |

Confirmed by running `uv run pytest tests/unit/test_gateway_boot.py -x -q` → `4 passed`.

## Pre-existing Gateway Tests

`tests/test_gateway.py` continues to pass for all HOUSEHOLD_ID-related cases (5/6 pass). Verified by running with `.env` loaded (Postgres on port 5433):

```
1 failed, 5 passed in 0.14s
```

The single failure (`test_send_message_persists`) is unrelated to plan 16-05 — see "Deferred Issues" below.

## Operator-facing UX

Example stderr an operator sees in a misconfigured deploy (`unset HOUSEHOLD_ID; uv run gateway`):

```
FATAL: HOUSEHOLD_ID environment variable is unset or empty.
  The gateway refuses to start because every Conversation and WorkflowRun row would otherwise carry an empty household_id.
  Set HOUSEHOLD_ID in your .env file (see .env.example) and retry.
```

Exit code: `1`. No Python traceback — operator immediately sees the named env var and the remediation path.

On successful boot (`HOUSEHOLD_ID=hh-smoke` set), the gateway logs:

```
INFO:robotina.gateway:Starting Telegram gateway (polling mode) | household_id=hh-smoke
```

## Deviations from Plan

### Deviation 1 — CONTEXT.md "RuntimeError at handler module import" implemented as `sys.exit(1)` at gateway entrypoint

**Why:** CONTEXT.md Failure Strategy said "raise `RuntimeError` at handler module import via `os.environ['HOUSEHOLD_ID']`". RESEARCH.md Open Q1 (and Pitfall 1) flagged this as test-collection-breaking: pytest imports `robotina.gateway.handler` during collection (5 test files do `from robotina.gateway.handler import handle_message`), so a module-scope raise would prevent pytest from even discovering tests.

The plan resolved this by adopting RESEARCH Pattern 2 (entrypoint guard in `gateway/__init__.py::main()`) combined with RESEARCH Pattern 4 (per-message bracket-form read in `handler.py::handle_message`). Both behaviors satisfy the CONTEXT.md contract — non-zero exit, named stderr message, process refuses to start — without the test-collection hazard.

This is a planning-time deviation (CONTEXT.md → SPEC → PLAN); execution followed the plan exactly. Documented here per the PLAN's explicit "Deviation note" instruction.

### Deviation 2 — `[Rule 1 — Bug recovery] Task 1 commit attributed to parallel agent`

**What happened:** During Task 1 execution, parallel-wave agents (16-02, 16-04, 16-06) were committing to `main` concurrently. While I had `src/robotina/gateway/__init__.py` staged, another agent's commit operation absorbed my staged changes into `d7694bc docs(16-02): complete Pydantic NonEmptyHouseholdId plan summary`. My own commit at HEAD@{5} (`d5b73c2`) was force-reset to HEAD~1 by another agent's reset before my next operation, undoing my commit but preserving the working-tree changes.

**Why I did not retry-rewrite:** Rewriting history (interactive rebase / force push) would risk corrupting the parallel agents' commits and is explicitly forbidden by the executor's `<destructive_git_prohibition>` rule. The functional code IS in `main` at the correct file paths and the Wave 0 tests are GREEN — the attribution is the only issue.

**Affected commits:**
- Task 1 (`src/robotina/gateway/__init__.py` fail-fast guard) is in commit `d7694bc` with the misleading message `docs(16-02): complete Pydantic NonEmptyHouseholdId plan summary` — the commit also contains the legitimate 16-02 summary file, but the diff includes my Task 1 source edits.
- Task 2 (`src/robotina/gateway/handler.py` bracket-form read) is in my clean commit `4c8693d fix(16-05): handler.py uses bracket-form HOUSEHOLD_ID read (no silent default)`.

**Operator-visible impact:** None. `git log -p src/robotina/gateway/__init__.py` still shows the change diff. The Phase 16 plan-checker / Nyquist run will see both files updated and both tests GREEN.

**Future mitigation:** Parallel agents in the same wave should operate on disjoint file sets and ideally on dedicated worktrees. The Wave 1 plan files declared disjoint file ownership but the parallel agents ran on the same `main` branch without worktree isolation.

## Deferred Issues

### `tests/test_gateway.py::test_send_message_persists` SendResult vs str assertion mismatch

- **File:** `tests/test_gateway.py:127`
- **Failure:** `assert result == "7777"` but `result` is `SendResult(message_id='7777')`
- **Cause:** Pre-existing — `send.py::send_message` returns a `SendResult` dataclass; the test was written when the return type was raw `str`. Likely Phase 6 evolved the return type without updating the test.
- **Why deferred:** Not caused by plan 16-05 changes; out of scope per SCOPE BOUNDARY rule (executor only auto-fixes regressions caused by the current task).
- **Suggested follow-up:** Either update the assertion to `result.message_id == "7777"` or change `send_message` to return raw str. Logged in `deferred-items.md`.

## Plan-level Verification (post-execution)

```bash
$ grep -rE 'os.environ.get\(.HOUSEHOLD_ID.' src/robotina/
src/robotina/gateway/__init__.py:38:    household_id = os.environ.get("HOUSEHOLD_ID", "").strip()
```

Returns 1 match (not 0 as the PLAN's verification block expected). The plan's verification snippet conflicts with the PLAN's own Task 1 action text, which explicitly uses `os.environ.get("HOUSEHOLD_ID", "").strip()` — required to detect whitespace-only values per SPEC R1. The handler.py silent default IS eliminated (the only remaining `.get(...)` is the entrypoint guard, which is intentional and SPEC-mandated). Treating the PLAN verification line as the inconsistency rather than re-implementing.

```bash
$ grep -rEn 'os.environ\[.HOUSEHOLD_ID.\]' src/robotina/
src/robotina/gateway/handler.py:50:    household_id = os.environ["HOUSEHOLD_ID"]
```

1 bracket-form match (in handler.py). The PLAN's verification said `>= 2` (expecting one in `__init__.py` and one in `handler.py`), but Task 1's action explicitly specified `.get(...).strip()` for the entrypoint guard, so the bracket form correctly appears only in handler.py.

```bash
$ grep -c 'HOUSEHOLD_ID' src/robotina/gateway/send.py
0
```

Plan expected `>= 1` (stale docstring still present, 16-06 would clean up). Plan 16-06 already landed and cleaned it (commit `98ceb28 docs(16-06): remove stale HOUSEHOLD_ID reference from send.py docstring`), so the count is 0 instead. Not a regression — better state.

## Commit Hashes

| Task | Commit | Files | Notes |
|------|--------|-------|-------|
| 1 (gateway/__init__.py guard) | `d7694bc` | src/robotina/gateway/__init__.py (+1 file: 16-02 summary) | Commit message attributes to 16-02 due to parallel-agent race (Deviation 2). Functional code correct. |
| 2 (handler.py bracket form) | `4c8693d` | src/robotina/gateway/handler.py | Clean fix(16-05) commit. |

## Self-Check: PASSED

Verified via:
```bash
$ uv run pytest tests/unit/test_gateway_boot.py -x -q
4 passed in 1.16s

$ grep -c 'os.environ\["HOUSEHOLD_ID"\]' src/robotina/gateway/handler.py
1

$ grep -c 'sys.exit(1)' src/robotina/gateway/__init__.py
2   # one in docstring reference, one in actual code path

$ grep -n '^        sys.exit(1)' src/robotina/gateway/__init__.py
46:        sys.exit(1)
```

- [x] `src/robotina/gateway/__init__.py` contains `import sys`, the fail-fast guard, the FATAL stderr message, and the `.env.example` reference — VERIFIED at HEAD.
- [x] `src/robotina/gateway/handler.py` contains the bracket-form read and the updated docstring — VERIFIED at HEAD.
- [x] All 4 Wave 0 boot tests GREEN — VERIFIED.
- [x] Task 1 changes present in commit `d7694bc` (attribution noted as deviation) — VERIFIED via `git log -p`.
- [x] Task 2 commit `4c8693d` clean (1 file, 9 insertions, 2 deletions, no deletions) — VERIFIED.
