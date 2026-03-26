---
phase: 02-database-models-and-queue-layer
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, postgres, orm, enums, migration]

# Dependency graph
requires:
  - phase: 01-developer-tooling-and-infrastructure
    provides: Docker Compose Postgres 15, uv project setup, migrations/env.py skeleton, 0001_init migration
provides:
  - SQLAlchemy DeclarativeBase with engine and SessionLocal in src/robotina/db.py
  - Conversation and StoredMessage ORM models (SQLAlchemy 2.x Mapped style) in src/robotina/gateway/models.py
  - WorkflowRun and WorkflowRunStep ORM models (SQLAlchemy 2.x Mapped style) in src/robotina/queue/models.py
  - Alembic migration 0002 creating all four tables with native PostgreSQL ENUM types
  - Integration test suite (5 tests) gating on live Postgres correctness
affects:
  - 03-telegram-gateway (uses Conversation, StoredMessage, SessionLocal)
  - 05-workflow-engine (uses WorkflowRun, WorkflowRunStep, SessionLocal)
  - all phases that import from robotina.db, robotina.gateway.models, robotina.queue.models

# Tech tracking
tech-stack:
  added: []
  patterns:
    - SQLAlchemy 2.x Mapped + mapped_column declarative style (no Column() legacy style)
    - postgresql.ENUM with create_type=False in Alembic migrations (prevents duplicate type errors)
    - DO $$ BEGIN IF NOT EXISTS ... END $$ blocks for idempotent ENUM creation
    - DROP TYPE IF EXISTS for idempotent ENUM downgrade
    - @pytest.mark.integration marker for tests requiring live Postgres

key-files:
  created:
    - src/robotina/gateway/models.py
    - src/robotina/queue/models.py
    - migrations/versions/0002_models.py
    - tests/test_db_models.py
  modified:
    - src/robotina/db.py
    - migrations/env.py
    - pyproject.toml

key-decisions:
  - "Use postgresql.ENUM(create_type=False) in op.create_table columns, not sa.Enum, to avoid SQLAlchemy auto-creating types that were already created via DO $$ blocks"
  - "PostgreSQL 15 does not support CREATE TYPE IF NOT EXISTS — must use DO $$ IF NOT EXISTS in pg_type ... END $$ pattern"
  - "downgrade() uses DROP TYPE IF EXISTS via raw SQL for idempotent cleanup"
  - "pytest integration marker registered in pyproject.toml to avoid PytestUnknownMarkWarning"

patterns-established:
  - "Pattern 1: All ORM models import Base from robotina.db — no circular imports possible"
  - "Pattern 2: env.py imports model modules with # noqa: F401 to trigger registration with Base.metadata before target_metadata assignment"
  - "Pattern 3: Alembic migrations use DO $$ BEGIN IF NOT EXISTS ... END $$ for ENUM idempotency"

requirements-completed: [WF-01, QUEUE-01]

# Metrics
duration: 5min
completed: 2026-03-25
---

# Phase 02 Plan 01: Database Models and SQLAlchemy Layer Summary

**Four SQLAlchemy 2.x ORM models (Conversation, StoredMessage, WorkflowRun, WorkflowRunStep) with idempotent Alembic migration 0002 and 5-test integration suite on live Postgres**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-25T20:48:06Z
- **Completed:** 2026-03-25T20:52:31Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Extended src/robotina/db.py with DeclarativeBase subclass, SQLAlchemy engine, and SessionLocal factory while preserving run_migrations()
- Created gateway models (Conversation, StoredMessage) and queue models (WorkflowRun, WorkflowRunStep) verbatim from spec using SQLAlchemy 2.x Mapped style
- Delivered Alembic migration 0002 that applies cleanly on fresh database and survives upgrade/downgrade/re-upgrade cycles without ENUM errors
- All 5 integration tests pass against live Postgres including unique constraint verification

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend db.py and create SQLAlchemy model files** - `e97f957` (feat)
2. **Task 2: Update env.py, create migration 0002, write model integration test** - `0b29ab1` (feat)

**Plan metadata:** (docs commit follows)

