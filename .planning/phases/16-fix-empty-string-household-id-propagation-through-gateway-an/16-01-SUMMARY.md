---
phase: 16-fix-empty-string-household-id-propagation-through-gateway-an
plan: 01
subsystem: testing
tags: [testing, validation, python, pydantic, conftest, wave-0, red-state]

# Dependency graph
requires:
  - phase: 15-recipe-artifact-accumulation-and-food-unit-validation
    provides: stable RecipeData / ReplyContext / task-input model surface that the new validation tests parametrize over
provides:
  - tests/conftest.py autouse `_set_household_id` fixture (HOUSEHOLD_ID=test-household for every test)
  - tests/unit/test_household_id_validation.py — 21 parametrized stubs (7 models × 3 cases) for REQ-HID-2
  - tests/unit/test_gateway_boot.py — 4 subprocess-isolated boot-guard stubs for REQ-HID-5
  - tests/unit/test_env_example.py — 3 file-content stubs for REQ-HID-6
affects: [16-02, 16-04, 16-05, 16-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave 0 RED-state stub pattern: failing tests committed before production source — failing IS the success signal"
    - "Root-level autouse fixture injects required env var so module-level bracket-form reads in production code don't break collection (Pitfall 6 mitigation from RESEARCH.md)"
    - "Subprocess isolation for testing entrypoints that sys.exit() — avoids killing the pytest runner"

key-files:
  created:
    - tests/unit/test_household_id_validation.py
    - tests/unit/test_gateway_boot.py
    - tests/unit/test_env_example.py
  modified:
    - tests/conftest.py

key-decisions:
  - "Wave 0 stubs commit in RED state — 19 failures (7 reject-empty + 7 reject-whitespace + 3 gateway exit-* + 2 env_example) IS the contract Wave 1 plans will satisfy"
  - "Whitespace rejection enforced at Pydantic layer (resolves RESEARCH Open Question 4): whitespace-only household_id must be rejected by Field(min_length=1, pattern=r'\\S') in plan 16-02, not only at the gateway entrypoint"
  - "Autouse fixture chosen over per-test setenv (RESEARCH Open Question 3 resolution): cleaner, survives future tests; the four gateway-boot subprocess tests deliberately bypass it via subprocess env= isolation"
  - "Gateway boot tests use subprocess isolation (RESEARCH Pattern 2 + Pitfall 1): main() will sys.exit(1) in plan 16-05; subprocess.run is the only safe way to capture returncode and stderr without killing pytest"

patterns-established:
  - "Wave-0-then-Wave-1 RED→GREEN gating: a phase's test scaffold lands first as failing assertions; downstream plans flip them to passing by changing production source. The wave boundary is `pytest --collect-only` succeeding, not `pytest` passing."
  - "Test-collection-safe required env vars: root conftest autouse fixture sets HOUSEHOLD_ID=test-household so bracket-form os.environ['HOUSEHOLD_ID'] reads landing in plans 16-03/16-05 don't break test collection. Negative tests (testing absence/empty behavior) explicitly delenv or use subprocess isolation."

requirements-completed: [REQ-HID-1]

# Metrics
duration: 2min
completed: 2026-05-15
---

# Phase 16 Plan 01: Wave 0 — Test Infrastructure Scaffold Summary

**Failing-test scaffold materialized: 28 new test IDs (21 Pydantic + 4 gateway-boot + 3 env_example) plus root autouse conftest fixture, all wired to fail predictably until plans 16-02/16-05/16-06 flip them green.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-15T18:41:08Z
- **Completed:** 2026-05-15T18:43:00Z (approx)
- **Tasks:** 2 / 2
- **Files modified:** 1 (tests/conftest.py)
- **Files created:** 3 (tests/unit/test_household_id_validation.py, tests/unit/test_gateway_boot.py, tests/unit/test_env_example.py)

## Accomplishments

- Root conftest now injects `HOUSEHOLD_ID=test-household` autouse for every collected test, neutralizing the test-collection time bomb that the Wave 1 bracket-form reads would otherwise plant (Pitfall 6).
- 21 parametrized Pydantic-model tests encode the REQ-HID-2 contract across all 7 task-input models — empty and whitespace cases RED, valid cases GREEN.
- 4 gateway-boot tests encode the REQ-HID-5 contract: three subprocess tests (missing/empty/whitespace HOUSEHOLD_ID → non-zero exit + stderr mentions the var) and one in-process happy-path test (valid HOUSEHOLD_ID + monkeypatched ApplicationBuilder must not raise SystemExit).
- 3 `.env.example` tests encode the REQ-HID-6 contract: file exists, contains `HOUSEHOLD_ID=` line, has "required" in the comment block directly above it.
- Full repo collection still succeeds: 264 tests collected vs 236 pre-Wave-0 baseline (+28 new, 0 regressions).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add autouse HOUSEHOLD_ID fixture to tests/conftest.py** — `fb6ab3c` (test)
2. **Task 2: Create test stubs — Pydantic non-empty validation + gateway boot + .env.example** — `43c11d1` (test)

**Plan metadata commit:** (to follow this SUMMARY)

## Files Created/Modified

### Modified

- `tests/conftest.py` — added `@pytest.fixture(autouse=True) def _set_household_id(monkeypatch)` that calls `monkeypatch.setenv("HOUSEHOLD_ID", "test-household")`. Placed after the existing import block and before the first non-autouse fixture so it runs before any fixture or test body. Pre-existing `db_session`, `redis_conn`, `make_update` fixtures preserved verbatim.

### Created

- `tests/unit/test_household_id_validation.py` — 21 parametrized tests over `[IncomingMessageInput, RecipeResearchInput, RecipeResearchGatherInput, RecipeResearchInstructionsInput, RecipeResearchIngredientsInput, RecipeResearchMetadataInput, RecipeLoadInput]`. Three cases per model: rejects `""` (RED), rejects `"   "` (RED), accepts `"hh-1"` (currently GREEN — regression guard for plan 16-02).
- `tests/unit/test_gateway_boot.py` — 4 tests. Subprocess helper `_run_gateway_main(env)` invokes `python -c "from robotina.gateway import main; main()"` with an env dict that copies PATH/PYTHONPATH/VIRTUAL_ENV but strips HOUSEHOLD_ID. Three subprocess tests assert non-zero exit + stderr mentions HOUSEHOLD_ID. One in-process test monkeypatches `gateway_pkg.ApplicationBuilder` to a tiny fake and asserts `main()` returns without `SystemExit`.
- `tests/unit/test_env_example.py` — 3 tests. Resolves repo root via `Path(__file__).resolve().parents[2]`. Tests: file exists (GREEN today), `^HOUSEHOLD_ID=` line present (RED), "required" mention in the 5 lines above (RED).

## RED-State Verification (the Wave 0 success signal)

```
$ uv run pytest tests/unit/test_household_id_validation.py tests/unit/test_gateway_boot.py tests/unit/test_env_example.py -q
19 failed, 9 passed in 3.87s
```

Breakdown of the 19 failures (all expected; these encode the downstream contract):

| Failure | Count | Flipped GREEN by |
|---|---|---|
| `test_household_id_rejects_empty[<7 models>]` | 7 | Plan 16-02 — adds `Field(min_length=1)` |
| `test_household_id_rejects_whitespace[<7 models>]` | 7 | Plan 16-02 — adds `pattern=r"\S"` to the same `Field`/`Annotated` alias |
| `test_main_exits_on_missing_household_id` | 1 | Plan 16-05 — adds boot guard at top of `main()` |
| `test_main_exits_on_empty_household_id` | 1 | Plan 16-05 — same guard |
| `test_main_exits_on_whitespace_household_id` | 1 | Plan 16-05 — guard must `.strip()` before checking |
| `test_household_id_documented` | 1 | Plan 16-06 — adds `HOUSEHOLD_ID=` line to `.env.example` |
| `test_household_id_marked_required` | 1 | Plan 16-06 — adds "required" comment block above the line |

The 9 passing tests are the regression guards: 7 `test_household_id_accepts_valid` (constructions with `"hh-1"` must keep working through Wave 1), `test_env_example_exists` (file is already on disk), and `test_main_boots_with_valid_household_id` (currently passes because there's no guard; will continue passing after plan 16-05 adds one because it provides a valid HOUSEHOLD_ID).

## Verification Commands Run

```
$ uv run pytest tests/ --collect-only -q | tail -5
236 tests collected  (Task 1, before Task 2 created the 28 new test IDs)

$ uv run pytest tests/unit/test_household_id_validation.py tests/unit/test_gateway_boot.py tests/unit/test_env_example.py --collect-only -q | tail -10
28 tests collected in 0.01s

$ uv run pytest --collect-only -q | tail -3
264 tests collected in 0.25s   (full repo, post-Wave-0 — +28 vs baseline, 0 regressions)
```

All Task 1 and Task 2 acceptance criteria pass; full RED-state verification above.

## Downstream Plan → Test Mapping

| Plan | Wave | Flips GREEN |
|---|---|---|
| 16-02 (Pydantic Field constraints) | 1 | 14 of 19 failures (all `test_household_id_rejects_empty[*]` + `test_household_id_rejects_whitespace[*]`) |
| 16-03 (tool-construction validators — `HouseholdManagerApiTool`, `StartWorkflowTool`) | 1 | 0 of these 19 (its own stubs live in `tests/unit/test_household_manager_api_tool.py` + `tests/unit/test_start_workflow_tool.py`, owned by 16-03; this plan only scaffolded the Wave 0 files VALIDATION.md flagged as MISSING) |
| 16-04 (`queue_workflow` guard) | 1 | 0 of these 19 (its own stub lives in `tests/test_workflow_runner.py`, owned by 16-04) |
| 16-05 (gateway boot guard) | 1 | 3 of 19 (`test_main_exits_on_*`) |
| 16-06 (`.env.example` + docstring sweep + PROJECT.md decision) | 1 | 2 of 19 (`test_household_id_documented`, `test_household_id_marked_required`) |

VALIDATION.md row 16-01-01 and 16-01-02 are now both ✅ ready (Wave 0 stubs collectible).

## Deviations from Plan

### Auto-fixed Issues

None — both tasks executed exactly as written. Plan-verbatim files; no Rule 1/2/3 fixes required.

### Notes on Scope-Adjacent Items NOT Done (correctly out of scope for 16-01)

VALIDATION.md "Wave 0 Requirements" also lists four additional stub additions to **existing** test files:

- `tests/unit/test_household_manager_api_tool.py` — `test_empty_household_id_rejected` (REQ-HID-3)
- `tests/unit/test_start_workflow_tool.py` — `test_empty_household_id_rejected` + `test_run_rejects_empty_in_context` (REQ-HID-3)
- `tests/test_workflow_runner.py` — `test_queue_workflow_rejects_empty_household_id` (REQ-HID-4)
- `tests/integration/test_gateway_startup.py` — gateway entrypoint stub (REQ-HID-5)
- `tests/unit/test_gateway_handler.py` — `test_handler_uses_bracket_form` (REQ-HID-5)

The 16-01 PLAN explicitly scoped Task 2 to **three** new files: `test_household_id_validation.py`, `test_gateway_boot.py`, `test_env_example.py`. The remaining stubs are owned by the **implementation plans themselves** (16-03 owns its tool stubs, 16-04 owns its workflow_runner stub, etc.) — this is consistent with how the downstream plans' VALIDATION rows reference `tests/unit/test_household_manager_api.py::test_empty_household_id_rejected` etc. (i.e. those plans add the test alongside the source change in a TDD-style commit pair). Not a deviation; the plan boundary is intentional.

If the downstream plans turn out NOT to also commit their test stubs Wave-0-first, the verifier can flag a Nyquist gap; for now the 16-01 contract delivered exactly what 16-01-PLAN.md scoped.

## Authentication Gates

None.

## Known Stubs

The three new test files are themselves stubs in the GSD sense — they assert behavior that has not yet been implemented (RED). They are NOT placeholder/no-data-source stubs in the verifier sense; they encode contracts, and they will be flipped to GREEN by named downstream plans (table above). This is intentional and is the Wave 0 contract.

Threat Flags: none — these are test-only files, no new network/auth/file-access surface.

## Self-Check: PASSED

- `tests/conftest.py` modified — `grep -c "_set_household_id" tests/conftest.py` = 1 ✓
- `tests/unit/test_household_id_validation.py` created — exists ✓
- `tests/unit/test_gateway_boot.py` created — exists ✓
- `tests/unit/test_env_example.py` created — exists ✓
- Commit `fb6ab3c` — present in `git log --oneline` ✓
- Commit `43c11d1` — present in `git log --oneline` ✓
- `uv run pytest --collect-only` reports 264 tests (236 baseline + 28 new) ✓
- RED-state verified: 19 failed, 9 passed on the three new files ✓
