---
phase: quick-260327-j4k
plan: "01"
subsystem: experiments
tags: [langwatch, experiment, observability, send-notification]
dependency_graph:
  requires: []
  provides: [send-notification experiment with LangWatch Experiment API]
  affects: [experiments/send_notification.py]
tech_stack:
  added: []
  patterns: [langwatch.Experiment context manager, experiment.log for per-case evaluation, OTel force_flush on exit]
key_files:
  created: []
  modified:
    - experiments/send_notification.py
decisions:
  - "langwatch.Experiment used as outermost context instead of per-case langwatch.trace() to group all traces under one experiment run"
  - "experiment.log() called from main() (the caller) after extracting outcome, not inside run_experiment_case(), so the function stays a pure agent invoker"
  - "force_flush() placed in finally block at main() exit to guarantee OTel traces are sent before process terminates"
metrics:
  duration: "2min"
  completed: "2026-03-27"
  tasks: 1
  files: 1
---

# Quick Task 260327-j4k: Fix send-notification experiment to use LangWatch Experiment API

**One-liner:** Replaced bare `langwatch.trace()` calls with `langwatch.Experiment` context manager, added `experiment.log()` per case, and added `force_flush()` in a finally block to prevent silent trace drops on exit.

## What Was Done

### Task 1: Refactor experiment to use langwatch.Experiment, evaluation.log, and force_flush

Rewrote `experiments/send_notification.py` with three targeted changes:

1. **Experiment context manager in main():** Wrapped the full test loop (including the `patch.object` block) inside `langwatch.Experiment(experiment_slug="send-notification", run_name=f"prompt-V001 model=...")` so all case traces are grouped under a single experiment run in LangWatch.

2. **Removed `langwatch.trace()` from `run_experiment_case()`:** The function now simply calls `agent.invoke()` with `RunnableConfig(callbacks=[langwatch.langchain.LangChainTracer()])` and returns the result. The Experiment context handles the parent trace. After each `run_experiment_case()` call, main() extracts the outcome and calls `experiment.log(input=..., output=..., passed=bool)` including on exception paths.

3. **Added `force_flush()` in finally block:** `otel_trace.get_tracer_provider().force_flush()` is called in a `try/finally` wrapping the Experiment context, ensuring OTel spans are flushed before process exit even if a case or the experiment itself raises.

**Commit:** `c5645b7`
**Files modified:** `experiments/send_notification.py`

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all functionality is wired.

## Self-Check: PASSED

- `experiments/send_notification.py` exists and passes syntax check (`uv run python -c "import ast; ast.parse(...)"` → `syntax OK`)
- Commit `c5645b7` present in `git log`
- `langwatch.Experiment` present (line 152)
- `experiment.log(` present (lines 178, 193)
- `force_flush()` present (line 220)
- `langwatch.trace()` removed (grep returns no matches)
