---
phase: 22-multi-recipe-per-message-topic-1
plan: 01
subsystem: queue/wake-helper
tags: [wake-helper, pydantic, sqlalchemy, ordering, batch-03, batch-04]
requires:
  - Phase 18 D-13 constructor-injected invocation_id on StartWorkflowTool
  - Phase 20 D-04 _check_and_dispatch_wake single helper + UPDATE-RETURNING idempotency
  - Phase 20 D-06 WakeInvocationInput.outcomes list
  - Phase 21 multi-call surface on StartWorkflowTool (no-op for this plan)
provides:
  - WorkflowOutcomeSummary.recipe_query (str | None) field — Pydantic
  - _check_and_dispatch_wake ASC ordering by WorkflowRun.created_at (D-06)
  - _check_and_dispatch_wake recipe_query plumbing from shared_context (D-08)
  - to_user_message() success-with-slug and failure-with-query line formats (D-07)
affects:
  - Future plan 22-02 (V006 prompt) will consume slug+query in wake-context worked examples
  - BATCH-03 (consolidated wake reply with name+slug) data plumbing complete
  - BATCH-04 (readable partial-failure lines) data plumbing complete
tech-stack:
  added: []
  patterns:
    - Pydantic optional-field-with-default for forward-compatible model evolution
    - Defensive (col or {}).get(...) idiom for nullable JSONB key reads (Pitfall 6)
    - SQLAlchemy 2.x .order_by(Column.asc()) on Query result chain
key-files:
  created:
    - tests/queue/test_wake_helper_ordering.py
  modified:
    - src/robotina/queue/task_types.py
    - src/robotina/queue/workflow_runner.py
    - tests/queue/test_task_types_wake_models.py
decisions:
  - D-06 ORDER BY created_at ASC on sibling-runs query (vs strict batch_index — deferred)
  - D-07 to_user_message rewrite (slug, query, drop legacy parenthetical)
  - D-08 surface recipe_query via WorkflowOutcomeSummary, not AddRecipeOutcome (no Alembic)
metrics:
  duration: 8 minutes
  completed: 2026-05-20
---

# Phase 22 Plan 01: Wake-helper polish for multi-recipe Summary

Wake-helper now produces correctly-ordered, recipe_query-enriched
WorkflowOutcomeSummary entries, and the synthesized Spanish wake-context
preamble renders BATCH-03 (name+slug success lines) and BATCH-04
(query+reason failure lines) the V006 prompt will summarize from.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add `recipe_query` field + rewrite `to_user_message` + 4 new unit tests | `d0cfdfc` | `src/robotina/queue/task_types.py`, `tests/queue/test_task_types_wake_models.py` |
| 2 | ORDER BY `created_at ASC` + `recipe_query` population + integration test | `8f11d3d` | `src/robotina/queue/workflow_runner.py`, `tests/queue/test_wake_helper_ordering.py` |

## Changes

### `src/robotina/queue/task_types.py`

- `WorkflowOutcomeSummary` gains `recipe_query: str | None = None` (D-08).
  `model_config = ConfigDict(extra="forbid")` retained — Pydantic still
  rejects unknown fields.
- `WakeInvocationInput.to_user_message()` fully rewritten (D-07):
  - Success lines: `- ✓ add-recipe: Lentejas (slug: lentejas, run <id>)`
    when `recipe_slug` is present; falls back to no-slug form otherwise.
  - Failure lines: `- ✗ add-recipe: canelones falló: no encontré la receta
    (run <id>)` using `recipe_query` instead of legacy
    `(receta sin nombre)`.
  - Trailing parenthetical: `(Wake-trigger; el usuario espera el resumen
    final.)` — replaces legacy `(... el usuario ya fue notificado.)`
    (Phase 21 removed the `notify` step; legacy text mis-trained the LLM
    into terse "you already heard from me" replies).

### `src/robotina/queue/workflow_runner.py`

- Sibling-runs query in `_check_and_dispatch_wake` now appends
  `.order_by(WorkflowRun.created_at.asc())` (D-06). Best-available proxy
  for user-utterance order under provider parallel tool calls (Pitfall 5);
  strict batch_index ordering deferred.
- Outcome append populates
  `recipe_query=(r.shared_context or {}).get("recipe_query")` (D-08).
  The `(x or {}).get(...)` form survives both null `shared_context` and
  missing key (Pitfall 6).

### `tests/queue/test_task_types_wake_models.py`

- `_make_wake_with` helper signature extended with
  `recipe_query: str | None = None`.
