---
verdict: pending
date: <YYYY-MM-DD — operator fills>
operator: <name — operator fills>
---

# Phase 22 Multi-Recipe Eval Smoke — Final Verdict

**Status:** PENDING — operator must run the eval harness against both backends and fill this file before Phase 22 closes. Per D-15, this verdict is the load-bearing acceptance gate for BATCH-01..05 — no automated test can measure whether the LLM extracts N recipes from a Spanish multi-recipe utterance. See the eval set (`22-EVAL-SET.md`) and the two per-backend results files (`22-EVAL-RESULTS-ollama.md`, `22-EVAL-RESULTS-openai.md`) referenced below.

## Sources

- `.planning/phases/22-multi-recipe-per-message-topic-1/22-EVAL-SET.md` — 30 Spanish utterances across 10 coverage classes (per D-03)
- `.planning/phases/22-multi-recipe-per-message-topic-1/22-EVAL-RESULTS-ollama.md` — Ollama `gpt-oss:20b` results (informational only per D-04)
- `.planning/phases/22-multi-recipe-per-message-topic-1/22-EVAL-RESULTS-openai.md` — OpenAI staging results (MERGE GATE per D-04)

## Thresholds (per D-04)

- **OpenAI staging — merge gate**: ≥ 95% count accuracy on the full set AND ≥ 90% recipe-name accuracy on the multi-recipe rows = PASS.
- **Ollama dev — informational only.** Failures noted but do NOT block merge. If Ollama drops below 70%, operator notes it here for future model-upgrade tracking.
- **Anthropic — optional.** Run only if the operator chooses; not required for merge.

## Operator runbook

1. Ensure `OPENAI_API_KEY` and `LANGWATCH_API_KEY` are exported in the shell. (`OLLAMA_URL` + a running Ollama daemon with `gpt-oss:20b` is OPTIONAL — skip the dev pass if absent.)
2. Run dev pass (informational): `uv run experiments.multi_recipe_eval --backend ollama` — produces filled `.planning/phases/22-multi-recipe-per-message-topic-1/22-EVAL-RESULTS-ollama.md`.
3. Eyeball the per-class breakdown; note anything systemic in the Ollama results "Notes" section.
4. Run merge-gate pass: `uv run experiments.multi_recipe_eval --backend openai` — produces filled `.planning/phases/22-multi-recipe-per-message-topic-1/22-EVAL-RESULTS-openai.md`.
5. Review the OpenAI results table — confirm count-correct and name-correct numbers against the thresholds above (≥95% count + ≥90% name on multi-recipe rows).
6. Commit both filled EVAL-RESULTS files:
   ```
   git add .planning/phases/22-multi-recipe-per-message-topic-1/22-EVAL-RESULTS-*.md
   git commit -m "test(22): commit eval results — openai=<pass|fail>, ollama=<note>"
   ```
7. Fill in the **Verdict** section below; set frontmatter `verdict:` to one of `pass`, `pivot`, or `fail`; fill `date:` and `operator:`.
8. Commit this file:
   ```
   git add .planning/phases/22-multi-recipe-per-message-topic-1/22-SMOKE.md
   git commit -m "test(22): manual eval smoke — verdict <pass|pivot|fail>"
   ```
9. If verdict = `pass`: tick BATCH-01..05 in `.planning/REQUIREMENTS.md` (Plan 22-04 Task 3 — operator may delegate to Claude in a follow-up commit by re-invoking `/gsd:execute-phase 22` or asking Claude to run the conditional REQUIREMENTS tick).

## Verdict

- **OpenAI staging (merge gate):** PENDING — `<PASS / FAIL — operator notes>`
- **Ollama dev (informational):** PENDING — `<note>`
- **Decision:** PENDING — operator selects one of:
  - `GO (pass)` — V006 prompt + eval evidence sufficient → tick BATCH-01..05.
  - `PIVOT (pivot)` — OpenAI failed merge gate → file defensive `StartWorkflowTool.max_calls_per_turn` follow-up per CONTEXT Deferred Ideas; do NOT tick BATCH-01..05 yet.
  - `NO-GO (fail)` — re-open phase planning; do NOT tick BATCH-01..05.
- **Verdict (set in frontmatter):** `pending` → `pass` / `pivot` / `fail`

## Follow-ups by verdict

- **`pass`** — Run Plan 22-04 Task 3 (REQUIREMENTS.md ticks: BATCH-01..05 from `[ ]` to `[x]`, traceability `Pending` → `Complete`, "Last updated" line refreshed).
- **`pivot`** — File quick-task: defensive code cap on `StartWorkflowTool.max_calls_per_turn = 5` (per CONTEXT Deferred Ideas); re-run this smoke after the pivot lands; if PASS after pivot, then tick BATCH-01..05.
- **`fail`** — Re-open `/gsd:plan-phase 22 --gaps`; iterate on V006 prompt; re-run this smoke.

## References

- D-04 (thresholds), D-05 (per-backend results file structure), D-15 (operator gate is the load-bearing acceptance), D-16 (V005 retained for rollback) — `.planning/phases/22-multi-recipe-per-message-topic-1/22-CONTEXT.md`.
- BATCH-01..05 — `.planning/REQUIREMENTS.md`.
- PITFALL 12 (multi-recipe LLM parsing unreliability) — `.planning/research/PITFALLS.md`.
- Template pattern: `.planning/phases/21-tool-surface-flip-remove-acknowledge-notify/21-SMOKE.md`.
