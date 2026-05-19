---
status: complete
phase: 17-conversation-fk-closure
source: [17-VERIFICATION.md, 17-RUNBOOK.md]
started: 2026-05-19T00:00:00Z
updated: 2026-05-19T00:15:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Execute Phase 17 deploy runbook against live dev DB
expected: |
  Steps 1–5 of 17-RUNBOOK.md succeed: workers stopped → RQ drained →
  `TRUNCATE workflow_runs, workflow_run_steps RESTART IDENTITY CASCADE` →
  `uv run migrate` upgrades to 0006 cleanly → workers restarted.
  `\d workflow_runs` shows `conversation_id character varying not null` with FK
  `workflow_runs_conversation_id_fkey` → `conversations(id)`, and `outcome json` nullable.
result: pass
notes: |
  Verified via 3 messages (2 simple interactions + 1 workflow):
  conversation_id present and populated, FK constraint present, outcome
  column present (typed JSON, nullable). `outcome` unpopulated is expected —
  SC#4 / D-06 keep it nullable + unused until Phase 20.

### 2. Telegram smoke test post-runbook
expected: |
  Send a single Telegram message to the bot (e.g. "hola"). The gateway upserts a
  Conversation row; `run_task` runs
  `session.query(Conversation).filter_by(platform=Platform.TELEGRAM, chat_id=<chat>).one()`
  successfully (no `NoResultFound`); a new `WorkflowRun` row is written with
  `conversation_id` matching that Conversation row's id and `outcome IS NULL`.
result: pass
notes: |
  Operator sent 3 Telegram messages (2 simple interactions + 1 workflow)
  post-runbook. No `NoResultFound`; `WorkflowRun` rows show `conversation_id`
  populated correctly and `outcome IS NULL` (expected — SC#4 / D-06).

### 3. Re-run integration migration test post-runbook
expected: |
  `uv run pytest tests/test_workflow_runner.py::test_migration_0006_upgrades_and_downgrades -q`
  exits 0. Currently RED locally because dev Postgres has leftover v1.0
  `workflow_runs` rows; the runbook's TRUNCATE in Test 1 is the explicit gating
  step that flips it green. Confirms Success Criterion #2.
result: pass
notes: |
  Operator re-truncated workflow_runs and ran the full integration suite. This
  specific test is ABSENT from the failure list (`integration-tests.log`),
  confirming it passed. Remaining 5 integration failures are dashboard test-side
  fallout from the new NOT NULL `conversation_id` (mechanical fix — inline
  `WorkflowRun(...)` ctors missing the Conversation pre-insert pattern already
  established in `tests/dashboard/conftest.py:71-90`) plus 1 stale
  `test_send_message_persists` assertion unrelated to Phase 17. Logged in the
  Gaps section below for post-UAT cleanup.

### 4. Flip ARCH-01 / ARCH-05 traceability table entries to Completed
expected: |
  After Tests 1–3 pass, change `| ARCH-01 | Phase 17 | Pending |` and
  `| ARCH-05 | Phase 17 | Pending |` to `Completed` in `.planning/REQUIREMENTS.md`,
  and tick the Phase 17 checkbox in `.planning/ROADMAP.md`.
result: pass
notes: |
  Applied:
  - `.planning/REQUIREMENTS.md` line 12: ARCH-01 checkbox `[ ]` → `[x]`
  - `.planning/REQUIREMENTS.md` line 16: ARCH-05 checkbox `[ ]` → `[x]`
  - `.planning/REQUIREMENTS.md` line 129: ARCH-01 status `Pending` → `Completed`
  - `.planning/REQUIREMENTS.md` line 133: ARCH-05 status `Pending` → `Completed`
  - `.planning/ROADMAP.md` line 38: Phase 17 checkbox `[ ]` → `[x]` + closing note
    updated to reflect live-DB verification completed 2026-05-19.

## Summary

total: 4
passed: 4
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

# Phase 17 UAT additional observations — non-blocking, defer to post-UAT /gsd:quick

- truth: "Dashboard list/polling tests construct `WorkflowRun(...)` inline without pre-inserting a Conversation row"
  status: failed
  reason: |
    Phase 17 NOT NULL `conversation_id` enforcement (correct production behavior)
    causes test-side IntegrityError. `tests/dashboard/conftest.py:71-90`
    `make_failed_cascade_run` already shows the right pattern; the 4 inline
    constructions need the same 3-line treatment.
  severity: minor
  test: post-UAT
  artifacts:
    - path: tests/dashboard/test_list_view.py
      issue: "lines 82, 113 — WorkflowRun ctor missing conversation_id + matching Conversation insert"
    - path: tests/dashboard/test_polling_halt.py
      issue: "lines 19-26, 42-50 — same pattern"
  missing:
    - "Update 4 dashboard tests to pre-insert Conversation row and pass conversation_id"
  debug_session: ""
  scope: "post-Phase-17 /gsd:quick"

- truth: "`tests/test_gateway.py::test_send_message_persists` asserts on legacy raw-string return"
  status: failed
  reason: |
    `send_message()` returns `SendResult(message_id=...)` since commit 3b4a163
    (pre-Phase-17). Test still asserts `result == "7777"`. Unrelated to Phase 17.
  severity: minor
  test: post-UAT
  artifacts:
    - path: tests/test_gateway.py
      issue: "line 127 — change to `result.message_id == '7777'`"
    - path: src/robotina/gateway/send.py
      issue: "line 86 — SendResult return type"
  missing:
    - "Update assertion to match SendResult shape"
  debug_session: ""
  scope: "post-Phase-17 /gsd:quick"

- truth: "`tests/unit/test_prompts.py::test_skill_index_appended_to_prompt` mock missing invocation_id"
  status: failed
  reason: |
    Phase 18 commit 0f5ad54 added a hard bracket-read `job.meta['invocation_id']`
    in `run_task`. Mock job.meta only has `task_type` → KeyError. Production code
    is correct; test mock is stale to in-flight Phase 18 plumbing.
  severity: minor
  test: post-UAT
  artifacts:
    - path: src/robotina/queue/jobs.py
      issue: "line 165 — invocation_id bracket-read introduced in Phase 18"
    - path: tests/unit/test_prompts.py
      issue: "line 73 — mock_job.meta missing invocation_id"
  missing:
    - "Add invocation_id to mock_job.meta — belongs in Phase 18 plan 18-02"
  debug_session: ""
  scope: "Phase 18 — plan 18-02 or a Phase-18 /gsd:quick (NOT a Phase 17 gap)"

- truth: "`tests/unit/test_gateway_boot.py::test_main_exits_on_missing_household_id` fails on dev env .env leak"
  status: failed
  reason: |
    Already documented in `deferred-items.md` line 13. `.env` provides
    HOUSEHOLD_ID so the gateway reaches Telegram bootstrap (token reject) instead
    of the missing-env-var guard. Pre-existing, unrelated to Phase 17/18.
  severity: minor
  test: post-UAT
  artifacts:
    - path: tests/unit/test_gateway_boot.py
    - path: .planning/phases/17-conversation-fk-closure/deferred-items.md
      issue: "already tracked"
  missing:
    - "Already deferred — no new action"
  debug_session: ""
  scope: "already in deferred-items.md"
