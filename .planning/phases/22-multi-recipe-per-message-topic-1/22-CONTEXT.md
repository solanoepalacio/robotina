# Phase 22: Multi-recipe per message (Topic 1) — Context

**Gathered:** 2026-05-20
**Status:** Ready for planning
**Mode:** `--auto` (Auto Mode active — every D-NN below is Claude's call with rationale; user can redirect any decision before `/gsd:plan-phase 22` runs.)

<domain>
## Phase Boundary

Teach Robotina to fan out N add-recipe workflows (1 ≤ N ≤ 5) from one Spanish user
message and compose a single consolidated final reply on wake. The multi-call
tool surface already exists from Phase 21; outcome aggregation and the wake
invocation path already exist from Phase 20. Phase 22 is **primarily a Robotina
prompt change (V005 → V006), a small wake-helper polish, and an eval set**.

**In scope (planner picks final wave structure):**

1. **Robotina prompt V006** in `src/robotina/agent/prompts/robotina/V006.md` —
   V005 + multi-recipe extraction examples + ambiguity-via-respond worked
   examples + soft-cap-at-5 worked example. V005 stays for rollback.
2. **`agents.py` bump** — `handle-incoming-message` agent prompt path
   `V005.md` → `V006.md` (same one-line edit as Phase 21 D-10).
3. **`WakeInvocationInput.to_user_message()` polish** in
   `src/robotina/queue/task_types.py:379` — include `recipe_slug` on success
   lines (BATCH-03 "name+slug"); include the original `recipe_query` on
   failure lines (so failures read "Canelones falló: …" not "(receta sin
   nombre) falló"); drop the "(usuario ya fue notificado)" parenthetical
   (legacy from Phase 20 V004 when the `notify` step still pre-notified —
   Phase 21 removed `notify`; the user only gets the pre-batch ack +
   wake reply now).
4. **Stable sibling-run ordering** in `_check_and_dispatch_wake`
   (`workflow_runner.py:195`) — add `.order_by(WorkflowRun.created_at.asc())`
   on the sibling-runs query so `WakeInvocationInput.outcomes` arrive in
   enqueue order (best available proxy for user-input order under parallel
   tool calls — Pitfall 5). Concurrency=1 + sequential `start-workflow`
   calls on a single LLM turn make enqueue order match user-utterance
   order in practice; strict guarantee would require a `batch_index` field
   on tool args (deferred — Pitfall 5 says ordering is acceptable for v1.1).
5. **Expose `recipe_query` to wake** — add `recipe_query: str | None = None`
   to `WorkflowOutcomeSummary`; populate it in `_check_and_dispatch_wake`
   from `WorkflowRun.shared_context["recipe_query"]`. Planner picks the
   exact mechanism (this is the lightest-touch option — no
   `AddRecipeOutcome` schema change, no migration).
6. **Eval set** — `22-EVAL-SET.md` (≥ 30 Spanish utterances with expected
   N + expected names) committed under the phase dir. Covers single,
   N=2/3/4/5, over-cap (N>5), compound-dish ambiguous ("pollo al horno con
   papas"), sauce-on-recipe ("canelones con salsa blanca y boloñesa"),
   sanity ("salt and pepper chicken" — must NOT split), ambiguous /
   no-specific-recipe ("agregá algo rico"), and free-text Spanish-only
   (URL+text cross-source case is intentionally NOT included — Phase 23).
7. **Eval harness** — `experiments/robotina/multi_recipe_eval.py`. One
   concrete script (per memory `feedback_avoid_premature_abstraction` —
   no generic eval framework). Iterates the YAML/JSON eval-set, dispatches
   each utterance through the existing `handle-incoming-message` agent
   against the LLM backend selected by env (Ollama for dev, OpenAI for
   staging, optionally Anthropic), captures per-utterance tool-call counts
   from the agent result, and emits a per-backend markdown report
   (`22-EVAL-RESULTS-<backend>.md`) with a go/no-go line. LangWatch
   instrumentation stays active per CLAUDE.md so traces land in the
   experiment collection.
8. **`22-SMOKE.md`** — operator's final go/no-go verdict file (mirrors the
   21-SMOKE.md pattern). Verdict references the EVAL-RESULTS reports.
9. **REQUIREMENTS.md ticks** for BATCH-01..05 in the final wave / smoke
   commit.

**Out of scope (deferred):**

- URL ingestion (URL-*) — Phase 23. V006 does NOT teach URL handling. If
  V006 sees a URL in the user message, it asks the user to wait
  ("todavía no manejo enlaces directos, ¿podés escribir el nombre?") or
  ignores the URL and treats free-text recipes. Phase 23's V007 adds URL
  routing.
- `recipe-image` (IMG-*) — Phase 24.
- New `ask_user(question)` tool (Pitfall 12 recommendation) — not added in
  Phase 22 (see D-04). `respond()` already covers ambiguity escalation
  semantically.
- Defensive code cap at N=5 — NOT added per BATCH-05 ("decided at prompt
  level, not enforced by code"). Prompt is the cap; the smoke set
  validates it.
- Strict user-utterance ordering (a `batch_index` field on
  `StartWorkflowTool` args) — deferred per Pitfall 5. `created_at`-based
  enqueue ordering is sufficient for v1.1.
- Compose Agent split (COMP-01) — v2.
- Conversation-history truncation (Pitfall 9 context bloat) — future
  hardening; not load-bearing for N ≤ 5 batches in v1.1.

</domain>

<decisions>
## Implementation Decisions

> **Auto-mode note:** Every D-NN below is Claude's call under the no-stopping
> system reminder. The user can redirect any decision before `/gsd:plan-phase 22` runs.

### Over-cap behavior (BATCH-05)

- **D-01: V006 prompt teaches "ask to split" as the default over-cap response.**
  If the user names > 5 recipes in one message, Robotina calls
  `respond(text="Son muchas recetas a la vez. ¿Probamos de a cinco? Decime cuáles vamos a empezar y arrancamos.")`
  then `terminate()` — **NO `start-workflow` calls are emitted**.
  - **Why ask-to-split (not "proceed with first 5"):** "proceed with 5" silently
    drops recipes 6+ — the user typed those deliberately. Asking preserves
    user agency and matches Pitfall 12's "ask once, save right" UX
    posture (Robotina cannot reorder the user's mental priority).
  - **No defensive code cap.** Per BATCH-05 ("decided at prompt level, not
    enforced by code"), `StartWorkflowTool` does not validate N. The
    prompt is the cap; the eval-set's over-cap rows validate the prompt
    holds. If the LLM ignores the cap and emits 50 calls, the smoke
    catches it.

### Eval set design (BATCH-01..05 acceptance + Pitfall 12)

- **D-02: One concrete eval harness, not a framework.**
  `experiments/robotina/multi_recipe_eval.py` — single script,
  `feedback_avoid_premature_abstraction` honored. Reuses the existing
  `LLMBackend` machinery + agent factory + LangWatch instrumentation
  (no new wiring). The script reads `22-EVAL-SET.md` (or a sibling
  `.yaml` if markdown parsing is painful — planner decides), runs each
  utterance through `handle-incoming-message`, counts the
  `start-workflow` tool calls per turn, compares against expected,
  emits a per-backend markdown report with verdict.
  - **Why a script and not a pytest suite:** smoke-style runs against
    paid backends (OpenAI staging) cannot live in CI — they're
    operator-triggered. The 30-utterance × 2-backend matrix is too
    expensive to gate on every PR. Manual smoke + committed results +
    go/no-go line is the established Phase 21 pattern (Phase 21 D-16).
  - **Why ≥ 30 utterances, not 30–50 like Pitfall 12 says:** 30 is the
    floor that meaningfully covers the ambiguity classes; sizing above
    that has diminishing returns until v2 when we have real user-message
    data to mine. The set can grow as the eval program matures.

- **D-03: Eval-set coverage classes (planner picks exact utterances; ≥ 30 total).**
  Each class needs ≥ 3 utterances:
  1. **Single-recipe (N=1)** — "agregá lentejas", "quiero hacer milanesas", etc.
  2. **Multi-recipe N=2** — "agregá canelones y pollo al horno"
  3. **Multi-recipe N=3** — "agregá canelones, pollo y arroz pilaf"
  4. **Multi-recipe N=4 or 5** — at-cap utterances
  5. **Over-cap N>5** — "agregá canelones, pollo, arroz, lentejas, milanesas, salmón, ravioles" — expected: 0 start-workflow calls, 1 respond(ask-to-split), 1 terminate.
  6. **Compound dish (ambiguous 1-vs-2)** — "agregá pollo al horno con papas" — expected: clarify via respond() OR emit 1 workflow (V006 must pick one and document; recommended: prefer FEWER → 1 workflow with the compound name as the query string).
  7. **Sauce-on-recipe (1 not 2)** — "agregá canelones con salsa blanca y boloñesa" — expected: 1 workflow.
  8. **Sanity / must-NOT-split** — "salt and pepper chicken", "papa rellena", "pollo a la portuguesa" — expected: 1 workflow per phrase. Small Ollama models notoriously split these.
  9. **Ambiguous non-recipe** — "hola", "agregá algo rico" — expected: 0 workflows, 1 respond(clarify), 1 terminate.
  10. **Cross-source (URL + text)** — NOT included in Phase 22 (deferred to Phase 23 — see Out of scope).

- **D-04: Pass thresholds.**
  - **OpenAI staging — merge gate**: ≥ 95% count accuracy on the full
    set (i.e. ≤ 1 wrong row out of 30 if the set is exactly 30; scale
    proportionally). ≥ 90% recipe-name accuracy on the multi-recipe
    rows (Levenshtein-based or LLM-judge — planner picks; LLM-judge is
    less code).
  - **Ollama dev — informational only.** Failures noted but do NOT block
    merge (`gpt-oss:20b` is the dev backend, not the production target).
    If Ollama drops below 70% the operator notes it in `22-SMOKE.md` for
    future model-upgrade tracking.
  - **Anthropic — optional.** Run only if the operator chooses; not
    required for merge.

- **D-05: Eval results file structure.** Each backend run produces
  `22-EVAL-RESULTS-<backend>.md` with: header (backend, model, date,
  operator), per-row table (utterance, expected N, observed N, recipe
  names observed, OK?, LangWatch trace), aggregate counts, go/no-go
  line. `22-SMOKE.md` is the operator's final verdict pointing at the
  per-backend results; mirrors Phase 21 D-13.

### Order preservation + wake reply format (BATCH-03, BATCH-04)

- **D-06: `ORDER BY workflow_runs.created_at ASC` in `_check_and_dispatch_wake`.**
  The sibling-runs query at `workflow_runner.py:195` currently has no
  `ORDER BY` — outcomes arrive in arbitrary DB-row order. Phase 22
  adds the clause. Rationale: under concurrency=1 + Phase 18's
  constructor-injected `invocation_id`, `start-workflow` tool calls
  serialize through a single agent process; each call writes a
  `WorkflowRun` row with `created_at = now()`. Enqueue order is the
  best available proxy for user-utterance order. Strict guarantee
  would require a `batch_index` field on tool args — deferred per
  Pitfall 5 (acceptable for v1.1).

- **D-07: `WakeInvocationInput.to_user_message()` polish.** Changes to
  the existing implementation at `task_types.py:379`:
  1. **Drop "(Wake-trigger; el usuario ya fue notificado.)"** — this
     parenthetical is legacy from Phase 20 V004 when the `notify` step
     pre-notified the user. Phase 21 removed `notify`; in v1.1 the user
     ONLY gets the pre-batch `respond()` ack + this wake reply. The
     parenthetical mis-trains the LLM into terse "you already heard
     from me" replies. Replace with a short instruction line if needed:
     "(Wake-trigger; el usuario espera el resumen final.)".
  2. **Success lines include recipe_slug**: "✓ Lentejas guisadas
     (slug: lentejas-guisadas)" — BATCH-03 "name+slug".
  3. **Failure lines include the original recipe_query** (D-08): "✗ canelones
     falló: no encontré la receta" — currently the failure line uses
     "(receta sin nombre)" if outcome is None (FAILED workflows have
     `outcome=None` because `finalize-outcome` only runs on DONE per
     Phase 20 D-03). Fix by surfacing the query string from
     `WorkflowOutcomeSummary.recipe_query` (D-08).

- **D-08: `WorkflowOutcomeSummary.recipe_query: str | None = None`**.
  Add the optional field; populate it in `_check_and_dispatch_wake`
  from `r.shared_context["recipe_query"]`. `None` is allowed for forward
  compatibility (e.g. Phase 23's URL-sourced workflows where the query
  string semantic is the URL itself; Phase 23 picks its own surfacing).
  - **Why not add to `AddRecipeOutcome`:** `AddRecipeOutcome` is the
    deterministic-step output (built by `finalize-outcome`). The
    original query lives on `WorkflowRun.shared_context`, not in
    artifacts. Less invasive to surface from the wake helper.

- **D-09: V006 wake-context reply composition rule.** V006 keeps V005's
  "compose ONE Spanish `respond()` summarizing all outcomes" rule and
  adds explicit worked examples for partial-failure (BATCH-04):
  - **Single-recipe success:** "Listo, guardé Lentejas guisadas
    (lentejas-guisadas)."
  - **Multi-recipe all-success:** "Listos los tres: Canelones
    (canelones-de-choclo), Pollo al horno (pollo-al-horno), Arroz pilaf
    (arroz-pilaf)."
  - **Multi-recipe partial failure (BATCH-04):** "Listos dos:
    Pollo al horno (pollo-al-horno), Arroz pilaf (arroz-pilaf).
    Canelones no salió — no encontré la receta. ¿Probamos con otro
    nombre?"
  - **Multi-recipe all-failure:** "No pude guardar ninguna: Canelones
    (no encontré la receta), Pollo (timeout). Probemos de a una."
  - Order matches the wake preamble (which is now ASC by `created_at`
    per D-06 — best available proxy for user-utterance order).
  - **NEVER call `respond()` once per outcome** (Phase 21 D-09 rule
    carries forward).

### Ambiguity handling (Pitfall 12)

- **D-10: No new `ask_user` tool.** V006 instead teaches: "If you
  cannot confidently determine the recipe count or one of the recipe
  names, call `respond(text="<Spanish clarifying question>")` and
  `terminate()` — do NOT start any workflows." Worked examples cover
  the compound-dish case ("pollo al horno con papas" → ambiguous;
  default = prefer-fewer, i.e. 1 workflow with the compound name) and
  the wholly-ambiguous case ("agregá algo rico" → clarify via respond).
  - **Why not add `ask_user`:** `respond()` is already a non-terminal,
    Spanish-text tool that maps 1:1 to "ask the user a question." Adding
    a sibling tool whose only difference is intent labelling would be
    premature abstraction (per memory
    `feedback_avoid_premature_abstraction` — wait until 3+ concrete
    instances). Phase 22 has exactly one instance.

- **D-11: V006 default for compound dishes — prefer FEWER recipes.**
  "Pollo al horno con papas" → 1 workflow with `value="pollo al horno
  con papas"` (the recipe-research-gather agent then decides if it's
  one dish or a "main + side" pairing — that's downstream's job, not
  Robotina's). Pitfall 12's "prefer FEWER recipes" guidance,
  operationalized. The eval set's compound-dish rows assert this.

- **D-12: Sauce-on-recipe always 1.** "Canelones con salsa blanca y
  boloñesa" → 1 workflow. V006 has an explicit worked example because
  small Ollama models tend to split this. The "y" conjunction inside
  a noun phrase is the trap.

### Test strategy (Claude's Discretion)

- **D-13: Automated regression tests** for code-path changes (`workflow_runner.py`
  ORDER BY clause, `WakeInvocationInput.to_user_message()` formatting,
  `WorkflowOutcomeSummary` schema):
  - `tests/queue/test_wake_helper_ordering.py` — three WorkflowRuns
    inserted with explicit `created_at` timestamps; assert
    `_check_and_dispatch_wake` builds `outcomes` in `created_at` ASC
    order.
  - `tests/queue/test_wake_invocation_input.py` (extend existing) —
    success line includes slug; failure line includes recipe_query;
    legacy "(usuario ya fue notificado)" string is absent.
  - `tests/queue/test_task_types.py` (extend) — `WorkflowOutcomeSummary`
    accepts `recipe_query=None` and `recipe_query="x"`.

- **D-14: Agent-surface test (mocked LLM)** — extend the existing
  `handle-incoming-message` agent test to assert the `V006.md` prompt
  loads (not V005). No multi-recipe behavior is asserted in unit tests
  — that's the eval set's job (the LLM IS the thing under test).

- **D-15: Manual eval is the load-bearing gate** — D-02..D-05 above.
  Operator-driven. Verification routes as `human_needed` until the
  operator commits `22-SMOKE.md` with `verdict: pass`. Mirrors Phase
  21 D-24.

- **D-16: V005 retained for rollback.** Per project convention
  (V001..V005 all in `src/robotina/agent/prompts/robotina/`).

### Claude's Discretion

- **Prompt file naming:** `src/robotina/agent/prompts/robotina/V006.md`.
  V006 forks V005 verbatim and adds the multi-recipe + ambiguity +
  over-cap sections.
- **Eval set storage:** the canonical eval set is a markdown table in
  `22-EVAL-SET.md` (human-readable, reviewable). The harness parses it
  (or a sibling YAML — planner picks). One file, two formats is
  acceptable if the YAML is auto-generated from the markdown.
- **Eval-results commit ordering:** code/prompt commits land first;
  REQUIREMENTS.md ticks + EVAL-RESULTS + 22-SMOKE.md verdict commit
  LAST (after operator runs the smoke).
- **No new env vars.** The harness reads the existing
  `RECIPE_RESEARCH_API_TOKEN` / Ollama URL / model env vars already used
  by experiments.
- **No new Alembic revision.** Phase 22 is pure code + prompt + eval.
  `WorkflowOutcomeSummary.recipe_query` is a Pydantic field, not a DB
  column. `WorkflowRun.shared_context` already stores `recipe_query`
  (Phase 5 contract).
- **Dashboard:** no new task-type labels; no template changes (no new
  agents). Out of scope.
- **`overrides/*.json` sync:** no agent changes → no overrides
  changes. The Phase 21 D-12 CI guard stays green.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 22: Multi-recipe per message (Topic 1)" — phase goal, 4 success criteria, dependency on Phase 21.
- `.planning/REQUIREMENTS.md` BATCH-01..05 — the five requirements this phase delivers.

### Architecture and pitfalls (load-bearing context)
- `.planning/research/PITFALLS.md` Pitfall 4 — `return_direct` removal lets LLM text leak; V006 inherits V005's "respond is the only user-visible channel" rule. No change for Phase 22 beyond worked examples.
- `.planning/research/PITFALLS.md` Pitfall 5 — `create_agent` does not expose `parallel_tool_calls=False`; multi-recipe ordering is provider-dependent. D-06 mitigates with `ORDER BY created_at ASC` on the wake helper.
- `.planning/research/PITFALLS.md` Pitfall 12 — Multi-recipe LLM parsing is unreliable. D-02..D-05 operationalize this with a 30-utterance eval set + per-backend harness + thresholds. D-10 declines the `ask_user(question)` tool recommendation.
- `.planning/research/PITFALLS.md` Pitfall 13 — `respond()` is sync but Telegram is async; V006 inherits Phase 21 D-01's queue-based send semantics. No change.
- `.planning/research/PITFALLS.md` "UX Pitfalls" table — "Silent multi-recipe partial failure" → BATCH-04's exact mitigation: `respond()` always summarizes ALL outcomes (success + failure) explicitly. D-09 V006 worked examples enforce this.
- `.planning/research/PITFALLS.md` "Performance Traps" — "Multi-recipe fan-out without cap" → BATCH-05's mitigation (D-01 ask-to-split).
- `.planning/research/ARCHITECTURE.md` §"Phase F — Multi-recipe prompt" (if section exists at that name) — Phase 22 IS the multi-recipe prompt phase per the v1.1 milestone framing.

### Prior phase context (carries forward — do NOT re-decide)
- `.planning/phases/21-tool-surface-flip-remove-acknowledge-notify/21-CONTEXT.md` — Phase 21 decisions. Phase 22 inherits:
  - D-01 `RespondTool` at_front=True non-terminal — KEEP. V006 uses it for pre-batch ack, ambiguity clarification, and wake-reply composition.
  - D-02 `TerminateTool` `return_direct=True` — KEEP. V006 inherits the "end every turn with terminate()" rule.
  - D-03 `StartWorkflowTool` multi-call, `return_direct=False`, `{workflow_type, input: AddRecipeQueryInput}` — KEEP unchanged. Phase 22 is the LLM-behavior layer on top of this surface.
  - D-04 multi-call surface enabled (no code change) — KEEP. Phase 22 just teaches Robotina to USE it.
  - D-09 V005 prompt structure (3-tool surface, output rule, language rule) — V006 forks V005 and adds multi-recipe + over-cap + ambiguity examples.
  - D-13/D-16 manual-smoke pattern — Phase 22 mirrors with `22-EVAL-SET.md`, `22-EVAL-RESULTS-<backend>.md`, `22-SMOKE.md`.
- `.planning/phases/20-wake-rule-outcome-plumbing/20-CONTEXT.md` — Phase 20 decisions. Phase 22 inherits:
  - D-04 single `_check_and_dispatch_wake` helper. Phase 22 modifies the sibling-runs query (D-06) and the outcome-summary build (D-08); does NOT change the wake-dispatch semantics.
  - D-06 `WakeInvocationInput.outcomes` list — Phase 22 enriches per-outcome with `recipe_query`.
  - D-13 dashboard outcome cell — no change.
- `.planning/phases/18-robotinainvocation-entity/18-CONTEXT.md` — D-13 constructor-injected `invocation_id` on StartWorkflowTool. KEEP. Phase 22 relies on this for the concurrent-tool-call race mitigation (Pitfall 5).
- `.planning/phases/17-conversation-fk-closure/17-CONTEXT.md` — D-03/D-04 constructor-injected `conversation_id`. KEEP.

### Existing codebase contracts (current state — Phase 21 landed 2026-05-19)
- `src/robotina/agent/prompts/robotina/V005.md` — current Robotina prompt. Fork to V006.
- `src/robotina/agent/agents.py` — `handle-incoming-message` agent loads `V005.md` today. Phase 22 bumps to `V006.md`.
- `src/robotina/agent/tools/start_workflow.py` — multi-call surface in place; NO change in Phase 22.
- `src/robotina/agent/tools/respond.py`, `src/robotina/agent/tools/terminate.py` — NO change.
- `src/robotina/queue/task_types.py:355` `WorkflowOutcomeSummary` — Phase 22 adds `recipe_query: str | None = None`.
- `src/robotina/queue/task_types.py:379` `WakeInvocationInput.to_user_message()` — Phase 22 modifies per D-07 (slug on success, recipe_query on failure, drop legacy parenthetical).
- `src/robotina/queue/workflow_runner.py:195` `_check_and_dispatch_wake` sibling-runs query — Phase 22 adds `.order_by(WorkflowRun.created_at.asc())` AND populates `recipe_query` on each `WorkflowOutcomeSummary` from `r.shared_context["recipe_query"]`.
- `experiments/recipe_research.py`, `experiments/recipe_load.py` — existing experiment script pattern. Phase 22 adds `experiments/robotina/multi_recipe_eval.py` following the same LangWatch-instrumented shape.
- `pyproject.toml` `[project.scripts]` — add `"experiments.multi_recipe_eval" = "experiments.robotina.multi_recipe_eval:main"` (or similar) so the smoke is runnable via `uv run experiments.multi_recipe_eval`.

### Project conventions
- `CLAUDE.md` "LangWatch instrumentation must be active during both production and experiment runs" — the eval harness MUST set the LangWatch experiment tag (per-utterance `metadata={"phase": "22", "utterance_id": ...}`) so traces are reviewable.
- Memory `feedback_avoid_premature_abstraction` — applied at D-02 (one concrete script, not a framework) and D-10 (no new `ask_user` tool).
- Memory `feedback_prompts_language` — V006 body in English; `respond()` examples in Spanish (Argentine / Latin American).
- Memory `feedback_overrides_in_sync` — no agent registry changes in Phase 22, so no overrides changes; CI guard stays green.
- Memory `feedback_test_before_handoff` — D-15 (operator runs eval smoke before reporting Phase 22 complete) honors this.
- Memory `feedback_queue_at_front` — V006 inherits Phase 21 D-01; `respond()` queues at front.
- Memory `feedback_no_task_id_in_code` — no "Phase 22" / quick-task tags in code; D-NN refs in comments are durable design refs and allowed.
- Memory `project_compose_agent_vision` — V006 keeps Robotina as both decider AND composer. Compose-agent split deferred to v2.
- Memory `project_local_dev_setup` — agent/gateway run on host; Ollama is dev backend, OpenAI is staging. Eval harness runs from host with `uv run experiments.multi_recipe_eval`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Multi-call tool surface (Phase 21 D-03/D-04)** — `StartWorkflowTool` already accepts N calls per turn, `return_direct=False`. Phase 22 is the LLM-behavior layer on top; zero code change to the tool itself.
- **Wake-helper aggregation (Phase 20 D-04/D-06)** — `_check_and_dispatch_wake` already collects sibling-run outcomes into a `WakeInvocationInput`. Phase 22 enriches: ORDER BY + recipe_query on summary.
- **`WakeInvocationInput.to_user_message()` Spanish synthesis** — already builds per-outcome lines. Phase 22 polishes the line format (D-07) and drops the legacy parenthetical.
- **LangWatch experiment instrumentation pattern** — `experiments/recipe_research.py` and `experiments/recipe_load.py` show the boilerplate: `langwatch.setup(...)`, agent dispatch, trace tagging. `experiments/robotina/multi_recipe_eval.py` clones the shape.
- **`LLMBackend` abstraction (Phase 4)** — the eval harness selects backend via env (`OLLAMA_URL`, `OPENAI_API_KEY`, etc.) the same way the existing experiments do. No new adapter needed.
- **V005 prompt structure** — V006 forks V005 verbatim and adds three new sections (multi-recipe extraction examples, ambiguity/clarify-via-respond, over-cap ask-to-split).
- **Constructor-injected `invocation_id` (Phase 18 D-13)** — all N WorkflowRuns in a multi-recipe turn point to the same RobotinaInvocation atomically. No race. Phase 22 inherits this guarantee.

### Established Patterns
- **Prompt versioning (V001..V005)** — concrete, never abstract. V006 follows.
- **Manual smoke pattern (Phase 21 D-13)** — `<phase>-SMOKE.md` template, operator-run, go/no-go line. Phase 22 reuses with the eval-results split (`22-EVAL-SET.md`, `22-EVAL-RESULTS-<backend>.md`, `22-SMOKE.md`).
- **`shared_context["recipe_query"]` storage** — `StartWorkflowTool` writes the LLM-supplied query string here at workflow creation. Stable contract since Phase 5; Phase 22 reads it back in the wake helper (D-08).
- **One concrete script per experiment (memory `feedback_avoid_premature_abstraction`)** — `experiments/robotina/multi_recipe_eval.py` is one file, not a directory tree.
- **Spanish user-facing / English prompt body** — V006 follows.

### Integration Points
- `src/robotina/agent/prompts/robotina/V006.md` (NEW) — multi-recipe + ambiguity + over-cap prompt.
- `src/robotina/agent/agents.py` — bump `V005.md` → `V006.md` on handle-incoming-message.
- `src/robotina/queue/task_types.py:355` `WorkflowOutcomeSummary` — add `recipe_query: str | None = None`.
- `src/robotina/queue/task_types.py:379` `WakeInvocationInput.to_user_message()` — modify per D-07.
- `src/robotina/queue/workflow_runner.py:195` `_check_and_dispatch_wake` — add ORDER BY; populate `recipe_query` on each summary.
- `experiments/robotina/multi_recipe_eval.py` (NEW) — eval harness.
- `experiments/robotina/__init__.py` (NEW if missing).
- `pyproject.toml` `[project.scripts]` — add `experiments.multi_recipe_eval` shortcut.
- `.planning/phases/22-multi-recipe-per-message-topic-1/22-EVAL-SET.md` (NEW) — 30+ Spanish utterances with expected counts/names.
- `.planning/phases/22-multi-recipe-per-message-topic-1/22-EVAL-RESULTS-ollama.md` (NEW — operator) — per-backend results.
- `.planning/phases/22-multi-recipe-per-message-topic-1/22-EVAL-RESULTS-openai.md` (NEW — operator) — per-backend results.
- `.planning/phases/22-multi-recipe-per-message-topic-1/22-SMOKE.md` (NEW — operator) — final verdict.
- `tests/queue/test_wake_helper_ordering.py` (NEW) — ORDER BY assertion.
- `tests/queue/test_wake_invocation_input.py` (NEW or extend) — to_user_message format assertions.
- `tests/queue/test_task_types.py` (extend) — WorkflowOutcomeSummary schema.
- `tests/agents/test_handle_incoming_message_agent.py` (extend) — V006 prompt-path assertion.
- `.planning/REQUIREMENTS.md` — tick BATCH-01..05 in the final smoke commit.

</code_context>

<specifics>
## Specific Ideas

- **Phase 22's value is mostly in the eval set, not the code.** The code surface
  is small: V006 prompt fork, `agents.py` one-line bump, ~10 lines in
  `task_types.py`, ~3 lines in `workflow_runner.py`. The eval set is the
  empirical guarantee that BATCH-01..05 actually hold against the LLM.
- **PITFALL 12 is the load-bearing risk.** Multi-recipe LLM parsing is
  unreliable in subtle ways. The eval-set coverage classes (D-03) directly
  target the known failure modes (compound dish, sauce conjunctions,
  English noun-phrases like "salt and pepper chicken").
- **PITFALL 5 (parallel tool calls) is the secondary risk.** Phase 22
  accepts enqueue-order ≈ user-utterance-order via `ORDER BY created_at`
  (D-06). If a future phase needs strict ordering, add a `batch_index`
  field on `StartWorkflowTool` args; do NOT add mutable shared state.
- **Eval harness is intentionally minimal.** Per `feedback_avoid_premature_abstraction`,
  it's one script that loops, dispatches, counts, reports. No generic
  rubric engine, no plug-in scoring, no LLM-judge framework. If Phase
  24's image eval and Phase 23's URL eval both end up needing this
  pattern (3 instances), THAT's when to extract a shared helper.
- **The V006 "ask to split" example is the most important worked example
  in the prompt.** Without it, the LLM tends to fan out everything the
  user names. With it, the cap holds.
- **No automated CI harness for the eval.** Operator-triggered. Results
  committed. Mirrors Phase 21's pattern. Future v1.2 may automate
  against a tiny synthetic subset.

</specifics>

<deferred>
## Deferred Ideas

- **`ask_user(question)` tool** (Pitfall 12) — `respond()` already covers
  ambiguity escalation. Reconsider in v2 if Robotina needs a
  semantically distinct "I'm asking, not answering" signal (e.g. for
  composability with a future scheduler/follow-up system).
- **Strict user-utterance ordering via `batch_index`** (Pitfall 5) —
  enqueue-order is sufficient for v1.1. Add a `batch_index` field on
  `StartWorkflowTool` args + sort wake outcomes by it if any future
  phase needs strict ordering.
- **URL-aware multi-recipe** (cross-source case) — Phase 23. V006 stays
  free-text-only.
- **Defensive code cap on N** — BATCH-05 explicitly says prompt-level.
  If the smoke shows the prompt-level cap is unreliable, revisit with
  a `StartWorkflowTool.max_calls_per_turn` constructor field; not
  Phase 22.
- **Automated CI eval harness** — operator-triggered for v1.1.
  v1.2 may automate a tiny synthetic subset (e.g. 5 utterances against
  a mocked LLM that always emits N tool calls) as a regression smoke.
- **LLM-judge name-similarity scoring** — Levenshtein is the v1.1 floor;
  LLM-judge is a P2 upgrade. Planner picks which to implement first;
  recommended Levenshtein for speed + zero extra API cost.
- **Conversation-history truncation** (Pitfall 9) — context-bloat
  hardening; not load-bearing for N ≤ 5. v1.2.
- **Compose Agent split** (COMP-01) — v2. V006 keeps Robotina as
  decider + composer.
- **Same-recipe-name overlap detection** ("ya tenés X, querés
  sobreescribir?") — Pitfall 12 UX item; deferred (requires
  household-manager-api recipe-list query in the wake turn —
  add when overlap becomes a real complaint).

</deferred>

---

*Phase: 22-Multi-recipe per message (Topic 1)*
*Context gathered: 2026-05-20*
