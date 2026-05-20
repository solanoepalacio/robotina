---
verdict: pending
date: <YYYY-MM-DD — operator fills>
operator: <name — operator fills>
---

# Phase 21 Multi-call Smoke Results

**Status:** PENDING — operator must run smoke before merge (operator was AFK at plan-execute time on 2026-05-19).

**Backends:** Ollama `gpt-oss:20b` (local dev), OpenAI (staging)
**V005 prompt:** `src/robotina/agent/prompts/robotina/V005.md`
**Tool surface:** `RespondTool` (non-terminal) + `StartWorkflowTool` (multi-call, `return_direct=False`) + `TerminateTool` (`return_direct=True`)

## Utterance Set (EVAL-02 coverage)

The planner picks 5–8 utterances inside the envelope: 1 single-recipe + 2 multi-recipe (2–3 items) + 1 compound dish + 1 ambiguous + 1 over-cap. The set below satisfies the floor.

| # | Utterance (Spanish)                                                          | Coverage                          | Expected N workflows                       | Ollama N | Ollama OK? | OpenAI N | OpenAI OK? | LangWatch trace IDs | Notes |
|---|------------------------------------------------------------------------------|-----------------------------------|--------------------------------------------|----------|------------|----------|------------|---------------------|-------|
| 1 | agregá lentejas                                                              | single-recipe                     | 1                                          |          |            |          |            |                     |       |
| 2 | agregá canelones y pollo al horno                                            | multi (2)                         | 2                                          |          |            |          |            |                     |       |
| 3 | agregá canelones, pollo y arroz con verduras                                 | multi (3)                         | 3                                          |          |            |          |            |                     |       |
| 4 | agregá pollo al horno con papas                                              | compound dish (ambiguous: 1 or 2) | 1–2 (operator notes which)                 |          |            |          |            |                     |       |
| 5 | agregá algo rico para esta noche                                             | ambiguous (no specific recipe)    | 0 — should clarify, not start              |          |            |          |            |                     |       |
| 6 | agregá canelones, pollo, arroz, lentejas, milanesas, salmón                  | over-cap (>5)                     | should split or reject                     |          |            |          |            |                     |       |
| 7 | salt and pepper chicken                                                      | sanity (must NOT split tokens)    | 1 (not "salt" + "pepper chicken")          |          |            |          |            |                     |       |

## Tool-call Hygiene Checks (per backend, per utterance)

For each row, ALSO verify in the LangWatch trace:

- [ ] `terminate()` was called as the LAST tool call.
- [ ] No trailing AI free text in the final assistant message (PITFALL 4 mitigation — trailing AI text).
- [ ] `respond()` was called BEFORE `terminate()`, with Spanish text.
- [ ] N start-workflow calls match the expected N for the row (or operator notes the deviation).
- [ ] No `QueueTool` / `notify` step references in the trace (PITFALL 5 mitigation — parallel tool calls / dead code).

## Go / No-Go

**Ollama:** PENDING — `<PASS / FAIL — operator notes>`
**OpenAI:** PENDING — `<PASS / FAIL — operator notes>`

**Decision:** PENDING — operator marks one of:

- `GO` with current `{workflow_type, input}` schema — Phase 21 merges.
- `NO-GO` — pivot to list-form `start-workflow(actions=[...])` per D-15 BEFORE merge.

**Verdict (set in frontmatter):** `pending` → `pass` / `pivot` / `fail`

## Operator runbook

1. Start the worker locally: `uv run agent` (Ollama backend, local dev).
2. For each utterance, send the message via Telegram (or the test gateway) once on each backend.
3. Capture the LangWatch trace ID for each turn (Ollama dashboard URL + OpenAI dashboard URL).
4. Inspect the trace: confirm tool-call sequence, confirm `terminate()` is last, confirm no trailing AI text.
5. Record `N` (number of `start-workflow` calls observed) per backend in the row.
6. Mark `OK` / `FAIL` per row.
7. Switch backend to OpenAI (staging) and repeat steps 2–6.
8. Fill in the Go / No-Go section.
9. Set frontmatter `verdict:` to one of:
   - `pass` — merge Phase 21.
   - `pivot` — apply the D-15 list-form refactor, re-run the smoke, then merge.
   - `fail` — re-open phase planning.
10. Commit this file with message: `test(21): manual multi-call smoke <verdict>`.

## Pivot path (D-15)

If OpenAI shows unacceptable reliability (e.g. <80% correct N), pivot `StartWorkflowTool` to list-form:

```python
class StartWorkflowArgs(BaseModel):
    actions: list[StartWorkflowAction]  # one entry per workflow to start

class StartWorkflowAction(BaseModel):
    workflow_type: Literal["add-recipe"]
    input: AddRecipeQueryInput
```

Update the V005 prompt examples to use the list form. Re-run the smoke. Update this file's verdict accordingly.

## References

- D-13, D-14, D-15, D-16, D-24 in `.planning/phases/21-tool-surface-flip-remove-acknowledge-notify/21-CONTEXT.md`.
- EVAL-01, EVAL-02, EVAL-03 in `.planning/REQUIREMENTS.md`.
- PITFALL 4 (trailing AI text), PITFALL 5 (parallel tool calls) in `.planning/research/PITFALLS.md`.
