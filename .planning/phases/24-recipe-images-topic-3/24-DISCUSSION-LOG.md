# Phase 24: Recipe images (Topic 3) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-22
**Phase:** 24-Recipe images (Topic 3)
**Areas discussed:** Non-fatal runner capability shape; recipe-image agent shape & Pitfall 8 mitigation; Storage strategy (IMG-05); Shared-tail helper extraction + wake-reply update
**Mode:** `--auto` (Claude made each call under no-stopping reminder; user can redirect before `/gsd:plan-phase 24`.)

---

## Non-fatal runner capability shape

| Option | Description | Selected |
|--------|-------------|----------|
| (A) Definition flag on `WorkflowStepDef` + runner catches exceptions and writes structured "unavailable" artifact | Adds `non_fatal_on_failure: bool = False` to `WorkflowStepDef`. The runner's exception-handling branch checks the flag and converts to a structured `StepUnavailableArtifact`, advancing the workflow. Concentrates policy in one place; agent code unchanged. | ✓ |
| (B) Agent always returns structured output; never raises for known-miss conditions | Step is always DONE. Only real infrastructure exceptions FAIL. "Non-fatal capability" is documentation-only — no runner change. | |
| (C) Hybrid — both definition flag AND structured agent output | Belt-and-braces approach combining both options. | |

**Selected: (A) — `WorkflowStepDef.non_fatal_on_failure: bool = False` + runner writes `StepUnavailableArtifact` on exception.**

**Notes:**
- IMG-06's wording ("declared at step definition level") points directly at (A).
- (B) leaves transient errors (Tavily 503, safe_fetch timeout) to FAIL the workflow — the exact bug IMG-03 prevents.
- (C) is overkill; the agent CAN still return `image_url=None` for the deterministic-miss path (step DONE with a real artifact), while the flag handles unexpected exceptions. Those are two paths, not a hybrid policy.
- `_compose_failure_outcome`'s reason-truncation logic (`workflow_runner.py:52`) is reused for the unavailable artifact's `reason` field.
- Only `recipe-image` sets the flag in v1.1; capability is generic but application is narrow.

---

## `recipe-image` agent shape & Pitfall 8 mitigation

| Option | Description | Selected |
|--------|-------------|----------|
| (A) Deterministic task type — agent-less; mirrors `finalize-outcome` at `jobs.py:119` | New `run_task` branch calls `acquire_recipe_image(input) -> RecipeImageOutput` directly. No LangChain agent, no prompt, no LLM cost. | ✓ |
| (B) LLM agent with two tools (`SourcePageImageTool` + `TavilyImageSearchTool`) | Uniform with all other agents (LangWatch, response_format, AGENT_REGISTRY, overrides). | |
| (C) LLM agent with one branching tool (mirror `gather-from-url` FetchAndScrapeTool) | Tool branches internally; agent is passthrough. | |

**Selected: (A) — Deterministic task type; no LLM.**

| Pitfall 8 mitigation depth | Description | Selected |
|-----------------------------|-------------|----------|
| (M1) Top-result only; no vision check | Accept first Tavily image that passes safe_fetch + magic-byte. | |
| (M2) Vision-LLM top-3 check | Fetch top-3, send to vision-LLM with recipe name + ingredients; first YES wins; cap at 3. | |
| (M3) Top-result + source-page bypass; vision-LLM deferred to v1.2 | Source-page images skip any "right dish?" check (highly trusted); Tavily-fallback takes top result; manual eval is the gate. | ✓ |

**Selected mitigation: (M3) — Top-result + source-page bypass; vision-LLM deferred to v1.2 gated on eval.**

**Notes:**
- No LLM decision in v1.1 — both branches (source-page, Tavily) are mechanical. `gather-from-url` needed `response_format` for the no-scraper extraction case; recipe-image has no extraction step.
- Agent overhead would add ~$0.001-0.01 per recipe save for zero decision value.
- Precedent: `finalize-outcome` (Phase 20) is already agent-less; pattern exists at `jobs.py:119`.
- SUMMARY.md line 158: "escalate to vision-LLM only if <60% usable" — data-driven post-launch decision.
- Source-page images are the recipe author's chosen photo — bypassing vision check there is safe.
- Magic-byte validation via PIL is NOT included in v1.1 because URL pin (D-05) means we never decode the bytes — the household UI renders the URL in an `<img>` tag.

---

## Storage strategy (IMG-05)

| Option | Description | Selected |
|--------|-------------|----------|
| (A) URL pin — Robotina POSTs `image_url: str` in recipe payload; backend stores the URL string | No bytes transferred; backend just needs a new field. Link-rot risk. | ✓ |
| (B) Download-and-upload — Robotina fetches bytes via `safe_fetch`, strips EXIF, multipart-uploads to `/recipes/<id>/image` | Higher coordination cost (NEW backend endpoint); durable; legal cleaner. | |
| (C) ENV-gated hybrid — `IMAGE_STORAGE_STRATEGY=url_pin\|rehost`, default `url_pin` | Lets v1.1 ship as URL pin; v1.2 flip to rehost via flag. | |

**Selected: (A) — URL pin.**

**Notes:**
- Memory `feedback_avoid_premature_abstraction` — no rehost code in v1.1, so an ENV flag has nothing to gate.
- Backend has NOT committed to building a `/recipes/<id>/image` upload endpoint. URL pin is the minimum viable backend coordination.
- Pitfall 8's link-rot risk is documented as a v1.1 gap; broken-link sweep is the scheduler-milestone mitigation.
- EXIF strip + magic-byte validation only matter when redistributing; v1.1 doesn't.
- Industry standard for recipe aggregators is URL pinning.

