---
phase: 3
slug: gateway
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (already configured in pyproject.toml) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_gateway.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_gateway.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 1 | GW-01 | integration | `uv run pytest tests/test_gateway.py::test_incoming_message_persisted -x -q` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 1 | GW-02 | integration | `uv run pytest tests/test_gateway.py::test_duplicate_message_skipped -x -q` | ❌ W0 | ⬜ pending |
| 3-01-03 | 01 | 1 | GW-03 | integration | `uv run pytest tests/test_gateway.py::test_history_window -x -q` | ❌ W0 | ⬜ pending |
| 3-01-04 | 01 | 1 | GW-04 | integration | `uv run pytest tests/test_gateway.py::test_message_enqueued_at_front -x -q` | ❌ W0 | ⬜ pending |
| 3-01-05 | 01 | 1 | GW-05 | integration | `uv run pytest tests/test_gateway.py::test_send_message_persists -x -q` | ❌ W0 | ⬜ pending |
| 3-01-06 | 01 | 1 | GW-06 | integration | `uv run pytest tests/test_gateway.py::test_conversation_upsert -x -q` | ❌ W0 | ⬜ pending |
| 3-02-01 | 02 | 1 | GW-03 | integration | `uv run pytest tests/test_gateway.py::test_history_window -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_gateway.py` — stubs for GW-01 through GW-06
- [ ] `tests/conftest.py` — extend with gateway fixtures (live Postgres session, test Redis connection, mock PTB Update object)

*Existing pytest + integration test infrastructure from Phase 2 (tests/ directory, conftest.py) covers the framework — Wave 0 adds gateway-specific test stubs and fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `uv run gateway` starts PTB polling without crash | GW-01 | Requires real TELEGRAM_BOT_TOKEN env var | Set token, run `uv run gateway`, confirm no startup error |
| `uv run all` starts both agent and gateway | GW-01/INFRA | Requires live Redis + Telegram token | Run `uv run all`, confirm two processes start, Ctrl+C terminates both |
| Bot receives real Telegram message and enqueues job | GW-01 | Requires live Telegram bot | Send message from Telegram client, check RQ Dashboard for queued job |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
