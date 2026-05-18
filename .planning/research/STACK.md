# Stack Research — Milestone v1.1 (Workflows Abstraction Refinement)

**Domain:** Library additions/choices for three new product features on an existing Python/LangChain/Postgres/Redis/RQ agent — multi-recipe per message, URL-pointed recipe ingestion, recipe images.
**Researched:** 2026-05-18
**Confidence:** HIGH for recipe-scrapers, httpx, Tavily image search (verified via Context7 + official docs); MEDIUM for image-generation pricing (model lineup is in transition — DALL-E 3 → gpt-image-1.5 in mid-2026); LOW for household-manager image-storage API surface (not yet inspected — flagged for verification).

## Scope — What This Document Covers

This milestone adds three product features to an already-validated stack (see `CLAUDE.md` § Technology Stack for the full v1.0 inventory: LangChain 1.x `create_agent`, Pydantic v2, Postgres 15 + SQLAlchemy 2.x + Alembic, Redis 7 + RQ 2.5, FastAPI/Jinja2 dashboard, LangWatch + OTel, python-telegram-bot v21, Tavily, httpx, recipe-scrapers≥15.11.0 already declared).

**Three features. What's actually new at the dependency level:**

| Feature | New dependency? | Notes |
|---------|-----------------|-------|
| Multi-recipe per message | **No** | Pure refactor — drop `return_direct=True` on `StartWorkflowTool`, allow N tool calls per turn, plus the new `RobotinaInvocation` table on existing SQLAlchemy/Alembic. Zero new libs. |
| URL-pointed recipe (`gather-from-url`) | **No new libs** — uses already-declared `recipe-scrapers≥15.11.0` + existing `httpx≥0.27` | Need to switch httpx from async-only usage to a sync call inside the RQ worker. |
| Recipe images (`recipe-image` step) | **One choice to make** — image search (Tavily, already in stack) vs. AI generation (OpenAI gpt-image-1 / Imagen / Replicate, all *new* deps). | Recommendation below: Tavily-first, defer AI generation. |
| Robotina-as-decider refactor (RobotinaInvocation, FK closures, wake-rule) | **No new libs** | Code/schema rearrangement only on existing SQLAlchemy 2.x + Alembic. |

The existing stack is **complete enough** for two of the three features. The image step is the only one where a real library choice exists.

## Recommended Stack Additions

### Core Additions (already declared, just put to use)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `recipe-scrapers` | `>=15.11.0` (latest 15.11.0, Dec 2025) | Parse recipe HTML into structured `RecipeData` for `gather-from-url` step | Already declared in `pyproject.toml` since Phase 8 (currently unused). De-facto standard for Python recipe extraction; 2.2k★ on GitHub, 165 releases, actively maintained, supports Python 3.10–3.14. Parses JSON-LD, microdata, RDFa, and OpenGraph in one call. Has a `wild_mode=True` flag that lets it work on **any** site with schema.org Recipe markup — critical for the long tail of unsupported sites. |
| `httpx` | `>=0.27` (latest 0.28.1) | Fetch URL HTML for `recipe-scrapers` to parse | Already in stack for `household-manager-api` tool. Reuse in sync mode inside the RQ worker (RQ worker bodies are sync). Pattern: `httpx.get(url, follow_redirects=True, timeout=15.0, headers={"User-Agent": "RobotinaBot/1.0"})`. No new dependency. |
| `tavily-python` | `>=0.3` (latest 0.7.24, Apr 2026) | Recipe-image acquisition via `include_images=True` in the same Tavily client already used for `web-search` | Already declared. Setting `include_images=True` returns a top-level `images` list of URLs (and `include_image_descriptions=True` adds LLM-generated alt-text). Same API key (`RECIPE_RESEARCH_API_TOKEN`-style env var), same rate-limit budget, same client object. Zero new deps for V1 image acquisition. |

### Recommended Pattern for `gather-from-url`

