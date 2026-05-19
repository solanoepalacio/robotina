---
phase: 17
slug: conversation-fk-closure
status: human_needed
date: 2026-05-18
score: 7/7 code-side must-haves verified; 1 operator-gated runbook execution remaining
re_verification:
  previous_status: null
  previous_score: null
  gaps_closed: []
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Execute Phase 17 deploy runbook against the live development DB"
    expected: "Steps 1-5 of `.planning/phases/17-conversation-fk-closure/17-RUNBOOK.md` succeed: workers stopped → RQ drained → `TRUNCATE workflow_runs, workflow_run_steps RESTART IDENTITY CASCADE` executed → `uv run migrate` upgrades to revision 0006 cleanly → workers restarted. Post-migrate `\\d workflow_runs` in psql shows `conversation_id character varying not null` plus a FK constraint named `workflow_runs_conversation_id_fkey` referencing `conversations(id)`, and `outcome json` nullable."
    why_human: "Requires `docker compose stop`, raw `psql` TRUNCATE, and `uv run migrate` against a live local DB. Destructive (drops historical `workflow_runs` rows) and not safe to run autonomously."
  - test: "Telegram smoke test post-runbook"
    expected: "Send a single Telegram message to the bot (e.g. 'hola'). The gateway upserts a Conversation row; `run_task` runs `session.query(Conversation).filter_by(platform=Platform.TELEGRAM, chat_id=<chat>).one()` successfully (no `NoResultFound`); a new `WorkflowRun` row is written with `conversation_id` matching that Conversation row's id and `outcome IS NULL`."
    why_human: "Requires a live Telegram bot session and live LLM backend. End-to-end behavior cannot be exercised under unit/mock tests."
  - test: "Re-run integration migration test post-runbook"
    expected: "`uv run pytest tests/test_workflow_runner.py::test_migration_0006_upgrades_and_downgrades -q` exits 0. This test is currently RED in the local environment because the dev Postgres has leftover v1.0 `workflow_runs` rows (documented in `deferred-items.md`); the runbook's TRUNCATE is the explicit gating step that flips it green."
    why_human: "Same root cause as the runbook gate — the test cannot pass until the operator pre-cleans the live DB. Once green, this confirms Success Criterion #2."
  - test: "Flip ARCH-01 / ARCH-05 traceability table entries to `Completed`"
    expected: "After the runbook + smoke test pass, change `| ARCH-01 | Phase 17 | Pending |` and `| ARCH-05 | Phase 17 | Pending |` to `Completed` in `.planning/REQUIREMENTS.md`, and tick the Phase 17 checkbox in `.planning/ROADMAP.md`."
    why_human: "Operator-only documentation update gated on runbook success."
---

# Phase 17: Conversation FK Closure — Verification Report

**Phase Goal (ROADMAP):** Every WorkflowRun is linked to its originating Conversation via FK; existing rows are safely backfilled.

**Goal as redefined by D-01 / Plan 17-04 wording update:** Every WorkflowRun is linked to its originating Conversation via FK; the column lands NOT NULL in a single Alembic revision against a pre-cleaned table (no in-migration backfill).

**Verified:** 2026-05-18
**Status:** `human_needed` — code-side scope fully delivered and tested green; only the operator-gated runbook execution + Telegram smoke test remain.
**Re-verification:** No — initial verification.

---

## Goal Achievement

