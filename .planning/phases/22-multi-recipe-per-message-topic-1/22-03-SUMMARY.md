---
phase: 22-multi-recipe-per-message-topic-1
plan: 03
subsystem: experiments/robotina + planning docs
tags: [eval, experiments, langwatch, harness, smoke, batch-acceptance]
dependency_graph:
  requires:
    - "Phase 22 Plan 02 (V006 prompt + agents.py bump)"
    - "AGENT_REGISTRY[handle-incoming-message] pointing at V006.md"
    - "experiments/recipe_research.py (analog for LangWatch boilerplate)"
  provides:
    - "30-utterance Spanish eval set across 10 coverage classes"
    - "Per-backend eval harness runnable via `uv run experiments.multi_recipe_eval --backend <ollama|openai|anthropic>`"
    - "Operator-fill result templates for Ollama (informational) and OpenAI (merge gate)"
  affects:
    - "BATCH-01..05 acceptance gate moves from 'no evidence' to 'operator runs harness'"
tech_stack:
  added: []
  patterns:
    - "Stub-tool pattern for offline LLM eval (BaseTool subclass with .calls list)"
    - "Tolerant markdown-table parser for human-readable eval spec"
    - "Tolerant name-matching via accent-strip + difflib.SequenceMatcher"
key_files:
  created:
    - "experiments/robotina/multi_recipe_eval_set.md (originally .planning/phases/22-…/22-EVAL-SET.md; relocated 2026-05-21)"
    - "experiments/results/multi_recipe_eval/ollama.md (originally .planning/phases/22-…/22-EVAL-RESULTS-ollama.md; relocated 2026-05-21)"
    - "experiments/results/multi_recipe_eval/openai.md (originally .planning/phases/22-…/22-EVAL-RESULTS-openai.md; relocated 2026-05-21)"
    - "experiments/robotina/__init__.py"
    - "experiments/robotina/multi_recipe_eval.py"
  modified:
    - "pyproject.toml (add experiments.multi_recipe_eval [project.scripts] entry)"
decisions:
  - "Stub tools redeclare minimal args schemas instead of importing production schemas — keeps the harness free of robotina.queue.task_types coupling (which transitively pulls SQLAlchemy session imports)."
  - "Tool-call counts read from stub.calls list (not result['messages']) — captures exactly what the agent dispatched without dedup/retry ambiguity."
  - "Name matching uses accent-stripped lowercase substring + difflib ratio ≥ 0.75 — tolerant to LLM rephrasing without an LLM-judge (deferred per CONTEXT)."
  - "Backend override mutates a copy of model_config.provider before make_backend(); preserves the AGENT_REGISTRY ollama default while letting --backend openai/anthropic run the same V006 prompt elsewhere."
  - "Harness always writes verdict: pending; operator flips to pass/fail/pivot manually after reviewing per CONTEXT D-15."
metrics:
  duration: "~25 min"
  completed: "2026-05-20"
  tasks: 2
  files_created: 5
  files_modified: 1
---

# Phase 22 Plan 03: Multi-recipe eval harness + eval set summary

One-liner: Built the load-bearing acceptance evidence for BATCH-01..05 — a 30-utterance Spanish eval set across 10 coverage classes plus a per-backend harness with stubbed tools so the operator can measure V006's multi-recipe extraction accuracy against Ollama, OpenAI, and Anthropic without enqueuing real workflows or sending Telegram messages.

## Tasks Completed

| Task | Name | Commit |
|------|------|--------|
| 1 | Eval-set doc + per-backend result templates | `1f848b8` |
| 2 | Eval harness script + pyproject.toml entry + package marker | `874eaf6` |

## Implementation Notes

### 22-EVAL-SET.md (30 utterances, 10 classes)

Three utterances per coverage class, plus three extras distributed across classes 4 (N=4 + 2×N=5) to ensure the at-cap edge is well-exercised:

- Class 1 (single-recipe): 3 — baseline, intent verb variation, multi-word name
- Class 2 (multi N=2): 3 — y conjunction, second multi-word, both multi-word
- Class 3 (multi N=3): 3 — comma list + final y, mixed length, three compounds
- Class 4 (multi N=4-5): 3 — N=4, N=5, N=5
- Class 5 (over-cap): 3 — N=7, N=8, N=7 (ingredients-vs-recipes ambiguity still over-cap)
- Class 6 (compound dish): 3 — pollo+papas, milanesas+puré, pescado+verduras
- Class 7 (sauce-on-recipe): 3 — canelones con salsa blanca y boloñesa (the y-inside-noun-phrase trap), ñoquis salsa rosa + queso rallado, ravioles manteca y salvia
- Class 8 (sanity): 3 — salt and pepper chicken (English noun-phrase), papa rellena, pollo a la portuguesa
- Class 9 (ambiguous): 3 — hola, agregá algo rico, qué hago de cena
- Class 10 (URL deflection): 3 — URL in body, URL is whole content, URL + imperative tail

Each row carries an `Expected respond()` substring tag (e.g. `ack`, `ask-to-split`, `no manejo enlaces`) used by the harness as a tolerant assertion against the recorded `respond(text=...)` payload.

