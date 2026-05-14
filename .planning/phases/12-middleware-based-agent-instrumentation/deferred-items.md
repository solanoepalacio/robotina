# Phase 12: Deferred Items

Pre-existing issues discovered during Plan 12-02 execution that are OUT OF SCOPE for this plan (Rule: scope boundary — only fix issues directly caused by the current task's changes).

## `test_recipe_load_registered` expects `V002.md` but code points to `V003.md`

- **File:** `tests/unit/test_agents_registry.py:163`
- **Discovered during:** Plan 12-02 Task 2.1 Step 2 (full unit suite run after GREEN flip)
- **Root cause:** Commit `3ce39c5` (`fix(11-03): rewrite recipe-load V003 prompt — structurally prevent emit-before-POST hallucination`) bumped `src/robotina/agent/agents.py:155` from `recipe-load/V002.md` to `recipe-load/V003.md` but did not update the matching assertion in `test_agents_registry.py`. An earlier commit `9f3fd97` (`fix(11-03): bump prompt_path assertions in test_agents_registry.py to new V### versions`) had bumped the test to V002.
- **Impact:** 1 pre-existing test failure, isolated to Phase 11's recipe-load prompt versioning. Does NOT affect Phase 12 contracts.
- **Recommended fix:** One-line edit in `tests/unit/test_agents_registry.py:163` to expect `V003.md`. Suggested follow-up via `/gsd:quick` after Phase 12 closes.

## `tests/test_db_models.py::test_migration_creates_all_tables` requires Postgres

- **File:** `tests/test_db_models.py`
- **Discovered during:** initial `uv run pytest -x` (no `-x` filter on test path).
- **Root cause:** Integration test (not in `tests/unit/`) that requires `docker compose up` (Postgres) to be running. Plan 12-02 executor environment had no Postgres available.
- **Impact:** Does NOT affect Phase 12 contracts. Plan 12-01 SUMMARY ran only the unit suite (`tests/unit/`) and reported 24/24 green for the relevant slice. The full unit suite (`tests/unit/`) is 92/93 (the V002/V003 drift above is the lone unit failure).
- **Recommended fix:** None — integration tests run via Docker Compose. No action needed.
