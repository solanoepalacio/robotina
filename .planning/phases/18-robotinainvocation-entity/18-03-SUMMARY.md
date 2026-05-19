---
phase: 18
plan: 03
subsystem: queue+gateway
tags: [wave-2, wiring-rail, invocation-id, gateway-insert, dedup-guard]
requires:
  - Phase 18 Plan 01 complete (Wave 0 RED-state lock tests in place across gateway, ctor, signature, persistence)
  - Phase 18 Plan 02 complete (RobotinaInvocation ORM + migration 0007 + WorkflowRun.triggered_by_invocation_id NULLABLE FK)
provides:
  - queue_workflow signature now REQUIRES triggered_by_invocation_id: str (no default) — written to WorkflowRun row at construction
  - StartWorkflowTool constructor field invocation_id: str (no Pydantic alias, not in args_schema) — propagated to queue_workflow as triggered_by_invocation_id=self.invocation_id
  - run_task handle-incoming-message branch reads invocation_id via bracket access (job.meta["invocation_id"]) — KeyError on miss is the fail-loud invariant contract (D-15)
  - Gateway handler inserts RobotinaInvocation(trigger=USER_MESSAGE, status=PENDING, trigger_ref_id=stored.id) STRICTLY AFTER the StoredMessage IntegrityError dedup short-circuit; meta now carries invocation_id=inv.id alongside task_type
affects:
  - src/robotina/queue/workflow_runner.py
  - src/robotina/agent/tools/start_workflow.py
  - src/robotina/queue/jobs.py
  - src/robotina/gateway/handler.py
  - tests/test_workflow_runner.py (3 queue_workflow call sites bulk-updated)
  - tests/unit/test_agent_runner.py (3 mock_job.meta fixtures bumped to include invocation_id)
  - tests/conftest.py (db_session teardown extended to DELETE FROM robotina_invocations first)
tech-stack:
  added: []
  patterns:
    - "Bracket-access for invariant reads (job.meta[\"invocation_id\"]) — never .get() — when upstream caller is contractually obligated to set the key (D-15)"
    - "Constructor-injection over args_schema for tool fields the LLM must NOT supply (Pitfall 5) — same shape as Phase 17 conversation_id"
    - "Insert-after-dedup ordering for ancillary rows that must NOT orphan on uniqueness violations (D-24 / Pitfall 1)"
key-files:
  created: []
  modified:
    - src/robotina/queue/workflow_runner.py
    - src/robotina/agent/tools/start_workflow.py
    - src/robotina/queue/jobs.py
    - src/robotina/gateway/handler.py
    - tests/test_workflow_runner.py
    - tests/unit/test_agent_runner.py
    - tests/conftest.py
decisions:
  - "D-11/D-13/D-14/D-15/D-24 inherited from 18-CONTEXT.md verbatim; this plan is mirror-not-invent execution of the Phase 17 Plan 03 topology with the gateway-insert added."
  - "Rule 2 deviation: tests/conftest.py db_session teardown extended to DELETE FROM robotina_invocations BEFORE stored_messages/conversations. The new FKs (robotina_invocations.trigger_ref_id -> stored_messages.id and robotina_invocations.conversation_id -> conversations.id) would otherwise produce ForeignKeyViolation on every gateway test teardown after Task 3.4 lands. Pure test-infra fix; no production behavior change."
  - "Rule 2 deviation (Task 3.3 fixtures): three mock_job.meta dicts in tests/unit/test_agent_runner.py bumped to include 'invocation_id': 'inv-test' so the bracket read job.meta[\"invocation_id\"] does not KeyError under mock conditions. Production runtime invariant unchanged — gateway always sets the key."
metrics:
  duration: ~10m
  completed: 2026-05-19
  files_modified: 7
  files_created: 0
  tasks_completed: 4 / 4
---

# Phase 18 Plan 03: Wiring Rail Summary

