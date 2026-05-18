# Feature Research — Milestone v1.1 Workflows Abstraction Refinement

**Domain:** Recipe-management Telegram agent — three product features (multi-recipe per message, URL-pointed recipe, recipe images)
**Researched:** 2026-05-18
**Confidence:** MEDIUM-HIGH (recipe-scrapers/SSRF/image-source patterns well-documented; consolidated-reply UX patterns are convention-driven, not standardized)

## Scope & Reading Order

This research is grouped by the THREE new feature categories in this milestone. Existing capabilities (single-recipe text-query pipeline, Telegram gateway, RQ queue, LangWatch instrumentation, 4-layer household_id validation, `response_format=PydanticModel`) are NOT re-researched — see `.planning/PROJECT.md` for the v1.0 baseline.

The architectural refactor (Robotina-as-decider, `RobotinaInvocation` entity, FK closure on `WorkflowRun`, wake-when-all-workflows-done, removal of `acknowledge-add-recipe`) is the *enabler* for these features but is documented separately in `plans/02-workflow-refinement/description.md`. This file focuses on what each *product feature* needs and what to skip.

Categories below are intended to become REQUIREMENTS.md sections.

---

## Category 1: Multi-Recipe Intake

**Goal:** A single user message like *"agregá canelones de choclo, pollo al horno y arroz pilaf"* is parsed into N recipes; each becomes an independent `add-recipe` workflow; one consolidated final reply is sent after the last one drains.

### Table Stakes

| Feature | Why Expected | Complexity | Notes / Dependencies |
|---------|--------------|------------|----------------------|
| LLM-driven N-recipe extraction from one message | Users speak naturally ("agregá A, B y C"); rule-based splitters fail on Spanish coordination ("y", "más", commas, "porfa"). Modern recipe/cooking assistants all accept compound requests. | M | Robotina prompt teaches the pattern + bound `start-workflow` tool. Depends on `response_format` / multi-tool-call already being available in the LangChain 1.x stack (Phase 11). |
| Per-recipe independent fate (one failure ≠ batch failure) | Cancelling 3 recipes because canelones failed is unacceptable. Industry convention (AWS SQS partial-batch-failure, S3 Batch Operations PARTIAL status) treats per-item outcomes as independent. | S | Already aligned with the milestone's "fate-sharing is workflow's scope" rule. Each workflow = independent. |
| Consolidated final reply summarizing N outcomes | The user sent one message; one final reply is the natural unit. Three separate "✓ done" messages spam the chat. | S | Wake-when-all-workflows-done rule already in milestone description. Robotina sees N `WorkflowRun.outcome` rows at wake time. |
| Outcome status tri-state (SUCCESS / PARTIAL / FAILED) | S3 Batch Operations and most batch frameworks expose at minimum the three states; users need to know if *any* recipe got saved or none did. | S | Derived in the Robotina prompt from the N outcomes; no schema change beyond per-workflow `outcome`. |
| Per-recipe failure reason in the final reply | A 2-of-3 partial summary that omits *why* canelones failed is useless ("¿pero por qué?"). Compact reason strings on the failed outcomes. | S | `WorkflowRun.outcome` carries a short structured failure reason; Robotina renders it. |
| Order-preserving summary | If the user listed "A, B, C", the reply should reflect outcomes in that order. Reordering is confusing and looks like a bug. | S | Robotina prompt instruction; trivial once the dispatched workflow set is keyed by user-provided position. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes / Dependencies |
|---------|-------------------|------------|----------------------|
| Pre-dispatch ack ("voy con 3: A, B, C — te aviso al terminar") | Sets expectations during sequential drain (concurrency=1; 3 recipes ≈ 1-3 min). Without it, the user thinks Robotina ignored them. | S | One `respond()` call before the N `start-workflow` calls in the same Robotina turn. Already supported by the new tool surface. |
| Inline correction / deduplication ("ya tenés pollo al horno; lo agregás igual?") | Saves the user from creating duplicates when their library is small. Differentiator vs. raw batch ingest. | M | Robotina pre-checks via `household-manager-api` read tools before dispatching workflows. Depends on the existing list-recipes read tool. |
| Mixed intent in one batch (e.g. "agregá A y B, y borrá C") | Power-user UX; the same dispatch model trivially supports heterogeneous workflow types. | M | Future-friendly: the `start-workflow` tool already accepts `workflow_type`. Requires `delete-recipe` workflow (not in this milestone) so deferred. |
| Chunked progress chatter ("listo canelones, sigo con pollo…") | More engaging during long batches. | M | The milestone description explicitly punts this: "mid-batch progress chatter from a single Robotina turn" is **out of scope** for V1; the answer is workflow chunking, not a wake-policy knob. Deferred. |

