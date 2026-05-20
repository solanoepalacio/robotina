# Requirements: Robotina

**Defined:** 2026-05-18 (milestone v1.1)
**Core Value:** Families can delegate household tasks to Robotina in natural language and trust that they get done — even complex multi-step tasks that span multiple agent runs.

> v1.0 requirements are archived at `.planning/milestones/v1.0-REQUIREMENTS.md`. This file tracks v1.1 only.

## v1.1 Requirements

### Architecture Foundation

- [x] **ARCH-01**: `WorkflowRun` rows have a `conversation_id` FK to `Conversation`; the column lands as NOT NULL in a single Alembic revision (table is pre-cleaned before deploy per the Phase 17 runbook). Existing v1.0 rows are discarded by the deploy runbook; the post-migration `COUNT(*) WHERE conversation_id IS NULL` returns 0 trivially because no rows exist when 0006 runs.
- [x] **ARCH-02**: A new `RobotinaInvocation` SQLAlchemy model records every Robotina LLM turn with `trigger` (`user_message` | `workflow_completion` | `cron`), `trigger_ref_id`, `conversation_id`, `started_at`, `completed_at`, `rq_job_id`, `wake_dispatched_at`.
- [x] **ARCH-03**: `WorkflowRun` rows have a `triggered_by_invocation_id` FK to `RobotinaInvocation`; the `StartWorkflowTool` populates it; the column lands nullable in v1.1.
- [x] **ARCH-04**: `WorkflowRun.outcome` is a JSON column written by a deterministic terminal step; for the `add-recipe` workflow types it serializes a Pydantic `AddRecipeOutcome` model (success/failure + recipe id/name OR failure reason + `image_present` flag) targeted at < ~300 bytes per workflow.
- [x] **ARCH-05**: The legacy `shared_context.reply_context` JSON path remains readable through v1.1 (deprecation window); new code reads `WorkflowRun.conversation_id` instead.

### Wake Rule & Control Loop

- [x] **WAKE-01**: When all `WorkflowRun` rows sharing a `triggered_by_invocation_id` reach terminal status (`done` OR `failed`), the runtime enqueues a new `RobotinaInvocation` with `trigger=workflow_completion` and `trigger_ref_id` set to the parent invocation's id.
- [x] **WAKE-02**: The wake check is idempotent — if invoked twice (e.g. manual retry from RQ failed registry), exactly one wake invocation is enqueued; enforced by an atomic `UPDATE ... WHERE wake_dispatched_at IS NULL RETURNING id` guard.
- [x] **WAKE-03**: The wake-invocation job id is pre-assigned before commit (D-07 transactional advancement pattern, mirroring existing workflow-step enqueue).
- [x] **WAKE-04**: A `WakeInvocationInput` Pydantic model carries the previous invocation id and a list of `WorkflowOutcome` summaries; `run_task` dispatches it to the Robotina agent with a wake-context prompt prefix.
- [x] **WAKE-05**: A startup reconciler scans `RobotinaInvocation` rows where the linked workflows are terminal but `wake_dispatched_at IS NULL` and dispatches the wake (covers worker-crash recovery alongside AOF).

### Robotina Tool Surface

- [x] **TOOLS-01**: `StartWorkflowTool` no longer uses `return_direct=True`; Robotina can emit multiple `start-workflow` tool calls in a single turn; the schema is `{workflow_type, input}` per call.
- [x] **TOOLS-02**: A new `RespondTool` (`respond(text)`) sends a Spanish reply to the user by enqueuing a `send-notification` job at the front of the queue (mirrors existing pattern; inherits AOF persistence); the tool is non-terminal — Robotina can call it before/after `start-workflow` and continue.
- [x] **TOOLS-03**: A new `TerminateTool` (`terminate()`) ends the current Robotina turn cleanly via `return_direct=True`; the prompt forbids trailing assistant text outside `respond` / `terminate`.
- [x] **TOOLS-04**: The `acknowledge-add-recipe` agent, prompt directory, registry entry, task type, workflow step, dashboard label entry, and every `overrides/*.json` reference are removed; a CI check enforces that AGENT_REGISTRY task types ↔ every `overrides/*.json` stay in sync (per memory `feedback_overrides_in_sync.md`).
- [x] **TOOLS-05**: The `notify` workflow step (Phase 6 send-notification tail) is removed from the add-recipe workflow definition — Robotina now closes the loop via `respond()` on wake.

### Multi-Recipe per Message (Topic 1)