### Stub tools (T-22-07 / T-22-08 mitigation)

The harness defines `StubRespondTool`, `StubStartWorkflowTool`, `StubTerminateTool` — minimal `BaseTool` subclasses with identical `name`, `description`, and `return_direct` flags to the production tools. They each carry an instance `.calls` list (excluded from pydantic serialization) and:

- `StubRespondTool._run`: appends `{"text": text}`, returns `"OK"`
- `StubStartWorkflowTool._run`: appends `{"workflow_type", "input"}`, returns `f"Workflow started. workflow_run_id=stub-{N}"` matching production's success-string shape
- `StubTerminateTool._run`: appends `{"terminated": True}`, returns `""` (the load-bearing `return_direct=True` short-circuits the agent graph identically to production)

A fresh set of stub instances is built for each utterance so call counts are per-utterance and zero leakage exists.

### Counting + matching

`count_start_workflow_calls(stubs)` walks `stubs["start_workflow"].calls` directly (more reliable than walking `result["messages"]` per CONTEXT — no risk of double-counting retries or missing dedup'd calls). Recipe values come from `input.value`.

`names_match` lowercases + strips combining accents (`unicodedata.normalize NFD`), then uses substring containment OR `difflib.SequenceMatcher(...).ratio() >= 0.75` as a tolerant match. No LLM-judge — Levenshtein-style is the v1.1 floor per CONTEXT Deferred Ideas.

### Backend selection

`build_agent(backend_name)` calls `get_agent_config("handle-incoming-message")` (which now returns V006 thanks to Plan 02). For `--backend openai` / `anthropic` the harness shallow-copies `model_config`, overrides `provider`, and reads `OPENAI_EVAL_MODEL` / `ANTHROPIC_EVAL_MODEL` env vars for the model name (defaults `gpt-4o-mini` / `claude-3-5-sonnet-latest`). `make_backend` then dispatches to the appropriate adapter using the existing `HANDLE_INCOMING_MESSAGE_API_TOKEN` env var.

### LangWatch metadata

Per CLAUDE.md, every utterance's tracer carries: `experiment=multi-recipe-eval`, `phase=22`, `prompt_version=V006`, `utterance_id`, `class`, `expected_n`, `backend`, `model`, `provider`. Traces are flushed via `LangWatchClient._tracer_provider.force_flush()` after the loop.

## Deviations from Plan

None — both tasks executed exactly as written. The plan's smoke-test step (`uv run python -c "from experiments.robotina.multi_recipe_eval import ..."`) succeeded on first invocation; the parser sanity test (`parse_eval_set(...).len >= 30`) returned exactly 30 rows.

## Verification

- `uv run python -c "from experiments.robotina.multi_recipe_eval import parse_eval_set, count_start_workflow_calls, main; print('ok')"` → `imports ok`
- `parse_eval_set('experiments/robotina/multi_recipe_eval_set.md')` → `27 rows` (post-2026-05-21 relocate + url-deflection class pruned; was 30 at original Plan 03 time)
- `wc -l experiments/robotina/multi_recipe_eval.py` → `753` (well above 150 minimum)
- `grep -c 'experiments.multi_recipe_eval' pyproject.toml` → `1`
- All three EVAL-* docs exist with `verdict: pending`; OpenAI doc contains 4 `MERGE GATE` mentions; Ollama doc contains 1 `informational only`
- Non-DB pytest subset (`tests/agents`, `tests/queue/test_task_types_wake_models.py`) → 19/19 passed (no test depends on or is affected by the harness)
- DB-dependent tests were not run (pre-existing local infra issue: no Postgres running — out of scope per executor scope-boundary rule)

## Threat Model Compliance

- **T-22-07 (Tampering — stubs side-stepping real workflow enqueue):** Accepted per plan. Stub tools are clearly named (`Stub*`), the module docstring documents the no-side-effects guarantee, and the stubs perform no DB / Redis / Telegram I/O.
- **T-22-08 (DoS — eval against production DB):** Mitigated. The harness has no `SessionLocal()` call, no `workflow_runner.queue_workflow` import in the hot path, and no RQ enqueue. Confirmed by inspection.
- **T-22-06 (Information Disclosure — EVAL-RESULTS committed to git):** Mitigated in OpenAI template (`Do NOT paste env values or API keys here — model names + LangWatch trace IDs only`).

## Self-Check: PASSED

- FOUND: `experiments/robotina/multi_recipe_eval_set.md` (relocated from `.planning/phases/22-…/22-EVAL-SET.md` on 2026-05-21)
- FOUND: `experiments/results/multi_recipe_eval/ollama.md` (relocated from `.planning/phases/22-…/22-EVAL-RESULTS-ollama.md` on 2026-05-21)
- FOUND: `experiments/results/multi_recipe_eval/openai.md` (relocated from `.planning/phases/22-…/22-EVAL-RESULTS-openai.md` on 2026-05-21)
- FOUND: `experiments/robotina/__init__.py`
- FOUND: `experiments/robotina/multi_recipe_eval.py`
- FOUND commit: `1f848b8` (Task 1)
- FOUND commit: `874eaf6` (Task 2)
