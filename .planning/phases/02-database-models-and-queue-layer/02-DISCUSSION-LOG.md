# Phase 2: Database Models and Queue Layer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the discussion.

**Date:** 2026-03-25
**Phase:** 02-database-models-and-queue-layer
**Mode:** discuss
**Areas discussed:** Model file organization, Queue state logging

## Gray Areas Presented

| Area | Options presented |
|------|------------------|
| Model file organization | Single `models.py` vs split by domain sub-package |
| Pydantic task I/O placement | (not selected for discussion — Claude's discretion) |
| Queue state logging | RQ worker callbacks vs direct logging in job functions |

## Decisions Made

### Model File Organization
- **Selected:** Split by domain sub-package
- **Decision:** `robotina/gateway/models.py` (Conversation, StoredMessage) + `robotina/queue/models.py` (WorkflowRun, WorkflowRunStep); shared `Base` in `db.py`

### Queue State Logging
- **Selected:** RQ worker callbacks (Recommended)
- **Decision:** `LoggingWorker(Worker)` subclass in `runner.py` overrides `perform_job` — centralized lifecycle logging, no per-job logging required

## Claude's Discretion

- **Pydantic task I/O placement:** `robotina/queue/task_types.py` — follows established sub-package pattern, imported by queue, agents, and task runner
- **RQ verification approach:** Integration test against live Redis (mirrors Phase 1 test approach)

## No Corrections

All selections confirmed as presented.