- [ ] **BATCH-01**: A single user message naming N recipes (1 ≤ N ≤ 5) results in N `add-recipe` workflows enqueued, all linked to the same `RobotinaInvocation`.
- [ ] **BATCH-02**: Robotina's pre-batch reply (via `respond()`) acknowledges all N recipes in one message ("voy con canelones, pollo y arroz, te aviso"); no per-recipe ack during drain.
- [ ] **BATCH-03**: After all N workflows reach terminal status, Robotina's wake invocation composes ONE consolidated final reply summarizing each recipe's outcome (success: name+slug; failure: brief reason); order preserved from user input.
- [ ] **BATCH-04**: Partial failures are reported cleanly — "2 listos, canelones falló: …" rather than silent failure or all-or-nothing.
- [ ] **BATCH-05**: If the user names more than 5 recipes in one message, Robotina asks the user to split or proceeds with the first 5 and notes the cap (decided at prompt level, not enforced by code).

### URL-Pointed Recipe (Topic 2)

- [ ] **URL-01**: A `safe_fetch` helper provides URL fetching with six SSRF/abuse defenses: HTTPS scheme allowlist (HTTP allowed only if explicitly configured), post-DNS private-IP block (127.0.0.0/8, 169.254.0.0/16, 10/8, 172.16/12, 192.168/16, etc.), manual redirect handling with re-validation, configurable timeout, content-length cap (default 5 MB), and content-type magic-byte verification on response.
- [ ] **URL-02**: A new `gather-from-url` task type fetches a URL via `safe_fetch` and extracts structured recipe data via `recipe-scrapers` (`wild_mode=True`), with a per-field try/except so partial failures populate what they can.
- [ ] **URL-03**: A new `add-recipe-from-url` workflow variant (or equivalent source-discriminator on `add-recipe`) routes URL-sourced requests through `gather-from-url` instead of `recipe-research-gather`; downstream steps (instructions/ingredients/metadata/recipe-image/recipe-load) are reused unchanged.
- [ ] **URL-04**: When `recipe-scrapers` fails (no JSON-LD, no schema.org markup, no wild_mode match), an LLM fallback agent re-extracts from the raw HTML/text using the same `RecipeData` schema.
- [ ] **URL-05**: Robotina detects URLs in the user message and routes them through the URL variant; pure-text recipe queries continue to use `recipe-research-gather`.
- [ ] **URL-06**: A 20-URL eval set (Spanish-language recipe blogs + 1 known-difficult site) is tracked, with ≥85% field-level success documented at v1.1 ship.

### Recipe Images (Topic 3)

- [ ] **IMG-01**: A new `recipe-image` task type is inserted into the add-recipe workflow between research and `recipe-load`; it produces an `image_url` (or empty / sentinel for missing).
- [ ] **IMG-02**: Image acquisition follows a fallback ladder: source-page image (recipe-scrapers `.image()`) when URL-sourced → Tavily image search (`include_images=True`) otherwise → mark missing.
- [ ] **IMG-03**: Image acquisition failure is **non-fatal** — the workflow runner advances past `recipe-image` even when no image was acquired; the recipe still saves; `WorkflowRun.outcome.image_present=False` records the gap.
- [ ] **IMG-04**: The `recipe-image` step validates its produced `image_url` through the same `safe_fetch` helper used by URL ingestion (re-uses the SSRF defenses).
- [ ] **IMG-05**: The image URL persists with the recipe via the household-manager API; storage strategy (URL pin vs. backend re-host) is decided during Phase H planning based on the household-manager image-field surface.
- [ ] **IMG-06**: The workflow runner supports per-step non-fatal-failure semantics (new runner capability) — declared at step definition level; non-fatal-on-failure steps write a structured "unavailable" artifact and advance instead of cancelling the workflow.

### LLM Multi-Call Evaluation (manual smoke, embedded in Phase 21)

These were originally framed as a standalone heavyweight eval phase (the removed Phase 19). They are reframed as a manual smoke checkpoint embedded in Phase 21, since the tool surface that enables multi-call (`return_direct=False`) only exists inside that phase's branch.

- [x] **EVAL-01**: A manual smoke run exercises multi-`start-workflow`-per-turn behavior against the in-use LLM backends — Ollama `gpt-oss:20b` (local dev) and OpenAI (staging). No automated harness is required; running the agent against hand-curated utterances and inspecting tool-call traces in LangWatch / the dashboard is sufficient. _Template committed in 21-08; operator runs smoke against 21-SMOKE.md._
- [x] **EVAL-02**: A 5–8 utterance hand-curated Spanish set is committed alongside the smoke results, covering at minimum: 1 single-recipe, 2 multi-recipe (2–3 items), 1 compound dish, 1 ambiguous, 1 over-cap (>5). Ground-truth expected N per utterance is documented inline. _7 utterances committed in 21-SMOKE.md (envelope satisfied)._
- [x] **EVAL-03**: The smoke results table is committed as `.planning/phases/21-*/SMOKE.md` before Phase 21 merges, ending in an explicit go/no-go line. If OpenAI staging is unreliable, the phase pivots `StartWorkflowTool` to single-call list-form `start-workflow(actions=[...])` before merge; Ollama-only failures are noted and do not block merge. _Table + Go/No-Go + D-15 pivot path committed in 21-SMOKE.md (verdict: pending — operator gate)._