### Anti-Features (DO NOT BUILD)

| Anti-Feature | Why Tempting | Why Problematic | Alternative |
|--------------|--------------|-----------------|-------------|
| `start-workflow(list_of_workflows=[...])` — single list-form tool call | Looks cleaner than N tool calls; one call is "simpler". | Tool-calling reliability research shows LLMs are *more* reliable emitting N independent tool calls than one tool call with an array argument, especially across providers. Structured-output success rates per step compound: 95% per-step × 10 steps ≈ 60% completion. Per-call validation is better. The milestone description lists this as an open question — research consensus leans multi-call. | Multi-call: `start-workflow` invoked N times in one Robotina turn. Matches OpenAI/Anthropic parallel-tool-call patterns. |
| Per-recipe inline assistant messages while batch drains | Feels "live" / "responsive". | Spec explicitly out of scope. The concurrency=1 worker is also processing those `send-notification` jobs in series, so they'd interleave badly with workflow steps, and there's no clear winner for ordering. Also defeats the consolidated-reply UX. | One pre-dispatch ack + one post-batch consolidated reply. Use workflow chunking if mid-batch is truly needed. |
| Rule-based regex/grammar splitter (commas, "y", "más") | Cheap, no LLM cost. | Spanish coordination + user-paste variability + emojis + URLs mixed with names = fragile. The same Robotina turn that needs to decide *intent* is already an LLM call; let it produce the N items as structured tool calls. | LLM extraction (Robotina turn) producing N `start-workflow` calls. |
| Hard cap "max 10 recipes per message" enforced at gateway | "Safety" against runaway batches. | Premature; concurrency=1 already throttles. A cap at the Robotina-prompt level (soft guidance) is fine, but a hard gateway reject creates a confusing failure mode. | Soft guidance in the Robotina prompt: if the user lists >N, ask for confirmation. Hard caps only at higher layers if abuse appears. |
| Retry-failed-only "redo" tool | Looks helpful; mirrors AWS SQS partial-batch retry. | Each workflow is already idempotent at the household-manager level (recipe name uniqueness check); a redo is just "send the message again". No retry state machine needed in V1. | The user re-asks; failed-registry rows are visible in the queue dashboard for operator inspection (already shipped in Phase 13). |

### Complexity Hint Summary

| Concern | Hint | Driver |
|---------|------|--------|
| Robotina prompt — multi-recipe extraction | S | Single prompt change + `response_format` already in place |
| Robotina prompt — consolidated-reply composition over N outcomes | M | Prompt-quality work, but small structurally |
| Removing the `return_direct=True` on `StartWorkflowTool` | S | Already called out in the milestone migration notes |
| Tracking outcomes back to the originating Robotina invocation | M | New `triggered_by_invocation_id` FK + wake check |
| Test coverage (1, 2, 3, all-fail, partial-fail, all-success) | M | 5-6 integration test scenarios needed |

### Dependencies on Existing Features

- **`RobotinaInvocation` entity** (milestone refactor) — wake rule requires it
- **`WorkflowRun.outcome`** column (milestone refactor) — compact per-recipe summary
- **`StartWorkflowTool` without `return_direct=True`** (milestone refactor) — allows N calls per turn
- **Existing `add-recipe` workflow** (v1.0) — unchanged; each batch item is one instance
- **Existing `response_format=PydanticModel`** (Phase 11) — schema-constrained outputs
- **Existing 4-layer `household_id` validation** (Phase 16) — same household across all N dispatches

---

## Category 2: URL-Pointed Recipe Ingestion

**Goal:** *"agregá esta receta: https://example.com/foo"* ingests THAT recipe (not a hallucinated variant). New `gather-from-url` first step; downstream pipeline unchanged.

### Table Stakes

