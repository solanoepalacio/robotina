---
phase: 23
slug: url-ingestion-topic-2
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-20
last_updated: 2026-05-20
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> All test files are CREATED in this phase (no pre-existing test files referenced as MISSING).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/unit tests/url tests/agents tests/queue -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~30-60s for quick; ~2-3min full (existing repo baseline) |

---

## Sampling Rate

- **After every task commit:** Run task-specific automated verify (per-plan).
- **After every plan wave:** Run quick command.
- **Before `/gsd-verify-work`:** Full suite must be green.

---

## Per-Task Verification Map

| Plan-Task | File Created/Modified | Test File | Automated Verify Command | Coverage Notes |
|-----------|----------------------|-----------|--------------------------|----------------|
| 23-01 T1 | src/robotina/url/safe_fetch.py | (import smoke only) | `uv run python -c "from robotina.url.safe_fetch import safe_fetch, SafeFetchResult, SafeFetchError"` | Module importability |
| 23-01 T2 | tests/url/test_safe_fetch.py (NEW) | tests/url/test_safe_fetch.py | `uv run pytest tests/url/test_safe_fetch.py -q` | 20+ tests, respx-mocked, one per SSRF defense + composite scenarios |
| 23-02 T1 | task_types.py + start_workflow.py | tests/unit/test_start_workflow_tool.py (EXTEND) | `uv run pytest tests/unit/test_start_workflow_tool.py -q` | 5 new D-22 tests: pair-query, pair-url, mismatch-query-with-url, mismatch-url-with-query, legacy-add-recipe-literal |
| 23-02 T2 | workflows.py + workflow_runner.py + _macros.html | tests/queue/test_workflow_registry.py (EXTEND), tests/queue/test_wake_helper.py (EXTEND) | `uv run pytest tests/queue/test_workflow_registry.py tests/queue/test_wake_helper.py -q` | 5+1 D-21+D-08 tests |
| 23-03 T1 | src/robotina/agent/tools/fetch_and_scrape.py | (import smoke only) | `uv run python -c "from robotina.agent.tools.fetch_and_scrape import FetchAndScrapeTool"` | Module importability |
| 23-03 T2 | tests/agents/tools/test_fetch_and_scrape_tool.py (NEW) | same | `uv run pytest tests/agents/tools/test_fetch_and_scrape_tool.py -q` | 10+ tests: scraper happy/sad, quality gate, trafilatura fallback, servings_qty coercion, source_url fallback, html_text cap |
| 23-04 T1 | agents.py + overrides/*.json + V001.md + .env.example | (import + registry smoke) | `uv run python -c "from robotina.agent.agents import AGENT_REGISTRY; assert 'gather-from-url' in AGENT_REGISTRY"` + `uv run pytest tests/ -q -k 'overrides_sync or agent_registry'` | Registry presence + CI sync guard |
| 23-04 T2 | jobs.py + tests/agents/test_gather_from_url_agent.py (NEW) | same | `uv run pytest tests/agents/test_gather_from_url_agent.py -q` | 2+ tests: pass-through branch, html_text extract branch |
| 23-05 T1 | V007.md + agents.py + test_handle_incoming_message_agent.py (NEW/EXTEND) | same | `uv run pytest tests/agents/test_handle_incoming_message_agent.py -q` | 6 prompt-contract tests: path-v007, URL-handling-section, add-recipe-from-url example, add-recipe-from-query example, no-legacy-add-recipe-literal, V006-retained |
| 23-06 T1 | 23-EVAL-SET.md (NEW) | (file-structure check via python one-liner) | `uv run python -c "from pathlib import Path; p=Path('.planning/phases/23-url-ingestion-topic-2/23-EVAL-SET.md'); assert p.exists(); body=p.read_text(); assert '## URLs' in body and '## Scoring rule' in body"` | File structure + URL count |
| 23-06 T2 | experiments/gather_from_url.py + pyproject.toml | (self-test mode) | `uv run experiments.gather_from_url --backend openai --self-test` | End-to-end harness wiring, no network |
| 23-07 T1 | 23-SMOKE.md + 23-EVAL-RESULTS-*.md (NEW, operator-authored) | (manual checkpoint) | MANUAL — operator runs eval + Telegram smoke + writes verdict | Load-bearing manual gate per D-24 |
| 23-07 T2 | REQUIREMENTS.md | (conditional file check) | `uv run python -c` script that parses 23-SMOKE.md verdict and asserts REQUIREMENTS state matches | Conditional tick of URL-01..06 + EXP-02 |

---

## Wave 0 Requirements

All new test files are CREATED in this phase as part of the task that adds the corresponding production code. No MISSING `<automated>` references — every code-producing task is paired with the same-task or sibling-task test creation. Per Nyquist rule:

- 23-01 T2 creates `tests/url/test_safe_fetch.py` AS the verification artifact for 23-01 T1's safe_fetch module.
- 23-03 T2 creates `tests/agents/tools/test_fetch_and_scrape_tool.py` AS the verification for 23-03 T1's tool.
- 23-04 T2 creates `tests/agents/test_gather_from_url_agent.py` AS the verification for 23-04 T1's agent registration.
- 23-05 T1 creates/extends `tests/agents/test_handle_incoming_message_agent.py` in the same task that bumps the prompt path.

No pre-existing test files are referenced as MISSING; all test scaffolding lands within the same plan as the production code.

---

## Manual-Only Verifications

| Item | Why Manual | Where Recorded |
|------|------------|----------------|
| Real-world Spanish-blog eval against OpenAI staging | Requires live LLM API + live HTTP fetches against real recipe sites; cost + flakiness make it inappropriate for CI | `23-EVAL-RESULTS-openai.md` (operator-authored in 23-07) |
| Telegram end-to-end round-trip for a URL message | Requires live Telegram bot + live LLM + live household-manager API | `23-SMOKE.md` Telegram section (operator-authored in 23-07) |
| Final go/no-go verdict | Operator judgment based on aggregate eval + Telegram smoke | `23-SMOKE.md` `verdict:` line |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (only 23-07 T1 is manual, and it is gated by 23-07 T2's automated conditional REQUIREMENTS.md check)
- [x] Wave 0 covers all MISSING references (none exist — all test files created in-plan)
- [x] No watch-mode flags
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready for execution