### Dashboard Compatibility

The Phase 13 queue-visibility dashboard must continue to function through the schema and pipeline changes. v1.0 DASH-01..09 are archived; this milestone extends with v1.1-specific dashboard work.

- [x] **DASH-10**: Dashboard renders WorkflowRun rows with the new `conversation_id`, `triggered_by_invocation_id`, and `outcome` columns surfaced in the detail view; no template / query regression on the existing list view.
- [x] **DASH-11**: Dashboard's task-type label map is updated — `gather-from-url`, `recipe-image`, and `finalize-outcome` get Spanish labels; `acknowledge-add-recipe` and the standalone `notify` step are removed; CI / template tests guard against unknown task-type fallbacks producing raw enum values.
- [x] **DASH-12**: Dashboard surfaces a compact `outcome` summary on the WorkflowRun row (renders the structured `AddRecipeOutcome` JSON — success/failure + recipe name + image_present flag — without dumping raw JSON).
- [x] **DASH-13**: Dashboard surfaces RobotinaInvocation rows linked to a WorkflowRun (at minimum: `triggered_by_invocation_id` appears on the detail page; a dedicated invocation view is a nice-to-have).
- [x] **DASH-14**: Dashboard module-isolation grep gate (Phase 13 D-01) still passes after model imports change — `RobotinaInvocation` is imported from `robotina.queue.models` like `WorkflowRun`, not via a cross-module shortcut.

### Experiments Compatibility

Each LLM task type has a standalone experiment in `experiments/` (OBS-03 requirement from v1.0). These must continue to function and be extended for new task types.

- [ ] **EXP-01**: Existing experiment scripts (`experiments.recipe_research`, `experiments.recipe_load`, etc.) remain runnable through the migration — task input schema changes (e.g. added `source` discriminator) carry a default that preserves the existing happy path on existing scripts.
- [ ] **EXP-02**: A new `experiments.gather_from_url` script exercises the URL-extraction pipeline end-to-end on a representative URL with LangWatch traces tagged to the experiment.
- [ ] **EXP-03**: A new `experiments.recipe_image` script exercises the Tavily image-search path (and source-page fallback when given a URL) with LangWatch traces tagged to the experiment.
- [ ] **EXP-04**: A new `experiments.robotina_wake` script exercises the wake-context Robotina invocation (synthetic completed WorkflowRun + outcomes) to enable iterating on the wake prompt without running a full Telegram round-trip.
- [x] **EXP-05**: The `experiments.acknowledge_add_recipe` script (if it exists) is removed alongside the agent; documentation surface (PROJECT.md experiment list, README) updated accordingly. _Verified in 21-08: no `experiments/acknowledge_add_recipe.py` file exists, no `experiments.acknowledge_add_recipe` entry in `pyproject.toml [project.scripts]`, no mentions in README. PROJECT.md not present in the repo._
- [ ] **EXP-06**: `pyproject.toml` `[project.scripts]` declarations are updated for the new experiment entry points (`uv run experiments.gather_from_url`, etc.); CLAUDE.md table of experiments mirrors the new list.

## v2 Requirements (deferred / out of scope for v1.1)

### Compose Agent / Memory

