# Milestone 02 — Workflow Refinement

## Goal

Polish the recipe-adding capability into something genuinely useful for onboarding and ongoing use, by addressing three concrete UX gaps and the architectural mess that blocks them.

**Three product gaps to close:**

1. **Multi-recipe in one message.** Users can ask Robotina to add several recipes at once ("porfa agregá canelones de choclo, pollo al horno y arroz pilaf") — useful for onboarding.
2. **URL-pointed recipe.** Users can hand Robotina a URL and have it adopt that specific recipe ("agregá esta receta: https://example/recipe").
3. **Recipe images.** The add-recipe pipeline acquires and saves an image alongside the recipe.

## Why this matters

The first two unlock real onboarding flows — a user can populate their household's recipe library quickly without re-typing the prompt N times or describing a recipe they already have a link to. The third closes a quality gap; recipes without images feel half-done in any household UI.

But the *real* reason this milestone exists is that closing these three gaps cleanly forces the architectural cleanup we've been deferring. Trying to bolt multi-recipe onto the current shape exposes hard constraints (engine-enforced termination on `start-workflow`, ack-spam, no fan-out story, JSON-glued Conversation↔WorkflowRun coupling). Doing it right means we land a model that also supports cron-driven work, future multi-turn refinement, and the eventual Compose-agent vision.

## Architectural direction (agreed during exploration)

The single insight that unlocks the model: **Robotina is not a node in the work graph. Robotina is the agent that creates and consumes work graphs.** Workflows are *what Robotina dispatched*; Robotina lives outside them, gets re-invoked when they complete, and is the *only* path to the user.

### Entity model

```
Conversation                              (existing; thread per platform+chat_id)
├── StoredMessage                         (existing; user + assistant chat log)
├── RobotinaInvocation                    (new; one row per Robotina LLM turn)
│     ├── trigger: user_message | workflow_completion | cron (future)
│     ├── trigger_ref_id
│     └── started_at / completed_at
└── WorkflowRun                           (existing; gains FKs and outcome)
      ├── conversation_id                  (new FK — closes the JSON-glue mess)
      ├── triggered_by_invocation_id       (new FK — which Robotina turn started this)
      ├── workflow_type                    (existing; e.g. add-recipe)
      ├── input                            (existing as shared_context; now per-workflow)
      ├── status                            (existing)
      ├── outcome                           (new; compact Robotina-facing summary)
      └── WorkflowRunStep[]                 (existing; mostly unchanged)
```

Key shifts from today:
- `WorkflowRun` gains `conversation_id` FK — replaces the JSON-glued `shared_context.reply_context.chat_id` coupling.
- `WorkflowRun` gains `triggered_by_invocation_id` FK — the grouping that lets the runtime know when to wake Robotina.
- `WorkflowRun` is **immutable once created**: the agent declares its plan upfront. If more work is needed after a batch drains, Robotina is re-invoked and starts *another* batch of workflows.
- Fate-sharing is the workflow's natural scope: one step in a workflow fails → the rest of *that* workflow cancel (existing behavior). Different workflows are independent.
- `WorkflowRun.outcome` is the **Robotina-facing summary** (compact, structured). Step-level artifacts stay verbose and internal. This is the primary mechanism for preventing Robotina context bloat as work accumulates.

### Robotina's tool surface

- **Sync read tools** (existing: `household-manager-api`, etc.) — Robotina gathers context freely.
- **Sync write tools** (e.g. `update_recipe(id, patch)`) — small deterministic mutations that don't deserve a workflow.
- **`respond(text)`** — synchronous side-effect: writes a StoredMessage and sends to the user. Does NOT end the turn.
- **`start-workflow(workflow_type, input)`** — queues one workflow linked to the current Robotina invocation. May be called multiple times in a turn (multi-recipe = N calls).
- **`terminate()`** — ends the current Robotina invocation.

The current `return_direct=True` on `StartWorkflowTool` (engine-enforced single-tool-call termination) **goes away** — Robotina is expected to call `start-workflow` multiple times per turn.

