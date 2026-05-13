# Phase 11 — Verification

**Status:** Pending manual checkpoint
**Owner:** Solano (project user)
**Created:** 2026-05-13

---

## Manual 3-query End-to-End Checkpoint

**Goal:** Verify the 5 named agents emit structured output via the response_format / structured_response channel in production conditions; verify no canelones-class parse failures occur across 3 distinct recipe queries.

**Setup (one-time before running queries):**
1. Confirm Ollama daemon is running: `curl -s http://localhost:11434/api/tags | jq '.models[] | .name' | grep gpt-oss`
2. Confirm `uv run agent` starts cleanly and worker logs show no `LangGraphDeprecatedSinceV10` warnings.
3. Confirm LangWatch endpoint + API key are configured (`LANGWATCH_ENDPOINT`, `LANGWATCH_API_KEY` in env).
4. Confirm the household-manager API is reachable (the recipe-load step needs `GET /api/foods` + `POST /api/recipes`).

**Queries to run (one at a time, observe each end-to-end before queuing the next):**

| # | Telegram message | Expected outcome |
|---|------------------|------------------|
| 1 | `agrega ñoquis de papa` | WorkflowRun completes all 6 steps; user receives Spanish confirmation with recipe name + app link |
| 2 | `agrega tarta de zapallo` | Same — completes end-to-end |
| 3 | `agrega milanesa de berenjena` | Same — completes end-to-end |

**For each query, record:**

- `workflow_run_id` (from worker logs — `Workflow queued | workflow_type=add-recipe run_id=<UUID>`)
- `final state` of WorkflowRun (must be `DONE`)
- LangWatch trace URL
- Confirmation that each trace has `prompt_version` and `model` tags
- Any unexpected `ValueError: structured_response missing` log lines (must be ZERO across all 3 runs)
- Any Ollama 500 "error parsing tool call" retries (acceptable up to the 3-attempt budget; record count)

---

## Sign-Off

**Query 1: `agrega ñoquis de papa`**

- workflow_run_id: ___
- final state: ___
- LangWatch trace: ___
- prompt_version + model tags present? [ ] yes / [ ] no
- structured_response missing errors: ___
- Ollama 500 retries: ___
- Result: [ ] PASS / [ ] FAIL — notes:

**Query 2: `agrega tarta de zapallo`**

- workflow_run_id: ___
- final state: ___
- LangWatch trace: ___
- prompt_version + model tags present? [ ] yes / [ ] no
- structured_response missing errors: ___
- Ollama 500 retries: ___
- Result: [ ] PASS / [ ] FAIL — notes:

**Query 3: `agrega milanesa de berenjena`**

- workflow_run_id: ___
- final state: ___
- LangWatch trace: ___
- prompt_version + model tags present? [ ] yes / [ ] no
- structured_response missing errors: ___
- Ollama 500 retries: ___
- Result: [ ] PASS / [ ] FAIL — notes:

---

## Overall Sign-Off

All 3 queries PASS: [ ] yes / [ ] no
LangWatch trace tagging works: [ ] yes / [ ] no
Zero canelones-class regressions: [ ] yes / [ ] no

**Approval (write APPROVED if all three above are yes):** ___
**Approved by:** ___
**Approval date:** ___

Only after APPROVED above, run Task 4.2 to flip STATE.md status/progress fields, RRECIPE-07 / RLOAD-07 / WF-10 in REQUIREMENTS.md, and the ROADMAP.md Phase 11 box.
