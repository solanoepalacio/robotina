---
phase: 10-langchain-1-x-agent-api-migration
verified: 2026-05-13T13:00:00Z
status: passed
score: 5/5 success criteria verified
overrides_applied: 0
---

# Phase 10: LangChain 1.x Agent API Migration — Verification Report

**Phase Goal:** Replace `langgraph.prebuilt.create_react_agent` with `langchain.agents.create_agent` across all three LLMBackend adapters (Ollama, Anthropic, OpenAI) with strict behavior parity. Prerequisite unlock for Phases 11 (response_format) and 12 (middleware).

**Verified:** 2026-05-13
**Status:** passed
**Re-verification:** No — initial verification (no prior VERIFICATION.md existed)
**Verification approach:** Goal-backward — start from ROADMAP.md Success Criteria, verify each against the actual codebase. SUMMARYs are read for context but every claim is re-checked.

---

## Goal Achievement

### Success Criteria (from ROADMAP.md Phase 10)

| #  | Success Criterion                                                                                                                                             | Status     | Evidence                                                                                                                                                                                                                                                                                                                                                                                                              |
| -- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1  | All 3 LLMBackend adapters call `langchain.agents.create_agent`; no `create_react_agent` import; AGENT-11/D-03 decision record updated.                        | VERIFIED   | `src/robotina/llm/__init__.py:32` — `from langchain.agents import create_agent as _create_agent  # AGENT-12`. Three adapter call sites at lines 220, 253, 286 each call `_create_agent(model=..., tools=..., system_prompt=...)`. Old import: `grep -c "from langgraph.prebuilt import create_react_agent" src/robotina/llm/__init__.py` = 0. New decision record `.planning/decisions/agent-12-migrate-to-create-agent.md` exists (94 lines, all 6 expected section headers present). STATE.md line 131 records AGENT-11/D-03 supersession. |
| 2  | `return_direct=True` short-circuit preserved — QueueTool/StartWorkflowTool terminate in one round; `_extract_task_output` tool_message branch still fires.    | VERIFIED   | `tests/unit/test_queue_tool.py::test_queue_tool_short_circuits_create_agent` exits 0 (drives real `langchain.agents.create_agent` with a CountingModel and asserts exactly 1 LLM call). `tests/unit/test_start_workflow_tool.py::test_start_workflow_tool_short_circuits_create_agent` exits 0 (same shape). `src/robotina/queue/workflow_runner.py:47-48` tool_message branch is unchanged: `if getattr(last, "type", None) == "tool": return {"tool_message": str(last.content)}`. `uv run pytest tests/test_workflow_runner.py -q` → 15 passed. |
| 3  | Four test files updated to use `create_agent`; `uv run pytest` green.                                                                                          | VERIFIED   | Each of the four migrated test files has zero `from langgraph.prebuilt` imports outside the lock test's load-bearing forbidden-string assertions, and a `from langchain.agents` import: test_queue_tool.py (1), test_start_workflow_tool.py (1), test_household_manager_api_tool.py (1), test_llm_backend.py (3 patch targets, see notes). `uv run pytest tests/unit/test_llm_backend.py tests/unit/test_queue_tool.py tests/unit/test_start_workflow_tool.py tests/unit/test_household_manager_api_tool.py -q` → **32 passed**. `uv run pytest tests/unit/ -q` → **85 passed**. `uv run pytest -q -m "not integration" --deselect tests/test_pyproject.py::test_experiment_mains_importable` → **148 passed, 15 deselected**. The remaining test-suite failures (DB/gateway integration tests + test_agents_registry pollution from `test_experiment_mains_importable`) are out of Phase 10 scope and documented in 10-02-SUMMARY.md. |
| 4  | End-to-end `add-recipe` workflow runs to completion on a real recipe query with no semantic regression.                                                       | VERIFIED   | Approved by user on 2026-05-13 (per 10-03-SUMMARY.md and the verification_context note). Not re-verifiable automatically — gated on live Telegram + LangWatch + worker logs. The user confirmed: full workflow (acknowledge-add-recipe → recipe-research sub-agents → recipe-load → send-notification) ran end-to-end, the user received the final Telegram confirmation, LangWatch traces appeared in the correct collection, and no `LangGraphDeprecatedSinceV10` warnings appeared in worker logs. Tangential pydantic optional-field fix (commit `19b3b9d`) was a pre-existing schema bug unblocked during the verification gate — explicitly out of Phase 10 scope per verification_context. |
| 5  | CLAUDE.md tech stack table updated — `langchain >=1.2`, `langchain-core >=1.2`, langgraph demoted; "What NOT to Use" lists `create_react_agent`; Alternatives Considered table polarity flipped. | VERIFIED   | CLAUDE.md:27 — LangChain row says `langchain>=1.2`, `langchain-core>=1.2` with "Agent orchestration via `langchain.agents.create_agent`". CLAUDE.md:29 — langgraph row says `>=1.0` and "Underlying graph engine for `create_agent` ... not the agent API surface anymore." CLAUDE.md:86 — Alternatives Considered row polarity inverted: `langchain.agents.create_agent` recommended, `create_react_agent` is the alternative. CLAUDE.md:97 — new "What NOT to Use" row for `langgraph.prebuilt.create_react_agent`. CLAUDE.md:134 — Confidence Notes row updated. CLAUDE.md:142 — Sources line rewritten ("`create_agent` lives in `langchain.agents` as of LangChain 1.x"); old "moved to langgraph.prebuilt" wording absent (grep=0). |

