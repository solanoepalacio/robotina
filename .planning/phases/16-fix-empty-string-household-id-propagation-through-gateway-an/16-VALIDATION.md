---
phase: 16
slug: fix-empty-string-household-id-propagation-through-gateway-an
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-15
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Detailed `## Validation Architecture` lives in 16-RESEARCH.md — this file is the executor-facing sampling contract.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing project setup) |
| **Config file** | `pyproject.toml` (existing `[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/unit/test_task_types.py tests/unit/test_household_manager_api.py tests/unit/test_start_workflow.py tests/unit/test_workflow_runner.py -x -q` |
| **Full suite command** | `uv run pytest -x -q` |
| **Estimated runtime** | ~30 seconds for quick, ~3 minutes for full |

---

## Sampling Rate

- **After every task commit:** Run quick suite for files touched by the task
- **After every plan wave:** Run full unit suite for the affected module
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 0 | REQ-HID-1 | — | conftest sets `HOUSEHOLD_ID=test-household` for all tests | unit setup | `uv run pytest tests/unit/test_conftest_household.py -x -q` | ❌ W0 | ⬜ pending |
| 16-01-02 | 01 | 0 | REQ-HID-1 | — | Wave 0 test stubs exist and import cleanly | unit | `uv run pytest tests/unit/test_household_id_validation.py --collect-only` | ❌ W0 | ⬜ pending |
| 16-02-01 | 02 | 1 | REQ-HID-2 | — | `Field(min_length=1)` rejects `""` on all 7 task-input models | unit | `uv run pytest tests/unit/test_task_types.py::test_household_id_rejects_empty -x -q` | ❌ W0 | ⬜ pending |
| 16-02-02 | 02 | 1 | REQ-HID-2 | — | Valid non-empty `household_id` still constructs successfully | unit | `uv run pytest tests/unit/test_task_types.py::test_household_id_accepts_valid -x -q` | ❌ W0 | ⬜ pending |
| 16-03-01 | 03 | 1 | REQ-HID-3 | — | `HouseholdManagerApiTool(household_id="")` raises `ValueError` at construction | unit | `uv run pytest tests/unit/test_household_manager_api.py::test_empty_household_id_rejected -x -q` | ❌ W0 | ⬜ pending |
| 16-03-02 | 03 | 1 | REQ-HID-3 | — | `StartWorkflowTool` rejects empty `household_id` (default removed) | unit | `uv run pytest tests/unit/test_start_workflow.py::test_empty_household_id_rejected -x -q` | ❌ W0 | ⬜ pending |
| 16-03-03 | 03 | 1 | REQ-HID-3 | — | `start_workflow._run()` raises when `shared_context["household_id"]` empty (removes silent `.get("","")` fallback) | unit | `uv run pytest tests/unit/test_start_workflow.py::test_run_rejects_empty_in_context -x -q` | ❌ W0 | ⬜ pending |
| 16-04-01 | 04 | 1 | REQ-HID-4 | — | `queue_workflow(household_id="")` raises before any DB insert | unit | `uv run pytest tests/unit/test_workflow_runner.py::test_queue_workflow_rejects_empty_household_id -x -q` | ❌ W0 | ⬜ pending |
| 16-05-01 | 05 | 1 | REQ-HID-5 | — | Gateway entrypoint (`gateway/__init__.py::main`) raises `RuntimeError` when `HOUSEHOLD_ID` unset/empty | integration | `uv run pytest tests/integration/test_gateway_startup.py::test_missing_household_id_raises -x -q` | ❌ W0 | ⬜ pending |
| 16-05-02 | 05 | 1 | REQ-HID-5 | — | Per-message handler uses bracket-form read (no silent default) — `os.environ["HOUSEHOLD_ID"]` only | unit | `uv run pytest tests/unit/test_gateway_handler.py::test_handler_uses_bracket_form -x -q` | ❌ W0 | ⬜ pending |
| 16-06-01 | 06 | 1 | REQ-HID-6 | — | `.env.example` contains `HOUSEHOLD_ID=` | content | `grep -E "^HOUSEHOLD_ID=" .env.example` | ✅ | ⬜ pending |
| 16-06-02 | 06 | 1 | REQ-HID-7 | — | `gateway/send.py` no longer references `HOUSEHOLD_ID` in its docstring (audit confirmed unused) | content | `! grep -i HOUSEHOLD_ID src/robotina/gateway/send.py` | ✅ | ⬜ pending |
| 16-06-03 | 06 | 1 | REQ-HID-8 | — | PROJECT.md Key Decisions table has new row: `household_id is required and validated end-to-end` | content | `grep "household_id is required and validated" .planning/PROJECT.md` | ✅ | ⬜ pending |
| 16-07-01 | 07 | 2 | REQ-HID-9 | — | Full unit suite green | full | `uv run pytest tests/unit -x -q` | ✅ | ⬜ pending |
| 16-07-02 | 07 | 2 | REQ-HID-9 | — | Full integration suite green | full | `uv run pytest tests/integration -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — add autouse fixture that sets `HOUSEHOLD_ID=test-household` so module-level guards in entrypoint don't break collection. **Scope:** root conftest applies to all suites.
- [ ] `tests/unit/test_household_id_validation.py` — Pydantic model rejection tests for 7 task-input models (REQ-HID-2).
- [ ] `tests/unit/test_household_manager_api.py` — add `test_empty_household_id_rejected` (REQ-HID-3).
- [ ] `tests/unit/test_start_workflow.py` — add `test_empty_household_id_rejected` and `test_run_rejects_empty_in_context` (REQ-HID-3).
- [ ] `tests/unit/test_workflow_runner.py` — add `test_queue_workflow_rejects_empty_household_id` (REQ-HID-4).
- [ ] `tests/integration/test_gateway_startup.py` — gateway entrypoint missing-env-var test (REQ-HID-5). NEW FILE.
- [ ] `tests/unit/test_gateway_handler.py` — add `test_handler_uses_bracket_form` (REQ-HID-5).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Misconfigured deploy actually fails loudly with the expected error | REQ-HID-5 | Verifies operator UX — error message readability in real terminal/log output | 1. `unset HOUSEHOLD_ID` (or `HOUSEHOLD_ID=""`); 2. `uv run agent` (or equivalent gateway entrypoint); 3. Confirm `RuntimeError` with clear message naming the env var; 4. Confirm process exits non-zero. |
| Existing DB rows with `household_id=""` remain untouched (no migration) | CONTEXT.md decision | Negative test — confirms we didn't accidentally write a migration | `psql -c "SELECT count(*) FROM workflow_runs WHERE household_id=''"` returns same count before/after deploy. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