| Feature | Why Expected | Complexity | Notes / Dependencies |
|---------|--------------|------------|----------------------|
| schema.org Recipe JSON-LD extraction (primary path) | The overwhelming majority of food-blog and recipe sites publish JSON-LD Recipe markup; `recipe-scrapers` library handles 639 explicitly supported sites plus generic schema.org via `wild_mode`. | S | Use `recipe-scrapers` (`pip install recipe-scrapers`). Library parses JSON-LD, Microdata, RDFa, OpenGraph; the spec already names it. |
| Microdata + RDFa + OpenGraph fallback | Older sites use Microdata/RDFa; many blogs at least set OpenGraph image + title. `recipe-scrapers` covers all of these natively. | S | Included in `recipe-scrapers`; no extra work. |
| LLM fallback for sites without structured data | The long tail of personal blogs publishes recipes as plain HTML. Without LLM extraction, those URLs hard-fail. | M | New `gather-from-url` agent: fetches HTML, runs LLM extraction with `response_format=RecipeData`. Reuses the Pydantic schema already produced by `recipe-research-gather`. |
| SSRF defense: scheme allowlist (`http`, `https` only) | Without it, `file://`, `gopher://`, `ftp://` schemes can hit local files / internal services. CodeQL, Bearer, Snyk all flag this. | S | Validate parsed URL scheme before fetch. One-liner. |
| SSRF defense: block private/loopback/link-local IP ranges after DNS resolution | Attacker provides a URL whose hostname resolves to `127.0.0.1`, `169.254.169.254` (cloud metadata), `10.x.x.x`, `192.168.x.x`. Requires post-DNS-resolution IP check. | M | Resolve hostname → check IP against private ranges before issuing the HTTP request. Standard SSRF mitigation. |
| Redirect handling — manually-followed, re-validated | `requests`/`httpx` defaults follow redirects and do NOT re-validate the destination IP. SSRF papers cite this as the #1 bypass. | M | Set `follow_redirects=False`; manually iterate up to N redirects, re-running scheme + IP checks each hop. |
| Connection + read timeouts | An attacker URL that hangs forever blocks the sequential worker (concurrency=1). | S | `httpx.Timeout(connect=5, read=15)` baseline. |
| Content-Type validation | Servers can return non-HTML (huge binaries, video streams). | S | Check `Content-Type` starts with `text/html` or `application/xhtml+xml`; reject otherwise. |
| Response size cap | A 100MB HTML page exhausts memory. | S | Stream + abort after ~5MB (configurable). |
| Source-discriminator at workflow input (`{kind: "query" \| "url", value: ...}`) | The add-recipe pipeline must know which first step to run; downstream stays identical. | S | Already designed in milestone description. Pydantic discriminated union. |
| URL extraction from the user message | The user types "agregá esta: https://...", not a bare URL. Robotina must extract the URL substring before calling `start-workflow`. | S | Standard URL regex in the Robotina prompt; or pass the whole message as `value` and let the `gather-from-url` agent re-parse. The former is cleaner. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes / Dependencies |
|---------|-------------------|------------|----------------------|
| Robust LLM fallback with HTML→markdown reduction before extraction | Cleaner LLM context, lower hallucination on prose blogs. | M | Use `readability-lxml` or similar to strip nav/ads before LLM extraction. Defer to V2 unless wild_mode failure rate is high. |
| Translate non-Spanish recipe content into Spanish at ingestion | Family speaks Spanish; English/Italian recipe sites are common. | M | Add a translation step (or instruct the existing `recipe-research-instructions` / `recipe-research-ingredients` steps to translate during their already-LLM-driven refinement). Cheaper than a dedicated translation step. |
| Cache scraped URL → RecipeData for re-ingestion / idempotency | Avoid re-fetching when the user pastes the same URL twice. | M | Hash URL → DB row. Marginal value at our scale; defer. |
| Per-site adapter fallback (curated scraper override) | `recipe-scrapers` already has 639 site-specific adapters. | S | Free — `recipe-scrapers` picks site-specific adapter automatically before `wild_mode`. Not extra work. |
| Honor `robots.txt` / publisher ToS | Reputational/legal. Most cooking-blog ToS allow user-driven scraping for personal use, but it's polite. | S | Optional; many open-source recipe apps skip this. Document as a known concern. |

### Anti-Features (DO NOT BUILD)

