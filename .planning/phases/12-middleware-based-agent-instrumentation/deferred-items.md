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

## Phase 12 REVIEW findings deferred — pre-existing, out of Phase 12 diff

Two findings from `12-REVIEW.md` are documented but NOT fixed in Phase 12 because they are pre-existing bugs that predate the OBS-06 middleware migration. They were flagged by the reviewer but explicitly tagged as "not Phase 12's diff." Fixing them would expand scope and risk regressing the manual smoke gate currently awaiting user verification.

### WR-02: Session leak when `workflow_runner.on_step_start` raises

- **File:** `src/robotina/queue/jobs.py:76-84`
- **Status:** Deferred — pre-existing, out of Phase 12 scope
- **Discovered during:** Phase 12 code review (2026-05-13)
- **Root cause:** `_session = SessionLocal()` is created outside the outer `try`/`finally` that owns `_session.close()`. If `workflow_runner.on_step_start` raises, the session is leaked. Pre-existing since Phase 5 / Phase 07.1 when `on_step_start` was layered in.
- **Impact:** Does NOT affect Phase 12 contracts (Phase 12 only changed the callbacks list and removed the legacy callback module). Real correctness bug under DB-error conditions.
- **Recommended fix:** Move `_session = SessionLocal()` into a single `try`/`finally` bracketing the entire function body (or use a context manager). See `12-REVIEW.md` WR-02 for the suggested diff.

### IN-03: `assert last_exc is not None` stripped under `python -O`

- **File:** `src/robotina/llm/__init__.py:134, 165`
- **Status:** Deferred — pre-existing, out of Phase 12 scope
- **Discovered during:** Phase 12 code review (2026-05-13)
- **Root cause:** `_RetryingChatOllama._generate` / `_agenerate` use `assert last_exc is not None` before `raise last_exc`. Under `python -O` the assertion is elided, leaving `raise None` → `TypeError`. Pre-existing in the retry implementation.
- **Impact:** Unreachable in practice (the loop body guarantees `last_exc` is set on the only path that reaches the assertion). Real correctness hazard only if Robotina is ever run with `-O`, which is not part of any current invocation.
- **Recommended fix:** Replace assertion with an explicit `if last_exc is None: raise RuntimeError(...)` that survives `-O`. See `12-REVIEW.md` IN-03 for the suggested diff.

### IN-02: Log injection via unescaped newlines in tool args/output

- **File:** `src/robotina/agent/middleware.py:102,107`
- **Status:** Skipped during Phase 12 review-fix — parity with legacy callback is intentional; a minimal newline-only sanitization would create a partial mitigation that masks the broader control-character surface.
- **Discovered during:** Phase 12 code review (2026-05-13)
- **Root cause:** `logger.info("Tool call | tool=%s input=%s", ...)` and `logger.info("Tool result | output=%s", ...)` truncate to 200 chars but do not escape `\n`, `\r`, `\t`, `\x1b[` (ANSI), or backspace, allowing log impersonation (CWE-117) if a future tool emits free-form attacker-controlled text. Today's tools (HouseholdManagerApiTool / WebSearchTool) return JSON-safe content at the source, so the surface is theoretical.
- **Impact:** Does NOT affect Phase 12 contracts. Parity with the legacy callback is preserved; this is not a regression.
- **Recommended fix:** Add a `_safe()` helper that uses `repr()`-based escaping (handles all control chars, not just `\n`). See `12-REVIEW.md` IN-02 for the suggested diff. Track as a separate observability-hardening item.
