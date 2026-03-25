---
phase: 01-developer-tooling-and-infrastructure
plan: 03
subsystem: infra
tags: [rq, redis, python, pytest, uv, experiments]

# Dependency graph
requires:
  - phase: 01-02
    provides: pyproject.toml with correct script entries and hatch package declarations
provides:
  - RQ worker entrypoint (src/robotina/queue/runner.py) with graceful Redis failure
  - Three experiment stubs callable via uv run (recipe_research, recipe_load, send_notification)
  - Automated test scaffold covering INFRA-02, INFRA-03, INFRA-04 without Docker
affects:
  - 02-telegram-gateway
  - 05-workflow-orchestrator
  - 06-notification-agent
  - 08-recipe-research-agent
  - 09-recipe-load-agent

# Tech tracking
tech-stack:
  added: [rq, redis-py, pytest]
  patterns: [graceful-failure-entrypoint, experiment-stub-pattern]

key-files:
  created:
    - src/robotina/queue/runner.py
    - experiments/__init__.py
    - experiments/recipe_research.py
    - experiments/recipe_load.py
    - experiments/send_notification.py
    - tests/test_runner.py
    - tests/test_pyproject.py
  modified: []

key-decisions:
  - "Queue name is agent-tasks — all downstream phases must enqueue to this exact name"
  - "All RQ jobs must use result_ttl=-1 and failure_ttl=-1 per CLAUDE.md no-lost-tasks requirement"
  - "Runner catches all exceptions and calls sys.exit(1) — no unhandled tracebacks"
  - "experiments/__init__.py is required for uv run experiments.* entry points to resolve"

patterns-established:
  - "Graceful entrypoint pattern: try/except around infrastructure connection, logger.error + sys.exit(1) on failure"
  - "Experiment stub pattern: logging stub with Phase N implementation note, callable via uv run"
  - "Test infrastructure: pytest without Docker via offline assertions (file existence, source inspection, subprocess)"

requirements-completed: [INFRA-03, INFRA-04]

# Metrics
duration: 2min
completed: 2026-03-25
---

# Phase 01 Plan 03: Entrypoints and Test Scaffold Summary

**RQ task runner entrypoint with graceful Redis failure, three experiment stubs callable via uv run, and 11 automated tests covering INFRA-02 through INFRA-05 without Docker**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-25T19:57:20Z
- **Completed:** 2026-03-25T19:59:28Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- `src/robotina/queue/runner.py` provides the `uv run agent` entrypoint with graceful Redis failure: exits with code 1 and no unhandled traceback when Redis is unreachable
- Three `uv run experiments.*` stubs created and verified to exit 0
- 11 pytest tests cover pyproject.toml structure (INFRA-02), graceful Redis failure (INFRA-03), experiment importability (INFRA-04), and alembic config (INFRA-05 offline check) — all passing without Docker

## Task Commits

Each task was committed atomically:

1. **Task 1: Create uv run agent entrypoint and experiment stubs** - `b0b4ebf` (feat)
2. **Task 2: Create automated test scaffold for INFRA-02, INFRA-03, INFRA-04** - `f75cbd4` (test)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `src/robotina/queue/runner.py` - RQ worker entrypoint; reads REDIS_URL, attempts ping, exits 1 on failure
- `experiments/__init__.py` - Empty file making experiments an importable package
- `experiments/recipe_research.py` - Stub for Phase 8 recipe research experiment
- `experiments/recipe_load.py` - Stub for Phase 9 recipe load experiment
- `experiments/send_notification.py` - Stub for Phase 6 send notification experiment
- `tests/test_runner.py` - INFRA-03 graceful failure test + queue name assertion
- `tests/test_pyproject.py` - INFRA-02/04/05 offline structure tests (11 total)

## Decisions Made
- Queue name `agent-tasks` is explicit in runner source — test asserts it via source inspection so renaming fails loudly
- `uv sync --extra dev` required before running pytest (dev group contains pytest); documented in test run
- Subprocess test uses port 19999 (no service expected) rather than mocking to exercise the actual entrypoint path

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `uv run pytest` failed initially because dev dependencies not installed — resolved by running `uv sync --extra dev`. Not a code issue.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 1 is fully complete: Docker Compose, pyproject.toml, source skeleton, migrations, and entrypoints all in place
- Phase 2 (Telegram Gateway) can proceed — foundation ready
- Developer toolchain verified: `uv run agent`, `uv run migrate`, `uv run experiments.*`, `uv run pytest tests/` all function correctly

## Self-Check: PASSED

All 7 files verified on disk. Both task commits (b0b4ebf, f75cbd4) confirmed in git log.

---
*Phase: 01-developer-tooling-and-infrastructure*
*Completed: 2026-03-25*
