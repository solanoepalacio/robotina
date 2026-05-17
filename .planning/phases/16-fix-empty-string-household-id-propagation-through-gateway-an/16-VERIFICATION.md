---
phase: 16
status: passed
verified_at: 2026-05-15
uat_completed_at: 2026-05-16
must_haves_total: 11
must_haves_passed: 11
---

# Phase 16 Verification Report

**Phase Goal:** Stop empty-string `household_id` from silently propagating from a missing `HOUSEHOLD_ID` env var through `Conversation`, `IncomingMessageInput`, `WorkflowRun`, `StartWorkflowTool`, and `HouseholdManagerApiTool`.

**Verified:** 2026-05-15
**Verifier:** Claude (gsd-verifier, goal-backward)

---

## must_haves

| # | Must-have | Command / Evidence | Result | Status |
|---|-----------|--------------------|--------|--------|
| 1 | `NonEmptyHouseholdId` alias defined and applied to 7 task-input models | `grep -c "household_id: NonEmptyHouseholdId" src/robotina/queue/task_types.py` | `7` | PASS |
| 2 | Alias definition present | `grep -n "NonEmptyHouseholdId" src/robotina/queue/task_types.py` | Defined at line 51 with `min_length=1, pattern=r"\S"`; applied to IncomingMessageInput, RecipeResearchInput, RecipeResearchGatherInput, RecipeResearchInstructionsInput, RecipeResearchIngredientsInput, RecipeResearchMetadataInput, RecipeLoadInput | PASS |
| 3 | `StartWorkflowTool` default `""` removed | `grep -c 'household_id: str = ""' src/robotina/agent/tools/start_workflow.py` | `0`; field is now `household_id: NonEmptyHouseholdId` (no default, line 105) | PASS |
| 4 | `start_workflow.py` silent `.get("household_id", "")` fallback removed | `grep -c 'shared_context.get("household_id"' src/robotina/agent/tools/start_workflow.py` | `0`; bracket form `shared_context["household_id"]` at line 127 | PASS |
| 5 | Gateway entrypoint `sys.exit(1)` on empty/missing `HOUSEHOLD_ID` | `grep -n 'sys.exit' src/robotina/gateway/__init__.py` | line 46 — guarded by `if not household_id:` after `.strip()`, with clear stderr message naming the env var | PASS |
| 6 | Per-message handler uses bracket-form `os.environ["HOUSEHOLD_ID"]` | `grep -n 'os.environ\["HOUSEHOLD_ID"\]' src/robotina/gateway/handler.py` | line 50 — `household_id = os.environ["HOUSEHOLD_ID"]` | PASS |
| 7 | Stale `HOUSEHOLD_ID` reference removed from `gateway/send.py` | `grep -i HOUSEHOLD_ID src/robotina/gateway/send.py` | `0` matches | PASS |
| 8 | `.env.example` documents `HOUSEHOLD_ID=` with required-marker | `grep -E "^HOUSEHOLD_ID=" .env.example` | line 20 — `HOUSEHOLD_ID=replace-with-your-household-uuid` (preceded by comment block citing boot guard + Pydantic validator, lines 18–19) | PASS |
| 9 | PROJECT.md Key Decisions row mentions `sys.exit(1)` pattern | `grep -n "sys.exit" .planning/PROJECT.md` | line 66 — Key Decisions row "household_id is required and validated end-to-end (Phase 16)" cites `sys.exit(1)` and four-layer defence | PASS |
| 10 | Unit suite green (133 passed) | `uv run pytest tests/unit -x -q` | `133 passed in 2.17s` | PASS |
| 11 | `queue_workflow(household_id="")` raises `ValueError` before any DB write | `uv run pytest tests/test_workflow_runner.py::test_queue_workflow_rejects_empty_household_id -x -q` plus full `tests/test_workflow_runner.py` excluding the DB-bound migration test → `25 passed, 1 deselected`. Source: `workflow_runner.py:136–142` raises `ValueError` on empty/whitespace before any DB code path. | PASS |

**Score:** 11 / 11

---

## Behavioral Spot-Checks

| Behavior | Method | Result | Status |
|----------|--------|--------|--------|
| `RecipeResearchInput(household_id="")` raises `ValidationError` | `uv run python -c ...` import + construct | rejected | PASS |
| `RecipeResearchInput(household_id="   ")` raises `ValidationError` (whitespace) | same | rejected | PASS |
| `RecipeResearchInput(household_id="test")` succeeds | same | `household_id=test` | PASS |
| `StartWorkflowTool(household_id="")` raises | construct → `ValidationError` | rejected | PASS |
| `StartWorkflowTool()` (no kwarg) raises | construct → `ValidationError` (required field, no default) | rejected | PASS |
| `HouseholdManagerApiTool(household_id="")` raises | construct → `ValidationError` | rejected | PASS |