- Existing `Wake-trigger` assertions in `test_..._success` and
  `test_..._empty_list` updated to assert `"espera el resumen final"` (D-07
  text replacement); legacy `Wake-trigger` substring fully absent from
  the test file.
- Four new tests added:
  - `test_to_user_message_success_includes_slug`
  - `test_to_user_message_failure_uses_recipe_query`
  - `test_to_user_message_drops_legacy_parenthetical`
  - `test_workflow_outcome_summary_accepts_recipe_query_none_and_str`

### `tests/queue/test_wake_helper_ordering.py` (NEW)

- Reuses `FakeQueue`, `_make_conversation`, `_make_parent_invocation`,
  `_make_run` from `test_wake_dispatch.py` to avoid fixture duplication.
- `test_wake_helper_orders_outcomes_by_created_at_asc`: inserts three
  WorkflowRuns with `created_at` spaced 10 ms apart (Pitfall 1 clock-tie
  guard) and asserts both ASC ordering of `recipe_name` and exact
  `recipe_query` population.
- `test_wake_helper_handles_missing_recipe_query`: empty `shared_context`
  yields `recipe_query=None` without crash.

## Verification

```bash
$ set -a; source .env; set +a
$ uv run pytest tests/queue/test_task_types_wake_models.py \
                tests/queue/test_wake_helper_ordering.py \
                tests/queue/test_wake_dispatch.py -q
...............................                                          [100%]
31 passed in 0.13s
```

Plan's `<verify>` blocks both green:
- Task 1: `uv run pytest tests/queue/test_task_types_wake_models.py -x -q` → 12 passed
- Task 2: `uv run pytest tests/queue/test_wake_helper_ordering.py tests/queue/test_wake_dispatch.py -x -q` → 19 passed (1 `@pytest.mark.integration` deselected by default)

### Acceptance criteria (Task 1)

- `grep -c "recipe_query: str | None" src/robotina/queue/task_types.py` → 1 ✓
- `grep -c "usuario ya fue notificado" src/robotina/queue/task_types.py` → 0 ✓
- `grep -c "espera el resumen final" src/robotina/queue/task_types.py` → 2 (string in body + comment header reference) ✓
- `grep -c "slug: " src/robotina/queue/task_types.py` → 3 ✓
- 4 new test defs present in `test_task_types_wake_models.py` ✓
- `grep -c "Wake-trigger" tests/queue/test_task_types_wake_models.py` → 0 ✓

### Acceptance criteria (Task 2)

- `grep -c "order_by(WorkflowRun.created_at.asc())" src/robotina/queue/workflow_runner.py` → 1 ✓
- `grep -c "recipe_query=(r.shared_context or {}).get" src/robotina/queue/workflow_runner.py` → 1 ✓
- `tests/queue/test_wake_helper_ordering.py` exists with both test defs ✓

## Deviations from Plan

None — plan executed exactly as written.

### Observation (not a deviation)

Plan's overall `<verification>` step says:
`grep -rn "usuario ya fue notificado" src/` returns 0 lines.

One match remains: `src/robotina/agent/prompts/robotina/V004.md:41` — this is
an **archived prompt asset** retained for rollback per D-16 (project
convention: V001..VN prompts are immutable historical artifacts; only the
agent-registry pointer changes between versions). The file is no longer
loaded by `agents.py` (current points to V005, will point to V006 in
Plan 22-02). Production code paths return 0 hits as intended; the residue
is in frozen documentation only.

If desired, a separate housekeeping plan can scrub historical prompt
versions, but doing so contradicts D-16. Recommendation: leave as-is.

## Known Stubs

None.

## Threat Flags

None — Pydantic `extra="forbid"` retained on `WorkflowOutcomeSummary`;
`recipe_query` is `str | None` (T-22-01 mitigation as planned). No new
network endpoints, auth paths, file access, or schema changes.

## Self-Check: PASSED

Files:
- `src/robotina/queue/task_types.py` — FOUND
- `src/robotina/queue/workflow_runner.py` — FOUND
- `tests/queue/test_task_types_wake_models.py` — FOUND
- `tests/queue/test_wake_helper_ordering.py` — FOUND

Commits:
- `d0cfdfc` — FOUND on `main`
- `8f11d3d` — FOUND on `main`

## Next Steps

Plan 22-02 (V006 prompt fork + `agents.py` bump) consumes this data shape
in worked-example wake-context replies. Phase-level smoke (`22-SMOKE.md`)
will validate end-to-end against the LLM.
