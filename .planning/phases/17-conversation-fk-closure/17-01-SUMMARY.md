---
phase: 17-conversation-fk-closure
plan: 01
subsystem: testing

tags: [pytest, pydantic, sqlalchemy, alembic, tdd-red-state, lock-tests]

# Dependency graph
requires:
  - phase: 16-fix-empty-string-household-id-propagation-through-gateway-and-workflow-run
    provides: NonEmptyHouseholdId pattern (StartWorkflowTool ctor injection + queue_workflow guard) — Phase 17 mirrors topology for conversation_id
provides:
  - 13 RED-state lock tests encoding every Phase 17 contract (schema columns, constructor field, signature arg, run_task Conversation lookup, WorkflowOutcome stub) before any source change
  - ARCH-05 regression guard test (test_shared_context_reply_context_still_written) that asserts reply_context writes survive the deprecation window
  - Stubbed session.query(Conversation).one() pattern in the existing handle-incoming-message tool-injection test so Wave 2 ships atomically (no in-flight test churn)
affects: [17-02 wave-1-schema-migration, 17-03 wave-2-signatures-and-lookup, Phase 18 RobotinaInvocation lookup site reuses the same session.query(Conversation).one() idiom]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave-0 RED-state lock tests: every contract written as an executable test BEFORE the source change that satisfies it; failing-state IS the success signal of the plan"
    - "MagicMock-session.query(Conversation).filter_by(...).one() stub pattern used in 3 tests, ready for reuse in Phase 18"

key-files:
  created: []
  modified:
    - tests/test_workflow_runner.py
    - tests/unit/test_start_workflow_tool.py
    - tests/unit/test_agent_runner.py
    - tests/test_task_types.py

key-decisions:
  - "Reused Phase 13 `test_workflow_run_step_model_has_new_columns` pattern verbatim for both new column-existence tests (consistency across migration eras)"
  - "Reused Phase 13 `test_migration_0005_upgrades_and_downgrades` template verbatim for migration 0006 integration test (only target columns + revision number differ)"
  - "queue_workflow's missing conversation_id arg surfaces as a plain Python TypeError (signature enforcement), not a custom guard ValueError — D-05 explicitly chose no Python-level guard since FK + .one() upstream cover the invariant"
  - "Extended test_run_task_injects_all_three_tools_for_handle_incoming_message in place rather than adding a parallel test — Wave 2 must NOT need to touch this test, the conversation_id assertion lands now"

patterns-established:
  - "Wave-0 lock-test plan: planner enumerates contracts as test names, executor writes them all RED, subsequent wave plans turn each green by landing the corresponding source change; deviations from this contract surface as test diffs in source-change PRs"
  - "RED test taxonomy: ImportError (missing class) / AttributeError (missing attr on pydantic model) / pydantic ValidationError (missing required ctor field) / TypeError (missing required signature arg) / KeyError (build_input missing context key) — each error type maps unambiguously to one missing source contract"

requirements-completed: []

# Metrics
duration: 3min
completed: 2026-05-19
---

# Phase 17 Plan 01: Wave 0 RED-state lock tests Summary

**13 RED-state lock tests encoding every Phase 17 contract (WorkflowRun.conversation_id FK, WorkflowRun.outcome JSON column, migration 0006, queue_workflow signature, StartWorkflowTool ctor field, run_task Conversation lookup, WorkflowOutcome Pydantic stub) plus an ARCH-05 reply_context regression guard — all RED today, each flips green at its targeted wave.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-19T01:04:02Z
- **Completed:** 2026-05-19T01:07:29Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Encoded all six schema/signature/regression contracts of Plan 17-02/17-03 as executable RED tests in `tests/test_workflow_runner.py` (6 new tests, 199 line insertion).
- Encoded the StartWorkflowTool `conversation_id` ctor field contract (3 tests) and the run_task Conversation lookup + injection contract (2 new tests + 1 in-place extension to `test_run_task_injects_all_three_tools_for_handle_incoming_message`) — covering every D-03 / D-04 boundary.
- Encoded the WorkflowOutcome Pydantic stub contract (D-07) in `tests/test_task_types.py`.
- Pytest collection across the full suite remains GREEN (286 tests collected, 0 collection errors); the new RED tests fail only at execution, with the expected error taxonomy (ImportError / AttributeError / TypeError / KeyError) — clean diagnostic signal for the wave plans that follow.

