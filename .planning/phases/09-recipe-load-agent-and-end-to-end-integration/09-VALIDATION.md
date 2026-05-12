---
phase: 9
slug: recipe-load-agent-and-end-to-end-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest tests/unit/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | RLOAD-01 | unit | `uv run pytest tests/unit/test_agents_registry.py::test_recipe_load_registered -x` | Wave 0 | ⬜ pending |
| 09-01-02 | 01 | 1 | RLOAD-02 | unit | `uv run pytest tests/unit/test_agents_registry.py::test_recipe_load_uses_household_manager_skill -x` | Wave 0 | ⬜ pending |
| 09-01-03 | 01 | 1 | RLOAD-05 | unit | `uv run pytest tests/unit/test_prompts.py::test_prompt_file_exists_for_recipe_load -x` | Wave 0 | ⬜ pending |
| 09-02-01 | 02 | 2 | RLOAD-03 | manual-only | Experiment: `uv run experiments.recipe_load` | N/A | ⬜ pending |
| 09-02-02 | 02 | 2 | RLOAD-04 | manual-only | Experiment: `uv run experiments.recipe_load` | N/A | ⬜ pending |
| 09-03-01 | 03 | 3 | RLOAD-06 | smoke | `uv run experiments.recipe_load` (requires live API) | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_agents_registry.py::test_recipe_load_registered` -- covers RLOAD-01
- [ ] `tests/unit/test_agents_registry.py::test_recipe_load_uses_household_manager_skill` -- covers RLOAD-02
- [ ] `tests/unit/test_prompts.py::test_prompt_file_exists_for_recipe_load` -- covers RLOAD-05

*Existing test infrastructure covers Phase 9; only new test cases needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Agent resolves food/unit names to IDs | RLOAD-03 | Requires live household-manager API | Run `uv run experiments.recipe_load`, verify output contains `recipe_id` and resolved `foodId`/`unitId` |
| Agent creates recipe via compound POST | RLOAD-04 | Requires live household-manager API | Run `uv run experiments.recipe_load`, verify recipe appears in household-manager |
| Experiment completes with LangWatch trace | RLOAD-06 | Requires LangWatch API key | Run `uv run experiments.recipe_load`, verify trace in LangWatch dashboard |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