End-to-end wiring of `invocation_id` from gateway insert → `meta` channel → `run_task` bracket read → `StartWorkflowTool` constructor → `queue_workflow` signature → `WorkflowRun.triggered_by_invocation_id` row. Mirrors Phase 17 Plan 03 topology with the gateway-side `RobotinaInvocation` insert added (Phase 17 didn't need this because `Conversation` was already inserted by the gateway).

## Files Modified — Exact Blocks Touched

### src/robotina/queue/workflow_runner.py (Task 3.1 — committed in 06f3e94)
- Added `triggered_by_invocation_id: str` to `queue_workflow(...)` signature, positioned immediately after `conversation_id: str` (no default — D-14).
- Docstring extended with a paragraph mirroring the existing `conversation_id:` paragraph.
- `WorkflowRun(...)` construction now passes `triggered_by_invocation_id=triggered_by_invocation_id` immediately after `conversation_id=conversation_id`.
- No parallel `if not triggered_by_invocation_id` Python guard (D-14 — FK NULLABLE + upstream bracket-key read carry the invariant).
- 3 existing `queue_workflow(...)` call sites in `tests/test_workflow_runner.py` bulk-updated with `triggered_by_invocation_id="inv-1"` (lines ~658, ~811, ~839).

### src/robotina/agent/tools/start_workflow.py (Task 3.2 — committed in 95c81dc)
- Added `invocation_id: str` constructor field immediately after `conversation_id: str` (no Pydantic alias — D-13).
- `_run` body's `queue_workflow(...)` call now passes `triggered_by_invocation_id=self.invocation_id` immediately after `conversation_id=self.conversation_id`.
- `args_schema = StartWorkflowArgs` line UNCHANGED — `invocation_id` is constructor-injected, never LLM-supplied (Pitfall 5 guard).
- ARCH-05 `reply_context` write in `shared_context` UNCHANGED (Phase 17 deprecation-window regression guard stays GREEN).

### src/robotina/queue/jobs.py (Task 3.3 — committed in bbd8ae3)
- Inside the existing `if task_type == "handle-incoming-message":` branch, added `invocation_id = job.meta["invocation_id"]` (bracket access, not `.get()` — D-15) immediately after the Phase 17 Conversation `.one()` resolution.
- `StartWorkflowTool(...)` construction now passes `invocation_id=invocation_id` immediately after `conversation_id=conversation.id`.
- No other branch in `run_task` reads `invocation_id` (D-12: wake-triggered branches are Phase 20).

### src/robotina/gateway/handler.py (Task 3.4 — committed in 0f5ad54)
- Added top-of-file import: `from robotina.queue.models import InvocationStatus, InvocationTrigger, RobotinaInvocation`.
- Inserted new "Step 2b" block STRICTLY BETWEEN the existing `return  # deduplicated; do not enqueue` and the `# Step 3: Fetch history` comment — load-bearing source ordering per D-11 / D-24 / Pitfall 1. The block:
  - Constructs `RobotinaInvocation(conversation_id=conv.id, trigger=InvocationTrigger.USER_MESSAGE, trigger_ref_id=stored.id, status=InvocationStatus.PENDING)`.
  - `session.add(inv); session.flush()` to materialize `inv.id` while still inside the existing `with SessionLocal()` block.
  - Captures `invocation_id = inv.id` to a local variable so the post-commit enqueue can read it.
- Enqueue `meta` dict at line 131 changed from `{"task_type": "handle-incoming-message"}` to `{"task_type": "handle-incoming-message", "invocation_id": invocation_id}`.
- Conversation upsert, StoredMessage flush, dedup short-circuit `return`, history fetch, `session.commit()`, and `IncomingMessageInput` construction UNTOUCHED.

## Bulk Test Updates

- **tests/test_workflow_runner.py** — 3 pre-existing `queue_workflow(...)` call sites updated to pass `triggered_by_invocation_id="inv-1"`. The Plan 18-01 RED tests `test_queue_workflow_requires_triggered_by_invocation_id` and `test_queue_workflow_persists_triggered_by_invocation_id` flipped GREEN; Phase 17 `test_queue_workflow_persists_conversation_id` and `test_queue_workflow_requires_conversation_id` STAY GREEN.
- **tests/unit/test_agent_runner.py** — 3 `mock_job.meta` dicts in the handle-incoming-message tests bumped to include `"invocation_id": "inv-test"` (lines 278, 447, 517). Without this the new bracket read in `jobs.py` raises `KeyError` under mock conditions. Production runtime contract unchanged (gateway always sets the key — handler.py step 2b).
- **tests/conftest.py** — `db_session` teardown extended to `DELETE FROM robotina_invocations` before `stored_messages` and `conversations`. Required by the new FKs (`robotina_invocations.trigger_ref_id -> stored_messages.id` and `robotina_invocations.conversation_id -> conversations.id`).

## Test Transitions

| Test | Phase 18 transition |
| --- | --- |
| `tests/test_workflow_runner.py::test_queue_workflow_requires_triggered_by_invocation_id` | RED -> GREEN (Plan 18-01 lock test) |
| `tests/test_workflow_runner.py::test_queue_workflow_persists_triggered_by_invocation_id` | RED -> GREEN (Plan 18-01 lock test) |
| `tests/unit/test_start_workflow_tool.py::test_constructor_requires_invocation_id_no_default` | RED -> GREEN (Plan 18-01 lock test) |
| `tests/unit/test_start_workflow_tool.py::test_start_workflow_tool_propagates_invocation_id` | RED -> GREEN (Plan 18-01 lock test) |
| `tests/test_gateway.py::test_user_message_creates_invocation` | RED -> GREEN (Plan 18-01 lock test) |
| `tests/test_gateway.py::test_duplicate_message_no_orphan_invocation` | RED -> GREEN (load-bearing D-24 guard) |
| `tests/test_gateway.py::test_duplicate_message_skipped` | GREEN -> GREEN (Phase 17 dedup unchanged) |
| `tests/unit/test_start_workflow_tool.py::test_*reply_context*` | GREEN -> GREEN (ARCH-05 regression guard) |
| `tests/test_workflow_runner.py::test_queue_workflow_persists_conversation_id` | GREEN -> GREEN (Phase 17 regression guard) |
| `tests/test_workflow_runner.py::test_queue_workflow_requires_conversation_id` | GREEN -> GREEN (Phase 17 regression guard, fires on either-missing-arg TypeError) |
| `tests/dashboard/test_independence.py` (3 tests) | GREEN -> GREEN (DASH-14 module-isolation invariant unchanged) |

Targeted plan-level verification command:

```
DATABASE_URL=postgresql://robotina:robotina@localhost:5433/robotina \
  uv run pytest tests/test_gateway.py tests/test_workflow_runner.py \
    tests/unit/test_start_workflow_tool.py \
    --deselect tests/test_gateway.py::test_send_message_persists
```

Result: **61 passed, 1 deselected (pre-existing failure — see Deferred Issues)**.

DASH-14 verification:

```
DATABASE_URL=postgresql://robotina:robotina@localhost:5433/robotina \
  uv run pytest tests/dashboard/test_independence.py
```

Result: **3 passed**.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical test infrastructure] Extended tests/conftest.py db_session teardown to DELETE FROM robotina_invocations first**
- **Found during:** Task 3.4 (gateway test run after handler.py edits landed)
- **Issue:** After the new `RobotinaInvocation` insert, every gateway test that ran through the conftest teardown raised `ForeignKeyViolation: ... robotina_invocations_conversation_id_fkey` because `DELETE FROM conversations` ran before `DELETE FROM robotina_invocations`.
- **Fix:** Prepended `session.execute(text("DELETE FROM robotina_invocations"))` to the existing teardown finally-block; added a one-line comment pinning the rationale to Phase 18 FK introduction.
- **Files modified:** tests/conftest.py
- **Commit:** 0f5ad54 (combined with the handler.py edit because the conftest fix only makes sense once the handler.py insert lands)

