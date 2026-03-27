# Deferred Items — Phase 06

## Pre-existing Test Failures (out of scope)

### test_observability.py — 3 failing tests

**File:** `tests/unit/test_observability.py`

**Tests:**
- `test__setup_langwatch_in_workhorse_nonfatal_when_missing_credentials`
- `test__setup_langwatch_in_workhorse_reads_api_key_from_env`
- `test__setup_langwatch_in_workhorse_reads_endpoint_from_env`

**Error:** `ImportError: cannot import name '_setup_langwatch_in_workhorse' from 'robotina.queue.runner'`

**Discovery:** Found during 06-03 plan execution (full unit suite run).

**Status:** Pre-existing before Plan 06-03 changes (confirmed via git stash verification).

**Scope:** These tests reference a private function `_setup_langwatch_in_workhorse` that does not exist in `runner.py`. This is a stub/placeholder test from a future plan.

**Action required:** Investigate and implement `_setup_langwatch_in_workhorse` in `runner.py` in a future plan.
