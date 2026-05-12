---
phase: 8
slug: recipe-research-agent
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/ -x -q --ignore=tests/integration` |
| **Full suite command** | `uv run pytest tests/ -q --ignore=tests/integration` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q --ignore=tests/integration`
- **After every plan wave:** Run `uv run pytest tests/ -q --ignore=tests/integration`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 0 | RRECIPE-01..06 | unit | `uv run pytest tests/test_recipe_research*.py -q` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 1 | RRECIPE-03 | unit | `uv run pytest tests/test_web_search_tool.py -q` | ❌ W0 | ⬜ pending |
| 08-03-01 | 03 | 1 | RRECIPE-01,02,04 | unit | `uv run pytest tests/test_recipe_research_agents.py -q` | ❌ W0 | ⬜ pending |
| 08-04-01 | 04 | 2 | RRECIPE-05 | unit | `uv run pytest tests/test_prompts.py -q` | ✅ | ⬜ pending |
| 08-05-01 | 05 | 2 | RRECIPE-06,OBS-04 | integration | `uv run experiments.recipe_research` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_web_search_tool.py` — stubs for WebSearchTool unit tests
- [ ] `tests/test_recipe_research_agents.py` — stubs for recipe-research sub-task agents
- [ ] `tests/test_recipe_research_workflow.py` — stubs for updated workflow registry

*Existing test infrastructure (conftest.py, fixtures) covers shared needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| LangWatch trace appears in experiment collection | OBS-04 | Requires LangWatch cloud account | Run `uv run experiments.recipe_research`, check LangWatch UI for trace with prompt version tags |
| Tavily API returns Argentine recipe results | RRECIPE-03 | Requires live Tavily API key | Run experiment with TAVILY_API_KEY set, verify Spanish results |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
