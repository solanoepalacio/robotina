---
phase: 10-langchain-1-x-agent-api-migration
plan: 01
subsystem: agent-infrastructure
tags: [langchain, langchain-agents, langgraph, create_agent, create_react_agent, requirements, lock-test]

# Dependency graph
requires:
  - phase: 04-llm-module-and-agent-infrastructure
    provides: "AGENT-11 (create_react_agent from langgraph.prebuilt) — the contract this plan supersedes; tests/unit/test_llm_backend.py source-grep test"
provides:
  - "AGENT-12 requirement (unchecked) — all adapters must use langchain.agents.create_agent"
  - "AGENT-11 marked superseded by AGENT-12 in Phase 10"
  - "AGENT-12 traceability row mapped to Phase 10, status In Progress"
  - "v1 requirements coverage bumped 68 -> 69 total/mapped"
  - "Renamed source-grep test test_create_agent_used_not_agent_executor that locks the new import direction"
  - "Expected-failure gate: renamed test fails against unchanged source (proves the lock is real)"
affects: [10-02-PLAN, 10-03-PLAN, AGENT-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lock-test-first migration: invert the source-grep test BEFORE migrating the source so the migration direction is verifiable end-to-end (red at plan boundary, green after source change)"

key-files:
  created: []
  modified:
    - .planning/REQUIREMENTS.md
    - tests/unit/test_llm_backend.py

key-decisions:
  - "AGENT-12 starts unchecked and 'In Progress' in the traceability table; Plan 03 flips it to checked / Complete after manual end-to-end Telegram verification"
  - "AGENT-11 entry preserved verbatim with an inline '(superseded by AGENT-12 in Phase 10)' tag rather than deleted — keeps history of decisions readable"
  - "Per-adapter patch targets (patch('robotina.llm.create_react_agent', ...)) at lines 24/44/67 of test_llm_backend.py are intentionally NOT updated in this plan — Plan 02 owns them alongside the source change so the wave-1 boundary is clean (only the source-grep test changes here)"
  - "Lock-test EXPECTED-FAILURE state at the end of Plan 01 is the success signal, not a regression — Plan 02 resolves it by migrating src/robotina/llm/__init__.py"

patterns-established:
  - "Requirement supersession marker pattern: '*(superseded by REQ-XX in Phase N)*' suffix on the old requirement bullet — leaves the historical line intact while marking it as no-longer-current"
  - "Lock-test-first phase boundary: the test that proves the migration landed lives in wave 1 and is RED at the wave boundary; wave 2 turns it green via the source change"

requirements-completed: []  # AGENT-12 is added in this plan but stays unchecked; Plan 03 marks it complete after manual end-to-end verification

# Metrics
duration: 2min
completed: 2026-05-13
---

# Phase 10 Plan 01: AGENT-12 Requirement + Source-Grep Lock Test Summary

**AGENT-12 added to REQUIREMENTS.md (AGENT-11 marked superseded) and the source-grep test in tests/unit/test_llm_backend.py renamed + inverted to lock the langchain.agents.create_agent migration direction — establishes the contract and the lock-test that Plan 02's source change must satisfy.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-13T01:43:17Z
- **Completed:** 2026-05-13T01:44:59Z
- **Tasks:** 2 of 2
- **Files modified:** 2

## Accomplishments

- **Contract established:** AGENT-12 now exists as an active (unchecked) requirement under "### Agent Infrastructure" in `.planning/REQUIREMENTS.md`, with verbatim text from `10-RESEARCH.md` covering all three `LLMBackend` adapters (Ollama, Anthropic, OpenAI) and the four parity properties (`return_direct=True` short-circuit, message state shape, callback delivery, strict-args→ToolMessage(status='error') flow).
- **Supersession marker added** to AGENT-11's line so any reader sees the migration is in flight: `(superseded by AGENT-12 in Phase 10)`.
- **Traceability table row added:** `| AGENT-12 | Phase 10 | In Progress |` directly under the AGENT-11 row. Plan 03 will flip this to `Complete`.
- **Coverage summary updated:** `v1 requirements: 68 total` → `69 total`; `Mapped to phases: 68` → `69`. `Unmapped: 0 ✓` unchanged.
- **Lock-test in place:** `tests/unit/test_llm_backend.py::test_create_react_agent_used_not_agent_executor` renamed to `test_create_agent_used_not_agent_executor`. Its docstring now binds to AGENT-12. Its four assertions now:
  1. forbid `AgentExecutor` (unchanged from AGENT-11),
  2. require `from langchain.agents import create_agent` in source (new positive),
  3. forbid `create_react_agent` anywhere in source (new negative — inverted),
  4. forbid `from langgraph.prebuilt` anywhere in source (new negative).
- **Expected-failure gate verified:** Running the renamed test against the as-yet-unmigrated `src/robotina/llm/__init__.py` FAILS with `AssertionError: robotina.llm must import create_agent from langchain.agents`. The pytest run produced the required `AssertionError` and `FAILED` markers per the plan's acceptance criterion 4. **This failure is by design and is the success signal for Plan 01.** Plan 02 will resolve it by editing the source.

## Task Commits

Each task was committed atomically against the main working tree on branch `use-new-agent-version`:

1. **Task 1.1: Add AGENT-12 to REQUIREMENTS.md and mark AGENT-11 superseded** — `9acac81` (`docs`)
2. **Task 1.2: Rename source-grep test and invert assertions to lock the migration direction** — `a9673ee` (`test`)

**Plan metadata:** to be added in the final docs commit below (this SUMMARY.md + STATE.md + ROADMAP.md).

## Files Created/Modified

- `.planning/REQUIREMENTS.md` — AGENT-12 entry added under Agent Infrastructure, AGENT-11 supersession tag added inline, AGENT-12 traceability row added, coverage counts bumped 68→69.
- `tests/unit/test_llm_backend.py` — source-grep test renamed (`test_create_react_agent_used_not_agent_executor` → `test_create_agent_used_not_agent_executor`); docstring rewritten to bind to AGENT-12; assertion set inverted (positive `from langchain.agents import create_agent`, negative `create_react_agent` and `from langgraph.prebuilt`); `AgentExecutor` negative kept verbatim.

## Decisions Made

- **Lock test in EXPECTED FAILURE state — Plan 02 will resolve when source migration runs.** A failing assertion at the Plan 01 boundary is the success criterion, not a regression. This is the plan's design.
- **AGENT-11 line preserved with a supersession tag** rather than deleted — leaves decision history readable in the requirements doc.
- **AGENT-12 starts unchecked / "In Progress"** — Plan 03's manual end-to-end Telegram run is the gate that flips it to checked / Complete.
- **Per-adapter test patch targets left for Plan 02** — three `patch("robotina.llm.create_react_agent", ...)` calls at lines 24, 44, 67 are unchanged in this plan; Plan 02 will update them in lockstep with the source rename so the wave boundary stays clean (only the source-grep test moves in wave 1).

## Deviations from Plan

None — plan executed exactly as written. All four acceptance criteria for Task 1.1 and all four acceptance criteria for Task 1.2 (including the expected-failure gate AC4) pass.

The expected failure of `test_create_agent_used_not_agent_executor` against the unchanged `src/robotina/llm/__init__.py` is documented in the plan itself (lines 220 and 239 of `10-01-PLAN.md`) and is the explicit success signal for Plan 01 — not a deviation.

## Issues Encountered

None.

## User Setup Required

None — this plan only touches `.planning/REQUIREMENTS.md` and `tests/unit/test_llm_backend.py`. No env vars, no runtime config, no external services.

## Next Phase Readiness

- **Plan 10-02 is unblocked** and is now the next plan to run (Wave 2). Its job is to:
  1. Edit `src/robotina/llm/__init__.py` to replace `from langgraph.prebuilt import create_react_agent` with `from langchain.agents import create_agent`, rename the three adapter call sites, and preserve all four parity properties (return_direct short-circuit, message state shape, callback delivery, strict-args→ToolMessage flow).
  2. Update the three `patch("robotina.llm.create_react_agent", ...)` targets at lines 24/44/67 of `tests/unit/test_llm_backend.py` to the new symbol name in the same commit as the source change.
  3. Update the three remaining test files (`test_queue_tool.py`, `test_start_workflow_tool.py`, `test_household_manager_api_tool.py`) and sweep 7 comment-only references.
  4. Verify the renamed test from Plan 01 now PASSES (expected-failure → green is the wave-2 success gate).
- **Plan 10-03** (CLAUDE.md / STATE.md / PROJECT.md / new decision record + manual end-to-end Telegram verification) follows Plan 10-02 and is what flips AGENT-12 to checked / Complete in REQUIREMENTS.md and the traceability table.

## Self-Check: PASSED

Files verified to exist on disk:
- `.planning/REQUIREMENTS.md` — FOUND
- `tests/unit/test_llm_backend.py` — FOUND

Commits verified to exist in git history:
- `9acac81` (Task 1.1) — FOUND
- `a9673ee` (Task 1.2) — FOUND

Plan-level verification (from `<verification>` block of 10-01-PLAN.md):
1. `grep -c "AGENT-12" .planning/REQUIREMENTS.md` → **3** (≥3 required) ✓
2. `grep "v1 requirements: 69 total" .planning/REQUIREMENTS.md` → match ✓
3. `grep "^def test_create_agent_used_not_agent_executor" tests/unit/test_llm_backend.py` → match ✓
4. `uv run pytest tests/unit/test_llm_backend.py::test_create_agent_used_not_agent_executor --collect-only -q` → 1 test collected, exit 0 ✓
5. Renamed test FAILS when executed against unchanged source — `AssertionError: robotina.llm must import create_agent from langchain.agents` at `tests/unit/test_llm_backend.py:117` (expected; proves lock is real) ✓
6. No other tests in `test_llm_backend.py` modified — three `robotina.llm.create_react_agent` patch targets still present at lines 24/44/67 ✓

---
*Phase: 10-langchain-1-x-agent-api-migration*
*Plan: 01*
*Completed: 2026-05-13*