| Anti-Feature | Why Tempting | Why Problematic | Alternative |
|--------------|--------------|-----------------|-------------|
| "Just pass the URL to Tavily and let the existing query-pipeline figure it out" | Reuses the existing 5-step pipeline; one less code path. | This is *exactly* the bug the milestone exists to fix — Tavily returns *similar* recipes, and the LLM hallucinates a variant. Defeats the entire "use THIS exact recipe" promise. | New `gather-from-url` first step that does deterministic extraction first, LLM fallback second. |
| Following redirects with `follow_redirects=True` (the `requests`/`httpx` default) | "Simpler code." | Re-enables every SSRF bypass. `requests.get(url, allow_redirects=False, timeout=5)` is the documented secure pattern. | Manual redirect loop with re-validation per hop. |
| Trust-the-URL-scheme-from-user-input | Bare check on `urlparse(url).scheme in {"http","https"}` looks safe. | An attacker can craft `urlparse("javascript:...")` or use schemes a registered transport adapter handles. Combined with redirects, can land elsewhere. | Allowlist + scheme + IP-range + content-type, all four. Defense in depth. |
| Custom HTML parser ("we'll handle JSON-LD ourselves") | Avoids a dependency. | `recipe-scrapers` covers 639 sites + wild_mode for free, with active maintenance. Hand-rolling reimplements years of edge cases. | Use `recipe-scrapers`; only the LLM-fallback path is custom. |
| Allowing `data:` URIs / base64-embedded HTML | "Power user feature." | Bypasses all network defenses; no real use case. | Reject anything that isn't `http(s)://`. |
| Aggressive retry on URL fetch | "Robustness." | A slow/down site blocks the sequential worker even longer; user gets nothing for minutes. | One attempt, short timeout, clean failure → workflow outcome = `recipe_fetch_failed` with a Spanish reason. |
| Caching scraped HTML on disk | "Performance." | Compliance/PII risk (third-party content), and the worker is single-tenant on a single household; cache hit rate is near-zero. | None — re-fetch on retry. |

### Complexity Hint Summary

| Concern | Hint | Driver |
|---------|------|--------|
| `recipe-scrapers` integration | S | One library call, well-documented |
| LLM fallback agent (`gather-from-url` task type) | M | New agent definition, prompt, tool wiring (similar shape to `recipe-research-gather`) |
| SSRF defenses (scheme + IP + redirect + content-type + size + timeout) | M | Layered checks; existing patterns from CodeQL/Bearer/Snyk; ~100 LOC including tests |
| Source-discriminator wiring in `add-recipe` workflow definition | S | Pydantic discriminated union + first-step branch |
| Robotina prompt — extracting URLs from "agregá esta receta: https://..." | S | One prompt rule + a few examples |
| Integration tests against fixture HTML (known JSON-LD site + LLM-fallback site) | M | Need realistic HTML fixtures for both paths |

### Dependencies on Existing Features

- **Existing `add-recipe` workflow pipeline** — downstream steps (instructions/ingredients/metadata/load) reused verbatim; the `gather-from-url` step produces a `RecipeData` matching the existing schema
- **Existing `RecipeData` Pydantic schema** (Phase 15) — must be sufficient as the contract; the milestone description flags as an open question whether downstream "research" steps can tolerate well-populated input vs. needing refinement semantics
- **Existing `response_format=PydanticModel`** (Phase 11) — LLM fallback agent uses it
- **Existing `httpx` dependency** (already in stack) — for the URL fetch; configure with SSRF defenses
- **Existing food/unit semantic validation tools** (Phase 15) — downstream `recipe-research-ingredients` will still validate URL-sourced ingredient names

---

## Category 3: Image Acquisition

**Goal:** Every saved recipe gets an associated image when one is available. Failure to acquire an image is non-fatal (recipe still saves); the gap is reported in `WorkflowRun.outcome`.

### Table Stakes

