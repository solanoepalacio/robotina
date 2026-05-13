---
phase: 10-langchain-1-x-agent-api-migration
plan: 02
subsystem: agent-infrastructure
tags: [langchain, langchain-agents, langgraph, create_agent, create_react_agent, migration, return_direct, strict-args]

# Dependency graph
requires:
  - phase: 10-langchain-1-x-agent-api-migration
    provides: "Plan 01: AGENT-12 requirement (unchecked / In Progress) added to REQUIREMENTS.md; AGENT-11 marked superseded; renamed source-grep lock test `test_create_agent_used_not_agent_executor` in tests/unit/test_llm_backend.py, intentionally RED against the unmigrated source so the wave-2 GREEN flip is verifiable end-to-end"
provides:
  - "All three LLMBackend adapters (Ollama, Anthropic, OpenAI) in src/robotina/llm/__init__.py now call langchain.agents.create_agent via the self-recursion-guard alias `_create_agent`; `system_prompt=` keyword replaces `prompt=`"
  - "Plan 01's renamed source-grep lock test passes — closes the wave 1 → wave 2 RED→GREEN handoff"
  - "Four real-agent parity test files (test_llm_backend.py, test_queue_tool.py, test_start_workflow_tool.py, test_household_manager_api_tool.py) construct agents via the new factory"
  - "Two short-circuit parity tests renamed to test_queue_tool_short_circuits_create_agent / test_start_workflow_tool_short_circuits_create_agent; both green — confirms `return_direct=True` short-circuit semantics survive the migration"
  - "test_extra_field_in_agent_loop_yields_tool_error_message (household_manager_api) green under the new factory — strict-args → ToolMessage(status='error') parity preserved"
  - "Seven doc-only files swept: src/robotina/queue/jobs.py, src/robotina/queue/workflow_runner.py, src/robotina/agent/tools/queue.py, src/robotina/agent/tools/start_workflow.py, tests/test_workflow_runner.py, experiments/recipe_research.py, experiments/recipe_load.py"
  - "No remaining USAGE of the old factory anywhere under src/, tests/, or experiments/ (the only remaining literal mentions of `create_react_agent` / `langgraph.prebuilt` are inside the lock test's load-bearing forbidden-strings assertions)"
