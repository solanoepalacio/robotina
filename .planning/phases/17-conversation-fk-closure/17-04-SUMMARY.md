---
phase: 17-conversation-fk-closure
plan: 04
subsystem: documentation

tags: [requirements-alignment, roadmap-alignment, deploy-runbook, phase-closeout, wave-3, no-code-changes]

# Dependency graph
requires:
  - phase: 17-conversation-fk-closure
    provides: Plan 17-01 (Wave 0 RED-state lock tests), Plan 17-02 (Wave 1 schema migration 0006 + ORM + WorkflowOutcome stub), Plan 17-03 (Wave 2 queue_workflow + StartWorkflowTool + run_task Conversation lookup wiring) — the implementation that ARCH-01's new wording now correctly describes
provides:
  - REQUIREMENTS.md ARCH-01 wording aligned with the as-built implementation (single Alembic revision, table pre-cleaned per runbook; existing v1.0 rows discarded by deploy procedure)
  - ROADMAP.md Phase 17 success criterion #2 aligned with the single-revision implementation (trivial `COUNT(*) WHERE conversation_id IS NULL = 0` because pre-clean truncation makes the table empty when 0006 runs)
  - .planning/phases/17-conversation-fk-closure/17-RUNBOOK.md — operator-facing D-08 five-step deploy procedure as a discoverable artifact in the phase folder (no need to spelunk CONTEXT.md)
  - Deferred-items.md updated with the two environmental migration-test failures that the runbook itself will resolve (the runbook's failure-modes table predicted them)
affects: [Phase 17 close-out — ARCH-01 / ARCH-05 traceability table entries flip to Completed only after the operator executes the runbook against the live DB; future Claude sessions reading REQUIREMENTS.md will not re-litigate the three-step backfill rationale]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase-folder runbook artifact: the canonical operator deploy procedure lives alongside the phase's PLANs/SUMMARYs so the operator does not need to read CONTEXT.md to execute deploys. Pattern reusable for Phase 20 / Phase 22+ when DB rewrites land."
    - "Requirement-wording-as-deliverable: when a requirement's wording diverges from the implementation (here: D-01's single-revision decision contradicts ARCH-01's three-step phrasing), the planner explicitly includes a one-line REQUIREMENTS.md/ROADMAP.md edit in the phase plan rather than logging a follow-up. Closes the documentation loop atomically with the implementation that made it stale."

key-files:
  created:
    - .planning/phases/17-conversation-fk-closure/17-RUNBOOK.md
  modified:
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .planning/phases/17-conversation-fk-closure/deferred-items.md

# Decisions
decisions:
  - "Replace ARCH-01's three-step Alembic wording with single-revision pre-clean wording (per CONTEXT.md D-01). Documentation alignment only; ARCH-01 checkbox stays `[ ]` — the requirement flips to `[x]` only when the operator executes the runbook against the live DB and a Telegram smoke-test confirms the FK is populated. This is intentional: the requirement is not complete until production data reflects it."
  - "Touch ROADMAP.md Phase 17 success criterion #2 in the same edit. The plan explicitly scoped this beyond a pure REQUIREMENTS.md edit because the old three-step phrasing was duplicated in two places and leaving one stale would be a worse failure mode than amending both atomically."
  - "Materialize the D-08 five-step procedure as a stand-alone phase-folder artifact (17-RUNBOOK.md) rather than embedding it in the final commit message body. The runbook is the operator's reference under load (a live DB to deploy against); a commit message is a poor surface for a procedure that includes failure-modes and explicit DO-NOTs. The final commit message references the artifact path."
  - "Do NOT execute the runbook in this plan. The runbook is a deploy artifact; running it requires `docker compose stop`, `psql TRUNCATE`, and `uv run migrate` against a live environment. That is a manual operator gate (the same one that flips ARCH-01 / ARCH-05 to `[x]`)."
  - "Do NOT modify any source file in src/robotina/ or any test in tests/. Plan 17-04 is pure documentation. The plan's verification step #4 ran the post-17-03 unit suite to confirm no documentation edit accidentally touched code; 188 unit tests pass; the 3 failures (1 pre-existing gateway-boot environmental, 2 integration migration tests requiring a clean DB) are environmental and tracked in deferred-items.md."

# Metrics
metrics:
  duration: "~3 minutes"
  completed: "2026-05-19T01:27:01Z"
  tasks_completed: 2
  files_created: 1
  files_modified: 3
  commits: 2
---

# Phase 17 Plan 04: REQUIREMENTS.md + ROADMAP.md wording alignment + deploy runbook

One-liner: Closed the Phase 17 documentation loop — aligned ARCH-01 wording with the single-revision implementation in two files and materialized the D-08 deploy procedure as `17-RUNBOOK.md` so the operator can execute it without re-reading CONTEXT.md.

## What changed

### `.planning/REQUIREMENTS.md` — ARCH-01 wording

**Before (line 12):**
```
- [ ] **ARCH-01**: `WorkflowRun` rows have a `conversation_id` FK to `Conversation`; existing rows are backfilled from `shared_context.reply_context.chat_id` + `platform`; column is migrated nullable → backfill → NOT NULL via a three-step Alembic sequence.
```

**After:**
```
- [ ] **ARCH-01**: `WorkflowRun` rows have a `conversation_id` FK to `Conversation`; the column lands as NOT NULL in a single Alembic revision (table is pre-cleaned before deploy per the Phase 17 runbook). Existing v1.0 rows are discarded by the deploy runbook; the post-migration `COUNT(*) WHERE conversation_id IS NULL` returns 0 trivially because no rows exist when 0006 runs.
```

The checkbox stays `[ ]` — flips to `[x]` only after the operator executes the runbook and smoke-tests Telegram traffic per D-01 / D-08 close-out language. ARCH-01's traceability table row (`| ARCH-01 | Phase 17 | Pending |`) is unchanged at this stage.

### `.planning/ROADMAP.md` — Phase 17 success criterion #2

**Before (line 55):**
```
  2. The three-step Alembic sequence (add nullable → backfill → enforce NOT NULL) runs on a staging DB clone without orphan rows (post-migration `COUNT(*) WHERE conversation_id IS NULL` returns 0).
```

**After:**
```
  2. The single Alembic revision 0006 (add `conversation_id` NOT NULL + `outcome` nullable JSON in one upgrade) runs cleanly on a pre-cleaned database; post-migration `COUNT(*) WHERE conversation_id IS NULL` returns 0 trivially because the runbook truncates `workflow_runs` before applying 0006.
```

Every other ROADMAP row, requirement count, and progress-table cell is unchanged — only the single success-criterion line was touched.

### `.planning/phases/17-conversation-fk-closure/17-RUNBOOK.md` — new file (118 lines)

Five-step procedure (one-line summaries):

1. **Stop the workers** — `docker compose stop task-runner` + `scheduler-worker` if running; confirm no RQ worker is still attached to `agent-tasks`.
2. **Drain RQ** — verify zero PENDING / RUNNING workflows via rq-dashboard or `rq info`; do not proceed with jobs in flight (the TRUNCATE would orphan them).
3. **Truncate workflow tables** — `TRUNCATE workflow_runs, workflow_run_steps RESTART IDENTITY CASCADE;` via psql; conversations + stored_messages explicitly preserved.
4. **Apply the migration** — `uv run migrate` invokes `alembic upgrade head` which runs 0006; verify with `\d workflow_runs` (conversation_id NOT NULL VARCHAR with `workflow_runs_conversation_id_fkey` FK; outcome nullable JSON).
5. **Restart the worker** — `docker compose start task-runner` + smoke-test from Telegram with "hola"; verify a new WorkflowRun row has `conversation_id` populated and `outcome` NULL.

Additionally captured:
- **Failure-modes table** — three rows mapping observable symptoms (NotNullViolation, NoResultFound, MultipleResultsFound) to root causes (skipped TRUNCATE, stale RQ jobs, duplicate Conversation rows) and recovery actions.
- **"What NOT to do" guardrails** — no backfill `op.execute("UPDATE ...")` in 0006; no stripping of `chat_id`/`user_id`/`platform` from `StartWorkflowTool` until the ARCH-05 deprecation window closes post-v1.1; no premature flip of ARCH-01 / ARCH-05 to `[x]`.

### `.planning/phases/17-conversation-fk-closure/deferred-items.md` — appended

Added a "Plan 17-04 additional observations" section noting that the two integration migration tests (`test_migration_0005_upgrades_and_downgrades` and `test_migration_0006_upgrades_and_downgrades`) fail against the local test Postgres with `NotNullViolation` — the exact failure mode the runbook predicts. They will flip green automatically once the runbook executes Step 3 against the test DB. Plan 17-04 touched zero source/test files, so it cannot have introduced these failures (verified: documentation-only diff).

## Source / test files

None modified.

```
$ git diff --stat 0a5fbc8^..8e72f1e
 .planning/REQUIREMENTS.md                                  | 2 +-
 .planning/ROADMAP.md                                       | 2 +-
 .planning/phases/17-conversation-fk-closure/17-RUNBOOK.md  | 118 +++++++++++++++++++
 3 files changed, 119 insertions(+), 2 deletions(-)
```

The deferred-items.md append is staged for the final state-update commit (the standard Phase 17 close-out group: SUMMARY + STATE + ROADMAP progress, per execute-plan.md's `<final_commit>` step).

## Phase 17 close-out

This plan completes the Phase 17 documentation loop. Phase 17 ships across four plans:

| Plan | Wave | Subsystem | Output |
|------|------|-----------|--------|
| [17-01](17-01-SUMMARY.md) | 0 | testing | 13 RED-state lock tests encoding every Phase 17 contract |
| [17-02](17-02-SUMMARY.md) | 1 | database | Alembic 0006 single-revision migration + ORM columns + WorkflowOutcome stub |
| [17-03](17-03-SUMMARY.md) | 2 | workflow | `queue_workflow` / `StartWorkflowTool` / `run_task` wiring; Conversation.one() lookup |
| 17-04 (this plan) | 3 | documentation | REQUIREMENTS.md + ROADMAP.md wording alignment + 17-RUNBOOK.md |

**Operator gate to flip the requirement checkboxes:**

ARCH-01 and ARCH-05 stay `[ ]` in REQUIREMENTS.md until ALL of:

1. The operator executes `17-RUNBOOK.md` against the live DB (steps 1–5).
2. A real Telegram message produces a WorkflowRun row whose `conversation_id` equals the upserted Conversation's `id`.
3. The legacy `shared_context.reply_context` read paths (workflow_runner.py:401–533 dead-letter block and workflows.py:105–159 step `build_input`) continue to function unchanged — ARCH-05 deprecation window stays open through v1.1.

The runbook itself is the post-deploy verification surface. When all three conditions hold, the operator flips ARCH-01 and ARCH-05 to `[x]` and updates the traceability table at the bottom of REQUIREMENTS.md.

## Deviations from Plan

None — the plan executed exactly as written. Both tasks completed against the acceptance criteria on first attempt. No Rule 1-3 fixes required (no source code in scope, no test execution in scope beyond the post-tasks plan-level verification).

## Verification

### Task 4.1 acceptance criteria (all PASS)

- `grep -q "single Alembic revision" .planning/REQUIREMENTS.md` → 1 match (new wording)
- `grep -q "table is pre-cleaned before deploy" .planning/REQUIREMENTS.md` → 1 match
- `grep -c "three-step Alembic sequence" .planning/REQUIREMENTS.md` → 0 (old wording fully replaced)
- `grep -c "existing rows are backfilled from .shared_context.reply_context.chat_id" .planning/REQUIREMENTS.md` → 0
- `grep -c "^- \[ \] \*\*ARCH-01\*\*" .planning/REQUIREMENTS.md` → 1 (single bullet preserved)
- `grep -c "^- \[ \] \*\*ARCH-" .planning/REQUIREMENTS.md` → 5 (ARCH-01..05 all present)
- `grep "| ARCH-01 | Phase 17 | Pending |" .planning/REQUIREMENTS.md` → 1 line (traceability untouched)
- `grep -q "single Alembic revision 0006" .planning/ROADMAP.md` → 1 match
- `grep -c "three-step Alembic sequence" .planning/ROADMAP.md` → 0 (old wording replaced)

### Task 4.2 acceptance criteria (all PASS)

- `test -f .planning/phases/17-conversation-fk-closure/17-RUNBOOK.md` → exists
- `grep -q "Step 1 — Stop the workers"` → 1 match
- `grep -q "Step 2 — Drain RQ"` → 1 match
- `grep -q "TRUNCATE workflow_runs, workflow_run_steps RESTART IDENTITY CASCADE"` → 1 match
- `grep -q "uv run migrate"` → 3 matches (Step 4 command + verification block + procedure section)
- `grep -q "ARCH-05 deprecation window"` → 1 match
- `grep -q "workflow_runs_conversation_id_fkey"` → 1 match
- `wc -l 17-RUNBOOK.md` → 118 lines (in 80–200 range)

### Plan-level verification (per plan.md `<verification>`)

1. `grep "single Alembic revision" .planning/REQUIREMENTS.md` → updated line returned. ✅
2. `ls .planning/phases/17-conversation-fk-closure/17-RUNBOOK.md` → present. ✅
3. `grep "three-step Alembic" .planning/REQUIREMENTS.md` → 0 matches. ✅
4. `uv run pytest tests/unit/ tests/test_workflow_runner.py tests/test_task_types.py -q` → 188 passed, 3 failed. The 3 failures are all environmental (one pre-existing Telegram-bootstrap fixture leak documented in deferred-items.md from Plan 17-02 + two `@pytest.mark.integration` migration tests that require an empty `workflow_runs` table — i.e., the exact precondition the new runbook establishes). Plan 17-04 modified zero source/test files; it cannot have introduced these. Tracked in `deferred-items.md`.

### Commit log

```
8e72f1e docs(17-04): add Phase 17 deploy runbook (D-08 five-step procedure)
0a5fbc8 docs(17-04): align ARCH-01 wording with single-revision implementation
```

## Self-Check: PASSED

- `.planning/REQUIREMENTS.md` ARCH-01 wording updated: FOUND
- `.planning/ROADMAP.md` Phase 17 success criterion #2 updated: FOUND
- `.planning/phases/17-conversation-fk-closure/17-RUNBOOK.md` created: FOUND
- Commit `0a5fbc8` (Task 4.1): FOUND in `git log --oneline`
- Commit `8e72f1e` (Task 4.2): FOUND in `git log --oneline`
- No source/test files modified by this plan: confirmed via `git diff --stat 0a5fbc8^..8e72f1e` — only documentation files touched.
- No file deletions in either commit: confirmed via `git diff --diff-filter=D --name-only HEAD~1 HEAD`.
