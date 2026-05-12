# Decision: Switch LoggingWorker to SimpleWorker

## Context

`LoggingWorker` currently extends RQ's `Worker`, which forks a child process (work-horse) for every job. This creates two recurring problems:

1. **OTel/LangWatch breakage after fork** — `os.fork()` copies only the calling thread. Background threads (OTel BatchSpanProcessor, connection pools) die silently in the child. This forced the addition of `_setup_langwatch_in_workhorse()` which manually resets the LangWatch singleton and OTel global tracer provider after every fork. It works today but is fragile — it relies on LangWatch internal ClassVars and OTel's `Once` guard, both of which are implementation details subject to change without notice.

2. **Python 3.12 DeprecationWarning in tests** — pytest is multi-threaded; calling `os.fork()` from a multi-threaded process emits `DeprecationWarning: This process is multi-threaded, use of fork() may lead to deadlocks in the child`. Integration tests already switched to `SimpleWorker` to avoid this, creating an inconsistency between test and production worker.

## What fork() actually buys us

- **Crash isolation** — if a job calls `sys.exit()`, gets OOM-killed, or receives a fatal signal, only the child dies; the parent worker survives.
- **Memory isolation** — each job starts from a copy-on-write snapshot; memory leaks in one job don't accumulate across jobs.

## Why those benefits don't apply here

- Jobs are pure Python / LangChain agent calls — no native extensions that can segfault.
- Unhandled exceptions are already caught by `run_task()`'s try/except; those don't need fork isolation.
- `sys.exit()` in agent code would be a bug, not a design constraint.
- OOM is unlikely for LLM API calls (network-bound, not memory-bound).

## Proposed change

1. Change `LoggingWorker` to extend `SimpleWorker` instead of `Worker`.
2. Remove `_setup_langwatch_in_workhorse()` entirely.
3. Move `langwatch.setup()` to `main()` before starting the worker (standard single-process init).
4. Update the docstring on `LoggingWorker` — remove the fork-specific notes.

`perform_job()` override for structured logging is unaffected; `SimpleWorker` also calls `perform_job()`.

## Files to change

- `src/robotina/queue/runner.py` — extend `SimpleWorker`, remove `_setup_langwatch_in_workhorse`, add `langwatch.setup()` to `main()`
- `tests/test_queue_models.py` — update `test_logging_worker_is_worker_subclass` assertion to check `SimpleWorker` instead of `Worker`

## Risk

Low. The only regression scenario is a job that kills the process (OOM, `sys.exit()`), which would now take down the worker. Acceptable given the workload.