affects: [10-03-PLAN, AGENT-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Self-recursion guard alias: `from langchain.agents import create_agent as _create_agent` — needed because the LLMBackend.create_agent method has the same name as the factory function; aliasing prevents the method body from calling itself"
    - "Patch-target alignment: unittest.mock.patch targets follow the imported alias name (patch('robotina.llm._create_agent', ...)), not the upstream module path"
    - "Comment-sweep batching: pure-string doc-only edits across multiple files committed as a single sweep commit (no logic change) keeps the wave history clean"

key-files:
  created: []
  modified:
    - src/robotina/llm/__init__.py
    - tests/unit/test_llm_backend.py
    - tests/unit/test_queue_tool.py
    - tests/unit/test_start_workflow_tool.py
    - tests/unit/test_household_manager_api_tool.py
    - src/robotina/queue/jobs.py
    - src/robotina/queue/workflow_runner.py
    - src/robotina/agent/tools/queue.py
    - src/robotina/agent/tools/start_workflow.py
    - tests/test_workflow_runner.py
    - experiments/recipe_research.py
    - experiments/recipe_load.py

key-decisions:
  - "LLMBackend.create_agent METHOD name preserved verbatim (public contract); only the internal factory call (now `_create_agent`) and the keyword argument (now `system_prompt=`) changed"
  - "Protocol docstring's Plan-verbatim phrase `the previous ``create_react_agent`` path` rephrased to `the previous prebuilt ReAct-agent path` so the renamed source-grep lock test (which forbids the substring `create_react_agent` anywhere in src/robotina/llm/__init__.py) stays green — Rule 1 fix"
  - "AC1 grep-zero gate (zero matches of `create_react_agent` / `langgraph.prebuilt` under src/ tests/ experiments/) interpreted by INTENT not literally: the lock test in tests/unit/test_llm_backend.py necessarily contains those tokens as the forbidden-strings argument to its assertions; removing them would defeat the lock. Five remaining matches are all inside that lock test. The intent (no remaining USAGE outside the lock test) is verified by `grep ... | grep -v test_llm_backend.py | wc -l == 0`"
  - "Test-pollution from tests/test_pyproject.py::test_experiment_mains_importable (importing experiments/* runs `load_dotenv()` at module top, leaking AGENT_OVERRIDES_FILEPATH into agents_registry tests) is pre-existing — fails identically on Plan 10-01 final commit daf2f7b — and out of scope for Plan 10-02 (SCOPE BOUNDARY). Documented for a future quick-fix"

patterns-established:
  - "Self-recursion guard alias pattern for factory imports whose name collides with a method name"
  - "Lock-test verbatim mention exemption: when a source-grep lock test asserts that a string does not appear in source, the test file itself necessarily contains that string in its assertion args/docstring. Such mentions are load-bearing and do not count as `usage` for AC purposes"

requirements-completed: []  # AGENT-12 added in Plan 01, advanced toward Complete here; Plan 03 flips the requirements checkbox + traceability row to checked / Complete after manual end-to-end Telegram verification

# Metrics
duration: 7min
completed: 2026-05-13
---

# Phase 10 Plan 02: LLMBackend Adapter Migration to langchain.agents.create_agent Summary

**Migrated all three LLMBackend adapters (Ollama, Anthropic, OpenAI) plus four real-agent parity test files from `langgraph.prebuilt.create_react_agent` to `langchain.agents.create_agent` using a self-recursion-guard alias; lock test from Plan 01 transitions RED→GREEN; `return_direct` short-circuit and strict-args→ToolMessage(status='error') parity preserved under the new factory.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-13T01:48:32Z
- **Completed:** 2026-05-13T01:56:21Z
- **Tasks:** 3 of 3
- **Files modified:** 12

## Accomplishments

- **Source migrated** (1 file): `src/robotina/llm/__init__.py` now imports `from langchain.agents import create_agent as _create_agent` (alias required because the method has the same name). All three adapter `create_agent` methods (OllamaBackend, AnthropicBackend, OpenAIBackend) call `_create_agent(model=..., tools=..., system_prompt=...)` — keyword renamed from `prompt=`. Three docstrings rewritten: `_RetryingChatOllama`, `LLMBackend.create_agent` Protocol, and the three adapter method docstrings (via the Protocol docstring).
- **Lock test now GREEN.** `tests/unit/test_llm_backend.py::test_create_agent_used_not_agent_executor` was intentionally RED at the end of Plan 01 (proving the lock was real). It now passes — the wave 1 → wave 2 RED→GREEN handoff is the explicit success signal for this plan.
- **Four real-agent parity test files migrated:**
  - `tests/unit/test_llm_backend.py` — three `patch("robotina.llm.create_react_agent", ...)` targets at lines 24/44/67 updated to `patch("robotina.llm._create_agent", ...)`; three per-adapter test docstrings now read "AGENT-02 / AGENT-12: ... creates a langchain.agents.create_agent runnable".
  - `tests/unit/test_queue_tool.py` — `test_queue_tool_short_circuits_create_react_agent` renamed to `test_queue_tool_short_circuits_create_agent`; module docstring + import + factory call swapped. The `FakeMessagesListChatModel.bind_tools` override stays as-is (Pattern B in 10-PATTERNS.md — the new factory calls `model.bind_tools(...)` identically).
  - `tests/unit/test_start_workflow_tool.py` — same rename pattern as queue tool.
  - `tests/unit/test_household_manager_api_tool.py` — test name kept (`test_extra_field_in_agent_loop_yields_tool_error_message` is named for behavior, not factory); import + factory call swapped; test docstring + bind_tools comment updated.
- **`return_direct=True` short-circuit parity preserved:** both renamed parity tests (`test_queue_tool_short_circuits_create_agent`, `test_start_workflow_tool_short_circuits_create_agent`) drive their respective terminal tools through a real `langchain.agents.create_agent` graph with a stub model that always emits a tool call. Both assert the model is invoked exactly once — confirming the new factory terminates after the terminal tool runs, same as the legacy prebuilt path.
- **Strict-args parity preserved:** `test_extra_field_in_agent_loop_yields_tool_error_message` drives a tool call carrying an extra field through the new factory and confirms it produces `ToolMessage(status='error')` (not `TypeError`) — the exact failure mode that motivated Phase 7.1 strict-args, still surfaced cleanly under the new factory.
- **Seven doc-only files swept** (no functional change): docstring / comment references to `create_react_agent` updated to `langchain.agents.create_agent` in `src/robotina/queue/jobs.py`, `src/robotina/queue/workflow_runner.py`, `src/robotina/agent/tools/queue.py` (full module-docstring rewrite), `src/robotina/agent/tools/start_workflow.py` (full module-docstring rewrite), `tests/test_workflow_runner.py` (lines 271 + 336), `experiments/recipe_research.py` (line 106), `experiments/recipe_load.py` (line 151).
- **Grep-zero intent satisfied:** `grep -rn "create_react_agent\|langgraph.prebuilt" src/ tests/ experiments/ | grep -v "tests/unit/test_llm_backend.py" | wc -l` returns **0**. The five remaining matches are all inside the lock test's own assertion strings — load-bearing and intentional.
- **Full migration-relevant test suite green:**
  - `uv run pytest tests/unit/test_llm_backend.py tests/unit/test_queue_tool.py tests/unit/test_start_workflow_tool.py tests/unit/test_household_manager_api_tool.py -q` → **32 passed**
  - `uv run pytest tests/test_workflow_runner.py -q` → **15 passed**
  - `uv run pytest tests/unit/ -q -m "not integration"` → **85 passed**
  - `uv run pytest -q -m "not integration" --deselect tests/test_pyproject.py::test_experiment_mains_importable` → **148 passed, 15 deselected**

## Task Commits

Each task was committed atomically on branch `use-new-agent-version`:

1. **Task 2.1: Migrate the three LLMBackend adapters and update per-adapter test patch targets** — `ecdfa02` (`feat`)
2. **Task 2.2: Migrate the three real-agent parity test files (queue, start_workflow, household_manager_api)** — `56be11e` (`test`)
3. **Task 2.3: Comment/docstring sweep across the 7 doc-only files and verify the full test suite** — `c235ed6` (`docs`)

**Plan metadata:** to be added in the final docs commit below (this SUMMARY.md + STATE.md + ROADMAP.md).

## Files Created/Modified

- `src/robotina/llm/__init__.py` — import migrated to `from langchain.agents import create_agent as _create_agent`; three adapter call sites swapped to `_create_agent(..., system_prompt=...)`; `_RetryingChatOllama` and `LLMBackend.create_agent` docstrings rewritten.
- `tests/unit/test_llm_backend.py` — three `patch("robotina.llm.create_react_agent", ...)` targets updated to `patch("robotina.llm._create_agent", ...)`; three per-adapter test docstrings updated.
- `tests/unit/test_queue_tool.py` — module docstring updated; `test_queue_tool_short_circuits_create_react_agent` renamed to `test_queue_tool_short_circuits_create_agent`; factory import + call swapped.
- `tests/unit/test_start_workflow_tool.py` — same shape as queue tool: module docstring + test rename + factory swap.
- `tests/unit/test_household_manager_api_tool.py` — test docstring + bind_tools comment + factory import/call updated (test name kept).
- `src/robotina/queue/jobs.py` — `run_task` return-value docstring updated.
- `src/robotina/queue/workflow_runner.py` — `_extract_task_output` docstring updated.
- `src/robotina/agent/tools/queue.py` — module docstring fully rewritten to reference the LangChain 1.x factory.
- `src/robotina/agent/tools/start_workflow.py` — module docstring fully rewritten to reference the LangChain 1.x factory.
- `tests/test_workflow_runner.py` — two comment lines (271 + 336) updated.
- `experiments/recipe_research.py` — `extract_json_output` docstring "Pitfall 4" reference updated.
- `experiments/recipe_load.py` — `extract_json_output` docstring "Pitfall 4" reference updated.

## Decisions Made

- **Preserve the public `LLMBackend.create_agent` method signature verbatim.** Only the internal factory call (now `_create_agent`) and the keyword argument (now `system_prompt=`) change. All call sites in `agents.py`, `jobs.py`, and the experiments continue to call `backend.create_agent(system_prompt=..., tools=...)` unchanged.
- **Self-recursion guard alias is mandatory.** Without `as _create_agent`, the import name and the method name collide; calling `create_agent(...)` inside `OllamaBackend.create_agent` would resolve to the method itself, recursing infinitely. The alias is load-bearing — every adapter implementation and every test patch target depends on it.
- **Patch targets follow the alias, not the upstream module path.** Tests patch `robotina.llm._create_agent` (the name as imported into the module namespace) — patching `langchain.agents.create_agent` would not intercept the call because Python resolves the name at the point of import.
- **Lock-test exemption from grep-zero gate.** AC1 of Plan 02 prescribes zero matches of `create_react_agent` / `langgraph.prebuilt` under src/ tests/ experiments/. This conflicts with the renamed source-grep lock test (`test_create_agent_used_not_agent_executor`), which necessarily contains those exact tokens as the forbidden-strings argument to its `assert "create_react_agent" not in source` and `assert "from langgraph.prebuilt" not in source` clauses. The five remaining matches are all inside that lock test. The AC1 intent (no remaining USAGE outside the lock test) is verified.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Rephrased the Protocol docstring to avoid the literal token `create_react_agent`**

- **Found during:** Task 2.1 (after applying Edit 1.3 verbatim from the plan)
- **Issue:** The plan's verbatim text for the new `LLMBackend.create_agent` Protocol docstring contains the phrase `the previous ``create_react_agent`` path`. After Task 2.1's edits, the renamed source-grep lock test (`test_create_agent_used_not_agent_executor`) reads the entire `src/robotina/llm/__init__.py` source and asserts `"create_react_agent" not in source`. With the verbatim docstring, that assertion failed at line 120: `AssertionError: robotina.llm must not reference the deprecated create_react_agent`. The fail was caused by the literal substring inside the docstring text. This is a direct contradiction between two specified outcomes in the plan: the verbatim docstring text and the lock test's success criterion.
- **Fix:** Rephrased the docstring to `the previous prebuilt ReAct-agent path` — same semantic content (the contract is unchanged from the previous prebuilt path), no forbidden literal token.
- **Files modified:** `src/robotina/llm/__init__.py`
- **Verification:** Re-ran `uv run pytest tests/unit/test_llm_backend.py -q` → 6 passed (including the lock test).
- **Committed in:** `ecdfa02` (Task 2.1 commit)

**2. [Rule 3 - Blocking] Reinterpreted AC1 grep-zero gate as intent-based, not literal**

- **Found during:** Task 2.3 (final verification)
- **Issue:** Plan 02 AC1 reads `grep -rn "create_react_agent\|langgraph.prebuilt" src/ tests/ experiments/ 2>/dev/null | wc -l` must output `0`. After all doc-sweep edits, the grep returned 5 matches — every match inside `tests/unit/test_llm_backend.py` (lines 108, 120, 121, 123, 124), and every match is part of the lock test's own assertion strings or docstring. The lock test is designed to assert that those substrings do NOT appear in src/robotina/llm/__init__.py — the lock test file itself necessarily contains them. Literal AC1 is unachievable without removing the lock-test assertions, which would defeat the lock.
- **Fix:** Interpreted AC1 by intent: no remaining USAGE of the old factory anywhere outside the lock test. Verified with `grep -rn "create_react_agent\|langgraph.prebuilt" src/ tests/ experiments/ | grep -v "tests/unit/test_llm_backend.py" | wc -l` → 0.
- **Files modified:** None (interpretation, not code change)
- **Verification:** see above grep + full migration-relevant test suite green.
- **Committed in:** `c235ed6` (Task 2.3 commit, documented in commit body)

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug, 1 Rule 3 blocking-AC reinterpretation)
**Impact on plan:** Both auto-fixes resolved contradictions within the plan itself. No scope creep. No semantic drift — the Protocol docstring rephrase preserved meaning, and the AC1 reinterpretation preserved the success criterion's intent.

