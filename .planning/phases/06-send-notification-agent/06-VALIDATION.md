---
phase: 6
slug: send-notification-agent
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 0 | NOTIF-01 | unit | `uv run pytest tests/test_send_notification_tool.py -x -q` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | NOTIF-01 | unit | `uv run pytest tests/test_send_notification_tool.py -x -q` | ✅ | ⬜ pending |
| 06-02-01 | 02 | 1 | NOTIF-02 | unit | `uv run pytest tests/test_skills.py -x -q` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 1 | NOTIF-02 | integration | `uv run pytest tests/test_skills.py -x -q` | ✅ | ⬜ pending |
| 06-03-01 | 03 | 1 | NOTIF-03 | integration | `uv run pytest tests/test_agents_registry.py -x -q` | ✅ | ⬜ pending |
| 06-03-02 | 03 | 1 | NOTIF-04 | integration | `uv run pytest tests/test_agents_registry.py tests/test_prompts.py -x -q` | ✅ | ⬜ pending |
| 06-04-01 | 04 | 2 | NOTIF-05 | e2e | `uv run python experiments/send_notification.py` | ❌ W0 | ⬜ pending |
| 06-04-02 | 04 | 2 | OBS-03 | manual | see Manual Verifications | N/A | ⬜ pending |
| 06-04-03 | 04 | 2 | OBS-05 | manual | see Manual Verifications | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_send_notification_tool.py` — stubs for NOTIF-01 (tool construction, `_run`, DB persistence)
- [ ] `tests/test_skills.py` — stubs for NOTIF-02 (skill file loading, MarkdownV2 escape coverage)
- [ ] `experiments/send_notification.py` — stub for NOTIF-05/OBS-03/OBS-05 experiment entry point

*Wave 0 must create test stubs before Wave 1 implements the feature code.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| LangWatch trace appears in correct experiment collection | OBS-03 | Requires live LangWatch dashboard | Run `experiments/send_notification.py`, open LangWatch UI, verify trace in `send-notification-experiment` collection |
| MarkdownV2 message renders correctly in Telegram | OBS-05 | Requires live Telegram bot | Send a `send-notification` job with bold/italic/code content; verify rendered output in Telegram chat |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