| Feature | Why Expected | Complexity | Notes / Dependencies |
|---------|--------------|------------|----------------------|
| Image URL associated with each saved recipe | Recipes without images "feel half-done in any household UI" (milestone description). Industry-standard table stakes for recipe apps. | S | New `image_url` column on the recipe record (household-manager backend; coordinate with that team) OR Robotina stores it as part of the recipe payload. |
| Non-fatal image failure (recipe still saves; outcome reports gap) | Image-source APIs are flaky; blocking recipe save on flaky third-party APIs is unacceptable. | S | Already designed in milestone description. Image step's failure does not cancel the downstream `recipe-load` step. **Note:** This breaks the existing "fate-sharing" rule for one specific step — needs explicit handling. |
| Source for the image: web image search (V1 lean) | Milestone description says "V1 lean: web image search." Cheaper, faster, and yields real food photos rather than AI hallucinations. | S | Tavily already in the stack supports image search; or Unsplash/Pexels APIs (free tiers; well-documented). |
| Source URL pinned (not re-hosted) for V1 | Self-hosting needs CDN/storage decisions out of scope for this milestone. The milestone description leaves this open. | S | Store the third-party URL on the recipe record. Document link-rot risk; revisit if it becomes a real problem. |
| Per-recipe image-search query construction | "Canelones de choclo" + locale hint produces better results than just the dish name. | S | Image-search agent gets the full `RecipeData` and constructs a query. |
| URL validation before save (same SSRF hardening as Category 2) | Image URLs come from third-party APIs but still need scheme + content-type + IP-range checks since the URL gets persisted and re-served. | S | Reuse the SSRF-validation helper from Category 2. |
| Honor the image API's attribution requirement | Unsplash/Pexels require attribution per ToS. If we don't honor it, we violate API terms. | S | Persist photographer + source URL alongside the image; render attribution wherever the image is shown. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes / Dependencies |
|---------|-------------------|------------|----------------------|
| Image taken directly from the source page when URL-ingesting | For URL-pointed recipes, the page's own hero image (from `recipe-scrapers`' `.image()` method or OpenGraph `og:image`) is the *right* image. Avoids a redundant search. | S | `recipe-scrapers` returns image URL natively. Use it as the V1 default for URL-sourced recipes; fall back to web image search only if missing. |
| AI image generation fallback (DALL-E / Stable Diffusion) | When neither the source page nor image search yields a usable image, generate one. Surface differentiator. | L | Expensive, slow, and AI-generated food images have a known "uncanny valley" quality. Defer to V2 unless image-search hit rate is poor. |
| Image-quality heuristic ("is this actually food?") via a vision model | Image search returns plenty of off-topic results; a classifier filter improves hit rate. | L | Real value but high complexity. Defer to V2. |
| Re-host (download + store in backend) to avoid link rot | Long-term archive value; Unsplash URLs can change. | M | Requires backend image-storage endpoint, which is out of scope for this milestone (and a household-manager-side decision). Defer. |
| Alt-text generation for accessibility | Best practice for any UI that displays images. | S | Trivial — use the recipe name as alt text. Add when client app surfaces images. |
| Image-quality heuristic without ML (dimensions, file size, aspect ratio) | Reject 50×50 thumbnails. | S | Cheap; check during URL validation. |

### Anti-Features (DO NOT BUILD)

| Anti-Feature | Why Tempting | Why Problematic | Alternative |
|--------------|--------------|-----------------|-------------|
| AI image generation as the primary image source | "Always produces an image; never depends on third-party search APIs." | Cost (DALL-E is $0.04+ per image, 3× the cost of the *whole rest of the recipe workflow*), latency (slow on the sequential worker — blocks the queue), and the well-documented "AI-generated food looks plastic" problem. Real food photos from Unsplash/Pexels look better and are free or cheap. | Web image search (Tavily / Unsplash / Pexels); generation only as a Differentiator fallback in V2. |
| Block recipe save on image-acquisition failure | "Better not to save a half-done recipe." | The milestone description explicitly forbids this: "Failure to acquire an image is non-fatal (recipe still saves)." Real users prefer a saved recipe with no image to no saved recipe at all. | Non-fatal failure; report gap in `outcome`. |
| Aggressive retry on image search | "Robustness." | Same as URL-fetch retry: blocks the sequential worker. | One attempt, short timeout, mark gap, continue. |
| Image hotlinking via API URL without compliance with `Authorization`/cache rules | "Simplest possible thing." | Unsplash requires hotlinking through their proxied URLs (not raw S3 paths). Bypassing means breakage when they rotate URLs, plus ToS violation. | Use the official API's returned URL exactly; honor cache headers. |
| Per-recipe image *skip* control (user-driven "no image please") | Could be useful for some users. | Milestone description says "Per-recipe skippability (later; not V1 blocker)." | Defer. |
| Store images directly in Postgres (BYTEA) | Avoids a separate storage system. | Image data in Postgres bloats backups, hurts query performance, and locks us out of CDN serving later. Industry consensus: blob storage, not relational. | Store URL only in V1; consider object storage + CDN in V2 if re-hosting becomes a requirement. |
| Inferring image acceptability from search result rank alone | "Top result is usually best." | False often enough to matter: top Tavily/Unsplash result for "tarta" might be a generic tart, not the Argentine version. | Accept top result for V1; add quality filtering only if user complaints accumulate. |

### Complexity Hint Summary

| Concern | Hint | Driver |
|---------|------|--------|
| New `recipe-image` task type + agent + prompt | M | Standard agent shape, similar to existing research steps |
| Image-source tool wiring (Tavily image search OR Unsplash/Pexels) | S | One HTTP-tool wrapper; choose one provider |
| Non-fatal step semantics in the workflow runner | M | New: existing runner cancels remaining steps on any step failure. Image step needs an exception. Either a per-step `non_fatal=True` flag or a `try-extract-image-then-load` shape where the image step writes "missing" instead of failing. |
| `image_url` field on recipe — coordination with household-manager backend | S-M | External team coordination; treated as a known precondition. |
| URL-sourced path uses `recipe-scrapers`' `.image()` directly | S | Free; comes from the library already used for URL ingestion |
| SSRF/content-type validation on image URL before persist | S | Reuse helper from Category 2 |