## Issues Encountered

- **Pre-existing test pollution from `tests/test_pyproject.py::test_experiment_mains_importable`.** This test imports `experiments.recipe_research` and `experiments.recipe_load`. Both experiment modules call `load_dotenv()` at module-top, which loads `.env` and exports `AGENT_OVERRIDES_FILEPATH=overrides/openai.json` into `os.environ` without cleanup. Subsequent runs of `tests/unit/test_agents_registry.py` then see the override and 9 tests fail with `api_key_env == "API_TOKEN_OPENAI"` instead of the registry default (e.g., `RECIPE_LOAD_API_TOKEN`).
  - **Reproduced on Plan 10-01 final commit `daf2f7b`** with the same 9 failures — confirming the issue is pre-existing and orthogonal to Plan 10-02.
  - **Scope:** Out of scope (SCOPE BOUNDARY in execute-plan.md). The Plan 02 comment-sweep edits to `experiments/recipe_research.py:106` and `experiments/recipe_load.py:151` are pure string changes to docstring lines; they do not touch the module-top `load_dotenv()` calls.
  - **Suggested follow-up (quick task):** Move `load_dotenv()` inside `main()` in both experiment modules so importing the module does not mutate `os.environ`. Or have `test_experiment_mains_importable` save/restore the env around `importlib.import_module`.
  - **Today's verification approach:** Ran `uv run pytest -q -m "not integration" --deselect tests/test_pyproject.py::test_experiment_mains_importable` → **148 passed** (zero failures attributable to Plan 10-02).

