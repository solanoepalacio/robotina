---
verdict: pending
phase: 23
date: <YYYY-MM-DD — operator fills>
operator: <name — operator fills>
openai_score: <X/21 — operator fills>
anthropic_score: <X/21 — operator fills, optional>
ollama_score: <X/21 — operator fills, informational>
telegram_smoke: <pass | fail — operator fills>
---

# Phase 23 — URL Ingestion Smoke Verdict

**Status:** PENDING — operator must run the eval harness and Telegram round-trip before this verdict can flip. D-24 (load-bearing manual gate). All Phase 23 code, prompts, and the harness are committed (waves 1–4). The eval set is at `.planning/phases/23-url-ingestion-topic-2/23-EVAL-SET.md`.

**Backends (D-12):**
- OpenAI staging — **MERGE GATE.** Aggregate pass ≥ 17/21 (≈ 85% URL-level success) is the BLOCKING threshold for URL-06.
- Anthropic — optional companion run (record if executed; not a merge gate).
- Ollama dev — informational only (not run by default in this scaffold; results captured in this file only if operator decides to run).

---

## Pre-flight verification (read-only, no network)

Before running the live eval, verify the harness wiring is healthy with the no-network self-test:

```bash
uv run experiments.gather_from_url --backend openai --self-test
```

This exercises `langchain.agents.create_agent`, `response_format=RecipeData`, the real V001 prompt, and `FetchAndScrapeTool` against a canned schema.org JSON-LD payload (no internet, no real LLM tokens consumed beyond a single self-test call). It should complete in well under 1 minute and emit a single PASS row.

If self-test fails, STOP — do not run the full eval until wiring is fixed.

---

## Operator runbook

### 1. Run the OpenAI staging eval (BLOCKING MERGE GATE)

```bash
export GATHER_FROM_URL_API_TOKEN=<openai_staging_key>
export LANGWATCH_API_KEY=<langwatch_key>
uv run experiments.gather_from_url --backend openai --eval-set .planning/phases/23-url-ingestion-topic-2/23-EVAL-SET.md
```

The harness will overwrite `.planning/phases/23-url-ingestion-topic-2/23-EVAL-RESULTS-openai.md` with per-URL pass/fail rows and the aggregate score. The scaffolded skeleton in that file documents the expected shape — the harness fills it in.

Operator action after the run:
- Review per-URL results; spot-check 2–3 failures to confirm they are LLM-extraction failures rather than infrastructure failures (e.g., network timeout, missing key).
- Add per-URL LangWatch trace IDs in the table's `LangWatch trace` column (the harness leaves this blank).
- Record the aggregate score in the `openai_score` frontmatter of this file.

### 2. (Optional) Anthropic companion run

```bash
export GATHER_FROM_URL_API_TOKEN=<anthropic_key>
uv run experiments.gather_from_url --backend anthropic --eval-set .planning/phases/23-url-ingestion-topic-2/23-EVAL-SET.md
```

Output lands in `23-EVAL-RESULTS-anthropic.md`. Anthropic is NOT a merge gate; record the aggregate for completeness.

### 3. End-to-end Telegram smoke (BLOCKING — D-09 / D-24)

Send a real Telegram message to Robotina staging:

> "agregá esta receta: https://www.paulinacocina.net/receta-de-tarta-de-manzana/47322"

Verify in order:
- (a) Robotina respond()s pre-batch in Spanish ("voy con esa receta…" or similar).
- (b) `add-recipe-from-url` workflow appears in the rq-dashboard with `shared_context.recipe_url` populated.
- (c) The workflow drains through gather-from-url → instructions → ingredients → metadata → load → finalize-outcome.
- (d) The Wake invocation respond()s post-batch with the recipe name + slug.
- (e) The recipe appears in the household-manager backend (visible in the recipes list).

Record the URL tested and overall outcome in the table below.

### 4. Write the verdict

Edit this file's frontmatter:

- `verdict: pass` — OpenAI ≥ 17/21 AND Telegram smoke passed → Phase 23 merges; Task 2 of 23-07 ticks REQUIREMENTS.md.
- `verdict: fail` — OpenAI < 17/21 OR Telegram smoke failed → open gap-closure plan; do NOT tick REQUIREMENTS.md.
- `verdict: needs-revision` — partial pass with identified, addressable gaps → planner schedules a focused remediation plan.

Commit this file. Then signal `approved verdict=<value>` to the orchestrator to resume the deferred Task 2 (REQUIREMENTS.md ticks).

---

## OpenAI staging (MERGE GATE)

Aggregate: `<X/21>` (≥ 17/21 required per D-12).

See `.planning/phases/23-url-ingestion-topic-2/23-EVAL-RESULTS-openai.md` for per-URL detail.

Notes (operator-narrative):

```
<patterns, failure clusters, locale-unit observations, JS-gated site behavior, etc.>
```

## Anthropic companion (optional)

Aggregate: `<X/21>`.

See `.planning/phases/23-url-ingestion-topic-2/23-EVAL-RESULTS-anthropic.md`.

Notes:

```
<optional>
```

## Ollama dev (informational, optional)

Aggregate: `<X/21 — or "not run">`.

Notes:

```
<optional>
```

## Telegram end-to-end

| Field | Value |
|-------|-------|
| URL tested | `<https://… — operator fills>` |
| Pre-batch respond() observed | `<yes/no>` |
| Workflow ran add-recipe-from-url end-to-end | `<yes/no>` |
| Post-batch respond() observed | `<yes/no>` |
| Recipe visible in backend | `<yes/no>` |
| Outcome | `<pass / fail with notes>` |

## Verdict

`verdict: <pass | fail | needs-revision>`

Rationale:

```
<operator-narrative — why this verdict given the evidence above>
```

---

## References

- D-09 (manual gate), D-11 (per-URL scoring), D-12 (backend gate hierarchy), D-13 (file set), D-24 (load-bearing manual gate) in `.planning/phases/23-url-ingestion-topic-2/23-CONTEXT.md`.
- 21-URL eval set: `.planning/phases/23-url-ingestion-topic-2/23-EVAL-SET.md`.
- Harness: `experiments/gather_from_url.py` (registered as `uv run experiments.gather_from_url`).
- REQUIREMENTS impacted on `verdict: pass`: URL-01, URL-02, URL-03, URL-04, URL-05, URL-06, EXP-02.