**2. [Rule 2 - Missing critical test fixture data] Bumped three mock_job.meta dicts in tests/unit/test_agent_runner.py**
- **Found during:** Task 3.3 verification (test_run_task_injects_all_three_tools_for_handle_incoming_message raised KeyError on the new bracket read)
- **Issue:** The new `invocation_id = job.meta["invocation_id"]` bracket access in `jobs.py` legitimately raises `KeyError` when the key is absent (D-15 fail-loud contract). Three pre-existing test fixtures built their `mock_job.meta` without the key.
- **Fix:** Added `"invocation_id": "inv-test"` to each of the three `mock_job.meta` dicts (lines 278, 447, 517). The string value is opaque — no test asserts on it.
- **Files modified:** tests/unit/test_agent_runner.py
- **Commit:** bbd8ae3 (combined with the jobs.py edit because the fixture fix only makes sense once jobs.py reads the key)

## Deferred Issues

Logged to `.planning/phases/18-robotinainvocation-entity/deferred-items.md`:

- `tests/test_gateway.py::test_send_message_persists` — pre-existing failure on `assert result == "7777"` vs. actual `SendResult(message_id='7777')`. Confirmed unrelated to Plan 18-03 by stashing edits and re-running — failure persists. Out of scope.
- Full-suite delta: identical 15 failed / 289 passed / 8 errors counts before and after Plan 18-03 edits (verified by stash + re-run). All non-targeted failures are pre-existing and out of scope. Most are dashboard tests blocked by Phase 17's NOT NULL `workflow_runs.conversation_id` constraint (the dashboard test fixtures insert workflow rows with `conversation_id=None`) — Plan 18-04 dashboard surface work will need to address those.

## Threat Flags

None. All new surface (RobotinaInvocation insert, meta channel) is internal-process plumbing; no new network endpoints, auth paths, or file-access patterns introduced.

## Plan 18-04 Hand-off

Plan 18-04 will:
- Surface `triggered_by_invocation_id` in the dashboard list + detail views.
- Edit REQUIREMENTS.md to mark ARCH-02 / ARCH-03 complete.
- Add the deploy runbook + smoke test for the new FK.
- Likely needs to address the pre-existing dashboard test fixture issue (workflow rows inserted with `conversation_id=None`).

## Self-Check: PASSED

- Created file `.planning/phases/18-robotinainvocation-entity/18-03-SUMMARY.md`: FOUND.
- Commits (verified with `git log --oneline`):
  - `06f3e94` (Task 3.1, pre-existing): FOUND
  - `95c81dc` (Task 3.2, pre-existing): FOUND
  - `bbd8ae3` (Task 3.3): FOUND
  - `0f5ad54` (Task 3.4): FOUND