- **Integration tests not run** (Postgres + Redis containers not up locally). All `@pytest.mark.integration` tests are deselected; they do not exercise the migrated factory path (they cover gateway / RQ / DB persistence). Plan 03's manual end-to-end Telegram verification is the gate that validates the migration against live infra.

## User Setup Required

None — this plan modified source files, test files, and docstrings only. No env vars, no runtime config, no external services. Plan 03 will require user-driven Telegram verification before AGENT-12 is flipped to checked / Complete.

## Next Phase Readiness

- **Plan 10-03 is unblocked** and is now the next plan to run. Its job is to:
  1. Update `CLAUDE.md`, `STATE.md`, `PROJECT.md`, and add a new decision record documenting AGENT-12 as the active contract.
  2. Drive the manual end-to-end Telegram verification that flips AGENT-12 to checked / Complete in `.planning/REQUIREMENTS.md` and the traceability table.
  3. (Optionally) record a follow-up quick task for the `load_dotenv()` test-pollution issue documented above.

- **Migration is functionally complete.** All three adapters use the new factory; all four parity test files build agents via `langchain.agents.create_agent`; the source-grep lock test is green; `return_direct` short-circuit and strict-args→ToolMessage parity are both verified under the new factory.

## TDD Gate Compliance

Not applicable — this plan is type `execute`, not type `tdd`. The plan-level test-first lock pattern (Plan 01 RED → Plan 02 GREEN) is documented in Plan 01's summary and was satisfied here: the locked test `test_create_agent_used_not_agent_executor` went from RED (against unmigrated source) to GREEN (against migrated source) inside Task 2.1's commit `ecdfa02`.

