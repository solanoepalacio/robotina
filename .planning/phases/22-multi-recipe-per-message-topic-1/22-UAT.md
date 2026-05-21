---
status: complete
phase: 22-multi-recipe-per-message-topic-1
source: [22-01-SUMMARY.md, 22-02-SUMMARY.md, 22-03-SUMMARY.md, 22-04-SUMMARY.md]
started: 2026-05-20T00:00:00Z
updated: 2026-05-21T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: |
  Kill any running robotina worker / gateway. Start the stack fresh
  (`docker compose up -d postgres redis` for infra; `uv run agent` for the
  task-runner). The worker boots without import or registry errors, the
  AGENT_REGISTRY assertion test loads V006.md for handle-incoming-message,
  and a basic Telegram poke is processed end-to-end.
result: pass

### 2. V006 Prompt Wired In Registry
expected: |
  `grep V006.md src/robotina/agent/agents.py` shows handle-incoming-message
  pointing at V006.md (V005.md retained for rollback only).
  `uv run pytest tests/agents/test_agent_registry.py -q` passes — the
  registry assertion is locked to V006.
result: pass

### 3. Single Recipe (N=1) Extraction
expected: |
  Send a Telegram message: "agregá lentejas".
  Robotina sends ONE pre-batch ack respond() in Argentine Spanish
  (something like "Dale, te aviso cuando esté"), dispatches exactly ONE
  start-workflow(add-recipe, "lentejas"), then terminates. When the
  workflow completes, a consolidated wake reply arrives with the slug
  (e.g. "✓ add-recipe: Lentejas (slug: lentejas, run <id>)").
result: pass

