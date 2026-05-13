---
phase: 11
slug: structured-agent-output-via-response-format
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-13
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (with pytest-asyncio for async paths) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_workflow_runner.py tests/test_llm_backend.py tests/test_jobs.py -x` |
| **Full suite command** | `uv run pytest --ignore=tests/integration -x` |
| **Estimated runtime** | ~30 seconds quick; ~90 seconds full |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_workflow_runner.py tests/test_llm_backend.py tests/test_jobs.py -x`
- **After every plan wave:** Run `uv run pytest --ignore=tests/integration -x`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds (quick) / 90 seconds (full)

---

## Per-Task Verification Map

> Populated by the planner during PLAN.md authoring. Each task gets one row tying it to a requirement ID and an automated test command.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | - | - | RRECIPE-07 / RLOAD-07 / WF-08 | — | structured_response is read and validated | unit | `uv run pytest tests/test_workflow_runner.py -x` | ⬜ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_workflow_runner.py` — add new test cases for `_extract_task_output` structured_response branch (positive + negative); adapt existing `test_on_step_complete_*` fixtures to populate `structured_response` instead of feeding free-text JSON
- [ ] `tests/test_llm_backend.py` — add tests asserting each adapter (Ollama, Anthropic, OpenAI) wraps a Pydantic class in the correct Strategy (ToolStrategy vs ProviderStrategy) when `response_format=` is passed
- [ ] `tests/test_agents.py` — extend coverage to assert each of the 5 named agents has `response_format_model` set in `AgentConfig` and that `get_agent_config()` does NOT propagate `response_format_model` from override files

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end add-recipe runs 3 distinct queries without parse failures | ROADMAP success criterion #4 | Requires live Ollama LLM + live household-manager API; too slow/brittle for CI | Start `uv run agent`; from Telegram, send three distinct add-recipe messages (e.g., "agrega ñoquis de papa", "agrega tarta de zapallo", "agrega milanesa de berenjena"); verify each workflow completes without dead-lettered steps; record run IDs + LangWatch trace links in VERIFICATION.md |
| LangWatch traces still tagged with prompt version and model config | ROADMAP success criterion #5 | LangWatch SDK trace inspection is a UI/cloud lookup | After the 3-query run, open LangWatch project, confirm each trace has `prompt_version` and `model` tags, attach screenshots/trace IDs to VERIFICATION.md |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (quick) / 90s (full)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
