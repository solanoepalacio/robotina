---
phase: 23-url-ingestion-topic-2
plan: 07
subsystem: eval-and-requirements
tags: [eval, operator, requirements-tick, checkpoint]
status: scaffolded-awaiting-operator
dependency_graph:
  requires: [23-06]
  provides: [URL-06 verdict pathway, REQUIREMENTS tick gate]
  affects: [.planning/REQUIREMENTS.md (deferred), 23-SMOKE.md verdict]
tech_stack:
  added: []
  patterns: ["operator-gated end-of-phase smoke verdict (Phase 21 / Phase 22 analog)"]
key_files:
  created:
    - .planning/phases/23-url-ingestion-topic-2/23-SMOKE.md
    - .planning/phases/23-url-ingestion-topic-2/23-EVAL-RESULTS-openai.md
    - .planning/phases/23-url-ingestion-topic-2/23-EVAL-RESULTS-anthropic.md
    - .planning/phases/23-url-ingestion-topic-2/23-07-SUMMARY.md
  modified: []
decisions:
  - "Scaffolded eval-results files for openai + anthropic per orchestrator instruction (plan text references ollama; orchestrator override is binding because D-12 names OpenAI as the merge gate and Anthropic as the documented optional companion, whereas Ollama is informational-only and the operator may skip it entirely)"
  - "Task 2 (conditional REQUIREMENTS.md tick) DEFERRED — cannot run until operator records verdict in 23-SMOKE.md (D-24 load-bearing manual gate)"
metrics:
  duration: "~3 minutes (scaffold-only)"
  completed_date: "2026-05-20"
---

# Phase 23 Plan 07: Operator Eval Smoke + Conditional REQUIREMENTS Tick — Summary (PARTIAL — operator gate pending)

Scaffolded the smoke-verdict and per-backend eval-results templates that gate Phase 23 merge; Task 2 (REQUIREMENTS.md tick) deferred until the operator runs the harness and records a verdict per D-24.

## What was executed

### Task 1 (checkpoint:human-action): Operator runs eval + records SMOKE verdict

**Status:** SCAFFOLDED — awaiting operator action.

Created three artifacts so the operator can drop straight into the eval workflow:

1. **`23-SMOKE.md`** — frontmatter sets `verdict: pending`. Contains:
   - Pre-flight verification step (`uv run experiments.gather_from_url --backend openai --self-test`) — no-network end-to-end agent wiring check the operator runs first to catch regressions before spending real LLM tokens.
   - OpenAI staging runbook (MERGE GATE per D-12, ≥ 17/21 URLs pass per D-11).
   - Anthropic optional companion runbook.
   - Telegram end-to-end smoke runbook (D-09 / D-24) with the 5-step verification checklist (pre-batch respond → workflow drains → post-batch respond → recipe visible in backend).
   - Verdict-writing instructions and resume signal protocol (`approved verdict=<pass|fail|needs-revision>`).
2. **`23-EVAL-RESULTS-openai.md`** — skeleton mirroring the harness's actual output shape (`verdict: pending` frontmatter, 21-URL table pre-populated with the URLs from `23-EVAL-SET.md` so the operator/harness only fills the score columns). Documented as the BLOCKING merge gate.
3. **`23-EVAL-RESULTS-anthropic.md`** — same skeleton, marked as OPTIONAL companion. Operator may leave it as-is if they skip Anthropic; in that case `23-SMOKE.md` records `anthropic_score: not-run`.

The harness in `experiments/gather_from_url.py` will **overwrite** the eval-results files with real per-URL data when the operator runs it; the skeletons serve as (a) documentation of expected shape and (b) safe placeholders so the file paths exist for cross-references before the run.

### Task 2 (auto): Tick REQUIREMENTS.md (only if verdict: pass)

**Status:** DEFERRED — explicitly NOT executed in this scaffold pass.