All six runtime behaviors match the four-layer defence promised by the phase goal.

---

## Data-Flow Trace

| Layer | Artifact | Wiring Evidence | Status |
|-------|----------|-----------------|--------|
| Layer 1 — Boot guard | `gateway/__init__.py::main` | `os.environ.get("HOUSEHOLD_ID", "").strip()` + `sys.exit(1)` (lines 38–46) before `ApplicationBuilder` | WIRED |
| Layer 2 — Handler bracket read | `gateway/handler.py::handle_message` | `household_id = os.environ["HOUSEHOLD_ID"]` (line 50) flows into `Conversation.household_id` (line 63) and `IncomingMessageInput.household_id` (line 119) | WIRED |
| Layer 3 — Pydantic alias | `queue/task_types.py::NonEmptyHouseholdId` | Imported by `start_workflow.py` and `household_manager_api.py`; applied to 7 task-input models | WIRED |
| Layer 4 — Tool constructors | `StartWorkflowTool`, `HouseholdManagerApiTool` | Both declare `household_id: NonEmptyHouseholdId` with no default | WIRED |
| Layer 5 — Queue guard | `workflow_runner.queue_workflow` | Raises `ValueError` if `not household_id or not household_id.strip()` (lines 136–142) before DB write; called by `StartWorkflowTool._run` (line 136) | WIRED |

The full data flow `HOUSEHOLD_ID env → boot guard → handler bracket read → Conversation + IncomingMessageInput → Pydantic alias → tool constructors → queue_workflow guard` is verifiably intact in the codebase.

---

## findings

- `tests/test_workflow_runner.py::test_migration_0005_upgrades_and_downgrades` failed in my sandbox because Postgres on `localhost:5432` is not running. This is an environment artifact, not a phase regression — the test is DB-dependent and pre-exists Phase 16. All 25 in-process tests in that file pass. Not a gap.
- `gateway/__init__.py:38` deliberately uses `os.environ.get("HOUSEHOLD_ID", "").strip()` (not bracket form) because the entrypoint owns the boot-guard pattern: it must detect empty cleanly and call `sys.exit(1)` with a curated stderr message rather than surface a raw `KeyError`. This matches `CONTEXT.md` decisions and `SUMMARY.md` rationale; flagging here only because the bracket-form pattern (must-have #6) applies to the *per-message handler*, not the boot path. No inconsistency.
- Phase 16 added defensive guarantees at four distinct layers (boot, Pydantic, tool constructor, queue). The redundancy is intentional (defence in depth, called out in PROJECT.md row); not a smell.

---

## human_verification

Per `16-VALIDATION.md` "Manual-Only Verifications", these required a real terminal / DB session and were completed manually on 2026-05-16:

1. **Misconfigured deploy fails loudly with the expected error (REQ-HID-5 operator UX).** ✅ PASS
   - Tested three variants via `uv run gateway`: `unset HOUSEHOLD_ID`, `HOUSEHOLD_ID=""`, `HOUSEHOLD_ID="   "`.
   - All three exit with code `1`. stderr message names `HOUSEHOLD_ID`, points to `.env.example`, and process exits before `ApplicationBuilder` is called (no Telegram polling started).
   - Verified on 2026-05-16.

2. **Existing DB rows with `household_id=""` remain untouched (no migration written).** ✅ PASS
   - `migrations/versions/` ends at `0005_dashboard_columns.py` — no Phase 16 migration was added.
   - `psql ... SELECT count(*) FROM workflow_runs WHERE household_id=''` → `20` (out of 25 total). Pre-Phase-16 rows preserved.
   - Negative test: `queue_workflow(workflow_type="add-recipe", shared_context={}, household_id="", queue=None, session=None)` raised `ValueError` before any DB write; post-attempt count remained `20` (no new empty row created).
   - Verified on 2026-05-16.

---

## Verification Complete

**Status: passed**

All 11 must-haves are green and both manual UAT items have been executed. The phase goal — stopping empty-string `household_id` from silently propagating through the gateway, task-input models, tool constructors, and workflow runner — is observably achieved in the codebase via the four-layer defence (boot guard, Pydantic alias, tool constructor validation, queue_workflow guard). 133 unit tests pass; behavioral spot-checks and manual UAT confirm runtime rejection at every layer with readable operator UX.

## VERIFICATION COMPLETE

**Final Status: passed**
