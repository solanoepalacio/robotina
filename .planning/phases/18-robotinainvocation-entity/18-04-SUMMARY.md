---
phase: 18
plan: 04
subsystem: dashboard+docs
tags: [wave-3, dashboard, requirements, runbook, phase-wrap]
requires:
  - Phase 18 Plans 01-03 complete (schema, wiring, gateway insert)
provides:
  - workflow.html detail-view surfaces triggered_by_invocation_id (DASH-13)
  - REQUIREMENTS.md ARCH-02 wording aligned with implementation (rq_job_id, D-25)
  - 18-RUNBOOK.md operator deploy runbook (drain → migrate 0006→0007 → restart → smoke)
affects:
  - src/robotina/dashboard/templates/workflow.html
  - .planning/REQUIREMENTS.md
  - .planning/phases/18-robotinainvocation-entity/18-RUNBOOK.md
key-files:
  created:
    - .planning/phases/18-robotinainvocation-entity/18-RUNBOOK.md
  modified:
    - src/robotina/dashboard/templates/workflow.html
    - .planning/REQUIREMENTS.md
metrics:
  duration: ~5min
  completed: 2026-05-19
requirements: [ARCH-02, DASH-13, DASH-14]
requirements_addressed: [ARCH-02, DASH-13, DASH-14]
---

# Phase 18 Plan 04: Wave 3 Dashboard + Docs + Runbook Summary

Phase 18 wrap-up. Three sequential acts landed:

1. **Dashboard surface (DASH-13)** — `src/robotina/dashboard/templates/workflow.html` kv-grid gained a new dt/dd pair: `dt='Triggered by invocation'`, `dd='{{ run.triggered_by_invocation_id or "—" }}'`. DASH-13 RED tests (`test_detail_view_renders_triggered_by_invocation_id_when_set`, `test_detail_view_renders_em_dash_when_invocation_id_null`) flipped GREEN. No new dashboard imports, no cross-module edges — DASH-14 isolation preserved (commit `18ac7e4`).
2. **REQUIREMENTS.md ARCH-02 wording (D-25)** — single-line edit replacing stale `job_id` reference with `rq_job_id` to match the implemented column name.
3. **Deploy runbook (18-RUNBOOK.md)** — operator procedure for migrating staging/production from alembic 0006 → 0007: stop task-runner, `uv run migrate`, schema verification queries, restart, manual smoke (real Telegram message → assert `robotina_invocations` row + `workflow_runs.triggered_by_invocation_id` matches). Rollback path via `alembic downgrade 0006` documented (commit `370b803`).

## Verification

| Check | Result |
|---|---|
| DASH-13 detail-view RED tests | 2 / 2 GREEN |
| DASH-14 module isolation | 3 / 3 PASSED |
| REQUIREMENTS.md ARCH-02 references `rq_job_id` | YES (line 13) |
| 18-RUNBOOK.md created | YES |

## Manual Smoke (per feedback_test_before_handoff.md)

Verified live during Phase 18 UAT (8/8 passed, commit `9ef7907`):
- Real Telegram message → new `robotina_invocations` row with `trigger='user_message'`, `status='pending'`, `trigger_ref_id` matching latest `stored_messages.id`.
- `workflow_runs.triggered_by_invocation_id` non-NULL and matches the new invocation id.
- Dashboard detail view renders the new "TRIGGERED BY INVOCATION" row with the UUID (and em-dash for historical NULL rows).

## Commits

- `18ac7e4` — `feat(18-04): surface triggered_by_invocation_id in workflow detail view`
- `370b803` — `docs(18-04): align ARCH-02 wording (rq_job_id) and add phase 18 deploy runbook`

## What's Next

Phase 18 complete. Next phase per ROADMAP.md.
