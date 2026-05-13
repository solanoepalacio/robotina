---
phase: 11
slug: structured-agent-output-via-response-format
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-13
updated: 2026-05-13
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (with pytest-asyncio for async paths) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_workflow_runner.py tests/test_llm_backend.py tests/test_agents.py -x` |
| **Full suite command** | `uv run pytest --ignore=tests/integration -x` |
| **Estimated runtime** | ~15 seconds quick; ~90 seconds full |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_workflow_runner.py tests/test_llm_backend.py tests/test_agents.py -x`
- **After every plan wave:** Run `uv run pytest --ignore=tests/integration -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds (quick) / 90 seconds (full)

---

## Per-Task Verification Map

> Filled by the planner. Each task gets one row tying it to a requirement ID and an automated test command.
> Note: the orchestrator's planning context proposed `WF-08` but that ID was already used in Phase 5 (workflow failure handling). Plan 11-01 uses `WF-10` instead — the next free slot in the WF-* family.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1.1 | 11-01 | 1 | RRECIPE-07 / RLOAD-07 / WF-10 | — | Requirement IDs registered with traceability | grep | `grep -c "RRECIPE-07\|RLOAD-07\|WF-10" .planning/REQUIREMENTS.md` | ✅ | ⬜ pending |
| 1.2 | 11-01 | 1 | RRECIPE-07 / RLOAD-07 | — | Adapters wrap Pydantic class in correct Strategy per provider | unit | `uv run pytest tests/test_llm_backend.py -x` | ⬜ W0 | ⬜ pending |
| 1.3 | 11-01 | 1 | RRECIPE-07 / RLOAD-07 | — | AgentConfig.response_format_model exists; non-overridable | unit | `uv run pytest tests/test_agents.py -x` | ⬜ W0 | ⬜ pending |
| 2.1 | 11-02 | 2 | WF-10 | — | Tests for structured_response branch fail RED before refactor | unit (RED-state confirmation) | `uv run pytest tests/test_workflow_runner.py -x` | ✅ | ⬜ pending |
| 2.2 | 11-02 | 2 | WF-10 | — | _extract_task_output reads structured_response; raises on missing; tool_message branch preserved | unit | `uv run pytest tests/test_workflow_runner.py -x` | ✅ | ⬜ pending |
| 3.1 | 11-03 | 2 | RRECIPE-07 / RLOAD-07 | — | run_task threads response_format kwarg; binding tests written RED | grep + unit | `grep -c "response_format=config.response_format_model" src/robotina/queue/jobs.py` | ✅ | ⬜ pending |
| 3.2 | 11-03 | 2 | RRECIPE-07 / RLOAD-07 | — | 5 named agents bound to Pydantic Outputs; prompts bumped (JSON boilerplate stripped) | unit + grep | `uv run pytest tests/test_agents.py -x` | ✅ | ⬜ pending |
| 4.1 | 11-04 | 3 | RRECIPE-07 / RLOAD-07 / WF-10 | — | Decision record + STATE/CLAUDE.md + VERIFICATION.md template created | grep | `grep -c "Phase 11" .planning/STATE.md` (≥4) | ⬜ | ⬜ pending |
| 4.2 | 11-04 | 3 | RRECIPE-07 / RLOAD-07 / WF-10 | — | Manual 3-query end-to-end checkpoint signed APPROVED; REQUIREMENTS.md ticked Complete | manual (blocking checkpoint) | n/a — user runs Telegram queries, signs VERIFICATION.md | ⬜ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_llm_backend.py` — NEW FILE. 5 tests: Protocol signature; Ollama omits kwarg when None; Ollama wraps in ToolStrategy; Anthropic wraps in ProviderStrategy; OpenAI wraps in ProviderStrategy. (Plan 11-01 Task 1.2)
- [ ] `tests/test_agents.py` — NEW FILE. 4 tests in Plan 11-01 Task 1.3 (AgentConfig field defaults + non-overridable behavior) + 6 tests appended in Plan 11-03 Task 3.1 (5 registry bindings + 1 negative for out-of-scope agents). 10 tests total at phase end.
- [ ] `tests/test_workflow_runner.py` — 4 new test cases for `_extract_task_output` structured branch (positive + 2 negatives + defensive fail-loud); 1 existing test (`test_extract_task_output_handles_return_direct_toolmessage`) adapted to the new `expects_structured=False` signature. (Plan 11-02 Task 2.1)

*All Wave 0 test files / new test cases are created by the same plan that turns them green (red-first within a single task via `tdd="true"` markers). Wave 0 is not a separate plan.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end add-recipe runs 3 distinct queries without parse failures | ROADMAP success criterion #4 | Requires live Ollama LLM + live household-manager API; too slow/brittle for CI | Run via Plan 11-04 Task 4.2 — see `.planning/phases/11-.../11-VERIFICATION.md` for the explicit query list, observation criteria, and sign-off blocks |
| LangWatch traces still tagged with prompt version and model config | ROADMAP success criterion #5 | LangWatch SDK trace inspection is a UI/cloud lookup | After the 3-query run, open LangWatch project, confirm each trace has `prompt_version` and `model` tags. Record trace URLs in `11-VERIFICATION.md`. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify (4.2 is a checkpoint; manual verification by design)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every task in Plans 11-01 through 11-03 has an automated gate; only 4.2 is manual and it's the terminal task)
- [x] Wave 0 covers all MISSING references (`test_llm_backend.py` + `test_agents.py` are NEW files created in Plan 11-01 Tasks 1.2 and 1.3; new `test_workflow_runner.py` cases added in Plan 11-02 Task 2.1)
- [x] No watch-mode flags
- [x] Feedback latency < 15s (quick) / 90s (full)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved (planner) — pending execution