```python
# Inside the gather-from-url task body (sync RQ worker context).
import httpx
from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import RecipeScrapersExceptions  # base class

resp = httpx.get(
    url,
    follow_redirects=True,
    timeout=15.0,
    headers={"User-Agent": "RobotinaBot/1.0 (+https://...)"},
)
resp.raise_for_status()

try:
    # wild_mode=True lets it work on sites not in SCRAPERS but with schema.org markup
    scraper = scrape_html(resp.text, url, wild_mode=True)
    data = {
        "title": scraper.title(),
        "image": scraper.image(),       # used by recipe-image step OR pinned directly
        "ingredients": scraper.ingredients(),
        "instructions": scraper.instructions(),
        "total_time": scraper.total_time(),
        "yields": scraper.yields(),
    }
except RecipeScrapersExceptions:
    # LLM-fallback: feed resp.text (or a Readability-extracted subset) to an LLM step.
    ...
```

**Why `wild_mode=True` for this project:** the supported-sites list does not cover the long tail of Spanish-language recipe blogs ("recetasdesa.com", "cookpad.com/es", etc.) that a Uruguayan family is likely to share. With `wild_mode=True`, recipe-scrapers attempts schema.org parsing on any host — and most modern recipe sites publish JSON-LD because SEO demands it (Google recipe rich results require it). Empirically this covers the majority of sites without us writing per-host scrapers.

### Supporting Libraries — Existing, Just Documented Here

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `beautifulsoup4` | `>=4.12.3` (transitive via recipe-scrapers) | HTML parsing inside recipe-scrapers; also available for any custom Readability-like text extraction in the LLM-fallback path | Already pulled in transitively — no direct import needed unless we add a custom fallback parser. |
| `extruct` | `>=0.17.0` (transitive via recipe-scrapers) | Structured-data extraction (JSON-LD / microdata / RDFa) — the engine behind recipe-scrapers' `wild_mode` | Transitive. If we ever want raw structured-data inspection independent of recipe-scrapers, this is the library to call. |
| `isodate` | `>=0.6.1` (transitive via recipe-scrapers) | ISO 8601 duration parsing for `total_time`, `cook_time`, `prep_time` | Transitive. recipe-scrapers handles it for us. |

No new entries needed in `pyproject.toml`; these are pulled in by `recipe-scrapers`.

## Installation

```bash
# All required libs are already in pyproject.toml — no `uv add` needed for the URL feature.
# Verify recipe-scrapers is installed (it was declared but currently unused):
uv sync
uv run python -c "import recipe_scrapers; print(recipe_scrapers.__version__)"
# Should print 15.11.0 or newer.

# For the image step using Tavily, no new dep — same client.
# If we later decide to add AI generation, the openai SDK is already a transitive of langchain-openai:
uv run python -c "import openai; print(openai.__version__)"
```

## Image-Source Decision Matrix

This is the only *real* choice in milestone v1.1. Options:

