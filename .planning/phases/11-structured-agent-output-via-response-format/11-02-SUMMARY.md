---
phase: 11
plan: 02
subsystem: workflow-runner-artifact-extraction
tags:
  - structured-output
  - response_format
  - workflow-runner
  - artifact-extraction
  - tdd
  - canelones-fix
dependency_graph:
  requires:
    - "AgentConfig.response_format_model  # established in Plan 11-01"
    - "pydantic v2 BaseModel"
    - "langchain.agents.create_agent result['structured_response']  # contract"
  provides:
    - "_extract_task_output(result, *, expects_structured: bool)  # WF-10 surface"
    - "on_step_complete per-task_type response_format_model resolution"
  affects:
    - "src/robotina/queue/jobs.py  # response_format threading — Plan 11-03 (independent; lookup is lazy in on_step_complete)"
tech_stack:
  added: []
  patterns:
    - "Pure-function structured-output extraction (kwarg-bound; caller resolves expectation)"
    - "Lazy registry import inside on_step_complete to avoid module-level coupling"
    - "Fail-loud on missing structured_response (no silent free-text fallback)"
key_files:
  created: []
  modified:
    - "src/robotina/queue/workflow_runner.py"
    - "tests/test_workflow_runner.py"
decisions:
  - "expects_structured resolved INSIDE on_step_complete (not run_task) — keeps registry lookup in one place; single-source resolution at the consumer boundary."
  - "_extract_task_output is a pure function taking expects_structured: bool; no registry import — keeps it unit-testable in isolation (no registry mocks needed in tests)."
  - "KeyError on get_agent_config falls through to expects_structured=False — preserves tool_message fallback for unregistered/transitional task types (e.g. send-notification after 07.1 removed it from the registry)."
  - "Drop the legacy free-text JSON parse ladder entirely (prose-strip, code-fence strip, first-brace scan, json.loads retry). With response_format binding the 5 named agents in Plan 11-03, the ladder is unreachable on the success path AND a footgun for new agents added without response_format."
  - "Remove the TEMP DIAGNOSTIC logger.error block — its job (diagnosing the 2026-05-13 canelones parse failure) is done; the canelones-class failure is now structurally eliminated."
  - "Defensive: when expects_structured=False AND the final message is NOT a ToolMessage, raise ValueError. Locked in by test_extract_raises_when_not_structured_and_no_tool_message — no silent free-text consumption survives."
metrics:
  duration_minutes: 6
  completed_at: "2026-05-13T18:25:00Z"
---

# Phase 11 Plan 02: workflow_runner.py refactor — structured_response-first artifact extraction Summary

Refactored `_extract_task_output` in `src/robotina/queue/workflow_runner.py` to consume the structured-output API surface established by Plan 11-01. Removed the ~60-line free-text JSON parse ladder (prose-strip, markdown-fence-strip, first-brace scan, `json.loads` retry, TEMP DIAGNOSTIC log) and replaced it with a ~30-line implementation that prefers `result['structured_response']` and fails loudly on missing. The `return_direct` ToolMessage branch is preserved for non-structured agents (Phase 07.1 QueueTool / StartWorkflowTool short-circuit). `on_step_complete` now resolves `expects_structured` per task_type by looking up `AgentConfig.response_format_model`. All 19 workflow_runner tests pass (4 new + 1 adapted + 14 existing).

## What Was Built

**One-liner:** `_extract_task_output` now reads `structured_response` first and raises `ValueError` on missing — the canelones-class free-text parse failure is structurally eliminated for any agent that has `response_format_model` bound (Plan 11-03 binds them on the 5 named agents).

### Files