### Wake rule

**Hardcoded for V1, no per-workflow policy:**

> When all workflows linked to a given Robotina invocation reach terminal status (done or failed), the runtime enqueues a new Robotina invocation with `trigger=workflow_completion` and `trigger_ref_id=that invocation's id`.

The new Robotina invocation sees all those workflow outcomes plus the original conversation history. It may `respond` to the user, may dispatch more workflows (chained to its own invocation), or may just `terminate`. This continues until a Robotina invocation dispatches nothing and the chain ends.

Implications:
- **No "sibling" abstraction.** Grouping is just "shares a `triggered_by_invocation_id`".
- **No wake-policy choice.** Always-wait-for-all is the rule. Simple, predictable.
- **No mid-stream agent chatter during a batch.** Robotina speaks before the batch starts (`respond` then `start-workflow`×N) and after all of it drains. Silence in between.
- **Mid-stream chatter, when wanted, comes from chunking**: Robotina dispatches Workflow 1, gets woken on completion, dispatches Workflow 2 and speaks, etc. The framework rule stays the same; chunking is a Robotina-side pattern.

This is the simplest rule that supports the three topics. We can iterate on the wake mechanism later as real use cases push on it.

### Termination, two layers

- **Agent-turn termination:** Robotina calls `terminate()` → this LLM invocation ends. Workflows it dispatched continue draining.
- **Chain termination:** when all workflows for an invocation drain, the next Robotina invocation fires. The chain ends naturally when an invocation calls `terminate()` without having dispatched any workflows.

### Cancellation policy (V1)

Workflow-internal only. On any step failure inside a workflow, the runner marks that workflow FAILED and cancels its remaining steps. Other workflows linked to the same Robotina invocation are completely independent and run to completion. Robotina is informed via each workflow's `outcome` on the next invocation and decides what to tell the user.

## How the three topics land

### Topic 1: Multi-recipe in one message

Robotina parses the request, calls `start-workflow("add-recipe", {source: query, value: "canelones"})` × 3 (once per recipe) in one turn, then `terminate()`. The three workflows drain sequentially (concurrency=1). When the last one finishes, the runtime wakes Robotina. Robotina sees three workflow outcomes and composes a single reply ("listos los 3" / "2 listos, canelones falló porque…"). The ack-spam problem dissolves because there is no longer a built-in ack step — Robotina decides what to say and when.

### Topic 2: URL-pointed recipe

One `add-recipe` workflow type with a `source` discriminator in the input (`{kind: "query"|"url", value: ...}`). The workflow definition's first step varies by source:
- `query` → `recipe-research-gather` (existing, uses web search)
- `url` → `gather-from-url` (new step, deterministic JSON-LD / schema.org parsing first, LLM-fallback for the long tail)

Both produce a `RecipeData` complete enough for the rest of the pipeline. The downstream steps (instructions/ingredients/metadata/load) stay identical.

**Open questions to investigate:**
- Choice of scraping library (recipe-scrapers, custom, third-party API).
- Whether the existing downstream research steps tolerate a well-populated input (refine vs. create-from-nothing semantics).

### Topic 3: Recipe images

New step type (`recipe-image`) inserted into the add-recipe pipeline after research, before `recipe-load` (so the image URL is part of the atomic save). Applies to both query-sourced and URL-sourced variants. Failure is **non-fatal** — the recipe saves without an image, `WorkflowRun.outcome` reports the gap.

**Open questions to investigate:**
- Source: web image search vs. AI generation vs. hybrid. V1 lean: web image search.
- Storage: source URL pinned, or download + re-host via household-manager backend (avoid link rot).
- Per-recipe skippability (later; not V1 blocker).

## Out of scope for this milestone