## Task Commits

Each task was committed atomically:

1. **Task 1.1: RED-state schema + signature + ARCH-05 regression tests in tests/test_workflow_runner.py** — `3ff8296` (test)
2. **Task 1.2: RED-state StartWorkflowTool + run_task + WorkflowOutcome tests** — `efe6551` (test)

**Plan metadata commit:** _(this SUMMARY.md commit appended below)_

## Files Created/Modified

- `tests/test_workflow_runner.py` — appended 6 tests under new section header `# Phase 17 / ARCH-01: Conversation FK + outcome column` (+199 LOC).
- `tests/unit/test_start_workflow_tool.py` — appended 3 tests under new section header `# Phase 17 / ARCH-01: conversation_id constructor field` (+58 LOC).
- `tests/unit/test_agent_runner.py` — appended 2 tests under new section header `# Phase 17 / ARCH-01: run_task Conversation lookup + injection` AND extended `test_run_task_injects_all_three_tools_for_handle_incoming_message` in place with a `session.query(Conversation).one()` stub + a `sw_tools[0].conversation_id == "conv-from-db"` assertion so the existing test survives Wave 2 atomically (+139 LOC).
- `tests/test_task_types.py` — appended 1 test under new section header `# Phase 17 / D-07: WorkflowOutcome stub` (+26 LOC).

### Lock-test inventory (13 tests)

| # | Test | File | RED reason today | Turns GREEN in |
|---|------|------|------------------|---------------|
| 1 | `test_workflow_run_has_conversation_id_column` | tests/test_workflow_runner.py | `KeyError: 'conversation_id'` on `WorkflowRun.__table__.columns` | Wave 1 (Plan 17-02) |
| 2 | `test_workflow_run_has_outcome_column` | tests/test_workflow_runner.py | `KeyError: 'outcome'` on `WorkflowRun.__table__.columns` | Wave 1 (Plan 17-02) |
| 3 | `test_migration_0006_upgrades_and_downgrades` | tests/test_workflow_runner.py | `@pytest.mark.integration` — only runs in CI/local integration suite; will fail until `0006_*.py` exists | Wave 1 (Plan 17-02) |
| 4 | `test_queue_workflow_persists_conversation_id` | tests/test_workflow_runner.py | `KeyError: 'recipe_query'` via downstream build_input — current `queue_workflow` signature has no `conversation_id` kwarg | Wave 2 (Plan 17-03) |
| 5 | `test_queue_workflow_requires_conversation_id` | tests/test_workflow_runner.py | Currently `queue_workflow(...)` accepts the kwargs and proceeds past TypeError check — needs signature change | Wave 2 (Plan 17-03) |
| 6 | `test_shared_context_reply_context_still_written` | tests/test_workflow_runner.py | **Currently GREEN** — see deviation §1 below | (must stay GREEN forever) |
| 7 | `test_constructor_requires_conversation_id_no_default` | tests/unit/test_start_workflow_tool.py | Pydantic accepts kwargs silently (no `extra='forbid'` on BaseTool); test fails because the `with pytest.raises(ValidationError)` block does not actually raise | Wave 2 (Plan 17-03) |
| 8 | `test_constructor_accepts_non_empty_conversation_id` | tests/unit/test_start_workflow_tool.py | `AttributeError: 'StartWorkflowTool' object has no attribute 'conversation_id'` | Wave 2 (Plan 17-03) |
| 9 | `test_run_passes_conversation_id_to_queue_workflow` | tests/unit/test_start_workflow_tool.py | `queue_workflow` mock asserts `conversation_id` kwarg not present | Wave 2 (Plan 17-03) |
| 10 | `test_run_task_injects_all_three_tools_for_handle_incoming_message` (extended) | tests/unit/test_agent_runner.py | `AttributeError: 'StartWorkflowTool' object has no attribute 'conversation_id'` | Wave 2 (Plan 17-03) |
| 11 | `test_run_task_resolves_and_injects_conversation_id` | tests/unit/test_agent_runner.py | Same — tool has no conversation_id; lookup not yet wired in run_task | Wave 2 (Plan 17-03) |
| 12 | `test_run_task_raises_when_conversation_missing` | tests/unit/test_agent_runner.py | Expects `NoResultFound` propagation — run_task does not yet perform the lookup | Wave 2 (Plan 17-03) |
| 13 | `test_workflow_outcome_stub` | tests/test_task_types.py | `ImportError: cannot import name 'WorkflowOutcome' from 'robotina.queue.task_types'` | Wave 1 (Plan 17-02) |