### Dependencies on Existing Features

- **`recipe-scrapers` library** (from Category 2) — provides the source-page image for URL-sourced recipes
- **Existing `recipe-load` step** (v1.0) — receives an `image_url` field on the recipe payload; needs schema extension
- **`WorkflowRun.outcome`** (milestone refactor) — reports the "image missing" gap in a non-fatal way
- **Existing food/unit validation pipeline** (Phase 15) — image step runs *after* validation, *before* `recipe-load`; doesn't interact with validation
- **household-manager backend** (external) — must accept and store an `image_url` field on the recipe entity (out-of-repo coordination)

---

## Cross-Cutting Concerns

### URL Fetching Safety (used by Categories 2 + 3)

Both URL ingestion and image-URL persistence need the same hardened HTTP-fetch helper. Build it once.

**Required defenses (defense in depth):**
1. Scheme allowlist: `{"http", "https"}`
2. Hostname resolution → reject private/loopback/link-local IP ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16`, `::1`, `fc00::/7`)
3. Manual redirect handling with per-hop re-validation (no `follow_redirects=True`)
4. Connect + read timeouts (e.g. 5s / 15s)
5. Content-Type validation (HTML for Category 2; image/* for Category 3)
6. Response size cap (stream + abort)

**Implementation note:** A single `safe_fetch(url, allowed_content_types=...)` helper at the `tools/` layer is cleanest. Used by both `gather-from-url` and `recipe-image`.

### Spanish-Language UX

All user-facing output (per the existing project rules in `CLAUDE.md` and stored memories) must be in Spanish. The consolidated reply, partial-failure summaries, and image-missing notices all flow through Robotina's reply composition.

### LangWatch Trace Correlation

Each of the three feature categories adds new agent task types (`gather-from-url`, `recipe-image`) and changes Robotina's tool-call patterns. All new agents must be wired with the existing middleware-based LangWatch instrumentation (Phase 12) so traces appear in the correct experiment collection. Existing pattern is well-documented; no new work beyond following it.

### Queue Visibility Dashboard

The dashboard (Phase 13) already shows `step_input` and `failure_reason`. Multi-recipe batches will produce N concurrent-looking workflows (actually sequential under concurrency=1). The dashboard should remain usable without changes; verify in QA that the `triggered_by_invocation_id` grouping is queryable for debugging.

---

## Feature Dependencies Across Categories

```
Multi-Recipe Intake (Category 1)
    └── requires ──> Robotina-as-decider refactor (RobotinaInvocation, wake rule, return_direct removal)
                          └── enables ──> chaining (post-batch Robotina turn re-dispatches if needed)

URL Ingestion (Category 2)
    └── requires ──> new gather-from-url task type + source-discriminator on add-recipe input
    └── enables ──> source-page image (Category 3 differentiator)

Image Acquisition (Category 3)
    └── requires ──> new recipe-image task type
    └── requires ──> non-fatal-step semantics in workflow runner (NEW exception to fate-sharing rule)
    └── requires ──> image_url field on recipe entity (household-manager backend coordination)
    └── enhances ──> URL ingestion (Category 2): source-page image is the best path when available

Cross-cutting:
    safe_fetch(url) helper
    ├── used by Category 2 (URL ingestion)
    └── used by Category 3 (image URL validation)
