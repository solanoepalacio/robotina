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

**Update 2026-05-19 (UAT close):** Operator re-truncated `workflow_runs` and re-ran integration suite. `test_migration_0006_upgrades_and_downgrades` is now ABSENT from the failure list — confirmed green against a clean DB. `test_migration_0005_upgrades_and_downgrades` likewise unblocked.

## UAT additional observations (2026-05-19, Phase 17 UAT close)

Surfaced during full-suite test runs taken as part of UAT (integration + non-integration).

### Test-side fallout from Phase 17 NOT NULL `conversation_id` (mechanical, dashboard ctors)

| Test | File | Notes |
|------|------|-------|
| `test_list_view_renders_rows_newest_first` | `tests/dashboard/test_list_view.py` | Inline `WorkflowRun(...)` ctor at line 82 + 113 missing `conversation_id` and a matching pre-inserted `Conversation` row. `tests/dashboard/conftest.py:71-90` `make_failed_cascade_run` shows the correct pattern — apply the same 3-line treatment. |
| `test_list_row_links_to_detail` | `tests/dashboard/test_list_view.py` | Same root cause as above (line 113). |
| `test_detail_fragment_terminal_has_no_hx_trigger` | `tests/dashboard/test_polling_halt.py` | Same root cause — inline ctor at lines 19-26 without Conversation pre-insert. |
| `test_detail_fragment_running_has_hx_trigger` | `tests/dashboard/test_polling_halt.py` | Same root cause — lines 42-50. |

**Severity:** minor. Production code is correct; tests just never inserted the parent Conversation. The 4 teardown-cascade `PendingRollbackError`s in the same log file disappear once these are fixed.

**Resolution path:** Single `/gsd:quick` after Phase 17 close to update all 4 dashboard tests using the `conftest.py:71-90` pattern.

### Stale assertions unrelated to Phase 17

| Test | File | Notes |
|------|------|-------|
| `test_send_message_persists` | `tests/test_gateway.py` | Asserts `result == "7777"` but `send_message()` returns `SendResult(message_id=...)` since commit `3b4a163` (pre-Phase-17). Fix: `result.message_id == "7777"`. |

### Phase 18 churn — does not belong to Phase 17

| Test | File | Notes |
|------|------|-------|
| `test_skill_index_appended_to_prompt` | `tests/unit/test_prompts.py` | Phase 18 commit `0f5ad54` added `job.meta["invocation_id"]` hard bracket-read in `src/robotina/queue/jobs.py:165`. Test's `mock_job.meta` only sets `task_type` → `KeyError`. Belongs to Phase 18 plan 18-02 (or a Phase 18 `/gsd:quick`), NOT a Phase 17 gap. |

**Resolution path:** Phase-18-owned mock fix; do not bundle with the Phase 17 cleanup `/gsd:quick`.