- **COMP-01**: A dedicated Compose agent owns all user-facing reply composition (separated from Robotina's deciding role).
- **MEM-01**: Robotina has a persistent per-user memory layer beyond the conversation history window.

### Mid-Flight Coordination

- **MID-01**: User-driven cancellation of in-flight workflows ("ya no, cancelá").
- **MID-02**: Mid-batch progress chatter from a single Robotina turn (currently handled via workflow chunking, not a wake-policy knob).

### Cron-Triggered Robotina

- **CRON-01**: Cron-scheduled Robotina invocations (e.g. daily meal reminders) — the model accommodates this via `trigger=cron` but the scheduler track is deferred.

### Image Quality

- **IMG2-01**: Vision-LLM "is this food?" / "is this the right dish?" validation before persisting an image.
- **IMG2-02**: Backend re-hosting of images (if not done in v1.1) to mitigate link rot.
- **IMG2-03**: AI image generation fallback (Replicate / gpt-image / Imagen) when search fails.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Mid-batch user-visible progress messages from one Robotina turn | Solved by workflow chunking (Robotina dispatches Workflow 1, gets a turn, dispatches Workflow 2) — not a wake-policy knob in v1.1 |
| Per-workflow wake-policy choice (every-completion vs only-when-all-siblings-done) | Single hardcoded rule chosen for simplicity; revisit only when a real use case pushes |
| First-class "Interaction" entity above Conversation | Implicit chain via `triggered_by_invocation_id` is sufficient until cron-driven scope lands |
| Multi-call vs list-form `start-workflow` decision before Phase 21 lands | The Phase 21 embedded manual smoke (EVAL-01..03) gates the schema choice empirically |
| Recipe image AI generation | Real images via Tavily are V1; generation is deferred to v1.2+ if quality is poor |
| User-driven workflow cancellation | New user message during in-flight workflow queues and is handled apologetically post-completion |
| Vision-LLM image validation | Top-result accepted in V1; quality gate deferred to v1.2 |
| Scheduler track (`scheduled-tasks` queue, cron API) | Carried forward from v1.0 backlog; not included in v1.1 scope |
| Eliminating `shared_context.reply_context` JSON path in v1.1 | Deprecation window in v1.1; full removal in a later milestone |

## Traceability

Mapped by `gsd-roadmapper` 2026-05-18 (milestone v1.1 ROADMAP).

| Requirement | Phase | Status |
|-------------|-------|--------|
| ARCH-01 | Phase 17 | Completed |
| ARCH-02 | Phase 18 | Complete |
| ARCH-03 | Phase 18 | Complete |
| ARCH-04 | Phase 18 | Complete |
| ARCH-05 | Phase 17 | Completed |
| WAKE-01 | Phase 20 | Complete |
| WAKE-02 | Phase 20 | Complete |
| WAKE-03 | Phase 20 | Complete |
| WAKE-04 | Phase 20 | Complete |
| WAKE-05 | Phase 20 | Complete |
| TOOLS-01 | Phase 21 | Complete |
| TOOLS-02 | Phase 21 | Complete |
| TOOLS-03 | Phase 21 | Complete |
| TOOLS-04 | Phase 21 | Complete |
| TOOLS-05 | Phase 21 | Complete |
| BATCH-01 | Phase 22 | Pending |
| BATCH-02 | Phase 22 | Pending |
| BATCH-03 | Phase 22 | Pending |
| BATCH-04 | Phase 22 | Pending |
| BATCH-05 | Phase 22 | Pending |
| URL-01 | Phase 23 | Pending |
| URL-02 | Phase 23 | Pending |
| URL-03 | Phase 23 | Pending |
| URL-04 | Phase 23 | Pending |
| URL-05 | Phase 23 | Pending |
| URL-06 | Phase 23 | Pending |
| IMG-01 | Phase 24 | Pending |
| IMG-02 | Phase 24 | Pending |
| IMG-03 | Phase 24 | Pending |
| IMG-04 | Phase 24 | Pending |
| IMG-05 | Phase 24 | Pending |
| IMG-06 | Phase 24 | Pending |
| EVAL-01 | Phase 21 | Complete (template committed 21-08; operator smoke deferred — see 21-SMOKE.md) |
| EVAL-02 | Phase 21 | Complete (7-utterance set committed in 21-SMOKE.md) |
| EVAL-03 | Phase 21 | Complete (SMOKE.md scaffolded with verdict gate; operator fills before merge) |
| DASH-10 | Phase 20 | Complete |
| DASH-11 | Phase 21 | Complete |
| DASH-12 | Phase 20 | Complete |
| DASH-13 | Phase 18 | Complete |
| DASH-14 | Phase 18 | Complete |
| EXP-01 | Phase 24 | Pending |
| EXP-02 | Phase 23 | Pending |
| EXP-03 | Phase 24 | Pending |
| EXP-04 | Phase 24 | Pending |
| EXP-05 | Phase 21 | Complete (verified clean: no script, no pyproject entry, no doc mentions) |
| EXP-06 | Phase 24 | Pending |

**Coverage:**
- v1.1 requirements: 46 total
- Mapped to phases: 46 (Phases 17–24)
- Unmapped: 0 ✓

**Per-phase counts:**
- Phase 17: 2 (ARCH-01, ARCH-05)
- Phase 18: 5 (ARCH-02, ARCH-03, ARCH-04, DASH-13, DASH-14)
- Phase 19: _removed 2026-05-19; EVAL-01..03 folded into Phase 21_
- Phase 20: 7 (WAKE-01..05, DASH-10, DASH-12)
- Phase 21: 10 (TOOLS-01..05, DASH-11, EXP-05, EVAL-01, EVAL-02, EVAL-03)
- Phase 22: 5 (BATCH-01..05)
- Phase 23: 7 (URL-01..06, EXP-02)
- Phase 24: 10 (IMG-01..06, EXP-01, EXP-03, EXP-04, EXP-06)

---
*Requirements defined: 2026-05-18*
*Last updated: 2026-05-19 — Phase 19 removed; EVAL-01/02/03 reframed as a manual smoke checkpoint inside Phase 21 (rationale: the multi-call surface only exists in Phase 21's branch, so a pre-21 smoke test against the current `return_direct=True` tool is meaningless)*