Task 2 is conditional on `verdict: pass` in `23-SMOKE.md` (per the plan's `<acceptance_criteria>`). The verdict is `pending` because the operator has not yet:

- Run the OpenAI staging eval against the 21-URL set.
- Run the Telegram end-to-end smoke against a real recipe URL.
- Recorded the verdict in `23-SMOKE.md`.

When the operator commits a `verdict: pass` SMOKE.md and signals `approved verdict=pass`, the orchestrator should re-spawn an executor for plan 23-07 to run Task 2 only (resume signal). Task 2 will then:
- Flip `- [ ]` → `- [x]` for URL-01..06 + EXP-02 in `.planning/REQUIREMENTS.md`.
- Update the Traceability table rows from `Pending` to `Complete` (with the `≥17/21` reference on URL-06).

If the operator records `verdict: fail` or `verdict: needs-revision`, Task 2 must NOT run; the orchestrator opens a gap-closure plan instead.

## Commits

| # | Hash | Message | Files |
|---|------|---------|-------|
| 1 | `015d34b` | `docs(23-07): scaffold SMOKE.md + eval-results skeletons with operator runbook` | `23-SMOKE.md`, `23-EVAL-RESULTS-openai.md`, `23-EVAL-RESULTS-anthropic.md` |
| 2 | (this commit) | `docs(23-07): partial summary — Task 1 scaffolded, Task 2 deferred` | `23-07-SUMMARY.md` |

## Deviations from Plan

**1. Eval-results filename for second backend: anthropic instead of ollama**
- **Found during:** Task 1 scaffolding.
- **Issue:** Plan frontmatter lists `23-EVAL-RESULTS-ollama.md`. Orchestrator instructions explicitly request `23-EVAL-RESULTS-anthropic.md` instead.
- **Resolution:** Followed orchestrator instruction. The substantive D-12 contract names OpenAI as the merge gate and treats every other backend as informational — Anthropic is the documented "optional" companion that operators are more likely to actually run on staging. Ollama is a local-dev artifact that the operator may skip entirely. The harness supports all three backends (`--backend ollama|openai|anthropic`); when the harness runs with `--backend ollama` it will create `23-EVAL-RESULTS-ollama.md` at run time (not blocked by absence of a scaffold), so no operator-workflow capability is lost by scaffolding anthropic rather than ollama.
- **Files:** `23-EVAL-RESULTS-anthropic.md` (created) instead of `23-EVAL-RESULTS-ollama.md` (not created).
- **Commit:** `015d34b`.

## Authentication / human-action gates

This entire plan is a `checkpoint:human-action` gate by design (D-24 load-bearing manual gate). The orchestrator must surface the checkpoint and wait for the operator's resume signal.

## Known Stubs

The three scaffolded artifacts contain operator-fill placeholders (`<X/21>`, `<operator fills>`, etc.). These are intentional and documented as such in each file's prose. They are NOT data-flow stubs that prevent operation — they are deliberate template slots that the harness (for eval-results) or the operator (for SMOKE) populates.

## CHECKPOINT REACHED

**Type:** human-action
**Plan:** 23-07
**Progress:** 1/2 tasks scaffolded (Task 1 awaiting operator; Task 2 deferred behind Task 1)

### Completed (scaffolded) tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Scaffold SMOKE.md + eval-results skeletons + operator runbook | `015d34b` | `23-SMOKE.md`, `23-EVAL-RESULTS-openai.md`, `23-EVAL-RESULTS-anthropic.md` |

### Current task

**Task 1:** Operator runs eval + records SMOKE verdict
**Status:** awaiting operator action
**Blocked by:** Real-internet eval + real LLM tokens + real Telegram round-trip + human verdict — none of which a coding agent can perform.

### Awaiting

Operator must:
1. Run `uv run experiments.gather_from_url --backend openai --self-test` to verify wiring.
2. Run the full OpenAI eval against the 21-URL eval set (MERGE GATE).
3. (Optional) Run the Anthropic companion eval.
4. Perform the end-to-end Telegram smoke test against a real recipe URL.
5. Edit `23-SMOKE.md` frontmatter (`verdict: <pass|fail|needs-revision>`, scores, telegram_smoke).
6. Commit the updated `23-SMOKE.md` (and the harness-overwritten eval-results files).
7. Signal the orchestrator: `approved verdict=<value>` to resume Task 2.

On `approved verdict=pass`, the orchestrator should re-spawn this plan's executor for **Task 2 only** (REQUIREMENTS.md tick). On `fail` / `needs-revision`, the orchestrator should NOT re-spawn Task 2 — instead open a gap-closure plan and re-run Task 1 of 23-07 after fixes land.

## References

- D-09, D-11, D-12, D-13, D-24 in `.planning/phases/23-url-ingestion-topic-2/23-CONTEXT.md`.
- 21-URL eval set: `.planning/phases/23-url-ingestion-topic-2/23-EVAL-SET.md`.
- Harness: `experiments/gather_from_url.py`.
- Phase 21 analog: `.planning/phases/21-tool-surface-flip-remove-acknowledge-notify/21-SMOKE.md`.

## Self-Check: PASSED

- FOUND: `.planning/phases/23-url-ingestion-topic-2/23-SMOKE.md`
- FOUND: `.planning/phases/23-url-ingestion-topic-2/23-EVAL-RESULTS-openai.md`
- FOUND: `.planning/phases/23-url-ingestion-topic-2/23-EVAL-RESULTS-anthropic.md`
- FOUND commit: `015d34b`
- Task 2 confirmed NOT executed: `.planning/REQUIREMENTS.md` unchanged (no edits in this session).
- STATE.md / ROADMAP.md confirmed NOT touched (parallel-executor invariant).