**Score:** 5/5 success criteria verified.

### Note on the `langchain-core` Entry in SC5

ROADMAP SC5 calls for `langchain-core >=1.2`. CLAUDE.md:27 ("LangChain" row) does include `langchain-core>=1.2` in its version cell, matching the success criterion. However, CLAUDE.md:28 (a separate dedicated `langchain-core` row) still reads `>=0.3`. This is a **WARNING-level inconsistency** but does not affect the SC verdict — the SC's literal requirement is satisfied by the LangChain row at line 27. The separate `langchain-core` row at line 28 was not in Plan 10-03's six edits and looks like a documentation drift that the plan did not target. Suggested follow-up (quick task): align line 28 with the new floor.

---

## Required Artifacts

| Artifact                                                          | Expected                                                                       | Status                  | Details                                                                                                                                                                                                                                          |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------ | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `src/robotina/llm/__init__.py`                                    | Import + 3 migrated adapter call sites                                         | VERIFIED                | line 32 import; lines 220/253/286 call `_create_agent(..., system_prompt=...)`. `grep -c '_create_agent' src/robotina/llm/__init__.py` = 4 (1 import alias + 3 call sites). `grep -c "system_prompt=system_prompt" src/robotina/llm/__init__.py` = 3. |
| `tests/unit/test_llm_backend.py`                                  | Renamed lock test + 3 migrated patch targets + 3 per-adapter test docstrings   | VERIFIED                | line 107 `def test_create_agent_used_not_agent_executor` present; old name absent (grep=0). 3 occurrences of `patch("robotina.llm._create_agent", ...)` at lines 24/44/67; 0 occurrences of `patch("robotina.llm.create_react_agent", ...)`. 3 per-adapter docstrings reference `AGENT-02 / AGENT-12 ... langchain.agents.create_agent`. |
| `tests/unit/test_queue_tool.py`                                   | Test renamed; import + factory call swapped                                    | VERIFIED                | line 77 `def test_queue_tool_short_circuits_create_agent` present; line 89 `from langchain.agents import create_agent`; line 122 `agent = create_agent(model=model, tools=[tool])`. Module docstring updated. `bind_tools(self, tools, **kwargs): return self` override preserved (line 107). |
| `tests/unit/test_start_workflow_tool.py`                          | Test renamed; import + factory call swapped                                    | VERIFIED                | line 116 `def test_start_workflow_tool_short_circuits_create_agent` present; line 123 `from langchain.agents import create_agent`; line 162 `agent = create_agent(model=model, tools=[tool])`. Module docstring updated.                              |
| `tests/unit/test_household_manager_api_tool.py`                   | Test name preserved (behavior-based); factory call swapped                     | VERIFIED                | line 229 `def test_extra_field_in_agent_loop_yields_tool_error_message` preserved; line 245 `from langchain.agents import create_agent`; line 280 `agent = create_agent(model=model, tools=[tool])`. bind_tools comment updated.                       |
| `.planning/decisions/agent-12-migrate-to-create-agent.md`         | New decision record mirroring `switch-to-simple-worker.md` layout              | VERIFIED                | 94 lines. All 6 expected section headers present: `# Decision: Migrate from`, `## Context`, `` ## What `create_react_agent` actually buys us ``, `## Why those benefits don't apply here`, `## Proposed change`, `## Files to change`, `## Risk`.            |
| `CLAUDE.md`                                                       | 6 edits (Core Technologies × 2, Alternatives Considered, What NOT to Use, Confidence Notes, Sources)  | VERIFIED                | All 6 edits land at expected line ranges. See SC5 evidence above.                                                                                                                                                                              |
| `.planning/STATE.md`                                              | Line 130/131 records AGENT-11/D-03 supersession                                | VERIFIED                | line 131 reads "AGENT-11/D-03 superseded in Phase 10 by AGENT-12 — all agents now use `langchain.agents.create_agent` ...". Old wording absent (grep=0).                                                                                              |
| `.planning/PROJECT.md`                                            | New Key Decisions row for AGENT-12                                             | VERIFIED                | line 65: `` | `create_agent` from `langchain.agents` is used for all agents | LangGraph deprecated `create_react_agent` ... | — Active | ``. Three-column alignment matches existing rows.                                                                              |
| `.planning/REQUIREMENTS.md`                                       | AGENT-12 added & marked Complete; AGENT-11 superseded; traceability updated; footer marker updated     | VERIFIED                | line 62 AGENT-11 has `*(superseded by AGENT-12 in Phase 10)*` tag. line 63 `- [x] **AGENT-12**: ...` (checked). line 174 traceability row reads `| AGENT-12 | Phase 10 | Complete |`. line 214 coverage updated to "v1 requirements: 69 total". line 220 footer reads "Last updated: 2026-05-12 after Phase 10 — added AGENT-12 (LangChain 1.x agent API migration), marked AGENT-11 superseded". |
| 7 doc-only files (jobs.py, workflow_runner.py, queue.py tool, start_workflow.py tool, test_workflow_runner.py, recipe_research.py experiment, recipe_load.py experiment) | Comment/docstring sweep to reference `langchain.agents.create_agent`           | VERIFIED                | Each file has ≥1 occurrence of `langchain.agents.create_agent`. `test_workflow_runner.py` has 2 (lines 271 and 336 both updated).                                                                                                                |