### 4. Multi-Recipe (N=3) Extraction with Pre-Batch Ack
expected: |
  Send: "agregá lentejas, pollo al horno y tarta de jamón".
  Robotina sends exactly ONE pre-batch respond() ack (not 3), dispatches
  THREE parallel start-workflow calls (one per recipe, preserving the
  user's order), then terminates. No per-recipe ack messages should be
  sent during dispatch.
result: pass

### 5. Consolidated Wake Reply Lists Each Outcome
expected: |
  After all 3 workflows from test 4 finish, Robotina sends exactly ONE
  consolidated respond() listing each outcome on its own line — successes
  with name + slug, in the same order the user mentioned them. No
  per-recipe wake messages; no "you already heard from me" terse text.
result: pass

### 6. Partial-Failure Wake Rendering
expected: |
  Trigger a multi-recipe message where at least one workflow fails
  (e.g. a deliberately-nonexistent recipe like "canelones de unicornio").
  The consolidated wake reply shows successes with name+slug AND failures
  rendered with the original recipe_query plus reason
  (e.g. "✗ add-recipe: canelones de unicornio falló: no encontré la receta (run <id>)").
  Failures use the query the user typed, NOT a placeholder like "(receta sin nombre)".
result: pass

### 7. Wake Outcomes Ordered by Insertion (created_at ASC)
expected: |
  In tests 5 and 6, the order of outcome lines in the consolidated reply
  matches the order the recipes were mentioned in the user's message
  (proxied by WorkflowRun.created_at ASC, since provider may parallelize
  tool calls).
result: pass

### 8. Over-Cap (N>5) Ask-to-Split
expected: |
  Send a message naming 7 recipes (e.g. "agregá lentejas, milanesas,
  ñoquis, ravioles, tarta, pollo y empanadas"). Robotina responds with
  an ask-to-split message in Spanish ("Son muchas recetas a la vez..."
  or equivalent) and terminates. ZERO start-workflow calls are
  dispatched.
result: pass

### 9. Ambiguous Message Clarification
expected: |
  Send a vague message like "hola" or "qué hago de cena". Robotina
  responds asking for clarification in Spanish and terminates. ZERO
  start-workflow calls are dispatched.
result: pass

### 10. Compound Dish Stays as 1 Workflow
expected: |
  Send "agregá pollo con papas" (a single compound dish). Robotina
  dispatches ONE start-workflow with the compound name, not two
  separate workflows for "pollo" and "papas".
result: pass

### 11. Sauce-on-Recipe Stays as 1 Workflow
expected: |
  Send "agregá canelones con salsa blanca y boloñesa". The "y" sits
  inside a noun phrase, not as a list separator — Robotina dispatches
  exactly ONE start-workflow for the canelones, NOT separate workflows
  for salsa blanca and boloñesa.
result: pass

### 12. Eval Harness Merge-Gate Verdict (OpenAI)
expected: |
  Run `uv run experiments.multi_recipe_eval --backend openai` per the
  22-SMOKE.md runbook. OpenAI staging meets merge gate: ≥95% count
  accuracy on the full 30-utterance set AND ≥90% recipe-name accuracy
  on multi-recipe rows. 22-SMOKE.md frontmatter is updated to
  `verdict: pass` and committed; BATCH-01..05 ticked in REQUIREMENTS.md.
result: issue
reported: "OK? column says FAIL for every row even though many succeeded under LangWatch inspection; LangWatch trace column is empty."
severity: major

## Summary

total: 12
passed: 11
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Eval harness OK? column reflects merge-gate verdict (count + name) accurately per D-04"
  status: failed
  reason: "User reported: OK? column says FAIL for every row even though many succeeded under LangWatch inspection. Root cause located in experiments/robotina/multi_recipe_eval.py:580 — `ok = OK if (count_ok and name_ok and respond_ok) else FAIL`. The `respond_ok` gate calls `respond_tag_matches` (lines 376-388) which substring-checks the `Expected respond()` cell against the LLM's Spanish text. The eval-set tags (ack, ack-all, ask-to-split, clarify, clarify-what-recipe in 22-EVAL-SET.md) are class-internal labels — the LLM never literally emits 'ack' or 'clarify' in its Spanish reply. Result: respond_ok is False for ~all rows, dragging OK→FAIL even when count_ok and name_ok are both True. The aggregate header proves the underlying numbers are healthy (26/30 count, 20/21 name = 95.2%). Per D-04, merge gate is count + name only — respond_ok should not gate the OK column."
  severity: major
  test: 12
  root_cause: "respond_ok included in OK/FAIL verdict gate at multi_recipe_eval.py:580; eval-set's expected_respond_tag column uses class-internal labels that are not substrings of the actual Spanish respond() text the LLM emits"
  artifacts:
    - path: "experiments/robotina/multi_recipe_eval.py"
      issue: "Line 580: `ok = OK if (r.count_ok and r.name_ok and r.respond_ok) else FAIL` — respond_ok shouldn't be a merge-gate criterion per D-04 (count + name only)"
    - path: "experiments/robotina/multi_recipe_eval.py"
      issue: "Lines 376-388: respond_tag_matches uses substring assertion against tags that are class-internal labels, not literal Spanish phrases"
    - path: ".planning/phases/22-multi-recipe-per-message-topic-1/22-EVAL-SET.md"
      issue: "Expected respond() column populated with internal tags (ack, ack-all, clarify, clarify-what-recipe, ask-to-split) — only rows 28-30 use a literal Spanish substring (no manejo enlaces)"
    - path: ".planning/phases/22-multi-recipe-per-message-topic-1/22-EVAL-RESULTS-openai.md"
      issue: "All 30 rows show OK?=FAIL despite aggregate showing 26/30 count-correct and 20/21 name-correct"
  missing:
    - "Remove respond_ok from the OK?-column gate at multi_recipe_eval.py:580 (use OK = count_ok and name_ok only, matching D-04 merge gate)"
    - "Either (a) keep respond_tag as an informational separate column, or (b) replace internal tags with literal Spanish substrings the LLM actually emits"
    - "Regenerate 22-EVAL-RESULTS-openai.md so operator can read the real per-row verdict before flipping 22-SMOKE.md frontmatter"
  debug_session: ""

- truth: "Eval harness emits a clickable LangWatch trace URL or trace ID per utterance so operator can drill into failed rows"
  status: failed
  reason: "User reported: LangWatch trace column is empty. Root cause at experiments/robotina/multi_recipe_eval.py:586-587 — the per-row markdown line ends with hardcoded `|  |` (empty trace cell). The script creates a LangChainTracer per utterance (line 682) with rich metadata (utterance_id, class, backend, model, provider), opens it via `with tracer:` (line 697), and passes it as a callback (line 700) — but never reads back a trace ID, never persists one on EvalResult (the dataclass has no trace_id field), and the writer outputs an empty cell. Operator must currently go to LangWatch UI and filter by metadata manually to find each trace, which defeats the purpose of the column."
  severity: major
  test: 12
  root_cause: "EvalResult dataclass lacks a trace_id/trace_url field; the LangChainTracer's trace identifier is never extracted; write_results emits hardcoded empty cell at line 587"
  artifacts:
    - path: "experiments/robotina/multi_recipe_eval.py"
      issue: "Lines 472-479: EvalResult dataclass has no trace_id or trace_url field"
    - path: "experiments/robotina/multi_recipe_eval.py"
      issue: "Lines 682-701: LangChainTracer is created and used but trace ID is never extracted after the `with tracer:` block exits"
    - path: "experiments/robotina/multi_recipe_eval.py"
      issue: "Line 587: trailing `|  |` literal in the markdown row instead of a populated trace URL/ID cell"
  missing:
    - "Add `trace_id: str | None = None` (and optionally `trace_url: str | None = None`) to EvalResult"
    - "After agent.invoke() returns, read the trace ID off the LangWatch tracer (likely `tracer.trace_id` or via `langwatch.get_current_trace()` — verify against langwatch SDK)"
    - "In write_results, emit either the trace ID or a constructed LangWatch URL (e.g. `https://app.langwatch.ai/<project>/messages/<trace_id>`) in the final column"
    - "Document the LangWatch URL pattern in CLAUDE.md if not already (project slug + trace path) so future eval reports can build links consistently"
  debug_session: ""