| Option | Cost / call | Latency | Copyright risk | Quality (for food) | Library | Stack delta |
|--------|-------------|---------|----------------|--------------------|---------|-------------|
| **Tavily `include_images`** (recommended for V1) | $0 incremental (same Tavily plan we already pay for; budget shared with `web-search`) | ~1–2s | LOW-MEDIUM — returns links to existing web images, so we don't host. Pinning the source URL leaves attribution intact. Risk shifts to source publisher. **Link-rot risk if source goes 404.** | Variable — pulls real food photography from blogs, often excellent | Already in stack (`tavily-python>=0.3`) | None |
| OpenAI `gpt-image-1` (replacing DALL-E 3 mid-2026) | $0.011 (low) – $0.167 (high) per 1024×1024 | ~5–15s | NONE — original generation. We own the image. | High for stylised food; can struggle with realism on niche dishes (e.g., "canelones de choclo" looks suspiciously like generic cannelloni) | `openai>=1.0` (already transitive via `langchain-openai>=0.2`) | None (transitive) |
| Google `imagen-3` / Gemini image | $0.03–$0.04 per image | ~3–5s | NONE | Comparable to gpt-image-1, often better realism | `google-genai` — **new dep** | +1 lib + new auth env var |
| Replicate (Flux Schnell, SDXL, etc.) | $0.003–$0.04 per image | ~5–20s | NONE | Wide range — Flux Schnell is fast and decent for food | `replicate` — **new dep** | +1 lib + new API key |
| Bing Image Search API | $3 per 1000 calls (S1 tier) | ~500ms | MEDIUM-HIGH — Bing image results are aggregated; rights vary; need filtering by license | High (web's deepest image index) | `requests` / `httpx` direct | +1 API key, +1 env var |
| Google Custom Search Image API | $5 per 1000 calls (after free 100/day) | ~500ms | MEDIUM-HIGH — same caveat as Bing | High | `google-api-python-client` — **new dep** | +1 lib, +1 API key |

### Recommendation: Tavily-First, Generation Behind a Flag

**V1 default:** Tavily `include_images=True`. Reasons:
1. **Zero new dependencies, zero new API keys, zero new env vars** — keeps the milestone honest about being scoped to product/architecture, not procurement.
2. **Real food photos beat synthetic ones** for a household recipe library. Users will recognise their own family's dishes when the image looks like a real plate, not a stylised render.
3. **Tavily's image budget piggybacks on the existing search budget** — easy to model cost.
4. **Failure mode is graceful** — milestone spec says image acquisition is non-fatal. If Tavily returns nothing relevant, the recipe still saves.

**Open carve-out for later:** if Tavily image quality is poor for Spanish-language regional recipes (a real risk — image search engines are English-biased), add gpt-image-1 as a *secondary* generator behind an env-var flag. Don't add it in V1.

**What about copyright / link rot?** Two questions to flag for the household-manager backend track:
- **Storage:** Source URL pinned (V1, simplest) vs. download+rehost. The latter requires a household-manager image upload endpoint. **FLAGGED: the household-manager API image surface has not been inspected. Phase planning needs to check `agent/skills/household-manager/` for any existing image endpoints before committing to "pin source URL" as the V1 strategy.** If no image API exists yet, V1 stores the URL and accepts link-rot risk as known debt.
- **Rights:** Pinning the source URL means we're embedding (like an `<img src>`), not hosting. Standard web practice. Add a UA string to fetches so source publishers can identify and block if they object.

### Recommended Image Step Pattern (V1)

```python
# Inside the recipe-image task body.
from tavily import TavilyClient

client = TavilyClient(api_key=os.environ["RECIPE_IMAGE_API_TOKEN"])
result = client.search(
    query=f"{recipe_name} receta plato cocido",   # in Spanish; "cocido" filters out raw ingredient shots
    include_images=True,
    include_image_descriptions=True,
    max_results=5,
)
# Pick the first image; LLM step can re-rank using descriptions if quality matters
candidate_images = result.get("images", [])
if not candidate_images:
    # Non-fatal: record gap in WorkflowRun.outcome, recipe saves without image
    return RecipeImageOutput(image_url=None, reason="no_candidate")
return RecipeImageOutput(image_url=candidate_images[0])
```

Env var naming follows the existing `[TASK_TYPE]_API_TOKEN` convention: `RECIPE_IMAGE_API_TOKEN`. Whether this is *the same Tavily key* as `RECIPE_RESEARCH_API_TOKEN` or a separate one is a deployment choice — both reference the same project upstream, but separating them lets us budget per task type.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `recipe-scrapers` with `wild_mode=True` | Custom Readability + LLM-only extraction | If `wild_mode` schema-org fallback fails too often in real traffic. The LLM-fallback path inside `gather-from-url` already handles this — keep it as the second leg, not the primary. |
| `recipe-scrapers` | `scrape-schema-recipe` (PyPI) | `scrape-schema-recipe` is JSON-LD-only and narrower in scope. recipe-scrapers wraps the same idea plus per-site fixups for the long tail. No reason to choose the narrower lib. |
| `httpx` sync inside RQ worker | `httpx.AsyncClient` + `asyncio.run()` inside the worker | Pure sync is simpler and the RQ worker body is sync. Only switch to async if a single step needs concurrent fan-out fetches (not the case in V1). |
| Tavily image search | OpenAI `gpt-image-1` | If real-food-photo quality on Spanish-language regional recipes turns out to be poor. **Re-evaluate after V1 telemetry.** |
| Tavily image search | Replicate Flux Schnell | If we want the cheapest possible generation later. ~$0.003/image is hard to beat. Adds a new dep + API key. |
| Pinning source image URL | Download + rehost via household-manager backend | If link-rot becomes a measurable problem. **Requires household-manager to expose an image-upload endpoint — verify first.** |
| One Tavily key for both search and image | Separate `RECIPE_IMAGE_API_TOKEN` env var | Separate keys if we want per-task-type budget tracking or to rotate independently. Operational preference. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `requests` for URL fetching | Sync-only, blocks event loop, inconsistent with the rest of the codebase which uses `httpx` | `httpx.get(...)` (sync mode is fine inside the RQ worker) |
| `beautifulsoup4` written by hand for recipe extraction | Reinvents what `recipe-scrapers` already does, including per-site quirks accumulated over 6+ years | `recipe-scrapers.scrape_html(html, url, wild_mode=True)` |
| Selenium / Playwright for the URL feature | Massive dep, doesn't solve a real problem — recipe sites generally don't gate JSON-LD behind JS. recipe-scrapers explicitly says it does not "circumvent bot protection." If a site is JS-gated or blocks scraping, fail the workflow and let Robotina explain to the user. | Accept the V1 limitation; LLM-fallback handles a fraction of the long tail without browser automation. |
| DALL-E 3 (`dall-e-3` model name in OpenAI API) | OpenAI is sunsetting DALL-E 3 mid-2026 in favour of `gpt-image-1` / `gpt-image-1.5`. New DALL-E 3 calls will fail or be auto-redirected. | If/when we add generation, use `gpt-image-1` directly via the `openai` SDK (already a transitive dep of `langchain-openai`). |
| `aiohttp` | Duplicates `httpx`'s role with an inferior sync story. | Stick with `httpx`. |
| Adding `replicate` or `google-genai` in V1 | Each adds a new SDK + API key + env var + cost line for a feature whose primary path (Tavily) hasn't been validated yet. Premature dependency growth. | Tavily image search; revisit if Tavily quality is insufficient. |
| Bing Image Search API | As of Aug 2025, Microsoft announced sunset of the Bing Search APIs (general retirement track). Verify current availability before depending on it. Tavily fills the same role without that risk. | Tavily image search. |
| Adding any new library "just in case" for the Robotina-as-decider refactor | The refactor is schema + code shape changes on existing SQLAlchemy 2.x + Alembic + LangChain — no library can help. | Alembic migrations for `RobotinaInvocation` + new FKs on `WorkflowRun`; no new deps. |

## Stack Patterns by Feature Variant

**For Topic 1 (Multi-recipe per message):**
- No library additions.
- Drop `return_direct=True` on `StartWorkflowTool` in `src/robotina/agents/tools/start_workflow.py`.
- Allow `create_agent` to call the tool N times per turn — this is already native LangChain behavior once `return_direct` is off.
- The wake-when-all-workflows-done rule lives in the task-runner / queue layer; uses existing SQLAlchemy session + RQ enqueue.

**For Topic 2 (URL-pointed recipe with `gather-from-url`):**
- `httpx.get(...)` sync mode inside the RQ worker, 15s timeout, follow redirects, custom UA.
- `recipe_scrapers.scrape_html(html, url, wild_mode=True)` — pin `wild_mode=True` to maximise coverage.
- On `recipe_scrapers._exceptions.RecipeScrapersExceptions` (or empty fields after parse), fall back to an LLM extraction step using the same agent infrastructure (`langchain.agents.create_agent` + `response_format=RecipeData`).
- Network errors → fail the workflow with a structured `outcome` so Robotina can apologise specifically ("ese link no se pudo abrir, ¿lo verificás?").

**For Topic 3 (Recipe images, V1):**
- `TavilyClient(api_key=os.environ["RECIPE_IMAGE_API_TOKEN"]).search(query=..., include_images=True)`.
- Env var follows existing `[TASK_TYPE]_API_TOKEN` convention.
- Failure is non-fatal — populate `WorkflowRun.outcome` with `image_acquired: false, reason: ...` and the recipe saves anyway (per milestone spec).
- Image URL is **pinned to the source** in V1. Download + rehost is deferred pending verification of household-manager's image API.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `recipe-scrapers>=15.11.0` | Python 3.10–3.14 | This project pins `>=3.12,<3.13` in `pyproject.toml` → in range. |
| `recipe-scrapers>=15.11.0` | `beautifulsoup4>=4.12.3`, `extruct>=0.17.0`, `isodate>=0.6.1` | All transitive. Verified via PyPI metadata. |
| `httpx>=0.27` | `httpx 0.28.1` (latest stable Dec 2024) | Sync and async APIs both stable. The project's `>=0.27` floor is fine. |
| `tavily-python>=0.3` | latest 0.7.24 (Apr 2026) | `include_images` parameter is stable across 0.3 → 0.7.x. No breaking change in scope. |
| `openai>=1.0` (transitive via `langchain-openai>=0.2`) | `gpt-image-1` model | If we ever add generation, this is the SDK. `gpt-image-1` may require OpenAI org verification — operational gate, not a code change. |

## Sources

- **Context7 / ctx7 CLI:** `/hhursev/recipe-scrapers` (benchmark score 96.1, source reputation High) — confirmed the canonical Python recipe extraction library; verified `scrape_html`, `wild_mode`, image best-selection API. HIGH confidence.
- **PyPI:** `https://pypi.org/pypi/recipe-scrapers/json` — version 15.11.0 (Dec 10, 2025), Python 3.10–3.14, deps confirmed. HIGH confidence.
- **GitHub:** `https://github.com/hhursev/recipe-scrapers` — 2.2k★, 165 releases, "focused exclusively on HTML parsing" (does NOT fetch URLs itself — confirms we must pair with `httpx`). HIGH confidence.
- **PyPI:** `https://pypi.org/pypi/httpx/json` — 0.28.1 stable, sync interface confirmed. HIGH confidence.
- **Tavily docs:** `https://docs.tavily.com/sdk/python/reference` — `include_images` and `include_image_descriptions` parameters confirmed; tavily-python at 0.7.24 (Apr 2026). HIGH confidence.
- **OpenAI docs:** `https://developers.openai.com/api/docs/models/gpt-image-1` — `gpt-image-1` replaces DALL-E 3 mid-2026; org verification required; two endpoints (Generations + Edits). MEDIUM confidence on exact transition timing (announcement was as of May 2026).
- **Pricing references:** costgoat.com, intuitionlabs.ai (DALL-E vs gpt-image-1 comparison May 2026) — pricing ranges $0.011–$0.167 per 1024×1024 image confirmed across two sources. MEDIUM confidence.
- **Project files:** `pyproject.toml` (recipe-scrapers>=15.11.0 already declared, Phase 8), `plans/02-workflow-refinement/description.md` (open questions for scraping library and image source), `CLAUDE.md` (full existing stack inventory). HIGH confidence on what's already in.

## Flagged for Phase-Level Verification

1. **Household-manager image-storage API** — the milestone description explicitly raises "Storage: source URL pinned, or download + re-host via household-manager backend." The agent's `agent/skills/household-manager/` index has not been re-read in this research pass. Phase-planning for the `recipe-image` step **must** read those skill files and decide:
   - Does household-manager already accept an `image_url` field on recipe POST/PATCH? → V1 pin source URL.
   - Does household-manager accept binary image uploads? → V1 could download + rehost.
   - Neither? → V1 pins source URL; backend track adds upload endpoint in a follow-up.

2. **Tavily image-search quality on Spanish-language regional recipes** — there is no public data on how well Tavily ranks images for queries like `canelones de choclo receta plato cocido`. Recommend a small spike during phase planning: run 20 representative recipe names through `TavilyClient.search(..., include_images=True)` and eyeball the top-1 image. If less than ~60% are usable, escalate to generation-as-fallback.

3. **`gpt-image-1` model transition** — if we decide to add generation later in the milestone (or in v1.2), confirm at implementation time which model is GA (`gpt-image-1` vs `gpt-image-1.5`) and whether OpenAI org verification is in place for this project.

---
*Stack research for: Milestone v1.1 — Workflows Abstraction Refinement (multi-recipe, URL ingestion, images + Robotina-as-decider refactor)*
*Researched: 2026-05-18*
