# Project Research Summary

**Project:** Robotina
**Milestone:** v1.1 — Workflows Abstraction Refinement
**Domain:** Brownfield refactor of a Python/LangChain/Postgres/Redis/RQ recipe-management Telegram agent — Robotina-as-decider architectural inversion + three product features (multi-recipe per message, URL-pointed recipe ingestion, recipe images)
**Researched:** 2026-05-18
**Confidence:** HIGH on current code shape and refactor plan; HIGH on stack additions (recipe-scrapers, httpx-sync, Tavily image search — all verified); MEDIUM on LangChain 1.x `create_agent` parallel-tool-call semantics (needs empirical smoke test before Phase E lands); MEDIUM-LOW on third-party quality (recipe-scrapers `wild_mode` hit-rate on Spanish-language sites; Tavily image-search quality on regional Argentine/Uruguayan recipes).

## Executive Summary

Milestone v1.1 is *primarily an architectural refactor* of a working v1.0 system, with three product features layered on top. The single insight driving everything: **Robotina is not a node in the work graph; Robotina is the agent that creates and consumes work graphs.** The refactor introduces a new `RobotinaInvocation` entity, closes FK relationships on `WorkflowRun` (`conversation_id`, `triggered_by_invocation_id`, structured `outcome`), replaces engine-enforced `return_direct=True` termination with explicit `respond()`/`terminate()` tools, deletes the `acknowledge-add-recipe` workaround, and adds a hardcoded "wake when all sibling workflows terminal" rule. Doing this cleanly *enables* the three features (multi-recipe fan-out, URL ingestion, images) — bolting them onto today's shape would compound the existing JSON-glue mess.

The stack is **essentially complete** for two of three features: `recipe-scrapers>=15.11.0` is already declared (Phase 8) but unused — turning it on for the new `gather-from-url` step requires zero new dependencies beyond pairing it with the existing `httpx` in sync mode. Tavily's `include_images=True` parameter delivers image acquisition for V1 with zero new API keys. The only *real* library decision is image-source — research strongly recommends **Tavily-first, defer AI generation** (real food photos beat synthetic ones; non-fatal failure semantics make this safe).

