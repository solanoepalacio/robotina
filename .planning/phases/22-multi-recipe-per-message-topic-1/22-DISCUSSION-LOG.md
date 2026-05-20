# Phase 22 Discussion Log

**Date:** 2026-05-20
**Mode:** `--auto` (Auto Mode active — Claude made the calls without stopping)

## Gray areas presented

User selected ALL FOUR:

1. Over-cap behavior (BATCH-05)
2. Eval set design (Pitfall 12)
3. Order preservation + wake reply format (BATCH-03/04)
4. Ambiguity handling — add `ask_user` tool now?

## Decisions made (auto-mode rationale)

### 1. Over-cap (BATCH-05)
- **D-01 ask-to-split.** V006 prompt teaches `respond()` + `terminate()` with no
  `start-workflow` calls when N > 5. NOT "proceed with first 5" — that
  silently drops recipes 6+ the user typed deliberately. No defensive code
  cap (spec says prompt-level).

### 2. Eval set design
- **D-02 one concrete script** — `experiments/robotina/multi_recipe_eval.py`,
  not a framework. Per `feedback_avoid_premature_abstraction`.
- **D-03 ≥ 30 utterances across 10 coverage classes** — single, N=2/3/4/5,
  over-cap, compound-dish, sauce-on-recipe, sanity (must-NOT-split),
  ambiguous non-recipe, with URL+text cross-source intentionally deferred
  to Phase 23.
- **D-04 thresholds** — OpenAI staging ≥ 95% count accuracy = merge gate;
  Ollama dev informational only; Anthropic optional.
- **D-05 file structure** — `22-EVAL-SET.md` (canonical utterances) +
  `22-EVAL-RESULTS-<backend>.md` (per-backend) + `22-SMOKE.md` (final
  verdict). Mirrors Phase 21 D-13 pattern.

### 3. Order + wake reply format
- **D-06 ORDER BY `created_at` ASC** on the wake helper's sibling-runs
  query. Best available proxy for user-utterance order under provider
  parallel-tool-calls (Pitfall 5).
- **D-07 `WakeInvocationInput.to_user_message()` polish** — slug on
  success, recipe_query on failure, drop legacy "(usuario ya fue
  notificado)" parenthetical.
- **D-08 `WorkflowOutcomeSummary.recipe_query`** — optional field populated
  by the wake helper from `WorkflowRun.shared_context["recipe_query"]`.
  Lightest-touch surface vs adding it to `AddRecipeOutcome` (which only
  builds on DONE workflows).
- **D-09 V006 wake reply rule + worked examples** for partial-failure
  (BATCH-04) — single `respond()` summarizing all outcomes in order.

### 4. Ambiguity handling
- **D-10 NO new `ask_user` tool.** `respond()` already covers ambiguity
  escalation semantically. Per `feedback_avoid_premature_abstraction`,
  wait until 3+ concrete instances before splitting a "ask vs answer"
  abstraction.
- **D-11 compound dishes → prefer FEWER** (1 workflow for "pollo al horno
  con papas"). Downstream `recipe-research-gather` agent decides if it's
  a main+side pairing.
- **D-12 sauce-on-recipe always 1.** "Canelones con salsa blanca y
  boloñesa" → 1 workflow. Explicit V006 worked example because small
  Ollama models tend to split this.

### Test strategy (Claude's discretion)
- D-13 automated regression tests for code-path changes (ORDER BY,
  `to_user_message` format, `WorkflowOutcomeSummary` schema).
- D-14 agent-surface test asserts V006 prompt path.
- D-15 manual eval is the load-bearing gate; phase verifies as
  `human_needed` until `22-SMOKE.md` is `verdict: pass`.
- D-16 V005 retained for rollback.

### Claude's discretion items
- V006 file naming, eval-set markdown-with-optional-YAML, commit
  ordering (code first, results last), no new env vars, no Alembic
  revision, no dashboard changes, no overrides changes.

## Deferred ideas captured

- `ask_user` tool (v2)
- Strict ordering via `batch_index` (only if smoke shows enqueue-order
  insufficient)
- URL-aware multi-recipe (Phase 23)
- Defensive code cap on N (only if prompt-level proves unreliable)
- Automated CI eval harness (v1.2)
- LLM-judge name scoring (P2 upgrade over Levenshtein)
- Conversation-history truncation (v1.2)
- Compose Agent split (v2 COMP-01)
- Same-recipe-name overlap detection (deferred until real complaints)

## Scope creep redirected

None during discussion — all four gray areas stayed inside the BATCH-01..05
boundary. The cross-source (URL + text) case was acknowledged as Pitfall
12's example but kept out of Phase 22 scope (belongs to Phase 23's V007).
