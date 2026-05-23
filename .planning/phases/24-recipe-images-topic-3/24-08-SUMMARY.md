---
phase: 24-recipe-images-topic-3
plan: 08
subsystem: experiments
tags: [experiment-harness, wake-context-eval, synthetic-fixture, langwatch-trace, manual-gate, d-08b, v007-acceptability, pyproject-script, claude-md]

# Dependency graph
requires:
  - phase: 24-recipe-images-topic-3
    plan: 05
    provides: "WORKFLOW_REGISTRY carries recipe-image step inline-duplicated in both variants (Wave 5 dependency; no runtime touch from this plan)"
provides:
  - "experiments/robotina_wake.py — synthetic wake-context Robotina eval harness with 4 D-08b fixture rows (single-success-with-image, single-success-without-image (LOAD-BEARING for D-08), single-failure, mixed-batch-three-recipes)"
  - "Stub Respond / Terminate / StartWorkflow tools wired identically to production handle-incoming-message agent surface; no DB / Redis / Telegram side effects"
  - "LangWatch tracer per fixture row tagged experiment=robotina-wake-eval, phase=24, prompt_version=V007, label, image_present_values"
  - "24-WAKE-RESULTS-<backend>.md emitter with verdict: pending frontmatter + per-row results table + per-row details + D-08 V007 verdict checklist for operator (24-09) review"
  - "pyproject.toml [project.scripts] entry experiments.robotina_wake (sibling to 24-07's experiments.recipe_image)"
  - "CLAUDE.md installation reference for experiments.robotina_wake"