The riskiest single seam is LLM behavior under the new tool surface: `create_agent` does **not** expose `parallel_tool_calls=False` (LangChain issue #34010), so multi-recipe fan-out depends on the model reliably emitting N `start-workflow` tool calls per turn — and the development backend (`gpt-oss:20b` via Ollama) is the most likely failure point. A standalone smoke-test phase **before** the tool-surface flip is non-negotiable. Beyond that, four pitfalls deserve front-of-mind care: wake-rule double-fire on manual retries (Postgres-row-level `wake_dispatched_at` idempotency), three-step Alembic migration for NOT NULL FKs, the shared `safe_fetch` SSRF helper (used by both URL ingestion *and* image acquisition), and a schema-constrained `WorkflowOutcome` Pydantic model that prevents context bloat as invocation chains grow.

## Key Findings

### Recommended Stack

The v1.0 stack (LangChain 1.x `create_agent`, Pydantic v2, Postgres 15 + SQLAlchemy 2.x + Alembic, Redis 7 + RQ 2.5, FastAPI/Jinja2 dashboard, LangWatch + OTel, python-telegram-bot v21, Tavily, httpx) is preserved. The milestone is additive at the library level — no replacements, three "turn-on" actions, one decision.

**Stack additions (all verified HIGH confidence):**
- **`recipe-scrapers>=15.11.0`** (already declared, currently unused): JSON-LD + Microdata + RDFa + OpenGraph parser with 639 site-specific adapters plus `wild_mode=True` fallback. Library is parser-only — *we* fetch the URL.
- **`httpx>=0.27`** in sync mode (already in stack): paired with recipe-scrapers inside the sync RQ worker. No new dep; new call site.
- **`tavily-python>=0.3`** with `include_images=True` (already in stack): image acquisition for V1. Zero new API keys, same project, same budget. Optional separate `RECIPE_IMAGE_API_TOKEN` for per-task-type budgeting.

**Image-source decision:** Tavily image search ranks above gpt-image-1, Imagen, Replicate, Bing/Google Custom Search. Tavily is V1 default; generation stays a deferred carve-out.

**What NOT to use:** `requests` for URL fetching; Selenium/Playwright; DALL-E 3 by name (sunsetting mid-2026); `replicate`/`google-genai` in V1; new libraries for the Robotina-as-decider refactor.

See: `.planning/research/STACK.md`

### Expected Features

**Must have (P1 — v1.1 launch):**
- Multi-recipe parsing: N `start-workflow` calls per turn; consolidated post-batch reply; tri-state outcome; per-recipe failure reason; order-preserving; Spanish UX.
- URL ingestion: `recipe-scrapers` JSON-LD → `wild_mode` → LLM fallback → fail; `safe_fetch` helper with six SSRF defenses; source-discriminator on add-recipe input.
- Image acquisition: source-page image (recipe-scrapers `.image()`) when URL-sourced, Tavily image search otherwise; **non-fatal failure**; image URL validated via the same `safe_fetch` helper before persist.
- Per-workflow `WorkflowRun.outcome` with structured success/failure rendering.

**Should have (P2):** Pre-dispatch ack, inline dedup check, Spanish translation of foreign pages, image dimension sanity filter.

**Defer (P3 / v1.2+):** AI image generation fallback, vision-model "is this food?" filter, CDN re-hosting, workflow chunking, URL/HTML caching, mixed-intent batches.

**Anti-features:** `start-workflow(list_of_workflows=[...])` as the primary path; per-recipe inline assistant messages during a batch drain; "pass the URL to Tavily and let the existing pipeline figure it out"; AI generation as primary image source; blocking recipe save on image-acquisition failure.

See: `.planning/research/FEATURES.md`

### Architecture Approach

Pipeline today: `acknowledge → gather → instructions → ingredients → metadata → load → notify`.
Pipeline target: `gather|gather-from-url → instructions → ingredients → metadata → recipe-image → load → finalize-outcome`.

**Major components (target state):**
1. **`gateway/handler.py`** — Telegram → DB writes (Conversation, StoredMessage, RobotinaInvocation) → enqueue. Single responsibility.
2. **`queue/models.py`** — all persistent state + new `RobotinaInvocation` (placement here, NOT in gateway/models — avoids cycles).
3. **`queue/workflow_runner.py`** — workflow lifecycle + new `_check_wake_robotina(run, session, queue)` helper that takes the existing session (NOT its own).
4. **`queue/jobs.py`** — universal RQ entry point; dispatches `WakeInvocationInput` vs `IncomingMessageInput`.
5. **`agent/tools/start_workflow.py`** — `return_direct=False`, multi-call, discriminated-union input, `invocation_id` injected at construction (NOT mutable shared state).
6. **`agent/tools/respond.py`** (NEW) — non-terminal; enqueues a `send-notification` job at front (NOT direct `asyncio.run()`); inherits AOF persistence.
7. **`agent/tools/terminate.py`** (NEW) — terminal (`return_direct=True`).
8. **`agent/workflows.py`** — two registered variants `add-recipe-from-query` and `add-recipe-from-url` (recommended over dynamic step list); last step is deterministic `finalize-outcome`.

**Wake rule:** when all WorkflowRuns sharing a `triggered_by_invocation_id` reach terminal status (done OR failed), enqueue a new Robotina invocation. Idempotency via `wake_dispatched_at` column + atomic `UPDATE ... WHERE wake_dispatched_at IS NULL RETURNING id`. Pre-assign next invocation's `job_id` before commit (D-07 pattern).

See: `.planning/research/ARCHITECTURE.md`

### Critical Pitfalls

1. **Wake-rule double-fire on manual retry** — concurrency=1 doesn't save you; manual requeue from `FailedJobRegistry` re-fires terminal transition. Fix: `wake_dispatched_at` atomic UPDATE-RETURNING.
2. **`create_agent` does NOT expose `parallel_tool_calls=False`** (issue #34010) — multi-recipe is a load-bearing LLM-behavior assumption. Fix: dedicated smoke test BEFORE the tool-surface flip; `StartWorkflowTool` self-contained per call.
3. **SSRF + resource exhaustion on user-supplied URLs** — `recipe-scrapers` is parser-only; *we* own the fetch. Local dev runs agent on host with Postgres/Redis in Compose → `localhost` exposes the host. Fix: single `safe_fetch` helper with six layered defenses; FIRST commit in the URL phase; reused by image phase.
4. **Three-step Alembic migration for NOT NULL FKs** — single-shot with JSON-path backfill is fragile. Fix: nullable → separate data migration → enforce. Block deploy if in-flight workflows.
5. **`WorkflowRun.outcome` schema bloat** — verbose outcomes blow Robotina's context window after 3–4 chained batches. Fix: Pydantic `AddRecipeOutcome(BaseModel)` enforced at write time (~200 bytes/workflow).
6. **`return_direct=True` removal lets final AI text leak** — final assistant message becomes "user-facing" by default. Fix: `respond()` is the ONLY user-visible channel; `terminate()` is `return_direct=True`; never forward `result["messages"][-1].content`.
7. **`acknowledge-add-recipe` removal has hidden surface area** — `AGENT_REGISTRY` + every `overrides/*.json` + prompts dir + tests + dashboard + LangWatch. Fix: grep the literal string; add CI guard for AGENT_REGISTRY ↔ overrides.
8. **`respond()` sync/async boundary** — Telegram is async, RQ worker is sync. Fix: `respond()` enqueues `send-notification` at front (mirror existing pattern per memory `feedback_queue_at_front.md`); sequence-keyed idempotency.
9. **Wrong-dish images saved silently** — image search returns plausible-but-wrong images. Fix (V1): accept top result with documented quality risk; vision-LLM validation deferred to v1.2.

See: `.planning/research/PITFALLS.md`

## Implications for Roadmap

### Phase A: Conversation FK closure (foundation)
**Delivers:** `conversation_id` FK + nullable `outcome`; backfill; deprecation window for `reply_context`.
**Avoids:** Pitfall #4 (Alembic three-step).
**Risk:** MEDIUM.

### Phase B: RobotinaInvocation entity (additive, no wake yet)
**Delivers:** `RobotinaInvocation` table + `InvocationTrigger` enum + `UniqueConstraint(trigger_ref_id, trigger='workflow_completion')`; gateway writes invocation row; `triggered_by_invocation_id` populated by `StartWorkflowTool`.
**Avoids:** Pitfall #1 setup.
**Risk:** LOW.

### Phase C: LLM multi-call smoke test ⚠ MUST PRECEDE E
**Delivers:** experiment script in `experiments/robotina/`; evidence on multi-call reliability per backend; multi-recipe eval set (30–50 Spanish utterances).
**Avoids:** Pitfall #2.
**Risk:** HIGH (load-bearing).

### Phase D: Wake rule + outcome plumbing
**Delivers:** `_check_wake_robotina(session)` called from both `on_step_complete` AND `on_step_failed`; `wake_dispatched_at` atomic guard; pre-assigned `job_id` (D-07); startup reconciler; `WorkflowOutcome` Pydantic; `finalize-outcome` deterministic step; `WakeInvocationInput`; Robotina prompt V004.
**Avoids:** Pitfalls #1, #5.
**Risk:** MEDIUM-HIGH.

### Phase E: Tool-surface flip + remove acknowledge/notify
**Delivers:** `RespondTool` (front-of-queue `send-notification`); `TerminateTool` (return_direct=True); `StartWorkflowTool` refactored (multi-call, discriminated-union, invocation_id at construction); `acknowledge-add-recipe` deleted from AGENT_REGISTRY + all overrides + prompts + tests + dashboard; `notify` step removed; CI guard for AGENT_REGISTRY ↔ overrides; Robotina prompt V005.
**Avoids:** Pitfalls #6, #7, #8.
**Risk:** MEDIUM.

### Phase F: Multi-recipe (Topic 1, prompt-only)
**Delivers:** Robotina prompt V006 (extraction + consolidated reply + soft cap at 5); eval ≥95% on Anthropic/OpenAI, ≥85% on Ollama dev.
**Avoids:** Pitfall #2 compound.
**Risk:** MEDIUM.

### Phase G: URL ingestion (Topic 2)
**Delivers:** `safe_fetch` helper (FIRST commit — six SSRF defenses); `gather-from-url` task type + agent + prompt; recipe-scrapers integration with `wild_mode=True` + per-field try/except + LLM fallback; `add-recipe-from-url` workflow variant; Robotina prompt V007 (URL detection); 20-URL eval ≥85% field-level success.
**Avoids:** Pitfall #3.
**Risk:** MEDIUM.

### Phase H: Recipe images (Topic 3)
**Delivers:** `recipe-image` task type + agent + Tavily-image-search tool; non-fatal step semantics in runner (structured "unavailable" artifact advances; only infrastructure failures propagate); `image_url` field on recipe POST (backend coordination); magic-byte validation + EXIF strip; `safe_fetch` reuse for image URL; `AddRecipeOutcome.image_present` flag.
**Avoids:** Pitfall #9 (V1 accepts top result; vision-LLM validation deferred).
**Risk:** LOW-MEDIUM.

### Phase Ordering Rationale

- **A → B → C → D → E** is dependency-forced.
- **C standalone** is the strongest non-negotiable: every later phase's design pivots on its outcome.
- **F prompt-only** after E because multi-call mechanic must work before multi-recipe prompt.
- **G before H** because both need `safe_fetch` AND the URL-sourced image path is the best image source.
- **Risk concentration:** front-load A (migration), C (LLM check), D (wake), E (flip); F/G/H ride stable foundations.

### Research Flags

**Phases needing deeper research at planning time:**
- **Phase C** — empirical investigation, not library research; the smoke test IS the research.
- **Phase G** — inspect `agent/skills/household-manager/` for image-storage API (pin-URL vs. download+rehost decision); recipe-scrapers `wild_mode` spike against 20 representative Spanish-language URLs.
- **Phase H** — Tavily image-search quality eyeball test on 20 regional recipe names; household-manager `image_url` field coordination with backend team.

**Phases with standard patterns:** A (Alembic three-step), B (additive entity), D (D-07 already in codebase), E (mechanically well-bounded), F (prompt-only iteration).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All additions verified against PyPI + Context7 + official docs; existing v1.0 stack documented in CLAUDE.md. |
| Features | MEDIUM-HIGH | Patterns well-documented; multi-call vs list-form leans on research consensus pending Phase C confirmation. |
| Architecture | HIGH | Current code verified by direct reading; placement decisions follow existing import-direction conventions; build-order is dependency-forced. |
| Pitfalls | HIGH (architecture) / MEDIUM (LangChain semantics) / MEDIUM-LOW (third-party quality) | D-07/D-16/WR-02/Phase 11/16 invariants all verified; LangChain parallel-tool-call verified via GitHub #34010; recipe-scrapers Spanish-blog hit rate is largest unknown. |

**Overall:** HIGH for architectural plan and stack; MEDIUM for LLM-behavior assumptions (Phase C exists to convert speculation to evidence); MEDIUM-LOW for third-party quality (flagged for phase-level spikes).

### Gaps to Address

- LangChain `create_agent` parallel-tool-call behavior on `gpt-oss:20b` → Phase C smoke test; outcome may pivot E schema to list-form.
- Household-manager image-storage API surface → Phase G planning reads skill files; V1 pins source URL if no upload endpoint exists.
- `recipe-scrapers` `wild_mode` hit rate on Spanish-language blogs → Phase G spike; LLM fallback covers gap.
- Tavily image-search quality on Argentine/Uruguayan recipes → Phase H spike; escalate to vision-LLM or generation only if <60% usable.
- Downstream pipeline tolerance of pre-populated `RecipeData` (URL path) → may need refine-vs-create mode flag on instructions/ingredients/metadata steps; surface as Phase G risk.
- Per-source workflow variant vs. dynamic step list → ARCHITECTURE recommends per-source variants; revisit if a third branching workflow ever lands.

## Sources

### Primary (HIGH)
- `/hhursev/recipe-scrapers` (Context7) — canonical Python recipe extraction
- `https://pypi.org/pypi/recipe-scrapers/json` — 15.11.0, Python 3.10–3.14
- `https://docs.tavily.com/sdk/python/reference` — `include_images` parameters
- `https://docs.langchain.com/oss/python/langchain/agents` — `create_agent` ReAct semantics
- `https://github.com/langchain-ai/langchain/issues/34010` — `parallel_tool_calls` not exposed
- `https://docs.recipe-scrapers.com/` — parser-only; caller owns network/security
- Internal: `src/robotina/queue/workflow_runner.py`, `src/robotina/agent/tools/start_workflow.py`
- Internal: `CLAUDE.md`, `plans/02-workflow-refinement/description.md`

### Secondary (MEDIUM)
- CodeQL / Bearer / Datadog SSRF rules
- AWS SQS partial-batch-failure / S3 Batch tri-state status
- Agenta / DEV / ML Journey — multi-tool-call vs list-form patterns
- `https://developers.openai.com/api/docs/models/gpt-image-1` — DALL-E 3 → gpt-image-1
- costgoat.com / intuitionlabs.ai — image-generation pricing

### Tertiary (LOW)
- Spanish-language blog coverage by `wild_mode` — validate in Phase G
- Tavily image-search quality on regional recipes — validate in Phase H

---
*Research completed: 2026-05-18*
*Ready for roadmap: yes*