### Expected RED failure summary (run after this plan)

```
$ uv run pytest tests/test_workflow_runner.py::test_workflow_run_has_conversation_id_column \
                tests/test_workflow_runner.py::test_workflow_run_has_outcome_column \
                tests/test_workflow_runner.py::test_queue_workflow_persists_conversation_id \
                tests/test_workflow_runner.py::test_queue_workflow_requires_conversation_id \
                tests/unit/test_start_workflow_tool.py::test_constructor_requires_conversation_id_no_default \
                tests/unit/test_start_workflow_tool.py::test_constructor_accepts_non_empty_conversation_id \
                tests/unit/test_start_workflow_tool.py::test_run_passes_conversation_id_to_queue_workflow \
                tests/unit/test_agent_runner.py::test_run_task_injects_all_three_tools_for_handle_incoming_message \
                tests/unit/test_agent_runner.py::test_run_task_resolves_and_injects_conversation_id \
                tests/unit/test_agent_runner.py::test_run_task_raises_when_conversation_missing \
                tests/test_task_types.py::test_workflow_outcome_stub
=> 11 failed
```

Plus 1 integration test (`test_migration_0006_upgrades_and_downgrades`) gated by `@pytest.mark.integration`.
Plus 1 currently-GREEN regression guard (`test_shared_context_reply_context_still_written`) — see deviation §1.

## Decisions Made