**Modified:**
- `src/robotina/queue/workflow_runner.py` — `_extract_task_output` rewritten (signature `(result, *, expects_structured: bool = False)`, ~30 lines down from ~60); `on_step_complete` artifact-extraction block resolves `expects_structured` via lazy `get_agent_config(step.task_type)` lookup. Dropped `import json`; added `from pydantic import BaseModel`. Removed the TEMP DIAGNOSTIC logger.error and the entire prose-strip / code-fence / first-brace-scan / `json.loads` fallback ladder.
- `tests/test_workflow_runner.py` — 4 new tests + 1 adapted; module-level imports gained `pytest` and `from pydantic import BaseModel`.

## Tasks

| Task | Name                                                                                              | Commit  | Files                                                       |
| ---- | ------------------------------------------------------------------------------------------------- | ------- | ----------------------------------------------------------- |
| 2.1 R | RED: failing tests for new `_extract_task_output(expects_structured=...)` signature              | 08f73cb | tests/test_workflow_runner.py                               |
| 2.2 G | GREEN: refactor `_extract_task_output` + wire `on_step_complete` to resolve `expects_structured` | 4f6647b | src/robotina/queue/workflow_runner.py                       |

Total: 2 commits across 2 tasks (TDD RED → GREEN gate sequence intact).

## Tests

**Added (4):**
- `test_extract_returns_model_dump_when_structured_response_present` — positive path; `_Toy(x=1, y='hi')` in `structured_response` → `{"x": 1, "y": "hi"}`.
- `test_extract_raises_when_structured_expected_but_missing` — `structured_response=None` raises `ValueError` matching `"structured_response missing"`.
- `test_extract_raises_when_structured_expected_but_key_absent` — key entirely absent → same `ValueError`.
- `test_extract_raises_when_not_structured_and_no_tool_message` — defensive regression; non-tool terminal message with `expects_structured=False` raises `ValueError` matching `"no terminal ToolMessage"`.

**Adapted (1):**
- `test_extract_task_output_handles_return_direct_toolmessage` — call site updated to `_extract_task_output(result, expects_structured=False)`. Behavior assertion unchanged.

**Preserved (14):**
- 4 `test_on_step_complete_*` (writes_artifact, marks_step_done, enqueues_next_step, marks_workflow_done_when_final_step)
- `test_on_step_complete_advances_after_return_direct_ack`
- 4 `test_on_step_failed_*` (marks_step_failed, cancels_pending_steps, marks_workflow_failed, enqueues_dead_letter, skips_dead_letter)
- 2 `test_on_step_start_*` (marks_step_running, no_op_when_step_not_found)
- 2 `test_reply_context_not_in_*_input`

Why the `on_step_complete` tests stayed green: tests at lines 85, 113, 137, 185 pass `output = RecipeResearchInput(...)` or `{"result": "done"}` — none of these have a `"messages"` key, so they take the `elif hasattr(output, "model_dump")` or `elif isinstance(output, dict)` branches (unchanged). The new `get_agent_config` lookup only fires on the `"messages" in output` branch. The `acknowledge` test uses `task_type="hello-world"` (default in `make_step`); `"hello-world"` is NOT in `AGENT_REGISTRY`, so the `KeyError` branch fires and `expects_structured=False`, taking the tool-message path. Result: `{"tool_message": "Reply queued. job_id=xyz"}` — same as before.

## Code Delta

- **`_extract_task_output` line count:** ~60 → ~30 (50% reduction). Counting non-blank non-docstring lines: 36 lines of code → 16 lines of code.
- **Removed patterns:**
  - `import json`
  - `messages = result["messages"]` / `ai_messages = [m for m in messages if getattr(m, "type", None) == "ai"]` filtering
  - `if isinstance(raw, list): raw = " ".join(...)` Anthropic block flattening
  - `if content.startswith("```"):` markdown code-fence stripping
  - `try: parsed = json.loads(content)` retry + `except json.JSONDecodeError: ...` first-brace scan ladder
  - `logger.error("extract_task_output | parse failed | length=%d | full_content=%r", ...)` — the TEMP DIAGNOSTIC
