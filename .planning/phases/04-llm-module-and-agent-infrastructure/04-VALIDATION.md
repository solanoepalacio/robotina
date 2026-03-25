---
phase: 4
slug: llm-module-and-agent-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml (pytest section) |
| **Quick run command** | `uv run pytest tests/unit/ -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/ -q`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | AGENT-01 | unit | `uv run pytest tests/unit/test_llm_backend.py -q` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 1 | AGENT-02 | unit | `uv run pytest tests/unit/test_llm_backend.py -q` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 1 | AGENT-03 | unit | `uv run pytest tests/unit/test_llm_backend.py -q` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 1 | AGENT-04 | unit | `uv run pytest tests/unit/test_agents_registry.py -q` | ❌ W0 | ⬜ pending |
| 4-02-02 | 02 | 1 | AGENT-05 | unit | `uv run pytest tests/unit/test_agents_registry.py -q` | ❌ W0 | ⬜ pending |
| 4-03-01 | 03 | 1 | AGENT-06 | unit | `uv run pytest tests/unit/test_agent_runner.py -q` | ❌ W0 | ⬜ pending |
| 4-03-02 | 03 | 1 | AGENT-07 | unit | `uv run pytest tests/unit/test_agent_runner.py -q` | ❌ W0 | ⬜ pending |
| 4-04-01 | 04 | 2 | AGENT-08 | unit | `uv run pytest tests/unit/test_skills.py -q` | ❌ W0 | ⬜ pending |
| 4-04-02 | 04 | 2 | AGENT-09 | unit | `uv run pytest tests/unit/test_skills.py -q` | ❌ W0 | ⬜ pending |
| 4-05-01 | 05 | 2 | AGENT-10 | unit | `uv run pytest tests/unit/test_prompts.py -q` | ❌ W0 | ⬜ pending |
| 4-05-02 | 05 | 2 | AGENT-11 | unit | `uv run pytest tests/unit/test_prompts.py -q` | ❌ W0 | ⬜ pending |
| 4-06-01 | 06 | 2 | OBS-01 | unit | `uv run pytest tests/unit/test_observability.py -q` | ❌ W0 | ⬜ pending |
| 4-06-02 | 06 | 2 | OBS-02 | unit | `uv run pytest tests/unit/test_observability.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_llm_backend.py` — stubs for AGENT-01, AGENT-02, AGENT-03
- [ ] `tests/unit/test_agents_registry.py` — stubs for AGENT-04, AGENT-05
- [ ] `tests/unit/test_agent_runner.py` — stubs for AGENT-06, AGENT-07
- [ ] `tests/unit/test_skills.py` — stubs for AGENT-08, AGENT-09
- [ ] `tests/unit/test_prompts.py` — stubs for AGENT-10, AGENT-11
- [ ] `tests/unit/test_observability.py` — stubs for OBS-01, OBS-02

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| LangWatch trace appears in dashboard | OBS-02 | Requires live LangWatch account + network | Start worker, send test job, check LangWatch UI for trace with correct project/experiment tags |
| Runtime prompt override (no redeploy) | AGENT-05 | Requires running worker process + filesystem write | Set AGENT_OVERRIDES_FILEPATH, update JSON, enqueue job, confirm new prompt used in logs |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