- Mirrored Phase 13 migration-integration-test template verbatim for the new `test_migration_0006_upgrades_and_downgrades`: only the revision number (0006), the target table (`workflow_runs`), and the expected column types/nullability differ. Stylistic consistency reduces review burden when Plan 17-02 lands the actual migration file.
- Extended `test_run_task_injects_all_three_tools_for_handle_incoming_message` IN PLACE rather than adding a new test. Rationale: Plan 17-03 (Wave 2) lands the source change that flips this RED → GREEN; if Wave 2 also had to update an unchanged test, the wave boundary would not be atomic. Per the planner's explicit instruction, this extension lives in Wave 0 alongside the contract it asserts.
- Did NOT add a `NonEmptyConversationId` Pydantic alias (Claude's Discretion in 17-CONTEXT: FK + `.one()` raise are sufficient for a system-generated UUID). The new `conversation_id: str` field on StartWorkflowTool will be a plain `str` in Wave 2 — no alias plumbing required.

## Deviations from Plan

### Auto-fixed Issues

None — no source-file mutations were necessary or permitted in Wave 0.

### Observations (not deviations)

**1. `test_shared_context_reply_context_still_written` is GREEN in Wave 0, not RED**

- **Found during:** Task 1.1 verification run.
- **Plan expectation:** The plan's acceptance-criteria block said this test "will FAIL at Pydantic construction time (no conversation_id field yet)" and is therefore "ALSO RED in Wave 0".
- **Observed reality:** `StartWorkflowTool` is a `langchain_core.tools.BaseTool` subclass. BaseTool's Pydantic config does NOT set `extra='forbid'` at the model level (only `args_schema=StartWorkflowArgs` enforces forbid on tool ARGS, not on the tool object itself). Constructor kwargs unknown to the model are therefore silently accepted by Pydantic — `StartWorkflowTool(..., conversation_id="conv-1")` succeeds today, the test progresses, and the existing `start_workflow.py:144–152` reply_context write satisfies the only assertion.
- **Why this is OK:** The intent of the test is preserved verbatim — it enforces that `reply_context = {platform, chat_id, user_id}` is written into `shared_context`. The plan was explicit that this test must STAY green after Wave 2 lands the conversation_id field. The fact that it is already green just means the ARCH-05 invariant is currently satisfied. After Wave 2 the test becomes a stricter guard (because Wave 2 will read `self.conversation_id` somewhere in `_run`, and the test's `_capture` mock still captures kwargs by name).
- **No source change:** Per plan, no `src/` modifications. The RED-then-GREEN gradient simply has one fewer step than the plan estimated.

## Issues Encountered

None — straightforward APPEND-only edits to four test files. Pytest collection across the full test suite remained GREEN at all times.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 17-02 (Wave 1)** is unblocked. It must:
  - Add `WorkflowRun.conversation_id` (String, NOT NULL, FK → `conversations.id`) and `WorkflowRun.outcome` (JSON, nullable) to `src/robotina/queue/models.py`.
  - Author `migrations/versions/0006_conversation_fk_and_outcome.py` mirroring `0005_dashboard_columns.py`.
  - Define `WorkflowOutcome` Pydantic stub in `src/robotina/queue/task_types.py` per D-07.
  - Update the ARCH-01 wording in `.planning/REQUIREMENTS.md` per the D-01 note in 17-CONTEXT.
  - Flips tests #1, #2, #3 (integration), #13 to GREEN.
- **Plan 17-03 (Wave 2)** then:
  - Adds `conversation_id: str` to `queue_workflow()` signature.
  - Adds `conversation_id: str` to `StartWorkflowTool` constructor (no default).
  - Threads it through `_run`.
  - Wires the `session.query(Conversation).filter_by(platform=..., chat_id=...).one()` lookup in `src/robotina/queue/jobs.py` handle-incoming-message branch.
  - Flips tests #4, #5, #7, #8, #9, #10 (extension), #11, #12 to GREEN.
  - Test #6 (`test_shared_context_reply_context_still_written`) stays GREEN.

No blockers. The RED test set after this plan is EXACTLY the contracts the next two plans must satisfy.

## Self-Check: PASSED

- `tests/test_workflow_runner.py` exists with all 6 new test functions present: FOUND (`grep -c "def test_workflow_run_has_conversation_id_column\|def test_workflow_run_has_outcome_column\|def test_migration_0006_upgrades_and_downgrades\|def test_queue_workflow_persists_conversation_id\|def test_queue_workflow_requires_conversation_id\|def test_shared_context_reply_context_still_written"` → 6).
- `tests/unit/test_start_workflow_tool.py` exists with all 3 new tests: FOUND.
- `tests/unit/test_agent_runner.py` exists with 2 new tests + extension: FOUND (`grep -c "conv-from-db"` → 4).
- `tests/test_task_types.py` exists with `test_workflow_outcome_stub`: FOUND.
- Commit `3ff8296` (Task 1.1): FOUND in `git log --oneline`.
- Commit `efe6551` (Task 1.2): FOUND in `git log --oneline`.
- `uv run pytest tests/ --collect-only -q` → 286 tests collected, 0 collection errors.
- Targeted-run verification: 11 of the 12 non-integration new tests FAIL with expected error types; 1 (test_shared_context_reply_context_still_written) is GREEN early — documented in Deviation §1.

---
*Phase: 17-conversation-fk-closure*
*Completed: 2026-05-19*
