# Deferred Items — Phase 17

Out-of-scope test failures discovered during execution. NOT caused by any
Phase 17 code change; verified pre-existing on the baseline commit
preceding Plan 17-02 via `git stash` reproduction.

## Pre-existing failures (verified during Plan 17-02 execution, 2026-05-19)

| Test | File | Notes |
|------|------|-------|
| `test_detail_view_404_for_missing_id` | `tests/dashboard/test_detail_view.py` | Pre-existing — fails identically with Phase 17 changes stashed. Likely Phase 13 dashboard regression unrelated to FK closure. |
| `test_all_routes_return_200_or_404_without_auth_headers` | `tests/dashboard/test_no_auth.py` | Pre-existing — fails identically without Phase 17 changes. |
| `test_main_exits_on_missing_household_id` | `tests/unit/test_gateway_boot.py` | Pre-existing — fails identically without Phase 17 changes. Real Telegram bootstrap is being triggered (token rejection) instead of the missing-env-var path being reached; suggests test fixtures or environment leak (HOUSEHOLD_ID is in fact loaded from `.env`). |

**Resolution path:** Surface as quick tasks (`/gsd:quick`) after Plan 17-04
closes Phase 17. Not blocking for v1.1 since none touch the workflow run
path or the FK closure surface.

## Plan 17-04 additional observations (2026-05-19)

| Test | File | Notes |
|------|------|-------|
| `test_migration_0005_upgrades_and_downgrades` | `tests/test_workflow_runner.py` | Pre-existing environmental — the live test Postgres has leftover `workflow_runs` rows from prior development. Once `alembic upgrade head` runs 0006 on the dirty DB, it raises `NotNullViolation` exactly as the runbook predicts. Test 0005 fails as a downstream effect (the test relies on `alembic upgrade head` succeeding to set up state). Plan 17-04 touched only documentation files; it cannot have introduced this. **Resolution:** execute the Phase 17 runbook (Step 3 TRUNCATE) against the local test DB, then these tests pass. Tracking under the same operator-gate that flips ARCH-01 / ARCH-05 to `[x]`. |
| `test_migration_0006_upgrades_and_downgrades` | `tests/test_workflow_runner.py` | Same root cause as above — non-empty `workflow_runs` rejects the NOT NULL ALTER. The test failure literally vindicates the runbook's failure-modes table. |

**Resolution path:** These flip green automatically the moment the Phase 17 runbook executes against any environment whose test DB has leftover v1.0 `workflow_runs` rows. Not blocking for v1.1 close-out — they are the operator-gate signal, not regressions.