_Note: Task 1 was TDD — tests written first (RED), then models implemented (GREEN)_

## Files Created/Modified
- `src/robotina/db.py` - Added Base(DeclarativeBase), engine, SessionLocal; preserved run_migrations()
- `src/robotina/gateway/models.py` - Conversation, StoredMessage, Platform, MessageRole models
- `src/robotina/queue/models.py` - WorkflowRun, WorkflowRunStep, WorkflowStatus, WorkflowStepStatus models
- `migrations/env.py` - Replaced target_metadata=None with Base.metadata import + model registrations
- `migrations/versions/0002_models.py` - Alembic migration for all 4 tables with PostgreSQL ENUM types
- `tests/test_db_models.py` - 5 integration tests (importable, migration, tables exist, unique constraints)
- `pyproject.toml` - Added integration pytest marker registration

## Decisions Made
- Used `postgresql.ENUM(create_type=False)` from `sqlalchemy.dialects.postgresql` in `op.create_table` columns instead of generic `sa.Enum` — this prevents SQLAlchemy's `_on_table_create` hook from trying to re-create ENUM types that were already created by explicit DO $$ blocks
- PostgreSQL 15 lacks `CREATE TYPE IF NOT EXISTS` syntax — idempotency requires the `DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = ...) THEN CREATE TYPE ...; END IF; END $$` pattern
- downgrade() uses `DROP TYPE IF EXISTS` via `conn.execute(sa.text(...))` for clean idempotent teardown

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ENUM duplicate type error in migration**
- **Found during:** Task 2 (migration execution)
- **Issue:** Plan specified `sa.Enum(..., create_type=False)` but generic `sa.Enum` in SQLAlchemy 2.0.48 still fires `_on_table_create` causing "type already exists" even with `create_type=False`. Also `CREATE TYPE IF NOT EXISTS` is not supported on PostgreSQL 15.
- **Fix:** Switched to `postgresql.ENUM(..., create_type=False)` from `sqlalchemy.dialects.postgresql` for column type in `op.create_table`. Used `DO $$ BEGIN IF NOT EXISTS in pg_type ... END $$` for idempotent ENUM creation. Used `DROP TYPE IF EXISTS` in downgrade.
- **Files modified:** migrations/versions/0002_models.py
- **Verification:** Downgrade to 0001, re-upgrade to head — both succeed without errors
- **Committed in:** 0b29ab1 (Task 2 commit)

**2. [Rule 2 - Missing Critical] Registered integration pytest marker**
- **Found during:** Task 1 (test run)
- **Issue:** `@pytest.mark.integration` produced PytestUnknownMarkWarning — markers must be declared for clean test output
- **Fix:** Added `markers = ["integration: ..."]` to `[tool.pytest.ini_options]` in pyproject.toml
- **Files modified:** pyproject.toml
- **Committed in:** e97f957 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
- SQLAlchemy 2.0.48 generic `sa.Enum` ignores `create_type=False` in `op.create_table` column definitions; must use PostgreSQL dialect `ENUM` type instead — resolved by switching to `postgresql.ENUM`

## User Setup Required
None - no external service configuration required beyond what Phase 1 already established.

## Next Phase Readiness
- All four ORM models importable and registered with Base.metadata — Phase 3 (telegram-gateway) and Phase 5 (workflow-engine) can import and use them immediately
- SessionLocal factory available for DB session management
- Migration 0002 applied to local Postgres; Alembic version at head
- No blockers for Phase 3

---
*Phase: 02-database-models-and-queue-layer*
*Completed: 2026-03-25*

## Self-Check: PASSED

- FOUND: src/robotina/db.py
- FOUND: src/robotina/gateway/models.py
- FOUND: src/robotina/queue/models.py
- FOUND: migrations/versions/0002_models.py
- FOUND: tests/test_db_models.py
- FOUND: .planning/phases/02-database-models-and-queue-layer/02-01-SUMMARY.md
- FOUND commit: e97f957 (Task 1)
- FOUND commit: 0b29ab1 (Task 2)
- FOUND commit: 1ab20d1 (metadata)