The phase goal decomposes into four observable truths (one per ROADMAP success criterion). All four are met at the code/migration layer; SC#2 requires the operator runbook to flip the live DB before it can be observed end-to-end.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A WorkflowRun written via `StartWorkflowTool` carries `conversation_id` matching the originating Conversation | VERIFIED | `src/robotina/queue/jobs.py:138-170` (Conversation `.one()` lookup + `conversation_id=conversation.id` injected into `StartWorkflowTool` ctor); `src/robotina/agent/tools/start_workflow.py:138` (ctor field) + `:178` (`conversation_id=self.conversation_id` passed to `queue_workflow`); `src/robotina/queue/workflow_runner.py:110` (required arg) + `:162` (`conversation_id=conversation_id` on `WorkflowRun(...)`). End-to-end traced by `tests/unit/test_agent_runner.py::test_run_task_resolves_and_injects_conversation_id` (GREEN) and `tests/test_workflow_runner.py::test_queue_workflow_persists_conversation_id` (GREEN). |
| 2 | Single Alembic revision 0006 (adds `conversation_id` NOT NULL + `outcome` nullable JSON) runs cleanly on a pre-cleaned DB; post-migration `COUNT(*) WHERE conversation_id IS NULL = 0` trivially | VERIFIED (code-side) / OPERATOR-GATED (live DB) | `migrations/versions/0006_conversation_fk_and_outcome.py` exists with `revision='0006'`, `down_revision='0005'`, `op.add_column × 2`, `op.drop_column × 2`, ZERO `op.execute` / UPDATE backfill (D-02 honored). Integration test `test_migration_0006_upgrades_and_downgrades` exists in `tests/test_workflow_runner.py` but is RED on the local dev DB due to leftover v1.0 rows (documented in `deferred-items.md` — predicted by the runbook's failure-modes table). |
| 3 | Existing code paths reading `shared_context.reply_context.chat_id` continue to function | VERIFIED | `src/robotina/agent/tools/start_workflow.py:152-160` (the ARCH-05 `reply_context` write into `shared_context`) is **untouched** in Wave 2. `grep -c reply_context` returns 5 (write site + comments). Regression guard test `tests/test_workflow_runner.py::test_shared_context_reply_context_still_written` is GREEN. |
| 4 | `WorkflowRun.outcome` JSON column exists nullable (slot for Phase 20) | VERIFIED | `src/robotina/queue/models.py:46` (`outcome: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)`). Test `test_workflow_run_has_outcome_column` is GREEN. Migration 0006 adds the matching DDL column. |

**Score:** 4/4 success criteria addressed in code; SC#2's runtime confirmation against the live DB is operator-gated.

---

## Success Criteria Check

Verbatim against ROADMAP `Phase 17 → Success Criteria` (post Plan 17-04 wording update):

1. **"A new WorkflowRun written via `StartWorkflowTool` has `conversation_id` set and matches the Conversation the originating message belonged to."** — VERIFIED. Traced through `jobs.py:149-156` (lookup) → `jobs.py:164-170` (`StartWorkflowTool(..., conversation_id=conversation.id)`) → `start_workflow.py:174-181` (passed to `queue_workflow`) → `workflow_runner.py:159-165` (`WorkflowRun(conversation_id=...)`). Covered by 4 unit tests (`test_run_task_resolves_and_injects_conversation_id`, `test_run_task_raises_when_conversation_missing`, `test_run_passes_conversation_id_to_queue_workflow`, `test_queue_workflow_persists_conversation_id`) — all GREEN.
2. **"The single Alembic revision 0006 runs cleanly on a pre-cleaned database; post-migration `COUNT(*) WHERE conversation_id IS NULL` returns 0 trivially..."** — CODE-SIDE VERIFIED, OPERATOR-GATED for live execution. Migration file is syntactically valid Python with the correct revision metadata and exactly two `op.add_column` calls + symmetric two `op.drop_column` downgrade. Live-DB confirmation requires the operator to run the runbook (Step 3 TRUNCATE + Step 4 `uv run migrate`). `test_migration_0006_upgrades_and_downgrades` is RED on dirty local Postgres, which the runbook's failure-modes table literally predicts.
3. **"Existing code paths that previously read `shared_context.reply_context.chat_id` continue to function (deprecation window) — single-recipe happy path unaffected."** — VERIFIED. ARCH-05 regression guard `test_shared_context_reply_context_still_written` is GREEN; `reply_context` block in `start_workflow.py:152-160` is untouched.
4. **"`WorkflowRun.outcome` JSON column exists (nullable, unused this phase) ready for Phase 20."** — VERIFIED. Column in ORM + migration; `WorkflowOutcome` Pydantic stub in `task_types.py:337-341`.

---

## Requirement Coverage

Plans declared `requirements: [ARCH-01, ARCH-05]` across all four plans.

| Requirement | Source Plan(s) | Description (current REQUIREMENTS.md wording) | Status | Evidence |
|-------------|----------------|------------------------------------------------|--------|----------|
| ARCH-01 | 17-01, 17-02, 17-03, 17-04 | `WorkflowRun` rows have a `conversation_id` FK to `Conversation`; column lands NOT NULL in a single Alembic revision (table pre-cleaned per Phase 17 runbook) | SATISFIED (code-side); checkbox `[ ]` pending operator runbook | Migration 0006, ORM column, signature/wire-up, REQUIREMENTS.md wording updated to "single Alembic revision" (`.planning/REQUIREMENTS.md:12`). Traceability table shows `Pending` — flips to `Completed` only after operator gate (D-08). |
| ARCH-05 | 17-01, 17-03, 17-04 | Legacy `shared_context.reply_context` JSON path remains readable through v1.1 | SATISFIED (code-side); checkbox `[ ]` pending operator gate | `start_workflow.py:152-160` write preserved; `test_shared_context_reply_context_still_written` GREEN. Read sites (`workflow_runner.py` dead-letter + `agent/workflows.py` step `build_input`) unchanged. |

No orphaned requirements: `REQUIREMENTS.md` only maps ARCH-01 / ARCH-05 to Phase 17; both are addressed by at least one plan.

---

## Plan must_haves Audit

### Plan 17-01 (Wave 0 lock tests)
| Truth | Status | Evidence |
|-------|--------|----------|
| Pytest collects after Wave 0 changes | VERIFIED | All 11 lock tests run and pass at this point; collection green. |
| Schema-introspection tests for `WorkflowRun.conversation_id` + `WorkflowRun.outcome` exist | VERIFIED | `test_workflow_run_has_conversation_id_column`, `test_workflow_run_has_outcome_column` present in `tests/test_workflow_runner.py`. |
| Constructor-required tests for `StartWorkflowTool.conversation_id` exist | VERIFIED | `test_constructor_requires_conversation_id_no_default`, `test_constructor_accepts_non_empty_conversation_id`, `test_run_passes_conversation_id_to_queue_workflow` in `tests/unit/test_start_workflow_tool.py`. |
| `queue_workflow` signature contract test exists | VERIFIED | `test_queue_workflow_requires_conversation_id`, `test_queue_workflow_persists_conversation_id`. |
| `run_task` Conversation-lookup contract tests exist | VERIFIED | `test_run_task_resolves_and_injects_conversation_id`, `test_run_task_raises_when_conversation_missing`. |
| `WorkflowOutcome` stub import test exists | VERIFIED | `test_workflow_outcome_stub` in `tests/test_task_types.py`. |
| ARCH-05 regression guard test exists | VERIFIED | `test_shared_context_reply_context_still_written` — GREEN post-Wave 2. |

### Plan 17-02 (Wave 1 schema + ORM + stub)
| Truth | Status | Evidence |
|-------|--------|----------|
| D-01: Single Alembic revision 0006; `revision='0006'`, `down_revision='0005'` | VERIFIED | `migrations/versions/0006_conversation_fk_and_outcome.py:18-19`. |
| D-02: Upgrade body is `op.add_column × 2` only — no `op.execute`/SELECT/UPDATE backfill | VERIFIED | `grep "op.execute\|UPDATE"` returns 0 hits in the migration file; only `op.add_column × 2` + `op.drop_column × 2`. |
| D-06: `WorkflowRun.outcome` = `Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)` | VERIFIED | `src/robotina/queue/models.py:46`. |
| `WorkflowRun.conversation_id` = String, NOT NULL, FK to `conversations.id` | VERIFIED | `src/robotina/queue/models.py:37-39` (`String, ForeignKey("conversations.id"), nullable=False`). Migration `0006:25-32` matches. |
| D-07: `WorkflowOutcome` Pydantic stub importable with `status: Literal['pending'] = 'pending'` | VERIFIED | `src/robotina/queue/task_types.py:337-341`. |
| Pure schema-introspection tests turn GREEN | VERIFIED | 3 GREEN. |
| Migration integration test passes against live Postgres | UNCERTAIN (operator-gated) | Test exists; RED on the local dev DB due to dirty data, GREEN once the runbook truncates. |

### Plan 17-03 (Wave 2 signatures + wire-up)
| Truth | Status | Evidence |
|-------|--------|----------|
| D-05: `queue_workflow` has required `conversation_id: str` arg; NO parallel `if not conversation_id` guard | VERIFIED | `workflow_runner.py:110` (signature); `grep -c "if not conversation_id"` returns 0; Phase 16 `if not household_id...` guard at `:145` preserved. |
| `queue_workflow` assigns `conversation_id` on `WorkflowRun(...)` before commit | VERIFIED | `workflow_runner.py:162`. |
| D-03: `StartWorkflowTool.conversation_id: str` (plain str, no Annotated alias) | VERIFIED | `start_workflow.py:138`; `grep -r NonEmptyConversationId src/` returns 0. |
| `StartWorkflowTool._run` threads `self.conversation_id` into `queue_workflow` | VERIFIED | `start_workflow.py:178`. |
| D-04: `run_task` handle-incoming-message branch uses `session.query(Conversation).filter_by(platform=Platform(...), chat_id=...).one()` | VERIFIED | `jobs.py:149-156`. Lazy import at `:138`. Re-uses existing `_session` at `:150` (no second session opened). |
| All existing `StartWorkflowTool(...)` ctor sites + `queue_workflow(...)` call sites pass valid `conversation_id` | VERIFIED | All 11 lock + bulk-updated unit tests are GREEN in this run. |
| ARCH-05 reply_context write UNCHANGED at `start_workflow.py:152-160` | VERIFIED | Comparing against CONTEXT.md "Reusable Assets" / PATTERNS — `reply_context` write present, regression guard GREEN. |
| All Wave 0 RED tests turn GREEN | VERIFIED | `uv run pytest …` over the 11 named tests exits 0. |

### Plan 17-04 (Wave 3 docs + runbook)
| Truth | Status | Evidence |
|-------|--------|----------|
| REQUIREMENTS.md ARCH-01 wording matches single-revision implementation | VERIFIED | `.planning/REQUIREMENTS.md:12` contains "single Alembic revision"; no remaining "three-step Alembic sequence" phrasing. |
| ROADMAP.md SC#2 wording matches | VERIFIED | `.planning/ROADMAP.md:55` contains "The single Alembic revision 0006...". |
| Deploy runbook (D-08 5-step procedure) exists in phase folder | VERIFIED | `.planning/phases/17-conversation-fk-closure/17-RUNBOOK.md` present; contains `Step 1 — Stop the workers`, `TRUNCATE workflow_runs, workflow_run_steps RESTART IDENTITY CASCADE`, `uv run migrate`, failure-modes table, "What NOT to do" section. |

---

## Test Outcome

Targeted run of the 11 Phase 17 lock tests:

```
uv run pytest tests/test_workflow_runner.py::test_workflow_run_has_conversation_id_column \
              tests/test_workflow_runner.py::test_workflow_run_has_outcome_column \
              tests/test_workflow_runner.py::test_queue_workflow_persists_conversation_id \
              tests/test_workflow_runner.py::test_queue_workflow_requires_conversation_id \
              tests/test_workflow_runner.py::test_shared_context_reply_context_still_written \
              tests/unit/test_start_workflow_tool.py::test_constructor_requires_conversation_id_no_default \
              tests/unit/test_start_workflow_tool.py::test_constructor_accepts_non_empty_conversation_id \
              tests/unit/test_start_workflow_tool.py::test_run_passes_conversation_id_to_queue_workflow \
              tests/unit/test_agent_runner.py::test_run_task_resolves_and_injects_conversation_id \
              tests/unit/test_agent_runner.py::test_run_task_raises_when_conversation_missing \
              tests/test_task_types.py::test_workflow_outcome_stub
```
Result: **11 passed in 0.59s** — all Wave 0 RED tests are now GREEN, including the ARCH-05 regression guard.

Outside this run:
- `tests/test_workflow_runner.py::test_migration_0006_upgrades_and_downgrades` — RED in local dev environment because Postgres has leftover v1.0 `workflow_runs` rows. The runbook's TRUNCATE step is the explicit gate that flips it GREEN. Documented in `deferred-items.md`. NOT a Phase 17 gap.
- `tests/test_workflow_runner.py::test_migration_0005_upgrades_and_downgrades` — same root cause (alembic upgrade head runs 0006 as part of setup and trips on the dirty DB). NOT a Phase 17 gap.
- `tests/dashboard/test_detail_view.py::test_detail_view_404_for_missing_id`, `tests/dashboard/test_no_auth.py::test_all_routes_return_200_or_404_without_auth_headers`, `tests/unit/test_gateway_boot.py::test_main_exits_on_missing_household_id` — pre-existing failures verified before Phase 17 changes (`deferred-items.md`). NOT Phase 17 gaps.

---

## Anti-Patterns / Forbidden Patterns Audit

| Check | Expected | Result |
|-------|----------|--------|
| `grep -r "NonEmptyConversationId" src/` | 0 hits (alias intentionally absent per D-03) | 0 hits — PASS |
| `grep "op.execute\|UPDATE " migrations/versions/0006_*.py` | 0 hits (D-02) | 0 hits — PASS |
| `grep -c "if not conversation_id" src/robotina/queue/workflow_runner.py` | 0 (no parallel Python guard, FK + `.one()` cover) | 0 — PASS |
| Phase 16 REQ-HID-4 guard `if not household_id or not household_id.strip()` preserved | Present at `workflow_runner.py:145` | PASS |
| `reply_context` write in `start_workflow.py:152-160` preserved | Present (ARCH-05 deprecation window) | PASS |
| Other `elif task_type` branches in `jobs.py` untouched | 4+ branches unchanged | PASS |
| Module-top imports of `Conversation, Platform` in `jobs.py` | None (lazy per-branch import per Pattern D) | PASS — import at `:138` inside the branch |

---

## Gaps

**None — phase delivers full code-side scope.** Runbook execution and live-DB smoke test are operator-side gates explicitly designed into the phase (D-08), not in-phase gaps. They are surfaced in the `human_verification` section.

Specifically NOT gaps:
- `test_migration_0006_upgrades_and_downgrades` RED locally — the runbook's failure-modes table predicts this; flips GREEN the moment the operator runs TRUNCATE + migrate.
- ARCH-01 / ARCH-05 traceability checkboxes still `Pending` — by design (Plan 17-04 explicitly does not flip them; operator does so post-runbook).
- The three pre-existing test failures listed in `deferred-items.md` — verified pre-existing on the baseline commit preceding Plan 17-02, tracked as `/gsd:quick` follow-ups.

---

## VERIFICATION COMPLETE

**Status:** `human_needed`

**Code-side scope:** 11/11 lock tests GREEN. All four ROADMAP success criteria are addressable; SC#2's live-DB confirmation is operator-gated via `17-RUNBOOK.md`. ARCH-01 and ARCH-05 are satisfied at the implementation layer; their REQUIREMENTS.md checkboxes flip to `[x]` only after the operator executes the runbook against the live DB and confirms the Telegram smoke test.

**Operator next step:** Execute `.planning/phases/17-conversation-fk-closure/17-RUNBOOK.md` Steps 1-5 against the development database, run the Telegram smoke test, then flip the ARCH-01 / ARCH-05 entries in `.planning/REQUIREMENTS.md` and the Phase 17 checkbox in `.planning/ROADMAP.md` to `Completed` / `[x]`.

_Verified: 2026-05-18_
_Verifier: Claude (gsd-verifier)_