- **Added patterns:**
  - `if expects_structured: sr = result.get("structured_response"); if isinstance(sr, BaseModel): return sr.model_dump(mode="json")`
  - `if sr is None: raise ValueError("structured_response missing on response_format agent result; ...")`
  - `from pydantic import BaseModel`
  - In `on_step_complete`: lazy `from robotina.agent.agents import get_agent_config` + `expects_structured = agent_config.response_format_model is not None`

## Requirements Covered

- **WF-10** (Phase 11, In Progress) — `_extract_task_output` reads `structured_response`; fail-loud on missing for structured agents. Implementation landed in this plan; remains `In Progress` until Plan 11-04 manual end-to-end checkpoint flips it `Complete`.

## Verification

```bash
$ uv run pytest tests/test_workflow_runner.py -x
============================== 19 passed in 0.03s ==============================
```

| Acceptance Criterion | Result |
| --- | --- |
| `uv run pytest tests/test_workflow_runner.py -x` exits 0 | PASS (19 passed) |
| `grep -c "TEMP DIAGNOSTIC" src/robotina/queue/workflow_runner.py` returns 0 | PASS (0) |
| `grep -A2 "extract_task_output \| parse failed" src/robotina/queue/workflow_runner.py` returns no match | PASS (no match) |
| `grep -c "json\.loads" src/robotina/queue/workflow_runner.py` returns 0 | PASS (0; docstring reworded to avoid literal reference) |
| `grep -c "content\.find" src/robotina/queue/workflow_runner.py` returns 0 | PASS (0) |
| `grep -c "structured_response" src/robotina/queue/workflow_runner.py` >= 4 | PASS (10) |
| `grep -c "from pydantic import BaseModel" src/robotina/queue/workflow_runner.py` returns 1 | PASS (1) |
| `_extract_task_output` body is ~30 lines (down from ~60) | PASS (~50% reduction) |
| `on_step_complete` artifact-extraction block uses `get_agent_config` lookup | PASS (lazy import; KeyError → False fallback) |
| 4 new tests + 1 adapted test all green | PASS |
| 14 pre-existing tests in `test_workflow_runner.py` still green | PASS |

Full-suite signal (`uv run pytest --ignore=tests/integration`): 157 passed, 19 failed, 6 errors. All 19 failures + 6 errors are pre-existing and documented in `.planning/phases/11-structured-agent-output-via-response-format/deferred-items.md` (Plan 11-01 record). They fall in two categories:
- DB-dependent tests requiring a live Postgres (`tests/test_gateway.py`, etc.) — worktree has no docker-compose running. None of these tests touch `workflow_runner._extract_task_output`.
- `tests/unit/test_agents_registry.py` test pollution from `AGENT_OVERRIDES_FILEPATH` left set by a sibling test — unrelated to this plan.

This plan introduces ZERO new failures. Confirmed by comparing the failure list before/after the Plan 11-02 commits land; pre-Plan-11-02 the same 19 failures + 6 errors exist (per 11-01-SUMMARY.md verification block and deferred-items.md).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree branched from stale commit; merged use-new-agent-version**
- **Found during:** Initial plan-file load.
- **Issue:** The worktree was created from commit `139dfc9` which predates the Phase 11 planning commits (3e112e9, 74612e2, 0b992b7, 05bc195, …, 92aed02). The Phase 11 directory `.planning/phases/11-structured-agent-output-via-response-format/` did not exist on the worktree branch, so the PLAN.md could not be read.
- **Fix:** Ran `git merge use-new-agent-version --no-edit`. The merge fast-forwarded cleanly (no actual merge commit), bringing in all of Phase 10 wrap-up (a113582, f52533a, 8643828, 4123b35, c2fce52, 386374b, 47e0ac9, 19b3b9d), Phase 11 planning (3e112e9, …, 0b992b7), and Plan 11-01 (05bc195, e540e60, 8ae6c44, 1d11a9d, 5f23573, 8c99d54, 92aed02). The orchestrator instructed "Do not rebase"; a fast-forward merge satisfied that constraint while making the plan readable.
- **Files modified:** none directly; merge brought in pre-existing commits.
- **Commit:** none — this was a git operation, not a code change.

