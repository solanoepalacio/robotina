---
phase: quick
plan: 260327-gs5
subsystem: queue/runner
tags:

  - rq
  - worker
  - langwatch
  - simpleworker
  - fork-elimination

dependency_graph:
  requires: []
  provides: [LoggingWorker(SimpleWorker), simplified LangWatch setup]
  affects: [src/robotina/queue/runner.py, tests/test_queue_models.py]
tech_stack:
  added: []
  patterns:

    - SimpleWorker in-process execution
    - single LangWatch setup in main()

key_files:
  created: []
  modified: [src/robotina/queue/runner.py, tests/test_queue_models.py]
decisions:

  - LoggingWorker now extends rq.worker.SimpleWorker (not Worker) — eliminates os.fork(), making OTel/LangWatch safe at main() startup
  - _setup_langwatch_in_workhorse renamed to _setup_langwatch and moved to main() — no fork-reset workarounds needed in-process

metrics:
  duration: < 5min
  completed_date: 2026-03-27
  tasks_completed: 2
  files_modified: 2
status: complete
---

# Phase quick Plan 260327-gs5: Switch LoggingWorker to SimpleWorker Summary

**One-liner:** LoggingWorker now extends SimpleWorker (in-process, no fork), removing all OTel/LangWatch post-fork reset workarounds and simplifying LangWatch setup to a single call in main().

## What Was Done

Switched `LoggingWorker` from extending `rq.Worker` (fork-based) to `rq.worker.SimpleWorker` (in-process). This eliminated the entire `_setup_langwatch_in_workhorse()` workaround pattern — the `Client._reset_instance()`, `_TRACER_PROVIDER` null reset, and `Once` guard reset that only existed because `os.fork()` killed the `BatchSpanProcessor` thread in the child.

LangWatch is now initialized once in `main()` via `_setup_langwatch()` (renamed from `_setup_langwatch_in_workhorse`). The `perform_job()` method is clean: just lifecycle logging, no import hacks, no subprocess setup.

Test updated to assert `issubclass(LoggingWorker, SimpleWorker)` with appropriate messaging.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Switch LoggingWorker to SimpleWorker, simplify LangWatch setup | fd65e3b |
| 2 | Update test assertion to SimpleWorker inheritance | ea3c177 |

## Verification

All 8 tests in `tests/test_queue_models.py` pass.

Confirmed:

- No fork-related imports (`Client._reset_instance`, `opentelemetry.util._once`) remain in runner.py
- `_setup_langwatch()` called in `main()` before `worker.work()`
- `perform_job()` has no `basicConfig` or langwatch call
- `LoggingWorker(SimpleWorker)` class declaration in place

## Deviations from Plan

**1. [Rule 1 - Bug] Removed unused Worker import from test_logging_worker_overrides_perform_job**

- **Found during:** Task 2
- **Issue:** After changing test_logging_worker_is_worker_subclass, a second test (`test_logging_worker_overrides_perform_job`) still had `from rq import Worker` as an unused import.
- **Fix:** Removed the unused import from that test function.
- **Files modified:** tests/test_queue_models.py
- **Commit:** ea3c177

## Known Stubs

None.

## Self-Check: PASSED