```

---

## MVP Definition for This Milestone

### Launch With (v1.1)

- [ ] **Multi-recipe parsing in Robotina** — N `start-workflow` calls in one turn, consolidated post-batch reply (Category 1 table stakes)
- [ ] **URL-pointed ingestion** via `recipe-scrapers` (JSON-LD + Microdata + RDFa + OpenGraph + wild_mode) with LLM fallback (Category 2 table stakes)
- [ ] **`safe_fetch` helper** with all six SSRF defenses (cross-cutting)
- [ ] **Image acquisition** — source-page image when URL-sourced, web image search otherwise; non-fatal failure (Category 3 table stakes)
- [ ] **Per-recipe `WorkflowRun.outcome`** with structured success/failure rendering in the final reply
- [ ] **Order-preserving consolidated reply** in Spanish
- [ ] **Image URL validated via the SSRF helper** before persist (Category 3 table stakes)

### Add After Validation (v1.2+)

- [ ] **Pre-dispatch ack** ("voy con 3…") — easy win, defer if Robotina prompt is already complex enough
- [ ] **Inline deduplication check** before dispatch (Category 1 differentiator)
- [ ] **Spanish translation** of non-Spanish source pages (Category 2 differentiator)
- [ ] **Image dimension/aspect-ratio sanity filter** (Category 3 cheap differentiator)
- [ ] **`recipe-scrapers` site-specific adapter coverage audit** — pin a tested list

### Future Consideration (v2+)

- [ ] **Workflow chunking for mid-batch chatter** — when real use cases push on it
- [ ] **Mixed-intent batches** (add + delete + update in one message) — requires more workflow types
- [ ] **AI image generation fallback** — only if image-search hit rate proves poor
- [ ] **Vision-model "is this food?" filter** — requires a vision model in the stack
- [ ] **Re-host images on a household-manager-hosted CDN** — requires backend storage decisions
- [ ] **HTML→markdown reduction before LLM extraction** — V1 wild_mode + raw HTML is fine for an early version
- [ ] **URL/HTML caching for idempotent re-ingestion** — premature at current scale

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| N-call multi-recipe extraction | HIGH | LOW (prompt change + existing tooling) | P1 |
| Consolidated final reply | HIGH | LOW (prompt + outcome rendering) | P1 |
| Per-workflow `outcome` field on `WorkflowRun` | HIGH | LOW (schema + writer) | P1 |
| `recipe-scrapers` integration | HIGH | LOW (one library) | P1 |
| `gather-from-url` LLM-fallback agent | HIGH | MEDIUM (new agent + prompt + tool wiring) | P1 |
| `safe_fetch` SSRF helper | HIGH (correctness/security) | MEDIUM (multiple defenses + tests) | P1 |
| `recipe-image` agent (search-based) | HIGH | MEDIUM (new agent + image-search tool wiring) | P1 |
| Non-fatal step semantics in runner | HIGH (required by image step) | MEDIUM (runner change + tests) | P1 |
| Source-page image (recipe-scrapers `.image()`) | MEDIUM | LOW (free with recipe-scrapers) | P1 |
| Image URL validation pre-persist | HIGH (security) | LOW (reuse helper) | P1 |
| Pre-dispatch ack message | MEDIUM | LOW | P2 |
| Pre-dispatch dedup check | MEDIUM | MEDIUM (extra read call before dispatch) | P2 |
| Spanish translation of foreign recipes | MEDIUM | MEDIUM | P2 |
| Image dimension sanity filter | LOW-MEDIUM | LOW | P2 |
| AI image generation fallback | LOW-MEDIUM | HIGH | P3 |
| Vision-model "is this food" filter | MEDIUM | HIGH | P3 |
| Image re-hosting on backend CDN | MEDIUM | HIGH (requires backend work) | P3 |
| Workflow chunking pattern | LOW (until real demand) | MEDIUM | P3 |
| URL/HTML caching | LOW | MEDIUM | P3 |

**Priority key:**
- **P1:** Must have for v1.1 launch
- **P2:** Should have, add when implementation bandwidth allows; not launch-blocking
- **P3:** Defer until product feedback justifies the cost

---

## Open Questions Carried From Milestone Description

These come straight from `plans/02-workflow-refinement/description.md` "Decisions deferred to milestone discovery". This research informs them but does not close them — phase planning will:

1. **Multi-call vs list-form `start-workflow`** — Research leans **multi-call** (research consensus on tool-calling reliability, parallel-tool-call patterns in OpenAI/Anthropic). Confirm during Robotina prompt design.
2. **URL scraping library choice + fallback ladder** — Research recommends **`recipe-scrapers` (JSON-LD via library) → wild_mode → LLM fallback → fail**. Confirm by validating `recipe-scrapers` against the family's likely recipe-blog corpus in early phase work.
3. **Image source for V1 + storage location** — Research recommends **source-page image first (recipe-scrapers `.image()`) → web image search (Tavily or Unsplash) → mark missing**. Storage: pin source URL in V1; defer re-hosting decisions.
4. **Prompt shape for reliable multi-`start-workflow`** — Phase 11 (`response_format`) and the LangChain 1.x `create_agent` API already enable this. The risk is prompt-quality, not engine-capability. Plan iteration time in the phase.
5. **Wake edge cases (timeout vs failure)** — Both should count as terminal for wake. Confirm by pinning RQ failure-registry semantics in the runner change.
6. **`RobotinaInvocation` first-class vs in-memory** — Milestone description leans first-class; this research has no reason to disagree.
7. **Downstream pipeline tolerance of pre-populated `RecipeData` (URL path)** — A real risk: instructions/ingredients/metadata steps were authored assuming sparse input. May need a "refine vs create" mode flag on each. Surface as a Phase risk.

---

## Sources

- [recipe-scrapers GitHub (hhursev/recipe-scrapers)](https://github.com/hhursev/recipe-scrapers) — 639 supported sites; JSON-LD + Microdata + RDFa + OpenGraph; `wild_mode` fallback (HIGH confidence)
- [recipe-scrapers docs (Getting Started)](https://docs.recipe-scrapers.com/) — installation + `.image()` / `.to_json()` API (HIGH)
- [scrape-schema-recipe (alternative)](https://pypi.org/project/scrape-schema-recipe/) — schema.org-only Python lib; thinner alternative to recipe-scrapers (MEDIUM)
- [Mitigating SSRF — Datadog Static Analysis rule](https://docs.datadoghq.com/security/code_security/static_analysis/static_analysis_rules/python-flask/avoid-ssrf/) — Python SSRF prevention patterns (HIGH)
- [CodeQL: Full SSRF query help — Python](https://codeql.github.com/codeql-query-help/python/py-full-ssrf/) — formal SSRF criteria (HIGH)
- [Bearer CLI — Python unsanitized URL rule](https://docs.bearer.com/reference/rules/python_lang_http_url_using_user_input/) — defense layers (HIGH)
- [Tachyon — Why SSRFs are tricky to fix](https://tachyon.so/blog/ssrfs-trickiest-issue) — redirect-revalidation bypass (MEDIUM-HIGH)
- [Writing Secure Python Applications — SSRF, SQLi, XSS](https://chs.us/2025/11/writing-secure-python-applications-preventing-ssrf-sql-injection-and-xss/) — practical Python patterns (MEDIUM)
- [Unsplash API docs](https://unsplash.com/developers) — image search API; attribution requirements (HIGH)
- [Pexels API](https://www.pexels.com/api/) — alternative image API; simpler ToS (HIGH)
- [LaoZhang AI Blog — Free Image API Comparison (Unsplash vs Pexels vs Pixabay vs Wikimedia)](https://blog.laozhang.ai/en/posts/free-image-api) — comparison rationale (LOW-MEDIUM)
- [Max Woolf — AI-Generated Food Photography with DALL-E 2](https://minimaxir.com/2022/07/food-photography-ai/) — limitations of generated food images (MEDIUM)
- [Agenta — Structured Outputs and Function Calling with LLMs](https://agenta.ai/blog/the-guide-to-structured-outputs-and-function-calling-with-llms) — multi-tool-call vs list-form (MEDIUM-HIGH)
- [DEV — Structured Outputs vs Tool Calling: When Your Agent Needs Which](https://dev.to/thedailyagent/structured-outputs-vs-tool-calling-when-your-agent-actually-needs-which-kgk) — parallel tool calls preferred over list-form (MEDIUM-HIGH)
- [ML Journey — Reliable Structured Output from LLMs](https://mljourney.com/how-to-get-reliable-structured-output-from-llms/) — 95%→60% compounding-failure framing (MEDIUM)
- [LangChain docs — Structured output](https://docs.langchain.com/oss/javascript/langchain/structured-output) — `response_format` (HIGH)
- [AWS Lambda — Reporting batch item failures (SQS trigger)](https://docs.aws.amazon.com/lambda/latest/dg/example_serverless_SQS_Lambda_batch_item_failures_section.html) — partial-batch-success pattern (HIGH)
- [AWS S3 — Tracking job status and completion reports](https://docs.aws.amazon.com/AmazonS3/latest/userguide/batch-ops-job-status.html) — SUCCESS / PARTIAL / FAILED status tri-state (HIGH)
- [OneUptime — How to Implement Batch Reporting](https://oneuptime.com/blog/post/2026-01-30-batch-processing-reporting/view) — consolidated summary patterns (MEDIUM)
- Project context: `/home/solanoe/code/robotina-gsd/.planning/PROJECT.md`, `/home/solanoe/code/robotina-gsd/plans/02-workflow-refinement/description.md` (HIGH — authoritative for this milestone)

---
*Feature research for: Robotina v1.1 — multi-recipe, URL ingestion, recipe images*
*Researched: 2026-05-18*
