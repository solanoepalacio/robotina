---
phase: 23
slug: url-ingestion-topic-2
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-20
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Populated by planner per RESEARCH.md "Validation Architecture" section.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/unit -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | TBD (planner to fill from RESEARCH.md) |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green

---

## Per-Task Verification Map

*Populated by planner — see PLAN.md files.*

---

## Wave 0 Requirements

*Planner to extract from RESEARCH.md Validation Architecture.*

---

## Manual-Only Verifications

*Planner to extract any items where automation is impractical (e.g., real DNS rebinding test).*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