---

## Shared-tail helper extraction + wake-reply update

| Option (helper extraction) | Description | Selected |
|----------------------------|-------------|----------|
| (A) Inline-duplicate insertion of `recipe-image` in both variants | Two explicit 7-step lists in `WORKFLOW_REGISTRY`. No helper. | ✓ |
| (B) Extract `build_recipe_tail()` helper returning the 6-step tail | Both variants compose `[gather_step] + build_recipe_tail()`. Phase 23 D-01 explicitly deferred this extraction to Phase 24. | |

**Selected (helper): (A) — Inline duplication; further-defer the helper (user redirect from initial Auto Mode B-recommendation).**

| Option (wake-reply update) | Description | Selected |
|----------------------------|-------------|----------|
| (W1) No prompt change — V007 stays | `outcome.image_present` is structural data; user sees gap in the household UI, not the Telegram chat. | ✓ |
| (W2) V008 fork mentioning "sin foto" when image_present=False AND status=success | Surfaces the gap in the chat-side reply. | |
| (W3) Optional mention — V007 unchanged; agent uses judgment | Receives the flag; no new worked example. | |

**Selected (wake-reply): (W1) — No V008 fork in v1.1; gated empirically via `experiments.robotina_wake` smoke.**

**Notes (helper) — user redirect:**
- **Initial Auto Mode call was (B) extract helper now.** User redirected
  to (A) inline duplication.
- **User's reasoning:** "Though the workflow is working, the quality of
  the recipes scraped is very low still so we need to iterate over them.
  Premature abstraction will require refactoring later."
- The tail steps (instructions, ingredients, metadata, recipe-image,
  load) will churn as recipe-quality iteration lands. A shared helper
  would have to be refactored each time the per-variant divergence grows.
- Memory `feedback_avoid_premature_abstraction` — "Architecture immature;
  prefer concrete duplicated agents over generic ones until 3+ instances
  exist." Tail-steps stability is the precondition, not just step count.
- Phase 23 D-01's "extract in Phase 24" directive is advisory, not a
  hard contract — written before Phase 24's quality-iteration scope was
  clear. Consciously re-deferred with documentation in `<deferred>`.
- Drift risk mitigated by D-19: workflow-registry tests assert both
  variants have the `recipe-image` step.

**Notes (wake-reply):**
- W1 stance preserved, BUT the decision is no longer a vibe call —
  D-08b makes `experiments.robotina_wake` part of the Phase 24 gate.
- D-10 fixture set MUST include `outcome.status=success,
  image_present=False` so the operator can review V007's reply on the
  exact case where "sin foto" surfacing would be tempting. If the
  operator finds V007's no-mention behavior awkward, that triggers a
  V008 follow-up.
- A new artifact `24-WAKE-RESULTS-<backend>.md` is added (D-13) for the
  operator's per-row verdicts; `24-SMOKE.md` references it.
- Memory `feedback_test_before_handoff` honored — the script is the
  pre-handoff smoke.
- Memory `project_compose_agent_vision` — the future Compose agent
  will own image-aware reply composition. Don't churn V007 for a
  feature the future agent absorbs.

---

## Claude's Discretion

The following decisions were made by Claude (per Auto Mode) without explicit user input. User can redirect any of these before `/gsd:plan-phase 24` runs:

- **`tavily_image_search` query construction:** `f"{recipe.name} receta"` hardcoded; tunable in v1.2.
- **Tavily `max_results`:** 5 (only top result used in v1.1).
- **`safe_fetch(max_bytes)` for images:** 15 MB (vs 5 MB default for HTML).
- **`RecipeImageOutput` shape:** identical to `RecipeData` dump with `image_url` added (mirrors Phase 15 accumulator pattern).
- **Plan order:** 9 plans (24-01 non-fatal runner FIRST, then `RecipeData.image_url` field, then Tavily wiring, then `acquire_recipe_image`, then inline `recipe-image` insertion in both `WORKFLOW_REGISTRY` entries, then `finalize-outcome` update, then both experiment scripts, finally operator eval covering both image quality AND V007 wake-reply acceptability).
- **No new dependencies:** `tavily-python` + `recipe-scrapers` already declared.
- **No new env vars:** `TAVILY_API_KEY` already declared.
- **Dashboard label:** `"recipe-image": "Imagen"`.
- **Test scope:** load-bearing tests on `non_fatal_on_failure` flag (D-14), `acquire_recipe_image` branches (D-15), Tavily tool (D-16), safe_fetch wildcard (D-17), finalize-outcome image_present logic (D-18), workflow registry (D-19).

## Deferred Ideas

See `24-CONTEXT.md` `<deferred>` section for full list. Highlights:
- `build_recipe_tail()` shared-tail helper — *further* deferred (was Phase 23 D-01's directive for Phase 24) until tail steps stabilize.
- Vision-LLM "is this the right dish?" check (v1.2 follow-up gated on eval).
- Image download-and-rehost (v1.2 backend endpoint).
- EXIF strip + magic-byte validation (v1.2 alongside rehost).
- Periodic broken-link sweep (scheduler milestone).
- Multi-candidate retry on safe_fetch failure (v1.2).
- V008 wake-reply with image-aware text (deferred to future Compose agent).
- AI image generation as fallback (explicitly rejected for v1.x).