affects: [24-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Synthetic-input eval harness for an LLM agent: in-memory Pydantic input construction (synthetic_wake_input) feeds the production AgentConfig's prompt + skills, with capture-only Stub tools mirroring the production tool surface (name + return_direct + args_schema identical). Zero DB / Redis / Telegram side effects."
    - "Backend-agnostic agent build for an existing AgentConfig: clone model_config dict, swap provider + model + url for the chosen backend (ollama / openai / anthropic), keep prompt_path + skills + response_format_model from the registry."
    - "Per-row LangWatch trace via langwatch.langchain.LangChainTracer (matches gather_from_url + multi_recipe_eval); trace_id captured after the with-block and surfaced in the markdown report so operator can deep-link from the verdict table."
    - "Per-row stub buffer reset (`for stub in stubs.values(): stub.calls.clear()`) inside run_one so each row's captures are isolated even when the same agent instance is reused across rows."

key-files:
  created:
    - "experiments/robotina_wake.py"
  modified:
    - "pyproject.toml"
    - "CLAUDE.md"

key-decisions:
  - "Reused the multi_recipe_eval Stub Respond / Terminate / StartWorkflow tools verbatim (same name, description, return_direct, args_schema, call-capture semantics). Rationale: the wake-context agent surface IS the same handle-incoming-message surface — same AgentConfig, same V007 prompt. The stubs are the production-mirror pattern this phase + Phase 22 standardized on; reimplementing them would invite drift."
  - "Did NOT inject HouseholdManagerApiTool on the wake-turn stubs. Production wake-context dispatch (jobs.py InvocationTrigger.WORKFLOW_COMPLETION branch) DOES inject it — but v1.1 wake replies don't need backend reads, and if the agent attempts one during the eval, that itself is a useful observation for D-08b (visible in the LangWatch trace + as an absent respond() text). Documented inline in build_agent."
  - "Backend choices = {ollama, openai, anthropic} (mirrors gather_from_url + multi_recipe_eval) — gives the operator a comparison point across providers. Default-model selection follows the multi_recipe_eval convention (OPENAI_EVAL_MODEL / ANTHROPIC_EVAL_MODEL env overrides; gpt-4o-mini / claude-3-5-sonnet-latest as fallbacks)."
  - "synthetic_wake_input lazy-imports robotina.queue.task_types so build_fixture_rows() (which returns plain dicts) can be exercised from the verify-time inline Python snippet without loading SQLAlchemy. This mirrors the recipe_image.py lazy-import pattern from 24-07 and keeps --help cheap."
  - "Markdown report has BOTH a summary table (label / outcomes_summary / wake_reply / acceptable Y/N / trace_id) AND a per-row details section (synthetic user message in a code fence + numbered respond() texts + start-workflow calls + trace_id). The summary table is what the operator scans; the details section is what they cite in the verdict notes. The load-bearing single-success-without-image row is explicitly labeled 'LOAD-BEARING for D-08' in its Y/N cell so the operator can't miss it."

patterns-established:
  - "Wake-context agent eval pattern: synthetic WakeInvocationInput → production AgentConfig with V007 prompt → Stub Respond/Terminate/StartWorkflow → capture respond() texts → verdict-pending markdown emit. Reusable for any future wake-turn prompt iteration (V008+) or wake-trigger type."
  - "Empirical V007-acceptability gate via a single load-bearing row (single-success-without-image): if D-08 is empirically rejected by 24-09's operator review, the verdict triggers a V008 fork as a v1.2 follow-up. The fixture set + harness produce the evidence; no code change ships without it."

requirements-completed:
  - EXP-04
  - EXP-06

# Metrics
duration: ~10min
completed: 2026-05-22
---

# Phase 24 Plan 08: experiments.robotina_wake synthetic wake-context eval Summary

**Shipped the synthetic wake-context Robotina eval harness: 4 D-08b fixture rows (success+image_present=True, success+image_present=False [LOAD-BEARING for D-08 V007 acceptability], single-failure, mixed-batch-three-recipes), a runnable `uv run experiments.robotina_wake --backend {ollama|openai|anthropic}` script that constructs in-memory `WakeInvocationInput` objects and invokes the wake-context Robotina agent (V007 prompt) with capture-only Stub tools, and the `pyproject.toml` + `CLAUDE.md` script declarations (EXP-06). The harness emits a `verdict: pending` markdown report with a load-bearing D-08 V007 verdict checklist for operator (24-09) review.**

## Performance

- **Duration:** ~10 minutes
- **Tasks:** 2 / 2
- **Files created:** 1 (`experiments/robotina_wake.py`)
- **Files modified:** 2 (`pyproject.toml`, `CLAUDE.md` — surgical/additive sibling to 24-07's entries)
- **Commits:** 2 task commits

## Accomplishments

### Task 1 — experiments/robotina_wake.py harness (commit `4c0eadd`)

- Created `experiments/robotina_wake.py` (756 lines; target was ≥150, longer because the synthetic-input construction + Stub tool surface + per-row run + markdown emitter each pull their own blocks, mirroring the 24-07 recipe_image and Phase 22 multi_recipe_eval shape).
- Module header documents the D-10 / EXP-04 purpose, the 4 D-08b fixture rows, the load-bearing row, the no-side-effects guarantee, backend semantics, and prerequisites.
- Constants: `PHASE = "24"`, `PROMPT_VERSION = "V007"`, `EXPERIMENT_NAME = "robotina-wake-eval"`, `DEFAULT_OUT_TEMPLATE = ".planning/phases/24-recipe-images-topic-3/24-WAKE-RESULTS-{backend}.md"`.
- `build_fixture_rows() -> list[dict]` returns the canonical D-08b fixture-row specs (label + outcomes list with status / workflow_type / outcome dict / recipe_query). Each spec is a plain dict so the verify-time Python snippet can introspect without loading SQLAlchemy.
- `synthetic_wake_input(spec) -> WakeInvocationInput` lazy-imports `AddRecipeOutcome` / `WorkflowOutcomeSummary` / `WakeInvocationInput`, assigns random `workflow_run_id` / `previous_invocation_id` / `conversation_id` UUIDs, and produces a real Pydantic model. The `to_user_message()` method on `WakeInvocationInput` (already in production) renders the Spanish wake prompt verbatim.
- Capture-only Stub tools: `StubRespondTool` (records `{"text": text}` per call, `return_direct=False`), `StubStartWorkflowTool` (records `{workflow_type, input}`, `return_direct=False`, returns a fake `workflow_run_id`), `StubTerminateTool` (records `{terminated: True}`, `return_direct=True`). Tool `name` + description + args_schema mirror the production tools verbatim so the LLM sees zero surface difference. Per-row buffer reset in `run_one()` keeps captures isolated.
- `build_agent(backend_name)`: pulls `get_agent_config("handle-incoming-message")`, clones `model_config` and swaps provider/model/url for the chosen backend, builds `make_backend(model_config)`, wires Stub tools + read-skill tool (skills=["household-manager"] preserved from registry), reads V007 prompt + appends skill index, and calls `backend.create_agent(system_prompt=..., tools=..., response_format=None)`. Returns `(agent, config_used, stubs)`.
- `run_one(agent, spec, stubs, backend, config_meta) -> RowResult`: builds the synthetic input, resets stub buffers, creates a `langwatch.langchain.LangChainTracer(metadata={experiment, phase, prompt_version, label, n_outcomes, image_present_values, backend, model, provider})`, invokes the agent inside the tracer context, captures respond_texts / start_workflow_calls / terminated / trace_id, returns a `RowResult` dataclass.
- `write_results(out_path, backend, results, config_meta, operator)`: emits per-backend markdown with YAML frontmatter (`verdict: pending`, backend, model, prompt_version=V007, phase=24, date, operator), aggregate summary, per-row results table (label / outcomes_summary / wake_reply / acceptable Y/N / trace_id), per-row details section (synthetic user message in a code fence + numbered respond() texts + start-workflow calls + trace_id), D-08 V007 verdict checklist with the load-bearing row callout, and a trailing `verdict: pending` line.
- `main()` CLI: `--backend {ollama,openai,anthropic}` (required), `--out` (defaults to `DEFAULT_OUT_TEMPLATE`), `--limit` (default 4 — all rows), `--operator` (default `$USER`). Flushes LangWatch tracer provider before writing results.

### Task 2 — pyproject.toml + CLAUDE.md entries (commit `a61b037`)

- `pyproject.toml [project.scripts]`: added one line `"experiments.robotina_wake" = "experiments.robotina_wake:main"` immediately after the existing `experiments.recipe_image` line (24-07). No reflow of surrounding entries.
- `CLAUDE.md`: added one commented installation reference for `experiments.robotina_wake` next to the existing `experiments.recipe_image` comment in the Installation section. Mirrors the format used by 24-07.
- No new env var required — the harness uses existing LLM env vars (`HANDLE_INCOMING_MESSAGE_API_TOKEN` for openai/anthropic, ollama runs against `OLLAMA_URL`).
- Sibling 24-07 entry (`experiments.recipe_image`) remains intact. Verified by `grep -c 'experiments.recipe_image" = "experiments.recipe_image:main' pyproject.toml` → 1.

## Test Results

- Acceptance grep checks (all pass).
- `uv run python -c "import experiments.robotina_wake; experiments.robotina_wake.main"` → exit 0.
- `uv run experiments.robotina_wake --help` → exit 0, shows the expected CLI.
- `uv run python -c "import experiments.recipe_research, experiments.recipe_load, experiments.gather_from_url, experiments.recipe_image, experiments.robotina_wake"` → exit 0 (no regression of sibling experiments).
- `synthetic_wake_input` round-trip on all 4 fixture rows produces valid `WakeInvocationInput` instances; `to_user_message()` renders the Spanish wake prompt with success+slug, success-no-slug, failure+reason, and mixed-batch lines as expected.
- `uv run pytest tests/queue/test_finalize_outcome.py -q` → **16 passed** (no regression on the closest Phase 24 test surface).
- The full repo suite was not re-run; per 24-07's recorded baseline (423 passed / 38 failed / 74 errors, all failures/errors pre-existing infra issues — Postgres unreachable, langwatch credentials, dashboard auth), this plan touches no production code path that would invalidate the baseline.

## Acceptance grep counts

| Check | Expected | Actual |
|-------|----------|--------|
| `wc -l experiments/robotina_wake.py` | ≥150 | 756 |
| `grep -c 'def main' experiments/robotina_wake.py` | 1 | 1 |
| `grep -c 'PHASE = "24"' experiments/robotina_wake.py` | 1 | 1 |
| `grep -c 'WakeInvocationInput' experiments/robotina_wake.py` | ≥2 | 9 |
| `grep -c 'langwatch' experiments/robotina_wake.py` | ≥1 | 6 |
| `grep -c 'D-08' experiments/robotina_wake.py` | ≥1 | 14 |
| `grep -E 'from sqlalchemy\|import redis\|from rq' experiments/robotina_wake.py \| wc -l` | 0 | 0 |
| All 4 D-08b labels present (Python assertion) | yes | yes |
| Load-bearing row `image_present=False` (Python assertion) | yes | yes |
| `grep -c 'experiments.robotina_wake" = "experiments.robotina_wake:main' pyproject.toml` | 1 | 1 |
| `grep -c "experiments.robotina_wake" CLAUDE.md` | ≥1 | 1 |
| `grep -c 'experiments.recipe_image" = "experiments.recipe_image:main' pyproject.toml` (no 24-07 regression) | 1 | 1 |
| `uv run python -c "import experiments.robotina_wake; print('ok')"` | exit 0 | exit 0 |
| `uv run python -c "import experiments.recipe_research, experiments.recipe_load, experiments.gather_from_url, experiments.recipe_image, experiments.robotina_wake"` | exit 0 | exit 0 |
| `uv run pytest tests/queue/test_finalize_outcome.py -q` | exit 0 | 16 passed |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Robustness] Reused capture-only Stub tools from multi_recipe_eval verbatim**

- **Found during:** Task 1 — drafting the agent build path.
- **Issue:** Plan's example code sketched a `from robotina.llm import build_llm_backend` import and a "tools list: probably empty or stubs" comment with no concrete pattern. The production wake dispatch in `jobs.py` injects `RespondTool` + `StartWorkflowTool` (both of which require Redis to enqueue), `TerminateTool`, and `HouseholdManagerApiTool` (requires backend HTTP) — running any of those in a synthetic-eval context would either error or produce side effects. The plan acknowledged this and said the executor "MAY simplify by directly calling Robotina's prompt template" — but losing the multi-tool surface would change the LLM's behavior compared to the real wake-context turn.
- **Fix:** Reused the Stub Respond / Terminate / StartWorkflow tools from `experiments/robotina/multi_recipe_eval.py` (Phase 22) verbatim. Identical surface (same `name`, description, args_schema, return_direct) to the production tools, but capture-only — they record calls and return canned strings, no Redis / HTTP / DB. The LLM sees the same tool surface as production wake turns; the harness just observes what it does.
- **Files modified:** `experiments/robotina_wake.py`
- **Commit:** `4c0eadd`

**2. [Rule 2 — Robustness] Wrapped LangWatch agent.invoke in try/except around the with-tracer block**

- **Found during:** Task 1 — drafting `run_one`.
- **Issue:** If `agent.invoke` raises (LLM provider unreachable, prompt rejection, tool surface mismatch), the entire harness would fail to produce the markdown report — a deal-breaker for the operator who needs the verdict file even when one row blows up.
- **Fix:** `run_one` catches any exception from the `with tracer: agent.invoke(...)` block, sets `result.error`, and returns the partial result. The markdown table renders `ERROR: <message>` in the wake_reply cell for that row. The operator still gets the other 3 rows' verdicts.
- **Files modified:** `experiments/robotina_wake.py`
- **Commit:** `4c0eadd`

**3. [Rule 2 — Robustness] Per-row stub buffer reset**

- **Found during:** Task 1 — drafting `run_one`.
- **Issue:** Plan sketched no buffer-isolation logic. Without resetting between rows, row N's `respond_texts` would include rows 1..N-1's accumulated calls (stub Field default_factory creates the list once at instance construction).
- **Fix:** `for stub in stubs.values(): stub.calls.clear()` at the top of `run_one`. Captures are now isolated per row.
- **Files modified:** `experiments/robotina_wake.py`
- **Commit:** `4c0eadd`

### Cosmetic refresh (not a Rule 1 fix — behavior unchanged)

**4. CLAUDE.md commented installation reference (matches 24-07 format)**

- **Found during:** Task 2.
- **Issue:** Plan's verbatim CLAUDE.md snippet recommended a markdown table row. CLAUDE.md does NOT have an "Experiments" table — only the single commented-out `# "experiments.recipe_research" = ...` reference inside the Installation section, plus the line 24-07 added for `experiments.recipe_image`. Inventing a new table would cross-cut 24-07's pattern.
- **Fix:** Added a sibling commented-out reference for `experiments.robotina_wake` immediately after the 24-07 `experiments.recipe_image` comment. Same format. Future plans that add experiments scripts continue this pattern with one line each.
- **Files modified:** `CLAUDE.md`
- **Commit:** `a61b037`

### Deferred Items

None.

## Threat Flags

No new threat surface introduced. The harness:
- Constructs synthetic `WakeInvocationInput` objects in memory; no DB writes, no Redis enqueue, no HTTP requests to backend.
- Calls the configured LLM provider (Ollama / OpenAI / Anthropic) and the LangWatch tracer — same network egress as every other experiments script.
- Reuses the production V007 prompt + skills (read-only); no prompt modification.
- LangWatch trace metadata includes a `label` string (`single-success-with-image`, etc.) and `image_present_values` (booleans) — neither is secret.
- No new env var required; LLM tokens flow through existing `HANDLE_INCOMING_MESSAGE_API_TOKEN` (production) and the ollama/openai/anthropic provider env vars.

## Commits

| Task | Commit    | Description |
|------|-----------|-------------|
| 1    | `4c0eadd` | feat(24-08): add experiments.robotina_wake synthetic wake-context eval (EXP-04) |
| 2    | `a61b037` | chore(24-08): wire experiments.robotina_wake in pyproject.toml + CLAUDE.md (EXP-06) |

## Self-Check: PASSED

- File `experiments/robotina_wake.py`: FOUND
- File `pyproject.toml` modified: FOUND (entry at line 52)
- File `CLAUDE.md` modified: FOUND (commented reference)
- File `.planning/phases/24-recipe-images-topic-3/24-08-SUMMARY.md`: FOUND (this file)
- Commit `4c0eadd`: FOUND
- Commit `a61b037`: FOUND