**2. [Rule 1 - Bug] Docstring referenced removed `json.loads` pattern by name, triggering acceptance grep gate**
- **Found during:** Acceptance-gate grep verification after Task 2.2 GREEN commit (4f6647b).
- **Issue:** The original docstring text (lifted verbatim from the PLAN.md) said `"first-``{``-scan / ``json.loads`` fallback ladder is REMOVED"`. The `grep -c "json\.loads"` acceptance gate counted this literal docstring reference as a hit and would return 1 instead of the intended 0 (the gate's intent: no *code* uses `json.loads`).
- **Fix:** Reworded the docstring to describe the removed pattern in prose without the literal `json.loads` / `first-{-scan` tokens: "The legacy free-text JSON parse fallback ladder (prose-strip, markdown-code-fence stripping, first-brace scan, retry parse) is REMOVED". Intent preserved; grep gate now returns 0.
- **Files modified:** `src/robotina/queue/workflow_runner.py` (docstring only).
- **Commit:** folded into 4f6647b (same commit as the refactor itself — the docstring edit happened before `git add` while reviewing the gates).

### Out-of-scope discoveries (logged, NOT fixed)

Pre-existing test failures (DB-dependent + `AGENT_OVERRIDES_FILEPATH` pollution) — already recorded in `.planning/phases/11-structured-agent-output-via-response-format/deferred-items.md` under Plan 11-01. No incremental logging from this plan because the failure set is identical to what 11-01 measured.

## TDD Gate Compliance

| Task | RED commit | GREEN commit | Gate sequence intact? |
| --- | --- | --- | --- |
| 2.1+2.2 | 08f73cb (`test(11-02):` — 4 new + 1 adapted, all RED with TypeError on unknown kwarg) | 4f6647b (`refactor(11-02):` — implementation makes all 5 tests pass + 14 existing still green) | YES |

No REFACTOR commit was needed — the implementation was minimal and passed the tests as written. The docstring rewording was caught and folded into the GREEN commit pre-add, not as a separate refactor.

## Notes for Plan 11-03 and Plan 11-04

- **Plan 11-03** (binds `response_format_model` on the 5 named agents in `AGENT_REGISTRY`, threads `response_format=config.response_format_model` through `backend.create_agent()` in `run_task`): the workflow_runner is already ready. As soon as the 5 agents have `response_format_model` set in the registry, `on_step_complete`'s `get_agent_config(step.task_type).response_format_model is not None` will resolve to True for them, and `_extract_task_output` will read `structured_response` automatically. No further changes to `workflow_runner.py` needed.
- **Plan 11-04** (manual end-to-end checkpoint over 3 distinct recipe queries): when the live agents emit free-text instead of populating `structured_response`, the new `ValueError("structured_response missing on response_format agent result; ...")` will surface in the failed-job log immediately — much louder than the silent `parsed = None` → `ValueError("Could not parse JSON from agent output: ...")` of the old ladder. Plan 11-04 verification can grep RQ failed-jobs for this exact error message as a regression signal.

The non-overridable nature of `AgentConfig.response_format_model` (established in 11-01) is what makes this resolution safe: a developer cannot accidentally unset `response_format` via `overrides/*.json` and silently re-enter the (now-removed) free-text fallback path.

## Self-Check: PASSED

Verified files exist (worktree absolute paths):
- `/home/solanoe/code/robotina-gsd/.claude/worktrees/agent-ad15d62586b8bd8c1/src/robotina/queue/workflow_runner.py` FOUND
- `/home/solanoe/code/robotina-gsd/.claude/worktrees/agent-ad15d62586b8bd8c1/tests/test_workflow_runner.py` FOUND

Verified commits exist (`git log --oneline`):
- 08f73cb FOUND (Task 2.1 RED)
- 4f6647b FOUND (Task 2.2 GREEN)
