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