- **Memory layer.** Robotina memory was discussed as a future extension; the model accommodates it but does not require it for V1.
- **Mid-workflow user-driven cancellation.** If the user sends "ya no, cancelá" while a batch is in flight, V1 queues the message and Robotina handles it post-completion (apologetically late). Interruption / concurrent-invocation patterns are explicitly deferred.
- **Mid-batch progress chatter from a single Robotina turn.** Robotina speaks before and after each batch, not during. If progressive updates are wanted, the answer is **chunking workflows** (Robotina dispatches one workflow, gets a turn, dispatches the next…), not a wake-policy knob or a send-message step.
- **Per-workflow or per-batch wake policies.** Hardcoded "wake when all complete" is the V1 rule. Revisit once real use cases push on it.
- **A dedicated entity for "an interaction".** The chain of Robotina invocations + their workflows is implicit via `triggered_by_invocation_id`. A first-class entity (and its relationship to cron-driven work) can wait until cron lands and reveals what's actually needed.
- **Compose-agent split.** The eventual "one agent owns all user-facing reply composition" vision is consistent with this model but not part of this milestone. Robotina-as-decider is the foundation; a Compose-agent can be carved out later.

## Migration notes (for planning)

This is a real refactor but lighter than it could have been. Key touch points already identified:

- Add `RobotinaInvocation` table; the gateway message handler and the workflow runner's completion path both write rows here.
- `WorkflowRun`: add `conversation_id` FK, `triggered_by_invocation_id` FK, and `outcome` (JSON). Backfill `conversation_id` for existing rows from `shared_context.reply_context.chat_id` + platform.
- `StartWorkflowTool`: drop `return_direct=True`. Stop carrying `reply_context`/`household_id` through `shared_context`; the runner reads them from the linked Conversation and RobotinaInvocation. Tool args become `{workflow_type, input}` and the schema allows multiple calls per turn.
- Delete the `acknowledge-add-recipe` step from the add-recipe workflow; remove its agent registry entry and prompt directory. Robotina now calls `respond()` directly.
- Workflow runner: on terminal state for any workflow, check whether all workflows linked to its `triggered_by_invocation_id` are terminal; if yes, enqueue a new Robotina invocation with `trigger=workflow_completion`.
- Robotina prompt + tooling: teach it the new tool surface (`respond`, `start-workflow` callable N times, `terminate`) and the multi-recipe + URL-extraction patterns.
- Add `gather-from-url` task type, prompt, and tool wiring; declare its `RecipeData` output contract. Insert the source-branching first step into the add-recipe workflow definition.
- Add `recipe-image` task type, prompt, tool wiring, image-source strategy.
- Each workflow's final step writes a compact `outcome` to its WorkflowRun row (recipe id + name on success, structured failure reason otherwise).

## Success criteria (draft — for milestone discovery to refine)

- A single Telegram message containing 1-N recipes results in 1-N recipes saved to the household, with one final Robotina reply summarizing outcomes (success and failure).
- A message containing a recipe URL results in that exact recipe being saved (no hallucinated variant from a web search).
- Saved recipes have an associated image (when one can be acquired); image acquisition failure does not block recipe save.
- The architectural shifts (RobotinaInvocation table, WorkflowRun conversation FK, Robotina-as-decider, all-workflows-done wake rule) are in place, with the `acknowledge-add-recipe` workaround removed.
- No regressions in single-recipe text-query flow (today's working path).

## Decisions deferred to milestone discovery

- Should `RobotinaInvocation` be a first-class row in V1, or in-memory only with telemetry-as-needed? (Leaning first-class — it pays for itself the moment we want to debug Robotina decisions or attach memory.)
- Multi-call vs list-form for `start-workflow`: does Robotina call the tool N times in one turn, or once with a list of N workflows? Equivalent semantically; differs in prompt ergonomics and LLM reliability.
- URL scraping library choice and the failure-fallback ladder (JSON-LD → microdata → LLM extraction → give up).
- Image source for V1 and storage location (URL vs. backend-hosted).
- The exact prompt/tooling shape that makes Robotina reliably emit multiple `start-workflow` calls (this is the LLM-behavior piece that *can* fail silently — needs careful evaluation).
- Wake-rule edge cases: what happens if a workflow times out vs. fails — do both count as terminal for the wake check? (Almost certainly yes, but worth pinning down.)