## Self-Check: PASSED

Files verified to exist on disk:
- `src/robotina/llm/__init__.py` — FOUND (migrated import + 3 adapter call sites)
- `tests/unit/test_llm_backend.py` — FOUND (3 patch targets migrated, 3 docstrings updated)
- `tests/unit/test_queue_tool.py` — FOUND (test renamed, factory swapped)
- `tests/unit/test_start_workflow_tool.py` — FOUND (test renamed, factory swapped)
- `tests/unit/test_household_manager_api_tool.py` — FOUND (factory swapped)
- `src/robotina/queue/jobs.py` — FOUND (docstring updated)
- `src/robotina/queue/workflow_runner.py` — FOUND (docstring updated)
- `src/robotina/agent/tools/queue.py` — FOUND (module docstring rewritten)
- `src/robotina/agent/tools/start_workflow.py` — FOUND (module docstring rewritten)
- `tests/test_workflow_runner.py` — FOUND (two comments updated)
- `experiments/recipe_research.py` — FOUND (docstring updated)
- `experiments/recipe_load.py` — FOUND (docstring updated)
- `.planning/phases/10-langchain-1-x-agent-api-migration/10-02-SUMMARY.md` — FOUND (this file)

Commits verified to exist in git history:
- `ecdfa02` (Task 2.1) — FOUND
- `56be11e` (Task 2.2) — FOUND
- `c235ed6` (Task 2.3) — FOUND

Plan-level verification (from `<verification>` block of 10-02-PLAN.md):
1. **No remaining USAGE of `create_react_agent` / `langgraph.prebuilt` under src/, tests/, experiments/** — verified: `grep -rn "create_react_agent\|langgraph.prebuilt" src/ tests/ experiments/ | grep -v "tests/unit/test_llm_backend.py" | wc -l` returns **0**. (Five matches inside the lock test are load-bearing forbidden-strings assertions — see Rule 3 deviation in Deviations section.) ✓ (intent)
2. `uv run pytest tests/unit/test_llm_backend.py tests/unit/test_queue_tool.py tests/unit/test_start_workflow_tool.py tests/unit/test_household_manager_api_tool.py -q` → **32 passed** ✓
3. `uv run pytest -q -m "not integration" --deselect tests/test_pyproject.py::test_experiment_mains_importable` → **148 passed, 15 deselected** ✓ (the deselected test is a pre-existing env-pollution source, documented in Issues Encountered)
4. `src/robotina/llm/__init__.py` contains `from langchain.agents import create_agent as _create_agent` (1 occurrence) and three `return _create_agent(` call sites with `system_prompt=system_prompt` (3 occurrences each) — verified by grep. ✓
5. Two `..._short_circuits_create_agent` renamed parity tests pass — verifying success criterion 2 (return_direct semantics preserved). ✓

---
*Phase: 10-langchain-1-x-agent-api-migration*
*Plan: 02*
*Completed: 2026-05-13*
