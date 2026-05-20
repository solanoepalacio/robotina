---
phase: 21-tool-surface-flip-remove-acknowledge-notify
plan: 05
subsystem: agent-prompts
tags: [prompts, robotina, tool-surface, pitfall-4]
dependency_graph:
  requires: [21-01, 21-02, 21-03]
  provides: [V005 Robotina system prompt teaching respond/start-workflow/terminate surface]
  affects: [21-04 (bumps prompt_path V004 → V005 in agents.py)]
tech_stack:
  added: []
  patterns: [Prompt-level PITFALL 4 mitigation via strict Output Rule; English body / Spanish user-facing examples]
key_files:
  created:
    - src/robotina/agent/prompts/robotina/V005.md
  modified: []
decisions:
  - "V005 = V004 + new tool surface (per D-09). V004 retained for rollback."
  - "Wake-context turns SPEAK via respond() — reverses V004's 'reflect but cannot speak' stance (D-09)."
  - "Strict Output Rule forbids any user-facing text outside respond() arguments (PITFALL 4 prompt-level mitigation)."
  - "Single respond() per wake-context turn even with multiple outcomes (no Telegram spam)."
  - "Multi-recipe is mentioned but worked examples stay single-recipe — multi-recipe extraction lands in V006 / Phase 22."
  - "Forbidden behaviors enumerated explicitly (fabricated data, respond() after terminate(), omitted terminate(), free-form final text, legacy queue tool)."
metrics:
  duration: ~10 minutes
  completed_date: 2026-05-19
  tasks_completed: 1/1
  files_created: 1
---

# Phase 21 Plan 05: V005 Robotina Prompt Summary

V005 system prompt for the `handle-incoming-message` (Robotina) agent, teaching the new three-tool surface introduced in plans 21-01..21-03: `respond(text)`, `start-workflow(workflow_type, input)`, and `terminate()`. V004 is retained untouched in the prompt directory as a rollback target. The agents.py prompt_path bump (V004 → V005) is owned by plan 21-04 task 2; this plan is path-only.

## What was built

A single new prompt file `src/robotina/agent/prompts/robotina/V005.md` (141 lines) forked from V004. The fork preserves the V004 structure (Role / Inputs / Tools / Process / Rules / Wake context / Output) and adds:

1. **Three-tool surface in "Tools" section** — replaces V004's `queue` + `start-workflow` terminal-tool framing with the new non-terminal `respond()` / `start-workflow()` plus terminal `terminate()`. `start-workflow` schema documented as `(workflow_type, input)` where `input = {value: "<recipe query>"}` per D-03.
2. **Strict Output Rule section** (load-bearing for PITFALL 4) — explicitly states `respond()` is the ONLY user-visible channel and final-message text is silently dropped.
3. **Worked example — single-recipe USER_MESSAGE happy path** — `respond("Listo, voy con lentejas") → start-workflow(workflow_type="add-recipe", input={"value": "lentejas"}) → terminate()`.
4. **Worked example — wake-context happy path** — `respond("Lista guardada: Lentejas guisadas (id abc123)") → terminate()`.
5. **Worked example — wake-context failure path** — Spanish apology including `failure_reason`, single `respond()` then `terminate()`.
6. **Multi-outcome wake rule** — "compose a SINGLE `respond()` summarizing all outcomes; do NOT call `respond()` once per outcome" (Telegram spam mitigation).
7. **Phase 20 wake-context reversal note** — V004 said "you may reflect but cannot speak"; V005 reverses to "you CAN and SHOULD speak via `respond()`".
8. **Forbidden-behaviors list** — fabricating recipe data, `respond()` after `terminate()`, omitting `terminate()`, free-form final-message text, legacy queue tool.
9. **Multi-recipe minimal note** — "if the user lists multiple recipes, emit ONE `start-workflow` per recipe; worked examples land in a later prompt version" (defers BATCH to Phase 22 / V006).
10. **Language rule preserved** — English prompt body, Spanish strings inside `respond()` arguments.

Top-of-file HTML comment block references D-09, D-10, and PITFALL 4.

## Acceptance criteria (all passed)

- `test -f src/robotina/agent/prompts/robotina/V005.md` → exists.
- `test -f src/robotina/agent/prompts/robotina/V004.md` → retained, no git diff against pre-Phase-21 state.
- `grep -c "respond" V005.md` → 23 (>= 3 required).
- `grep -c "start-workflow" V005.md` → 10 (>= 2 required).
- `grep -c "terminate" V005.md` → 17 (>= 3 required).
- `grep -ic "only user-visible channel\|final assistant message" V005.md` → 2 (>= 1 required).
- `grep -c "Listo\|lentejas\|guardada" V005.md` → 7 (>= 1 required).
- `grep -c "QueueTool" V005.md` → 0 (must be 0 — the forbidden-behavior bullet refers to "the legacy `queue` tool" without using the identifier "QueueTool", satisfying the acceptance grep).
- `grep -c "acknowledge-add-recipe" V005.md` → 0.
- `wc -l V005.md` → 141 (>= 50 required).

## Deviations from Plan

**1. [Rule 1 — wording reconciliation] Forbidden-behavior bullet changed from "Calling QueueTool" to "Calling the legacy queue tool".**
- **Found during:** Acceptance verification.
- **Issue:** The plan's action bullet 7 said to forbid "QueueTool" by name, but the plan's own acceptance criterion required `grep -c "QueueTool" == 0`. The two were in tension.
- **Fix:** Restated the forbidden bullet as "Calling the legacy `queue` tool. It no longer exists. Use `respond()` instead." The semantics are preserved (LLM is told the old tool is gone) and the acceptance grep gate passes.
- **Files modified:** `src/robotina/agent/prompts/robotina/V005.md` (one bullet rephrased).
- **Commit:** Single commit `5e6109d` (the rephrase was applied before the commit).

No other deviations.

## Pre-execution context note

The worktree branch `worktree-agent-a2520aa8b76269f42` was created from an old base (32b7df4) that predates Phase 21. A rebase onto `main` (current tip 27731c5) was performed at the start of the plan to bring in the Phase 21 planning artifacts and the V004 prompt file. The rebase was clean (no conflicts). All work then proceeded on the per-agent worktree branch per the worktree HEAD safety rules.

## Commits

| # | Hash    | Message                                                                                              |
| - | ------- | ---------------------------------------------------------------------------------------------------- |
| 1 | 5e6109d | docs(21-05): add V005 Robotina prompt teaching respond/start-workflow/terminate surface              |

## Follow-ups owned by other plans

- **Plan 21-04 task 2:** bumps `handle-incoming-message` `prompt_path` from `V004.md` to `V005.md` in `src/robotina/agent/agents.py`. Until that lands, V005 is on disk but unused.
- **Phase 22 / V006:** multi-recipe extraction worked examples + over-cap rule.

## Self-Check: PASSED

- File `src/robotina/agent/prompts/robotina/V005.md` → FOUND (141 lines).
- File `src/robotina/agent/prompts/robotina/V004.md` → FOUND (untouched).
- Commit `5e6109d` → FOUND on branch `worktree-agent-a2520aa8b76269f42`.
- All acceptance grep gates → PASS (verified above).