---

## Key Link Verification

| From                                                                                          | To                                              | Via                                                | Status   | Details                                                                                                                                                                                                                                                                                |
| --------------------------------------------------------------------------------------------- | ----------------------------------------------- | -------------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/robotina/llm/__init__.py:OllamaBackend.create_agent` (line 215)                          | `langchain.agents.create_agent`                 | `_create_agent(...)` call at line 220              | WIRED    | Method body calls `_create_agent(model=self._model, tools=tools or [], system_prompt=system_prompt)`. Self-recursion guard alias `_create_agent` resolves to the imported factory via line 32. Return value flows to caller (`run_task` → `agent.invoke(...)`).                          |
| `src/robotina/llm/__init__.py:AnthropicBackend.create_agent` (line 248)                       | `langchain.agents.create_agent`                 | `_create_agent(...)` call at line 253              | WIRED    | Identical pattern to Ollama.                                                                                                                                                                                                                                                          |
| `src/robotina/llm/__init__.py:OpenAIBackend.create_agent` (line 281)                          | `langchain.agents.create_agent`                 | `_create_agent(...)` call at line 286              | WIRED    | Identical pattern to Ollama.                                                                                                                                                                                                                                                          |
| `tests/unit/test_llm_backend.py` (3 sites: lines 24, 44, 67)                                  | `robotina.llm._create_agent`                    | `unittest.mock.patch` target                       | WIRED    | All three patch targets aligned with the source's imported alias name. Patching `langchain.agents.create_agent` would not intercept the call — Python resolves the imported name at module import time. Tests pass.                                                                  |
| `tests/unit/test_queue_tool.py::test_queue_tool_short_circuits_create_agent`                  | `langchain.agents.create_agent` (real graph)    | direct import + factory call at line 122           | WIRED    | Test passes; asserts exactly 1 LLM call, proving `return_direct=True` short-circuit semantics survive the migration.                                                                                                                                                                |
| `tests/unit/test_start_workflow_tool.py::test_start_workflow_tool_short_circuits_create_agent`| `langchain.agents.create_agent` (real graph)    | direct import + factory call at line 162           | WIRED    | Test passes; same shape as queue tool short-circuit test.                                                                                                                                                                                                                              |
| `tests/unit/test_household_manager_api_tool.py::test_extra_field_in_agent_loop_yields_tool_error_message` | `langchain.agents.create_agent` (real graph) | direct import + factory call at line 280       | WIRED    | Test passes; drives a bad tool call through the real factory and asserts the loop produces `ToolMessage(status='error')` rather than raising `TypeError` — strict-args parity preserved.                                                                                              |
| `src/robotina/queue/workflow_runner.py::_extract_task_output` (lines 47-48)                   | tool-message branch                             | `if getattr(last, "type", None) == "tool":`        | WIRED    | Branch unchanged from pre-migration baseline. Verified by `uv run pytest tests/test_workflow_runner.py -q` → 15 passed (including consumer-side tests for the return_direct tool-message path).                                                                                          |

---

## Data-Flow Trace (Level 4)

Not applicable in the conventional UI/dashboard sense (no rendered data). For this phase, the analogous trace is the factory output shape and the consumer code that reads it:

- **Factory output:** `langchain.agents.create_agent` returns a `CompiledStateGraph` whose `.invoke({"messages": [...]})` returns a dict with a `messages` key whose last element is either an `AIMessage` (normal terminal) or a `ToolMessage` (when a `return_direct=True` tool ran).
- **Consumer:** `_extract_task_output` (workflow_runner.py:29-95) reads `result["messages"]`, branches on `last.type == "tool"`, otherwise scans for the last `ai` message and parses JSON.
- **Verification:** End-to-end Telegram run on 2026-05-13 (SC4, user-approved) confirms real data flows correctly through the entire pipeline (Telegram → enqueue → research → load → notify → Telegram reply). Worker logs showed no `LangGraphDeprecatedSinceV10` warnings. LangWatch traces appeared with spans for each agent invocation.

Status: **FLOWING** — verified empirically by the user.

---

## Behavioral Spot-Checks

| Behavior                                                                                          | Command                                                                                                                                                                  | Result                  | Status   |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------- | -------- |
| Source-grep lock test passes (proves migration direction is locked)                               | `uv run pytest tests/unit/test_llm_backend.py::test_create_agent_used_not_agent_executor -x -q`                                                                          | 1 passed                | PASS     |
| Queue tool short-circuit parity                                                                    | `uv run pytest tests/unit/test_queue_tool.py::test_queue_tool_short_circuits_create_agent -x -q`                                                                          | 1 passed                | PASS     |
| Start-workflow tool short-circuit parity                                                           | `uv run pytest tests/unit/test_start_workflow_tool.py::test_start_workflow_tool_short_circuits_create_agent -x -q`                                                       | 1 passed                | PASS     |
| Strict-args → ToolMessage(status='error') parity                                                   | `uv run pytest tests/unit/test_household_manager_api_tool.py::test_extra_field_in_agent_loop_yields_tool_error_message -x -q`                                            | 1 passed                | PASS     |
| Full unit suite                                                                                    | `uv run pytest tests/unit/ -q`                                                                                                                                          | 85 passed                | PASS     |
| Workflow runner integration tests (consumer of factory output)                                     | `uv run pytest tests/test_workflow_runner.py -q`                                                                                                                          | 15 passed                | PASS     |
| Migration-relevant scoped suite (per Plan 10-02 documented policy)                                 | `uv run pytest -q -m "not integration" --deselect tests/test_pyproject.py::test_experiment_mains_importable`                                                              | 148 passed, 15 deselected | PASS     |
| Full pytest suite without scope filter                                                             | `uv run pytest -q`                                                                                                                                                       | 19 failed, 144 passed, 6 errors | SKIP (out of scope) |

**Note on full-suite failures:** The 19 failures and 6 errors are NOT attributable to Phase 10:
- `tests/test_db_models.py` (5 failures): all `@pytest.mark.integration` — require live Postgres
- `tests/test_gateway.py` (6 failures + 6 errors): all `@pytest.mark.integration` — require live Postgres
- `tests/unit/test_agents_registry.py` (9 failures): documented test-order pollution from `tests/test_pyproject.py::test_experiment_mains_importable` (load_dotenv at module-top leaks AGENT_OVERRIDES_FILEPATH). Reproduced by 10-02-SUMMARY.md on Plan 10-01 final commit `daf2f7b` — pre-existing, out of Phase 10 scope.

Running `test_agents_registry.py` in isolation: 17 passed (confirms pollution origin).

---

## Requirements Coverage

| Requirement | Source Plan | Description                                                                                                | Status     | Evidence                                                                                                                                                                                                                                                              |
| ----------- | ----------- | ---------------------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AGENT-12    | 10-01, 10-02, 10-03 | All agents use `create_agent` from `langchain.agents`; deprecated `create_react_agent` is no longer imported anywhere in `src/` or `tests/`; the three LLMBackend adapters call `langchain.agents.create_agent(model, tools, system_prompt)` with strict parity (return_direct short-circuit, message state shape, callback delivery, strict-args→ToolMessage(status='error')). | SATISFIED  | All adapters call `_create_agent` (= `langchain.agents.create_agent`) at the three call sites. `grep -rn "create_react_agent\|langgraph.prebuilt" src/ tests/ experiments/ \| grep -v test_llm_backend.py \| wc -l` = 0. Four parity tests pass (lock + 2 short-circuit + 1 strict-args). REQUIREMENTS.md:63 marked `[x]`; traceability row marks Complete. AGENT-11 marked superseded. |

No orphaned requirements — REQUIREMENTS.md Phase 10 mapping contains only AGENT-12, and that ID is claimed by Plans 10-01, 10-02, and 10-03.

---

## Anti-Patterns Found

A scan of files modified in Phase 10 produced no blockers:

| File                                       | Pattern                                                                                                          | Severity | Impact                                                                                                                                                                       |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/unit/test_llm_backend.py:108,120-124` | Literal mentions of `create_react_agent` and `from langgraph.prebuilt`                                            | Info     | These are load-bearing forbidden-string assertions inside the source-grep lock test `test_create_agent_used_not_agent_executor`. Removing them would defeat the lock. Documented as Lock-test Exemption Pattern in 10-02-SUMMARY.md. Not a stub. |
| `src/robotina/queue/workflow_runner.py:78-86` | Logger statement labeled `TEMP DIAGNOSTIC (remove once recipe-research-gather parse failure is understood)`     | Info     | Pre-existing diagnostic, unrelated to Phase 10. Out of scope; not introduced by this phase.                                                                                  |
| `CLAUDE.md:28`                              | `langchain-core` standalone row still reads `>=0.3` while the new LangChain row at line 27 says `>=1.2`           | Warning  | Inconsistency vs. SC5 spirit (`langchain-core >=1.2`). The literal SC5 wording is satisfied by line 27. Suggested quick-task follow-up to align line 28.                       |

