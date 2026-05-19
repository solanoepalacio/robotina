---
phase: 18
slug: robotinainvocation-entity
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-19
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (project standard, configured in `pyproject.toml`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest -x -k "phase18 or invocation or workflow_runner or start_workflow or handler"` |
| **Full suite command** | `uv run pytest -x` |
| **Estimated runtime** | ~25-40 seconds (full); ~5-10 seconds (quick) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -x -k "phase18 or invocation or workflow_runner or start_workflow or handler"` (the touched-files slice)
- **After every plan wave:** Run `uv run pytest -x`
- **Before `/gsd-verify-work`:** Full suite must be green AND `uv run pytest tests/dashboard/test_independence.py -x` (DASH-14 module-isolation grep gate)
- **Max feedback latency:** 40 seconds

---

## Per-Task Verification Map

> Populated by the planner per task. Stubs below cover the requirement → test mapping discovered in RESEARCH.md §"Phase Requirements → Test Map".

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 18-XX-XX | TBD  | TBD  | ARCH-02     | —          | RobotinaInvocation model + table present | unit/migration | `uv run pytest tests/unit/test_models.py tests/migrations/test_0007.py -x` | ❌ W0 | ⬜ pending |
| 18-XX-XX | TBD  | TBD  | ARCH-03     | —          | `WorkflowRun.triggered_by_invocation_id` nullable FK persists end-to-end | integration | `uv run pytest tests/integration/test_workflow_runner.py -x -k triggered_by_invocation` | ❌ W0 | ⬜ pending |
| 18-XX-XX | TBD  | TBD  | ARCH-04     | —          | `AddRecipeOutcome` Pydantic shape defined; replaces `WorkflowOutcome` stub | unit | `uv run pytest tests/test_task_types.py -x` | ❌ W0 | ⬜ pending |
| 18-XX-XX | TBD  | TBD  | DASH-13     | —          | Detail view renders `triggered_by_invocation_id` row (UUID or "—") | template | `uv run pytest tests/dashboard/test_workflow_detail.py -x -k invocation` | ❌ W0 | ⬜ pending |
| 18-XX-XX | TBD  | TBD  | DASH-14     | —          | `RobotinaInvocation` imported from `queue.models` only; no cross-module shortcut | grep+AST | `uv run pytest tests/dashboard/test_independence.py -x` | ✅ | ⬜ pending |
| 18-XX-XX | TBD  | TBD  | success-criterion #1 | — | Gateway inserts RobotinaInvocation(USER_MESSAGE) + enqueues with meta['invocation_id'] | integration | `uv run pytest tests/test_gateway.py -x -k invocation` | ❌ W0 | ⬜ pending |
| 18-XX-XX | TBD  | TBD  | LOAD-BEARING (D-24) | — | Duplicate platform_message_id → NO orphan RobotinaInvocation insert | integration | `uv run pytest tests/test_gateway.py -x -k duplicate` | ⚠ extend existing | ⬜ pending |
| 18-XX-XX | TBD  | TBD  | success-criterion #2 | — | `StartWorkflowTool(invocation_id=)` → `queue_workflow(triggered_by_invocation_id=)` → persisted row | unit | `uv run pytest tests/unit/test_start_workflow_tool.py -x -k invocation` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Planner instruction:** Replace each `18-XX-XX` row with the actual task ID once PLAN.md files are generated. Each row must have a corresponding `<automated>` block in PLAN.md OR be listed in Wave 0 Requirements below.

---

## Wave 0 Requirements

> Test files that must exist BEFORE feature tasks can verify against them. Wave 0 stubs them with skip markers; subsequent waves fill them in.

- [ ] `tests/test_task_types.py` — `AddRecipeOutcome` shape assertions (replaces `WorkflowOutcome` stub site)
- [ ] `tests/migrations/test_0007.py` — upgrade/downgrade round-trip for `0007_robotina_invocations.py`
- [ ] `tests/test_gateway.py` — extend with `test_user_message_creates_invocation` and `test_duplicate_message_no_orphan_invocation` (the load-bearing D-24 guard)
- [ ] `tests/unit/test_start_workflow_tool.py` — extend with `invocation_id` constructor + propagation tests; update ALL existing 15+ `StartWorkflowTool(...)` constructor calls to include `invocation_id="inv-1"` (TypeError otherwise)
- [ ] `tests/integration/test_workflow_runner.py` — extend with `test_queue_workflow_persists_triggered_by_invocation_id`
- [ ] `tests/dashboard/test_workflow_detail.py` (or wherever Phase 13 placed dashboard template tests) — extend with `triggered_by_invocation_id` rendering assertion (UUID + "—" branches)
- [ ] Shared fixture: `invocation_factory(conversation_id, trigger=USER_MESSAGE, status=PENDING)` in `tests/conftest.py` or `tests/fixtures.py`

*All required files exist as stubs after Wave 0; feature waves fill in real assertions.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end smoke: real Telegram message → DB row inspection | success-criterion #1 | Validates the gateway → DB → enqueue chain against real Postgres + Redis with a real Telegram message; per `feedback_test_before_handoff.md` | 1. `docker compose up postgres redis -d` and `uv run migrate`. 2. Start gateway + task-runner. 3. Send a Telegram message. 4. Run `psql -c "SELECT id, trigger, trigger_ref_id, status FROM robotina_invocations ORDER BY created_at DESC LIMIT 1;"` — confirm one `USER_MESSAGE` row with `status=pending`. 5. Run `psql -c "SELECT id, triggered_by_invocation_id FROM workflow_runs ORDER BY created_at DESC LIMIT 1;"` — confirm FK set if a workflow was started. |
| Dashboard detail view renders "Triggered by invocation" row | DASH-13 | Visual confirmation per UI-SPEC; automated template test covers structure but not browser rendering | Open `http://127.0.0.1:8123/workflows/<run-id>` for a Phase-18-created WorkflowRun. Confirm "Triggered by invocation" dt/dd is present, mono-styled, with a UUID value (or "—" for a NULL row). |
| Migration runbook executes cleanly on staging | success-criterion #1 (deploy path) | The migration is additive but enum creation has historically tripped on existing DBs (Phase 2 lesson) | Follow the deploy runbook in the phase SUMMARY (planner to produce): `docker compose stop task-runner` → `uv run migrate` → confirm `robotina_invocations` table exists + `workflow_runs.triggered_by_invocation_id` column added → restart task-runner. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 40s
- [ ] `nyquist_compliant: true` set in frontmatter
- [ ] DASH-14 grep-gate (`tests/dashboard/test_independence.py`) verified green AFTER all Phase 18 commits

**Approval:** pending
