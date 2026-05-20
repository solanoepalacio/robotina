---
phase: 22-multi-recipe-per-message-topic-1
plan: 04
subsystem: planning-artifacts
tags: [smoke, operator-gate, partial-execution, checkpoint-paused]
status: partial
completion: 1-of-3-tasks
dependency_graph:
  requires:
    - 22-01 (V006 prompt + agents.py bump + code/test changes)
    - 22-02 (eval set markdown)
    - 22-03 (eval harness experiments/robotina/multi_recipe_eval.py + EVAL-RESULTS templates)
  provides:
    - 22-SMOKE.md scaffold (operator fills verdict)
  affects:
    - .planning/REQUIREMENTS.md BATCH-01..05 (conditional Task 3 — operator-gated)
tech_stack:
  added: []
  patterns: ["operator-gated smoke verdict (mirrors Phase 21 D-13/D-16)"]
key_files:
  created:
    - .planning/phases/22-multi-recipe-per-message-topic-1/22-SMOKE.md
  modified: []
decisions:
  - "Plan 22-04 is autonomous: false — Task 2 requires operator-only judgment (running eval harness against real OpenAI API + interpreting thresholds)."
  - "Task 1 (scaffold SMOKE) executed autonomously and committed."
  - "Task 3 (conditional REQUIREMENTS.md ticks) DEFERRED until operator commits verdict=pass."
metrics:
  duration_minutes: ~3
  completed_date: 2026-05-20
  tasks_executed: 1
  tasks_pending_operator: 2
  files_created: 1
  files_modified: 0
---

# Phase 22 Plan 04: Manual Eval Smoke + Conditional REQUIREMENTS Ticks — Partial Summary

**One-liner:** Scaffolded `22-SMOKE.md` (verdict: pending) with the operator runbook for running `experiments.multi_recipe_eval` against Ollama (informational) and OpenAI (merge gate ≥95% count + ≥90% name per D-04); paused at the human-action checkpoint that owns Task 2 and conditionally Task 3.

## Execution Status

| Task | Description | Status | Commit |
| --- | --- | --- | --- |
| 1 | Scaffold `22-SMOKE.md` (verdict: pending + operator runbook) | DONE | `ae186e0` |
| 2 | Operator runs eval harness on both backends + fills verdict | **PAUSED — operator gate** | — |
| 3 | Conditional REQUIREMENTS.md ticks for BATCH-01..05 (only on verdict=pass) | **PENDING — depends on Task 2** | — |

## Task 1 Details — Scaffold `22-SMOKE.md`

**Action:** Wrote `.planning/phases/22-multi-recipe-per-message-topic-1/22-SMOKE.md` following the Phase 21 21-SMOKE.md template, with:

- Frontmatter `verdict: pending`, `date:` and `operator:` placeholders.
- Header `# Phase 22 Multi-Recipe Eval Smoke — Final Verdict` + 3-line intro citing D-15 as the load-bearing gate for BATCH-01..05.
- `## Sources` listing `22-EVAL-SET.md`, `22-EVAL-RESULTS-ollama.md` (informational), `22-EVAL-RESULTS-openai.md` (MERGE GATE per D-04).
- `## Thresholds (per D-04)` — OpenAI ≥95% count + ≥90% name; Ollama informational only; Anthropic optional.
- `## Operator runbook` — numbered 9-step procedure with exact `uv run experiments.multi_recipe_eval --backend ollama|openai` commands and the two commit messages.
- `## Verdict` section with PENDING placeholders for OpenAI / Ollama / Decision; PASS / PIVOT / FAIL options spelled out.
- `## Follow-ups by verdict` covering pass (REQUIREMENTS tick), pivot (defensive code cap follow-up), fail (re-open `/gsd:plan-phase 22 --gaps`).
- `## References` to D-04, D-05, D-15, D-16, BATCH-01..05, PITFALL 12, and the Phase 21 template.

**Verification:** All 8 acceptance criteria passed:
- File exists: yes.
- `verdict: pending` count: 1.
- `MERGE GATE|merge gate` count: 4.
- `22-EVAL-RESULTS-openai.md` references: 3.
- `22-EVAL-RESULTS-ollama.md` references: 3.
- `Operator runbook` count: 1.
- `uv run experiments.multi_recipe_eval --backend ollama` count: 1.
- `uv run experiments.multi_recipe_eval --backend openai` count: 1.

**Done criteria met:** SMOKE scaffolded; verdict pending; runbook explicit; both EVAL-RESULTS files cross-referenced.

## Tasks 2 & 3 — Why Paused

Plan 22-04 is `autonomous: false`. Task 2 is a `checkpoint:human-action` gate (D-15): only the operator can run the eval harness against the real OpenAI API and apply the threshold judgment (≥95% count + ≥90% name on multi-recipe rows) that determines verdict ∈ {pass, pivot, fail}. Task 3 is conditional on verdict=pass and is therefore implicitly blocked by Task 2.

The executor returned a `CHECKPOINT REACHED — Operator gate (Plan 22-04 Task 2)` message with the exact commands, where to commit results, the merge gate, and the resume protocol.

## Resume Protocol

1. Operator runs the two eval commands (see runbook in `22-SMOKE.md`).
2. Operator commits both filled `22-EVAL-RESULTS-{ollama,openai}.md` files.
3. Operator fills in the Verdict section of `22-SMOKE.md` and sets frontmatter `verdict:` to `pass`, `pivot`, or `fail`.
4. Operator commits `22-SMOKE.md`.
5. To run Task 3 (only on verdict=pass): re-invoke `/gsd:execute-phase 22` or ask Claude to run "Plan 22-04 Task 3 conditional REQUIREMENTS tick" — Claude reads the verdict from `22-SMOKE.md` frontmatter; on `pass` flips BATCH-01..05 to `[x]`, traceability `Pending` → `Complete`, and refreshes the "Last updated" line; on any other verdict skips and documents the skip.

## Deviations from Plan

None. Task 1 executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- File: `/home/solanoe/code/robotina-gsd/.planning/phases/22-multi-recipe-per-message-topic-1/22-SMOKE.md` — FOUND.
- Commit `ae186e0` — FOUND (`git log --oneline --all | grep ae186e0`).
- File: `/home/solanoe/code/robotina-gsd/.planning/phases/22-multi-recipe-per-message-topic-1/22-04-SUMMARY.md` — created by this step.