No `TODO`, `FIXME`, placeholder, `return null`, `return []` or empty-handler stubs were found in the Phase 10 modified files.

---

## Acknowledged Deviations (Per Verification Context)

1. **LLMBackend Protocol docstring rephrasing** — The plan-verbatim phrase `the previous create_react_agent path` was rephrased to `the previous prebuilt ReAct-agent path` to avoid failing the renamed source-grep lock test. Documented in 10-02-SUMMARY.md "Deviations from Plan" Rule 1. Semantics preserved. Accepted.
2. **AC1 grep-zero gate interpreted by intent** — Five remaining matches of `create_react_agent` / `langgraph.prebuilt` exist inside `tests/unit/test_llm_backend.py` and are all load-bearing assertion strings in the source-grep lock test. The intent (no remaining USAGE outside the lock test) is verified by `grep ... | grep -v test_llm_backend.py | wc -l` = 0. Documented in 10-02-SUMMARY.md "Deviations from Plan" Rule 3. Accepted.
3. **Tangential pydantic optional-field fix (commit `19b3b9d`)** — A pre-existing pydantic schema bug surfaced during the Task 3.2 end-to-end checkpoint when an LLM omitted null-valued optional fields. Fixed inline as quick task `260512-pyd`. The fix is to `src/robotina/queue/task_types.py`, not any Phase 10 file. Explicitly out of Phase 10 scope per verification_context. Acknowledged for audit-trail clarity only.
4. **Pre-existing test_pyproject.py env-pollution** — `tests/test_pyproject.py::test_experiment_mains_importable` runs `load_dotenv()` at module-top of experiment modules, leaking `AGENT_OVERRIDES_FILEPATH` and breaking `test_agents_registry.py` when run in suite-order. Reproduced on Plan 10-01 final commit `daf2f7b` before any Phase 10 source change. Out of Phase 10 scope. Suggested follow-up quick task documented in 10-02-SUMMARY.md.

---

## Human Verification Required

None remaining. Success Criterion 4 (end-to-end Telegram run) was completed by the user on 2026-05-13 and explicitly recorded as APPROVED in 10-03-SUMMARY.md. The verification_context confirmed this is non-re-verifiable automatically. All other success criteria are programmatically verified.

---

## Gaps Summary

**No blocking gaps.** All 5 ROADMAP success criteria are satisfied; AGENT-12 is correctly marked Complete in REQUIREMENTS.md with the traceability table updated. The migration is functionally complete and Plans 11 and 12 are unblocked.

**Minor follow-ups (NOT blocking):**
- CLAUDE.md:28 `langchain-core` standalone row could be aligned to `>=1.2` for full internal consistency (low-priority documentation drift; SC5 literal wording is already satisfied via line 27).
- `tests/test_pyproject.py::test_experiment_mains_importable` env-pollution issue should be fixed as a quick task to restore unconditional `uv run pytest -q` greenness.

Neither follow-up affects the Phase 10 goal achievement.

---

## VERIFICATION COMPLETE

Phase 10 (LangChain 1.x Agent API Migration) is **verified passed**. All 5 success criteria from ROADMAP.md are satisfied with concrete codebase evidence. The phase goal — `langgraph.prebuilt.create_react_agent` → `langchain.agents.create_agent` migration with strict behavior parity — is achieved. AGENT-12 is correctly marked Complete. Plans 11 and 12 are unblocked.

---

*Verified: 2026-05-13*
*Verifier: Claude (gsd-verifier)*
