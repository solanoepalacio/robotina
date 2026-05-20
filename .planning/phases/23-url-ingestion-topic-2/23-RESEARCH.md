# Phase 23: URL ingestion (Topic 2) — Research

**Researched:** 2026-05-20
**Domain:** SSRF-safe HTTP fetching + `recipe-scrapers` integration + LLM-fallback HTML extraction + per-source workflow variant + Spanish recipe-URL eval harness
**Confidence:** HIGH on architecture and SSRF defenses (PITFALLS.md spec is concrete; codebase contracts all landed and locked); HIGH on `recipe-scrapers` API (verified via STACK.md inspection + GitHub README); MEDIUM on `trafilatura` integration shape (well-documented but new to this codebase); MEDIUM on Spanish blog scraper hit-rate (the 20-URL eval IS the empirical validation — no published benchmark exists for `wild_mode=True` against Argentine/Uruguayan recipe blogs).

## Summary

Phase 23 adds the first user-supplied-URL surface in the project, behind a security-critical
`safe_fetch` helper (lands as the FIRST commit per ROADMAP) and a new
`add-recipe-from-url` workflow variant that peers the existing (renamed) `add-recipe-from-query`.
The architecture lives on top of three fully-landed Phase 21/22 contracts:

1. Multi-call `StartWorkflowTool` with per-call typed `input` (Phase 21 D-03) — Phase 23
   extends the `workflow_type` Literal to two members and switches `input` to a plain
   union `AddRecipeQueryInput | AddRecipeUrlInput` (mutually-exclusive shapes; pydantic
   resolves without a discriminator); a `@model_validator(mode='after')` on the OUTER
   `StartWorkflowArgs` enforces the `workflow_type ↔ input` pairing.
2. `response_format=<Pydantic class>` on `langchain.agents.create_agent` (Phase 11) —
   the new `gather-from-url` agent reuses this with `response_format=RecipeData`. The
   agent's "decision" is trivial: if the deterministic `FetchAndScrapeTool` returns a
   valid `scraped_recipe`, pass it through; otherwise extract from `html_text` (trafilatura-
   cleaned plain text). One agent, one prompt, one response_format — uniform
   LangWatch + middleware instrumentation (Phase 12) inherited automatically.
3. Wake-helper enrichment (Phase 22 D-08) — `_check_and_dispatch_wake` already populates
   `WorkflowOutcomeSummary.recipe_query` from `shared_context["recipe_query"]`. Phase 23
   extends this read to fall back to `shared_context["recipe_url"]` (no schema change to
   `WorkflowOutcomeSummary` — its `recipe_query` field carries the dual semantic;
   renaming to `recipe_source` is deferred per `feedback_avoid_premature_abstraction`).

The security surface — `safe_fetch` with six SSRF/abuse defenses — is the load-bearing
risk. **The dev environment runs the agent on the HOST** (per memory
`project_local_dev_setup`), which means `localhost`, `127.0.0.1`, and the host's RFC1918
LAN address ARE reachable from the agent process. The SSRF defenses MUST actually fire
on these hostnames; this is testable and Plan 23-01's test suite is the verification.

**Primary recommendation:** Ship `safe_fetch` FIRST with a comprehensive test suite (one
test per defense, plus three composite attack scenarios from PITFALLS.md Pitfall 6).
Land the workflow-registry rename + new variant in a single atomic commit (D-01 + D-23
overrides sync). The `gather-from-url` agent is intentionally simple — the complexity
lives in the deterministic `FetchAndScrapeTool`; the LLM is just the variable extractor
on the fallback path. The 20-URL eval set (D-10) is the empirical validation of
`recipe-scrapers wild_mode=True` against the Spanish-blog long tail — there's no
published benchmark, so Phase 23 generates one.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 (URL-03): Per-source workflow types** — Rename `add-recipe` → `add-recipe-from-query`;
  add `add-recipe-from-url` peer. `StartWorkflowTool.workflow_type` becomes
  `Literal["add-recipe-from-query", "add-recipe-from-url"]`. `input` is a plain union
  `AddRecipeQueryInput | AddRecipeUrlInput` (mutually-exclusive shapes — no discriminator).
  `@model_validator(mode='after')` enforces `workflow_type ↔ input` pairing. Hard rename
  in ONE commit; no transitional alias.
- **D-02 (URL-03): `AddRecipeUrlInput {url: str}` only** — no `hint` field;
  `ConfigDict(extra='forbid')`.
- **D-03 (URL-02 + URL-04): `gather-from-url` is an LLM agent with
  `response_format=RecipeData` and one tool `FetchAndScrapeTool`.** Tool deterministically
  runs `safe_fetch` → `recipe-scrapers.scrape_html(html, wild_mode=True, org_url=url)` →
  per-field try/except → Pydantic validate → if passes AND ≥2 ingredients AND ≥1 step:
  return `scraped_recipe=<dump>`; ELSE clean HTML with `trafilatura.extract(...)` and
  return `html_text=<cleaned>`. `safe_fetch` failures re-raise — propagate to ToolMessage(error)
  → response_format extraction fails → step FAILED → wake reply surfaces URL +
  failure reason.
- **D-04: HTML preprocessing = `trafilatura>=1.6` (new dependency).** Recommended by
  PITFALLS Pitfall 7 verbatim; 10-50× token savings vs raw HTML on the LLM fallback path.
- **D-05 (URL-05): URL detection is LLM-judgment, not regex.** V007 teaches the rule;
  ambiguous bare hostnames → `respond()+terminate()` clarification (no `start-workflow`).
- **D-06: One `start-workflow` per URL.** Multi-URL messages emit N calls. Soft cap of 5
  (Phase 22 D-01) applies across combined query + URL count.
- **D-07: Mixed text + URL → one workflow per item, each routed to its variant.** No
  "mixed batch" abstraction.
- **D-08: Wake-helper reads BOTH `recipe_query` and `recipe_url` from `shared_context`.**
  Populates the existing `WorkflowOutcomeSummary.recipe_query` field via
  `r.shared_context.get("recipe_query") or r.shared_context.get("recipe_url")`. NO
  schema change. NO rename to `recipe_source` (deferred per
  `feedback_avoid_premature_abstraction`).
- **D-09 (EXP-02): One concrete `experiments/gather_from_url.py`** — single file, no
  framework (`feedback_avoid_premature_abstraction`). Same pattern as Phase 22's
  `experiments/robotina/multi_recipe_eval.py`. `pyproject.toml [project.scripts]` adds
  `experiments.gather_from_url`.
- **D-10 (URL-06): Eval set = 20 Spanish recipe blogs + 1 known-difficult site (21 total).**
  6 coverage classes (well-supported, wild_mode JSON-LD, LLM-fallback territory,
  locale-specific units, known-difficult, sanity non-recipe).
- **D-11: Field-level success metric.** Per-URL scoring evaluates presence of 8 expected
  fields. Per-URL pass = "≥ 6/8 expected-populated fields populated AND non-empty".
  Aggregate pass = "≥ 17/21 URLs pass" (≈85% URL-level).
- **D-12: Pass thresholds.** OpenAI staging = merge gate (≥85%); Ollama dev = informational;
  Anthropic optional.
- **D-13: Three files** — `23-EVAL-SET.md` (canonical), `23-EVAL-RESULTS-<backend>.md`
  (operator), `23-SMOKE.md` (final verdict).
- **D-14: `safe_fetch` location = `src/robotina/url/safe_fetch.py`.** NEW top-level
  `src/robotina/url/` package (sibling to `queue/`, `agent/`).
- **D-15: Sync, not async.** RQ workers are sync. `httpx.Client` sync mode.
- **D-16: `safe_fetch` signature.** `SafeFetchResult{final_url, content_bytes,
  content_type, status_code}` + `SafeFetchError` exception. Six defenses: scheme
  allowlist, post-DNS private/loopback/link-local IP block (RFC1918 + 127/8 + ::1 +
  169.254/16 + fe80::/10 + 0.0.0.0 + multicast), manual redirect re-validation
  (`follow_redirects=False`, max 3 hops), configurable timeout
  (`httpx.Timeout(connect=5, read=timeout_s, write=5, pool=5)`), content-length cap
  (header + stream), content-type sniff. Plus gzip-bomb defense (incremental decompress;
  reject ratio > 20:1).
- **D-17: `allow_http` env-gated.** `URL_INGESTION_ALLOW_HTTP` env var, default False.
  Added to `.env.example` per `feedback_env_example`.
- **D-18..D-23 (tests).** `tests/url/test_safe_fetch.py` (load-bearing safety net, one
  test per defense + redirect chain + gzip bomb), `tests/agents/tools/test_fetch_and_scrape_tool.py`,
  `tests/agents/test_gather_from_url_agent.py`, workflow registry + StartWorkflowTool
  schema tests, AGENT_REGISTRY + overrides sync (atomic commit per
  `feedback_overrides_in_sync`).
- **D-24: Manual eval = load-bearing user-facing gate** — `human_needed` until operator
  commits `23-SMOKE.md` with `verdict: pass`.
- **D-25: V006 retained for rollback.** V007 forks V006 verbatim + URL detection sections.

### Claude's Discretion

- **Plan ordering (planner final):** 23-01 `safe_fetch` + tests; 23-02 schema +
  workflow rename + new variant + dashboard label; 23-03 `FetchAndScrapeTool` +
  `recipe-scrapers` + trafilatura + tests; 23-04 `gather-from-url` agent + V001
  prompt + AGENT_REGISTRY + overrides + tests; 23-05 Robotina V007 prompt + agents.py
  bump + tests; 23-06 `experiments/gather_from_url.py` + `23-EVAL-SET.md` +
  pyproject scripts entry + harness self-test; 23-07 operator eval + `23-SMOKE.md` +
  REQUIREMENTS ticks.
- **Tool path:** `src/robotina/agent/tools/fetch_and_scrape.py`.
- **Dashboard:** `"gather-from-url": "Búsqueda por URL"` in `_macros.html` TASK_TYPE_LABELS.
- **No new Alembic migration.** Pure code + prompt + new dep. `shared_context` gains a
  `recipe_url` key for URL workflows (JSON data-only).

### Deferred Ideas (OUT OF SCOPE)

- `recipe-image` step (IMG-*) — Phase 24; the 6-step add-recipe-from-url variant lands
  without it; Phase 24 inserts in BOTH variants and extracts the shared-tail helper.
- Vision-LLM "is this the right page?" validation (Pitfall 8) — Phase 24.
- Spike-driven `wild_mode` hit-rate validation — folded INTO Phase 23's eval set.
- Household-manager API recipe-rehost decision — Phase 24.
- `hint` field on `AddRecipeUrlInput`.
- CDN/HTML caching.
- Cross-source batches abstraction.
- Renaming `WorkflowOutcomeSummary.recipe_query` → `recipe_source`.
- LLM-judge or vision-model field-correctness scoring on eval set.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| URL-01 | `safe_fetch` helper with six SSRF defenses (HTTPS allowlist, post-DNS private-IP block, manual redirect handling, timeout, content-length cap, content-type magic-byte verification) | D-14..D-17 + Standard Stack `httpx` sync + `ipaddress` stdlib; Pattern 1 (safe_fetch flow); Pitfall 1 (six-defense matrix); D-18 test suite is the load-bearing safety net. `[CITED: .planning/research/PITFALLS.md Pitfall 6]` |
| URL-02 | `gather-from-url` task type fetches URL via `safe_fetch`, extracts structured RecipeData via `recipe-scrapers wild_mode=True` with per-field try/except | D-03 deterministic `FetchAndScrapeTool` internals; Standard Stack `recipe-scrapers>=15.11.0` (already declared); Pattern 2 (FetchAndScrapeTool flow); Pitfall 2 (silent partial extraction) `[VERIFIED: STACK.md lines 28, 37, 175]` |
| URL-03 | `add-recipe-from-url` workflow variant routes URL-sourced requests; downstream steps reused unchanged | D-01 rename + new peer entry in `WORKFLOW_REGISTRY`; 6-step list inline-duplicated (helper extraction deferred to Phase 24 per `feedback_avoid_premature_abstraction`); Pattern 3 (workflow registry topology). |
| URL-04 | LLM fallback agent re-extracts from raw HTML when `recipe-scrapers` returns insufficient data | D-03 — the agent's prompt branch on `scraped_recipe` vs `html_text`; D-04 trafilatura preprocessing (token-cost reduction); response_format=RecipeData enforces same schema as scraped path. |
| URL-05 | Robotina detects URLs in user message and routes through URL variant; pure-text continues to use `add-recipe-from-query` | D-05 V007 LLM-judgment URL detection; D-06 one workflow per URL; D-07 mixed text+URL → one workflow per item routed to its variant; Pitfall 5 (URL-in-text detection ambiguity). |
| URL-06 | 20-URL Spanish-recipe-blog eval set runs and achieves ≥85% field-level success at v1.1 ship | D-10 21 URLs across 6 coverage classes; D-11 field-level scoring (8 expected fields per URL); D-12 OpenAI staging merge gate; Pitfall 3 (Spanish-blog hit-rate is the largest unknown). |
| EXP-02 | `uv run experiments.gather_from_url` exercises pipeline end-to-end with LangWatch traces tagged to experiment | D-09 single concrete script; mirrors `experiments/robotina/multi_recipe_eval.py` (already in repo); LangWatch metadata tags per CLAUDE.md observability constraint. |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| URL detection in user message | LLM (Robotina V007 prompt) | — | D-05: LLM-judgment, not regex. Punycode/IDN/percent-encoding edge cases make regex fragile. Eval set's mixed text+URL rows validate. |
| Per-URL `start-workflow(add-recipe-from-url, {url})` dispatch | LLM (Robotina V007 prompt) → `StartWorkflowTool._run` | `workflow_runner.queue_workflow` | D-06: one call per URL. The constructor-injected `invocation_id` (Phase 18 D-13) atomically links all sibling runs (URL + query mix) to the same `RobotinaInvocation`. |
| `workflow_type ↔ input` shape validation | `StartWorkflowArgs` Pydantic `@model_validator(mode='after')` (NEW Phase 23) | — | D-01: catches LLM-emitted mismatch (`workflow_type=add-recipe-from-query` + `input={url:...}`) at args-validation time → ToolMessage(error) → LLM retries with correct shape. The model_validator is the safety net that lets `input` stay a plain union (no discriminator). |
| URL fetch (HTTPS, DNS-resolve, IP check, redirects, caps) | `src/robotina/url/safe_fetch.py` (NEW deterministic Python) | — | D-14..D-17: single utility module; sync `httpx.Client`; stdlib `ipaddress`+`socket.getaddrinfo` for IP checks. Reused by Phase 24's `recipe-image` step — that's why it lives in `url/` (not `agent/tools/`). |
| HTML → structured RecipeData extraction (deterministic path) | `recipe-scrapers.scrape_html(html, wild_mode=True, org_url=url)` inside `FetchAndScrapeTool` | per-field `try/except` accumulator + Pydantic partial validate | D-03: deterministic, no LLM cost. Per-field try/except is non-negotiable (Pitfall 7 — `recipe-scrapers` raises per-method on missing data). |
| HTML → plain text (when scraper insufficient) | `trafilatura.extract(html, ...)` inside `FetchAndScrapeTool` | — | D-04: purpose-built; strips nav/footer/scripts; 10-50× cheaper than raw HTML for LLM context. |
| HTML → structured RecipeData extraction (LLM fallback path) | `gather-from-url` agent (LLM, `response_format=RecipeData`) | trafilatura-cleaned `html_text` from `FetchAndScrapeTool` | D-03: agent prompt is essentially `if scraped: pass-through else extract`. Response_format enforces RecipeData schema regardless of source. |
| Downstream steps (instructions/ingredients/metadata/load/finalize-outcome) | UNCHANGED — same agents as `add-recipe-from-query` | — | D-01 + URL-03: the artifact contract is `RecipeData`; whether `source_url` is populated by the scraper or by the LLM is invisible to downstream. |
| Wake reply surfaces URL on success/failure | `_check_and_dispatch_wake` (`workflow_runner.py:195`) reads `recipe_url` as fallback | `WakeInvocationInput.to_user_message()` (unchanged) | D-08: existing `WorkflowOutcomeSummary.recipe_query` field carries dual semantic; one-line code change. Phase 22 ORDER BY + slug-on-success already shipped. |

## Project Constraints (from CLAUDE.md)

- **Tech stack pinned:** Python 3.12; LangChain 1.x via `langchain.agents.create_agent`;
  RQ 2.5 (no scheduler add-on); SQLAlchemy 2.x (no 1.x `Column` style); Pydantic v2;
  `httpx` for async + sync HTTP; `recipe-scrapers>=15.11.0` (already declared per Phase 8).
  Phase 23 adds ONE new direct dep: `trafilatura>=1.6` (D-04).
- **No `AgentExecutor`, no `langgraph.prebuilt.create_react_agent`.** `gather-from-url`
  uses `LLMBackend.create_agent()` which wraps `langchain.agents.create_agent`. Phase 23
  introduces NO agent-factory changes.
- **LangWatch instrumentation MUST be active during production AND experiments**
  (CLAUDE.md observability). Middleware-based instrumentation (Phase 12) inherits
  automatically for the new `gather-from-url` agent. The eval harness tags traces with
  `phase=23`, `url=<the url>`, `backend=<backend>`.
- **`response_format=<Pydantic class>` is mandatory on artifact-producing agents** per
  Phase 11. `gather-from-url` uses `response_format=RecipeData`.
- **Single sequential worker (concurrency=1).** Each `safe_fetch` call holds the worker
  for up to `timeout_s + connect timeout` seconds. Defaults (15s read, 5s connect) are
  acceptable; if a real URL needs more, raise via the `timeout_s` arg per-call.
- **Always update `.env.example`** (memory `feedback_env_example`). D-17 adds
  `URL_INGESTION_ALLOW_HTTP=false` with comment "Dev/testing only — never set in
  production."
- **`overrides/*.json` must stay in sync with `AGENT_REGISTRY`** (memory
  `feedback_overrides_in_sync` + Phase 21 D-12 CI guard). D-23: the new
  `gather-from-url` agent gets entries in BOTH `AGENT_REGISTRY` AND every
  `overrides/*.json` (anthropic.json, openai.json, staging.ollama.json) in the SAME commit.
- **English prompt body, Spanish user-facing strings** (memory `feedback_prompts_language`).
  V007 + gather-from-url/V001 bodies in English. Spanish only in `respond()` payloads and
  user-facing dashboard labels.
- **No quick-task IDs in code** (memory `feedback_no_task_id_in_code`). D-NN refs are
  durable and allowed.
- **`uv run` shortcut required for new experiments** — D-09: add
  `experiments.gather_from_url = "experiments.gather_from_url:main"` to
  `pyproject.toml [project.scripts]`.

## Standard Stack

### Core (new + existing dependencies for Phase 23)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `recipe-scrapers` | `>=15.11.0` (latest 15.11.0 per Dec 2025) | Parse recipe HTML into structured fields (`title`, `ingredients`, `instructions`, `total_time`, `yields`, `image`, etc.); `wild_mode=True` falls back to schema.org/Recipe JSON-LD for any host | `[VERIFIED: STACK.md line 28 + pyproject.toml line 33]` already declared since Phase 8 but currently unused; 2.2k★ on GitHub; the de-facto Python recipe-parser; supports JSON-LD/microdata/RDFa/OpenGraph in one call; per-method exceptions on missing data (per-field try/except is mandatory per Pitfall 7). `[CITED: https://github.com/hhursev/recipe-scrapers]` |
| `trafilatura` | `>=1.6` (latest 2.0.0 per readthedocs; pin `>=1.6` to keep an upgrade window) | Strip HTML to clean plain text for the LLM fallback path (nav/footer/scripts/comments removed) | NEW dependency. PITFALLS Pitfall 7 names it verbatim: "via `trafilatura` or `readability-lxml`". Purpose-built; single call (`trafilatura.extract(html, include_comments=False, include_tables=True, output_format="txt")`); 10-50× token savings vs raw HTML. `[CITED: https://trafilatura.readthedocs.io/]` |
| `httpx` | `>=0.27` (already in stack — `pyproject.toml:28`; latest 0.28.1) | Sync HTTP client for `safe_fetch`; supports per-call `follow_redirects=False`, streaming `iter_bytes()`, configurable `Timeout`, `Limits` | `[VERIFIED: pyproject.toml:28]` no new dep. RQ workers are sync (D-15) — use `httpx.Client` not `AsyncClient`. |
| `ipaddress` (stdlib) | — | IP address classification (RFC1918, loopback, link-local, multicast, IPv4-mapped IPv6) | Stdlib — no new dep. `ipaddress.ip_address(ip).is_private / is_loopback / is_link_local / is_multicast` covers most categories; explicit `0.0.0.0` + `169.254.169.254` (AWS metadata) + IPv4-mapped IPv6 (`::ffff:127.0.0.1`) checks supplement. |
| `socket` (stdlib) | — | DNS resolution for IP check before HTTP call (`socket.getaddrinfo(host, None)`) | Stdlib — no new dep. Returns all A/AAAA records; check EVERY record (not just the first — multi-A-record DNS rebinding bypass). |

### Already in stack (relied on by Phase 23)

| Library | Version | Purpose |
|---------|---------|---------|
| `langchain` | `>=1.2` (installed per CLAUDE.md) | `create_agent` factory used by `LLMBackend.create_agent()` |
| `langchain-openai` | `>=0.2` | OpenAI backend (eval merge gate per D-12) |
| `langchain-ollama` | `>=0.2` | Ollama backend (dev / informational eval) |
| `langchain-anthropic` | `>=0.3` | Optional Anthropic backend |
| `langwatch` | `>=0.1` | Trace tagging in `experiments/gather_from_url.py` |
| `pydantic` | `v2` (`>=2.7`) | All Pydantic models (`AddRecipeUrlInput`, `SafeFetchResult`, `FetchAndScrapeResult`, `StartWorkflowArgs` model_validator) |

### Alternatives Considered

| Recommended | Alternative | Tradeoff |
|-------------|-------------|----------|
| `recipe-scrapers wild_mode=True` | `scrape-schema-recipe` | `scrape-schema-recipe` is JSON-LD-only; `recipe-scrapers` adds microdata + RDFa + OpenGraph + per-site fixups for the long tail. No reason to choose narrower. `[CITED: STACK.md:145]` |
| `recipe-scrapers wild_mode=True` | Custom BeautifulSoup recipe extractor | Reinvents 6+ years of per-site quirks; `recipe-scrapers` exists exactly for this. `[CITED: STACK.md:157]` |
| `trafilatura` | `readability-lxml` | Both viable per PITFALLS Pitfall 7. `trafilatura` has cleaner Python API (one `extract()` call vs `Document(html).summary()`), better maintained (Trafilatura 2.0.0 released; readability-lxml semi-dormant), purpose-built for plain-text output. Pick `trafilatura`. |
| `trafilatura` | Raw HTML to LLM | Token cost: 50-200 KB HTML → 1-5 KB cleaned text (10-50×). Also reduces LLM's tendency to extract from page chrome (nav, comments). `[CITED: D-04 rationale]` |
| Sync `httpx.Client` | Async `httpx.AsyncClient` | RQ workers are sync; mixing sync RQ entrypoint with async fetch requires `asyncio.run()` bridge (Pitfall 13 calls this out for `respond()`). Stay sync. `[CITED: D-15]` |
| `httpx` | `requests` | Project already uses `httpx`; consistency. `requests` has the same SSRF surface — same defenses needed. |
| Selenium / Playwright for JS-gated sites | — | Out of scope. Recipe sites generally don't gate JSON-LD behind JS (SEO/Google rich results require static JSON-LD). Eval set documents the one JS-only case as "expected failure". `[CITED: STACK.md:158]` |
| Plain union `AddRecipeQueryInput \| AddRecipeUrlInput` | Pydantic discriminated union (`Field(discriminator='kind')`) | Shapes (`{value:str}` vs `{url:str}`) are mutually-exclusive at JSON level; Pydantic resolves without a discriminator. Adding an explicit `kind` field forces the LLM to emit a 4th key it has no other reason to know about → more LLM-emit drift. Plain union + outer `@model_validator` is the safer choice. `[CITED: D-01 + Claude's Discretion]` |

**Installation:**

```bash
uv add trafilatura
# recipe-scrapers already in pyproject.toml — verify with:
uv run python -c "import recipe_scrapers; print(recipe_scrapers.__version__)"
```

**Version verification:** `recipe-scrapers` is declared at `>=15.11.0` (`pyproject.toml:33`);
verify the installed wheel against the registry before writing the plan
(`pip index versions recipe-scrapers` in a network-enabled shell — the offline sandbox
this research ran in could not query PyPI; planner runs the check at plan time).
Likewise verify `trafilatura` latest (web search reports 2.0.0; pin `>=1.6` to keep an
upgrade window without blocking on 2.x major).

## Project Structure (delta from current state)

```
src/robotina/
├── url/                          # NEW (D-14) — top-level sibling to queue/, agent/
│   ├── __init__.py               # NEW (empty)
│   └── safe_fetch.py             # NEW (D-14..D-17) — SafeFetchResult, SafeFetchError, safe_fetch()
├── agent/
│   ├── tools/
│   │   └── fetch_and_scrape.py   # NEW (D-03) — FetchAndScrapeResult, FetchAndScrapeTool
│   ├── prompts/
│   │   ├── robotina/
│   │   │   ├── V006.md           # RETAINED for rollback (D-25)
│   │   │   └── V007.md           # NEW — V006 + URL detection sections (D-05..D-07)
│   │   └── gather-from-url/
│   │       └── V001.md           # NEW (D-03) — pass-through-or-extract rule
│   ├── agents.py                 # MOD — V006→V007 path bump + new gather-from-url AgentConfig
│   └── tools/
│       └── start_workflow.py     # MOD — Literal extension + union input + model_validator
├── queue/
│   ├── task_types.py             # MOD — new AddRecipeUrlInput; doc comment on WorkflowOutcomeSummary.recipe_query dual semantic
│   ├── workflow_runner.py:195    # MOD — D-08 shared_context fallback read
│   └── (no models.py changes)    # NO Alembic migration
├── dashboard/
│   └── templates/_macros.html    # MOD — add "gather-from-url": "Búsqueda por URL"
overrides/
├── anthropic.json                # MOD — add gather-from-url block (atomic per D-23)
├── openai.json                   # MOD — same
└── staging.ollama.json           # MOD — same
experiments/
└── gather_from_url.py            # NEW (D-09, EXP-02)
tests/
├── url/
│   └── test_safe_fetch.py        # NEW (D-18) — comprehensive defense suite
├── agents/
│   ├── tools/
│   │   ├── test_fetch_and_scrape_tool.py  # NEW (D-19)
│   │   └── test_start_workflow_tool.py    # EXTEND (D-22)
│   ├── test_gather_from_url_agent.py      # NEW (D-20)
│   └── test_handle_incoming_message_agent.py  # EXTEND (V007 path)
└── queue/
    ├── test_workflow_registry.py          # EXTEND (D-21)
    └── test_wake_helper.py                # EXTEND (D-08 fallback read)
.planning/phases/23-url-ingestion-topic-2/
├── 23-EVAL-SET.md                # NEW (D-13) — 21 URLs + expected fields
├── 23-EVAL-RESULTS-openai.md     # NEW (operator)
├── 23-EVAL-RESULTS-ollama.md     # NEW (operator)
└── 23-SMOKE.md                   # NEW (operator) — verdict line
pyproject.toml                    # MOD — add trafilatura; add experiments.gather_from_url script
.env.example                      # MOD — add URL_INGESTION_ALLOW_HTTP=false
.planning/REQUIREMENTS.md         # MOD — tick URL-01..06 + EXP-02 (LAST commit per D-24)
```

## Architecture Patterns

### System Architecture Diagram — URL ingestion turn

```
Telegram user message ("agregá esta receta: https://recetasdesa.com/canelones-de-choclo")
    │
    ▼
Gateway enqueues handle-incoming-message job (meta["invocation_id"] = <new RobotinaInvocation.id>)
    │
    ▼
run_task → constructs RespondTool + StartWorkflowTool + TerminateTool + HouseholdManagerApiTool
    │ (invocation_id + conversation_id + household_id constructor-injected on tools)
    ▼
Robotina V007 agent loop:
    1. respond("Listo, voy con esa receta. Te aviso cuando termine.")          ──┐
    2. start-workflow(workflow_type="add-recipe-from-url",                       │
                      input={"url": "https://recetasdesa.com/canelones-de-choclo"})  ⇒ creates WorkflowRun
    3. terminate()                                                              ──┘   shared_context["recipe_url"]=<url>
                                                                                       triggered_by_invocation_id=<inv>
    │
    ▼ (first step enqueued by StartWorkflowTool._run via queue_workflow)
add-recipe-from-url workflow drains SEQUENTIALLY on the single worker (concurrency=1):
    │
    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Step 1: gather-from-url (NEW)                                                │
│   ├─ LLM agent (response_format=RecipeData)                                  │
│   ├─ Tool: FetchAndScrapeTool(url) → FetchAndScrapeResult                    │
│   │     ├─ safe_fetch(url)  ── 6 defenses (scheme, IP, redirects, timeout,   │
│   │     │                       content-len, content-type, gzip-bomb)        │
│   │     │     └─ SafeFetchError on any defense violation (re-raised)         │
│   │     ├─ recipe_scrapers.scrape_html(html, wild_mode=True, org_url=url)    │
│   │     ├─ per-field try/except → partial dict                               │
│   │     ├─ RecipeData.model_validate(partial)                                │
│   │     ├─ if valid AND ≥2 ingredients AND ≥1 step:                          │
│   │     │     return {scraped_recipe=<dump>, source_url, html_text=None}     │
│   │     └─ else: trafilatura.extract(html, include_comments=False, ...)      │
│   │           return {scraped_recipe=None, source_url, html_text=<cleaned>}  │
│   │                                                                          │
│   └─ Agent branches in prompt:                                               │
│         if scraped_recipe is not None: pass through via response_format      │
│         elif html_text is not None: extract RecipeData from html_text        │
│         else: (impossible — safe_fetch already raised)                       │
└──────────────────────────────────────────────────────────────────────────────┘
    │ artifact = RecipeData (with source_url populated)
    ▼
Step 2: recipe-research-instructions   ──┐
Step 3: recipe-research-ingredients      │  UNCHANGED — same agents as
Step 4: recipe-research-metadata         │  add-recipe-from-query; consume
Step 5: recipe-load                      │  RecipeData accumulator agnostic of source
Step 6: finalize-outcome                 ──┘
    │
    ▼
_check_and_dispatch_wake(invocation_id, session, queue)
    │ Phase 23 D-08: shared_context.get("recipe_query") or shared_context.get("recipe_url")
    │   populates existing WorkflowOutcomeSummary.recipe_query field
    │
    ▼
New RobotinaInvocation (trigger=WORKFLOW_COMPLETION)
    │
    ▼
Robotina V007 wake-context turn:
    1. respond("Listo, guardé Canelones de choclo (canelones-de-choclo).")
    2. terminate()
    │
    ▼
send-notification (at_front) → Telegram → user sees outcome
```

### Pattern 1: `safe_fetch` flow (D-16) — six defenses + gzip-bomb

```python
# src/robotina/url/safe_fetch.py
# Source: D-16 + PITFALLS Pitfall 6 + [CITED: OWASP SSRF prevention]
from __future__ import annotations
import ipaddress
import os
import socket
from typing import Iterable

import httpx
from pydantic import BaseModel

class SafeFetchResult(BaseModel):
    final_url: str
    content_bytes: bytes
    content_type: str
    status_code: int

class SafeFetchError(Exception):
    """Raised on any defense violation. Message names the defense."""

_MAX_REDIRECTS = 3
_GZIP_RATIO_CAP = 20  # decompressed/compressed
_BLOCKED_EXTRA_IPS = {ipaddress.ip_address("0.0.0.0"), ipaddress.ip_address("169.254.169.254")}

def _is_blocked_ip(ip_str: str) -> tuple[bool, str | None]:
    ip = ipaddress.ip_address(ip_str)
    # IPv4-mapped IPv6 → unwrap to v4 and re-check
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if ip in _BLOCKED_EXTRA_IPS:
        return True, f"IP {ip} is explicitly blocked"
    if ip.is_private:
        return True, f"IP {ip} is private (RFC1918)"
    if ip.is_loopback:
        return True, f"IP {ip} is loopback"
    if ip.is_link_local:
        return True, f"IP {ip} is link-local"
    if ip.is_multicast:
        return True, f"IP {ip} is multicast"
    if ip.is_unspecified:
        return True, f"IP {ip} is unspecified (0.0.0.0 / ::)"
    if ip.is_reserved:
        return True, f"IP {ip} is reserved"
    return False, None

def _resolve_and_check(host: str) -> None:
    """Resolve hostname to ALL A/AAAA records, reject if ANY is in blocked range."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise SafeFetchError(f"DNS resolution failed for {host}: {exc}")
    seen: set[str] = set()
    for family, _socktype, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0]
        if ip_str in seen:
            continue
        seen.add(ip_str)
        blocked, reason = _is_blocked_ip(ip_str)
        if blocked:
            raise SafeFetchError(f"Host {host} resolved to blocked IP: {reason}")

def _check_scheme(url: str, allow_http: bool) -> None:
    if url.startswith("https://"):
        return
    if url.startswith("http://") and allow_http:
        return
    raise SafeFetchError(f"Scheme not allowed: {url}")

def _decompress_with_cap(raw: bytes, encoding: str | None, max_bytes: int) -> bytes:
    if not encoding or encoding == "identity":
        return raw
    import gzip, zlib
    try:
        if encoding == "gzip":
            decompressed = gzip.decompress(raw)
        elif encoding in ("deflate", "x-deflate"):
            decompressed = zlib.decompress(raw)
        else:
            return raw  # br/zstd: defer — pin httpx auto-decompression
    except Exception as exc:
        raise SafeFetchError(f"Decompression failed ({encoding}): {exc}")
    if len(raw) > 0 and len(decompressed) / len(raw) > _GZIP_RATIO_CAP:
        raise SafeFetchError(f"Compression ratio {len(decompressed)/len(raw):.1f}x exceeds cap {_GZIP_RATIO_CAP}x")
    if len(decompressed) > max_bytes:
        raise SafeFetchError(f"Decompressed size {len(decompressed)} > max_bytes {max_bytes}")
    return decompressed

def safe_fetch(
    url: str,
    *,
    expected_content_type: str = "text/html",
    max_bytes: int = 5_000_000,
    timeout_s: float = 15.0,
    allow_http: bool | None = None,
) -> SafeFetchResult:
    # D-17: env-gated http override
    if allow_http is None:
        allow_http = os.environ.get("URL_INGESTION_ALLOW_HTTP", "").lower() in ("1", "true", "yes")

    current_url = url
    for hop in range(_MAX_REDIRECTS + 1):
        _check_scheme(current_url, allow_http)
        parsed = httpx.URL(current_url)
        host = parsed.host
        if not host:
            raise SafeFetchError(f"URL has no host: {current_url}")
        _resolve_and_check(host)

        timeout = httpx.Timeout(connect=5.0, read=timeout_s, write=5.0, pool=5.0)
        with httpx.Client(timeout=timeout, follow_redirects=False, headers={
            "User-Agent": "RobotinaBot/1.0 (+https://github.com/...)",
            "Accept": expected_content_type + ",*/*;q=0.1",
        }) as client:
            resp = client.get(current_url)

        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            if not location:
                raise SafeFetchError(f"Redirect {resp.status_code} without Location header")
            current_url = str(httpx.URL(current_url).join(location))
            if hop >= _MAX_REDIRECTS:
                raise SafeFetchError(f"Too many redirects (> {_MAX_REDIRECTS})")
            continue

        # Content-Length pre-check (header-based; cheaper than streaming the body)
        cl = resp.headers.get("Content-Length")
        if cl is not None and cl.isdigit() and int(cl) > 2 * max_bytes:
            raise SafeFetchError(f"Content-Length {cl} > 2 × max_bytes")

        # Read with size cap
        content = resp.content
        encoding = resp.headers.get("Content-Encoding", "identity")
        content = _decompress_with_cap(content, encoding, max_bytes)
        if len(content) > max_bytes:
            raise SafeFetchError(f"Body size {len(content)} > max_bytes {max_bytes}")

        # Content-type sniff
        content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        expected = expected_content_type.lower()
        accepted: Iterable[str]
        if expected == "text/html":
            accepted = ("text/html", "application/xhtml+xml")
        elif expected.startswith("image/"):
            accepted = ("image/",)  # prefix-match
        else:
            accepted = (expected,)
        if not any((content_type == a) or (a.endswith("/") and content_type.startswith(a)) for a in accepted):
            raise SafeFetchError(f"Content-Type {content_type!r} not in {accepted}")

        return SafeFetchResult(
            final_url=current_url,
            content_bytes=content,
            content_type=content_type,
            status_code=resp.status_code,
        )
    raise SafeFetchError("Unreachable: redirect loop exited without return")
```

**Defenses checklist (from D-16):**
1. ✅ Scheme allowlist (https-only unless `URL_INGESTION_ALLOW_HTTP=true`)
2. ✅ Post-DNS private/loopback/link-local IP block (every A/AAAA record checked; IPv4-mapped IPv6 unwrapped)
3. ✅ Manual redirect re-validation (`follow_redirects=False`, ≤ 3 hops, scheme + IP check each Location)
4. ✅ Configurable timeout (5s connect, `timeout_s` read, 5s write, 5s pool)
5. ✅ Content-Length cap (header pre-check ≤ 2× max_bytes; post-read body cap ≤ max_bytes)
6. ✅ Content-Type sniff (`text/html` or `application/xhtml+xml` for HTML; `image/*` prefix for images)
7. ✅ gzip-bomb defense (decompress incrementally; reject if expanded > 20× compressed)

### Pattern 2: `FetchAndScrapeTool` flow (D-03)

```python
# src/robotina/agent/tools/fetch_and_scrape.py
# Source: D-03 + PITFALLS Pitfall 7 (per-field try/except)
from __future__ import annotations
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from robotina.queue.task_types import RecipeData
from robotina.url.safe_fetch import safe_fetch

# Per-method exceptions in recipe-scrapers — import the base class
# [CITED: STACK.md:38 `from recipe_scrapers._exceptions import RecipeScrapersExceptions`]

class FetchAndScrapeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(description="The recipe URL to fetch and parse.")

class FetchAndScrapeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_url: str
    scraped_recipe: dict | None = None   # RecipeData.model_dump(mode='json') when scraper gave a valid result
    html_text: str | None = None         # trafilatura-cleaned plain text when scraped_recipe is None

class FetchAndScrapeTool(BaseTool):
    name: str = "fetch-and-scrape"
    description: str = (
        "Fetch a recipe URL with SSRF defenses and attempt deterministic recipe extraction. "
        "Returns either {scraped_recipe: <RecipeData dump>, source_url, html_text: null} "
        "OR {scraped_recipe: null, source_url, html_text: <cleaned plain text>}. "
        "Args: {url: <https URL>}."
    )
    args_schema: type[BaseModel] = FetchAndScrapeArgs

    def _run(self, url: str) -> str:
        # safe_fetch failures re-raise (D-03): the agent has no recovery path
        # with response_format=RecipeData mandatory; step gets marked FAILED
        # with the SafeFetchError text in failure_reason; wake reply surfaces
        # URL + reason.
        fetched = safe_fetch(url, expected_content_type="text/html")

        html = fetched.content_bytes.decode("utf-8", errors="replace")

        # Per-field try/except — Pitfall 7
        from recipe_scrapers import scrape_html
        from recipe_scrapers._exceptions import RecipeScrapersExceptions

        partial: dict[str, Any] = {}
        try:
            scraper = scrape_html(html, org_url=fetched.final_url, wild_mode=True)
        except RecipeScrapersExceptions:
            scraper = None
        except Exception:
            scraper = None

        if scraper is not None:
            for field_name, scraper_method in [
                ("name", "title"),
                ("description", "description"),
                ("total_time", "total_time"),
                ("prep_time", "prep_time"),
                ("cook_time", "cook_time"),
                ("servings_qty", "yields"),  # post-process to int
                ("source_url", "canonical_url"),
            ]:
                try:
                    val = getattr(scraper, scraper_method)()
                    if val:
                        partial[field_name] = val
                except Exception:
                    pass
            try:
                ingredients_raw = scraper.ingredients()
                partial["ingredients"] = [{"food_name": s} for s in ingredients_raw if s]
            except Exception:
                partial["ingredients"] = []
            try:
                instructions_raw = scraper.instructions_list()
                partial["steps"] = [{"body": s} for s in instructions_raw if s]
            except Exception:
                partial["steps"] = []

        # Validate against RecipeData (only `name` is required; everything else has defaults)
        valid_recipe: RecipeData | None = None
        if partial.get("name"):
            try:
                # Coerce servings_qty if it came as a string like "4 personas"
                if isinstance(partial.get("servings_qty"), str):
                    import re
                    m = re.search(r"\d+", partial["servings_qty"])
                    partial["servings_qty"] = int(m.group()) if m else None
                # Ensure source_url falls back to the fetched URL
                partial.setdefault("source_url", fetched.final_url)
                valid_recipe = RecipeData.model_validate(partial)
            except Exception:
                valid_recipe = None

        # Quality gate: ≥ 2 ingredients AND ≥ 1 step
        scraped_recipe_ok = (
            valid_recipe is not None
            and len(valid_recipe.ingredients or []) >= 2
            and len(valid_recipe.steps or []) >= 1
        )

        if scraped_recipe_ok:
            result = FetchAndScrapeResult(
                source_url=fetched.final_url,
                scraped_recipe=valid_recipe.model_dump(mode="json"),
                html_text=None,
            )
        else:
            from trafilatura import extract as trafilatura_extract
            cleaned = trafilatura_extract(
                html, include_comments=False, include_tables=True, output_format="txt"
            ) or ""
            result = FetchAndScrapeResult(
                source_url=fetched.final_url,
                scraped_recipe=None,
                html_text=cleaned[:200_000],  # safety cap on text size into LLM context
            )

        return result.model_dump_json()
```

### Pattern 3: `WORKFLOW_REGISTRY` topology after Phase 23 (D-01)

```python
# src/robotina/agent/workflows.py — replaces existing "add-recipe" entry
# Source: D-01 + URL-03 + memory feedback_avoid_premature_abstraction (inline-duplicate;
# extract shared-tail helper in Phase 24 when recipe-image inserts a step in both variants)

from robotina.queue.task_types import (
    AddRecipeQueryInput, AddRecipeUrlInput,  # NEW import
    FinalizeOutcomeInput, RecipeData,
    RecipeLoadInput, RecipeResearchGatherInput,
    RecipeResearchIngredientsInput, RecipeResearchInstructionsInput,
    RecipeResearchMetadataInput, ReplyContext,
)

# Shared step builders (5 of 6 steps identical between variants — duplicate inline
# for Phase 23; Phase 24 extracts when recipe-image lands in both)
_SHARED_TAIL_STEPS = [
    WorkflowStepDef(step_key="instructions", task_type="recipe-research-instructions",
        build_input=lambda ctx, a: RecipeResearchInstructionsInput(
            recipe=RecipeData(**a["gather"] if "gather" in a else a["gather-from-url"]),
            reply_context=ReplyContext(**ctx["reply_context"]),
            household_id=ctx["household_id"])),
    # ... ingredients, metadata, load, finalize-outcome
]
# Note: above pattern requires either two near-identical step lists OR a helper that
# picks the right artifact key. Planner's call — inline duplication is the simpler
# read and matches feedback_avoid_premature_abstraction; helper extraction matches Phase 24's
# need anyway. RECOMMENDED: inline duplicate with explicit `artifacts["gather"]` vs
# `artifacts["gather-from-url"]` keys for Phase 23; Phase 24 unifies.

WORKFLOW_REGISTRY: dict[str, WorkflowDefinition] = {
    "add-recipe-from-query": WorkflowDefinition(
        workflow_type="add-recipe-from-query",
        steps=[
            WorkflowStepDef(step_key="gather", task_type="recipe-research-gather",
                build_input=lambda ctx, _: RecipeResearchGatherInput(
                    query=ctx["recipe_query"],
                    reply_context=ReplyContext(**ctx["reply_context"]),
                    household_id=ctx["household_id"])),
            # instructions, ingredients, metadata, load, finalize-outcome — inline duplicate of the 5 tail steps
        ],
    ),
    "add-recipe-from-url": WorkflowDefinition(
        workflow_type="add-recipe-from-url",
        steps=[
            WorkflowStepDef(step_key="gather-from-url", task_type="gather-from-url",
                build_input=lambda ctx, _: GatherFromUrlInput(  # NEW Pydantic input model (see Open Questions)
                    url=ctx["recipe_url"],
                    reply_context=ReplyContext(**ctx["reply_context"]),
                    household_id=ctx["household_id"])),
            # instructions, ingredients, metadata, load, finalize-outcome — inline duplicate
            # (downstream steps read RecipeData from artifacts["gather-from-url"] instead of artifacts["gather"])
        ],
    ),
}
```

### Pattern 4: `StartWorkflowArgs` extended (D-01)

```python
# src/robotina/agent/tools/start_workflow.py — replaces StartWorkflowArgs
# Source: D-01 + Claude's Discretion (plain union, outer model_validator enforces pairing)

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from robotina.queue.task_types import AddRecipeQueryInput, AddRecipeUrlInput

class StartWorkflowArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_type: Literal["add-recipe-from-query", "add-recipe-from-url"] = Field(
        description="Workflow identifier. Either 'add-recipe-from-query' (free-text recipe) or 'add-recipe-from-url' (URL to a recipe page).",
    )
    input: AddRecipeQueryInput | AddRecipeUrlInput = Field(
        description=(
            "Typed input for the workflow. For 'add-recipe-from-query': {value: <query string>}. "
            "For 'add-recipe-from-url': {url: <https URL>}."
        ),
    )

    @model_validator(mode="after")
    def _enforce_pairing(self) -> "StartWorkflowArgs":
        if self.workflow_type == "add-recipe-from-query" and not isinstance(self.input, AddRecipeQueryInput):
            raise ValueError("workflow_type='add-recipe-from-query' requires input={value: str}")
        if self.workflow_type == "add-recipe-from-url" and not isinstance(self.input, AddRecipeUrlInput):
            raise ValueError("workflow_type='add-recipe-from-url' requires input={url: str}")
        return self
```

**Branch on input type inside `StartWorkflowTool._run`** — write `recipe_query` for
Query variant, `recipe_url` for URL variant, into `shared_context`:

```python
if isinstance(input, AddRecipeQueryInput):
    shared_context["recipe_query"] = input.value
elif isinstance(input, AddRecipeUrlInput):
    shared_context["recipe_url"] = input.url
```

### Pattern 5: `gather-from-url` agent prompt (D-03) — V001 rule shape

The planner writes the final prompt text. Required content:

- "Call `fetch-and-scrape(url)` EXACTLY ONCE with the URL from `input.url`."
- "If the tool returns `scraped_recipe` (non-null), emit it verbatim via `response_format`.
  Add `source_url` from the tool result if absent."
- "If the tool returns `html_text` (non-null) and `scraped_recipe` is null, extract a
  complete `RecipeData` from `html_text`. Set `source_url` from the tool result.
  Required: `name`, `ingredients` (≥ 2), `steps` (≥ 1). Units MUST be in the project
  canonical set (see recipe-research-* prompts for reference)."
- "Never fabricate data. If `html_text` clearly is not a recipe page, emit a minimal
  RecipeData with just `name` (extracted from page title) — downstream validation
  will reject it and the workflow will fail with a clear reason."
- English prompt body; emitted RecipeData fields in Spanish (recipe content language
  matches source; metadata field names per existing schema).

### Anti-Patterns to Avoid

- **DON'T use `recipe-scrapers` to fetch.** It is parser-only. `safe_fetch` is the
  fetcher. `scrape_html(html, ...)` takes pre-fetched HTML.
  `[CITED: PITFALLS.md Pitfall 6 + STACK.md:175]`
- **DON'T use `httpx.get(url, follow_redirects=True)` anywhere in the URL pipeline.**
  Defaults follow redirects without re-validating IPs — direct SSRF bypass.
  `[CITED: PITFALLS.md Pitfall 6 + https://github.com/Kozea/WeasyPrint/security/advisories/GHSA-983w-rhvv-gwmv]`
- **DON'T resolve DNS once and reuse the IP.** The IP check must run per call. If the
  first call resolves to a public IP and the next resolves to a private IP (DNS
  rebinding), re-resolving catches it.
- **DON'T check only the first A record.** `socket.getaddrinfo(host, None)` returns all
  records; loop through ALL of them. Multi-A-record DNS rebinding bypasses single-record checks.
- **DON'T catch `SafeFetchError` inside `FetchAndScrapeTool._run`.** Per D-03, re-raise
  so the agent has no recovery path and the step fails fast with a clear reason in
  `failure_reason`. The wake reply (Phase 22 D-08) surfaces it.
- **DON'T add a discriminator field to `AddRecipeQueryInput` / `AddRecipeUrlInput`.**
  The shapes (`{value}` vs `{url}`) are mutually exclusive at the JSON level. Adding
  `kind` forces the LLM to emit an extra field with no semantic purpose. Plain union +
  outer `@model_validator` is the safety net.
- **DON'T hand-roll an HTML cleaner.** Use `trafilatura.extract(...)`. Reinventing
  reaches the same edge cases trafilatura already handles.
- **DON'T extract a shared-tail helper between the two workflow variants in Phase 23.**
  Inline duplicate the 5 tail steps. Phase 24 inserts `recipe-image` in BOTH variants
  and the helper extraction belongs THERE per `feedback_avoid_premature_abstraction`.
- **DON'T add a defensive code cap to `StartWorkflowTool` for URL-vs-query mismatch.**
  The `@model_validator` IS the safety net. A code cap is redundant and dilutes the
  contract.
- **DON'T add a URL regex in V007.** D-05 is LLM-judgment. Punycode/IDN/percent-
  encoded paths/regional TLDs are easier for the LLM than for regex.
- **DON'T enqueue the new variant's first step under the old `add-recipe` workflow_type
  string.** After the rename commit, the literal string `"add-recipe"` MUST NOT appear
  in `WORKFLOW_REGISTRY` keys, `StartWorkflowTool.workflow_type` Literal, V007 worked
  examples, or any test. The Pitfall 7 (Workflow rename catches in-flight workflows)
  guidance: drain the queue before deploy, or accept failures in pre-launch env.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| URL fetch with security defenses | Custom `requests`/`urllib` wrapper | `safe_fetch` (this phase's contribution) wrapping `httpx.Client(follow_redirects=False)` + `ipaddress` + `socket.getaddrinfo` | Every defense is a known-easy-to-miss step (per-redirect re-validation, multi-record DNS, IPv4-mapped IPv6, gzip ratio). A dedicated module + tests is the right factoring. `[CITED: PITFALLS Pitfall 6]` |
| HTML → recipe field extraction | Custom BeautifulSoup recipe extractor | `recipe-scrapers.scrape_html(html, wild_mode=True, org_url=url)` | 6+ years of per-site quirks; parses JSON-LD + microdata + RDFa + OpenGraph in one call. `[CITED: STACK.md:157]` |
| HTML → clean plain text | Custom regex/BS4 stripping | `trafilatura.extract(html, include_comments=False, include_tables=True, output_format="txt")` | Purpose-built; strips nav/footer/scripts/comments better than ad-hoc rules; 10-50× token savings vs raw HTML. `[CITED: PITFALLS Pitfall 7]` |
| Pydantic shape pairing enforcement | Custom validation in `_run` | `@model_validator(mode='after')` on outer `StartWorkflowArgs` | Pydantic-native; runs before `_run`; failure becomes ToolMessage(error) the LLM can react to. `[CITED: D-01]` |
| IP classification | Custom CIDR-set checks | `ipaddress.ip_address(ip).is_private / is_loopback / is_link_local / is_multicast / is_reserved / is_unspecified` + explicit 169.254.169.254 + IPv4-mapped IPv6 unwrap | Stdlib covers RFC1918 + RFC4193 (IPv6 ULA) + RFC6890 special-use. Manual CIDR sets miss cases. |
| Multi-recipe URL parsing into batch | Single `start-workflow` with `urls=[...]` | One `start-workflow(add-recipe-from-url, {url: ...})` per URL | D-06. Matches Phase 22 multi-recipe pattern; reuses the `invocation_id` constructor-injection invariant; no schema change to the tool's args. |
| Eval framework | Generic eval-runner with config files | One concrete `experiments/gather_from_url.py` (single file) | `feedback_avoid_premature_abstraction` — Phase 22 set the pattern with `multi_recipe_eval.py`; Phase 23 mirrors. If THREE phases converge, THEN extract a shared helper. |

**Key insight:** SSRF is unrecoverable once exploited. The `safe_fetch` defense matrix is
non-negotiable — there is no "ship a simpler version now, harden later" path. The first
commit in Phase 23 is `safe_fetch` + comprehensive tests. Everything else builds on top.

## Runtime State Inventory

Phase 23 is a refactor + additive feature. Apply the rename-impact audit explicitly.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | `WorkflowRun` rows with `workflow_type="add-recipe"` in Postgres (any history surviving the v1.1 staging soaks). D-01 renames the registry key to `"add-recipe-from-query"`; in-flight rows with the OLD string in `workflow_type` will fail to resolve a definition at the next step transition. | Pre-deploy: drain the queue and verify zero `workflow_runs` rows in PENDING/RUNNING status with `workflow_type='add-recipe'` (operator runbook in Plan 23-02). Historical DONE/FAILED rows are read-only; their `workflow_type` string is informational only on the dashboard and does NOT cause runtime errors. Document in 23-02 plan. |
| | `shared_context` JSONB on existing `WorkflowRun` rows: contains `recipe_query` (Phase 5 contract, verified at `start_workflow.py:182`). Phase 23 adds a NEW key `recipe_url` for URL workflows; the read-side wake helper falls back from `recipe_query` to `recipe_url` (D-08). No backfill needed. | None for existing rows; new URL workflows write the new key. |
| **Live service config** | `overrides/anthropic.json`, `overrides/openai.json`, `overrides/staging.ollama.json` — files in git, all checked. Phase 21 D-12 CI guard enforces AGENT_REGISTRY ↔ overrides sync. | D-23: add `gather-from-url` block to ALL THREE files in the SAME commit as the AGENT_REGISTRY entry. `feedback_overrides_in_sync` is the explicit mandate. |
| | Dashboard label map `_macros.html` TASK_TYPE_LABELS — informational only; missing label = raw enum value displayed. | Add `"gather-from-url": "Búsqueda por URL"`. Phase 21 D-11 pattern. |
| | LangWatch project metadata tags — set per-call via experiment metadata. | Eval harness tags traces with `phase=23`, `url=<the url>`, `backend=<backend>` per CLAUDE.md. |
| **OS-registered state** | None — no Windows Task Scheduler, no launchd, no systemd units, no pm2 saved processes touch URL ingestion. RQ workers are foreground / Docker Compose. | None. |
| **Secrets/env vars** | NEW env var: `URL_INGESTION_ALLOW_HTTP` (default `false`); D-17 adds to `.env.example`. NO new API tokens needed for Phase 23 (existing `*_API_TOKEN` env vars cover the new `gather-from-url` agent — name TBD by planner, suggest `GATHER_FROM_URL_API_TOKEN`). | Add `URL_INGESTION_ALLOW_HTTP=false` + `GATHER_FROM_URL_API_TOKEN=` to `.env.example` with comments. Per memory `feedback_env_example`. |
| **Build artifacts** | `recipe-scrapers` (already declared) and `trafilatura` (NEW) wheels. `uv.lock` updates after `uv add trafilatura`. | Plan 23-03 commits `pyproject.toml` + `uv.lock` together. |

**Verified by:** grep of `WORKFLOW_REGISTRY` (1 entry: `"add-recipe"`), grep of
`workflow_type` Literals (`start_workflow.py:59`), grep of `overrides/*.json` (no
`gather-from-url` block in any), inspection of `_macros.html` TASK_TYPE_LABELS (no
`gather-from-url` label). All confirmed against the current codebase 2026-05-20.

## Common Pitfalls

### Pitfall 1: SSRF via DNS rebinding bypass (PITFALLS Pitfall 6 derived)

**What goes wrong:** Attacker controls a DNS record with TTL=0 that flips between
public and private IPs. Naive `safe_fetch` resolves once, sees public IP, passes the
check, makes the HTTP call — and the kernel re-resolves and lands on the private IP.

**Why it happens:** Time-of-check-to-time-of-use gap between `getaddrinfo` and the
HTTP call.

**How to avoid:**
- `httpx.Client(follow_redirects=False)` re-resolves DNS on each request by default (no
  IP pinning). The default IS the mitigation.
- DO NOT pin an IP and pass `Host:` header (an alternative mitigation that some SSRF
  guides recommend) — that requires bypassing httpx's `httpcore` connection pool, which
  is fragile.
- The redirect loop in `safe_fetch` re-runs `_resolve_and_check(host)` on every hop;
  even if the attacker waits to flip DNS until between resolutions, ONE of the resolution
  rounds will see the private IP.
- Test: `tests/url/test_safe_fetch.py` includes a redirect-chain-to-private-IP test
  (httpbin.org/redirect-to?url=http://169.254.169.254/...).

**Warning signs:** A URL passes `safe_fetch` but the worker logs show the connection
landed on an unexpected IP. (Hard to detect from logs alone; the redirect re-validation
is the structural defense.)

### Pitfall 2: `recipe-scrapers` silent partial extraction (PITFALLS Pitfall 7)

**What goes wrong:** Scraper "succeeds" but returns `title="Cooking Tips"` and
`ingredients=[]` because the page is a category listing, not a recipe page. Looks valid
to the Pydantic validator; isn't.

**Why it happens:** `recipe-scrapers` raises per-method on missing data
(`ElementNotFoundInHtml`, etc.), but if a category page happens to have schema.org
markup for a *featured* recipe, the scraper extracts partial data.

**How to avoid:**
- D-03 quality gate: scraped result only counts if `len(ingredients) >= 2` AND
  `len(steps) >= 1`. Below this floor, fall through to the LLM-fallback path.
- The 20-URL eval set's sanity rows (D-10 coverage class 6) include a non-recipe URL
  expected to FAIL — validates the floor catches it.

**Warning signs:** Eval row's per-URL field count is suspiciously low; LLM fallback
fires on a site that should be well-supported.

### Pitfall 3: Spanish blog hit-rate unknown (gap from `.planning/research/SUMMARY.md`)

**What goes wrong:** `recipe-scrapers wild_mode=True` advertises "any site with
schema.org/Recipe JSON-LD." Argentine/Uruguayan recipe blogs may publish incomplete
schema.org (e.g. `recipeIngredient` present but `recipeInstructions` as plain prose).
Hit-rate against the long tail is unverified.

**Why it happens:** No published benchmark. SEO compliance varies by blog vintage and
WordPress plugin set.

**How to avoid:**
- D-10: 20-URL eval set IS the empirical validation. Coverage classes 1-3 explicitly
  spread coverage across well-supported / wild_mode / LLM-fallback territory.
- D-12 OpenAI staging merge gate at ≥85% URL-level pass. If the rate is significantly
  below, the LLM-fallback path needs tightening (better prompt; possibly per-class
  rules) — NOT a code change to `safe_fetch` or `FetchAndScrapeTool`.

**Warning signs:** Eval results consistently show <80% pass on coverage classes 2-3
(wild_mode + LLM-fallback). Flags a need to revisit the V001 prompt for the agent's
LLM-extraction path.

### Pitfall 4: Workflow rename catches in-flight workflows

**What goes wrong:** Pre-deploy database has WorkflowRun rows in PENDING/RUNNING with
`workflow_type='add-recipe'`. After the D-01 rename, the next step transition looks up
`WORKFLOW_REGISTRY['add-recipe']` → KeyError → step FAILED with a confusing reason.

**Why it happens:** The rename is one atomic code commit, but in-flight workflows are
state at the time of deploy.

**How to avoid:**
- Pre-deploy runbook step in Plan 23-02: drain the queue (`rq empty agent-tasks`) and
  verify `SELECT COUNT(*) FROM workflow_runs WHERE status IN ('PENDING','RUNNING') AND
  workflow_type='add-recipe'` returns 0. In pre-launch private env, the queue is
  typically empty between dev sessions; runbook documents the check rather than
  forcing complex migration logic.
- Historical DONE/FAILED rows with `workflow_type='add-recipe'` continue to display
  correctly in the dashboard (dashboard renders the string verbatim; no lookup).

**Warning signs:** Post-deploy, the failed-job registry fills with `KeyError:
'add-recipe'` exceptions.

### Pitfall 5: V007 URL detection over-triggers on innocuous tokens

**What goes wrong:** V007 LLM treats anything that looks URL-ish as a URL — including
text fragments like "recetas.com" (bare hostname, no scheme), "see paula.cocina/recetas"
(formatted citation), or a literal product name like "Curry 2.0".

**Why it happens:** LLM-judgment is fuzzy on what's a URL.

**How to avoid:**
- D-05 explicitly: "If the URL pattern is ambiguous (e.g. bare `recetas.com` without
  scheme or path), ask the user via `respond()` with a Spanish clarifying question; do
  not start a workflow on ambiguous bare hostnames."
- V007 worked examples include both "agregá esta receta: https://x/y" (clear → URL
  workflow) AND "agregá la receta de paula.cocina/recetas" (bare-ish → respond clarify).
- Eval set's coverage class includes ambiguous-bare-hostname rows (operator can add
  during 23-EVAL-SET.md authoring).

**Warning signs:** Operator smoke shows URL workflow spawned on innocuous tokens; user
reports unexpected "buscando esa receta…" message.

### Pitfall 6: `RecipeData.source_url` collision between scraper and downstream metadata step

**What goes wrong:** `gather-from-url` populates `source_url` with the user-supplied URL.
The downstream `recipe-research-metadata` step (per its V004 prompt) ALSO sets
`source_url` from web search results — potentially overwriting the user's URL.

**Why it happens:** Both agents own the same field per the Phase 15 accumulating-
artifact contract; the contract docstring (`task_types.py:113-121`) says metadata
"owns servings_qty, servings_unit, prep_time, cook_time, total_time, source_url".

**How to avoid:**
- Plan 23-04 task: update `recipe-research-metadata` prompt rule — "If
  `source_url` is already set in the incoming RecipeData, preserve it unchanged. Only
  populate when null."
- Alternative: in `WORKFLOW_REGISTRY` for `add-recipe-from-url`, skip the metadata
  step's `source_url` field by build_input transformation. Cleaner but riskier (changes
  the contract). Prefer the prompt rule.
- Test: a fixture `RecipeData` with `source_url="https://x"` passes through metadata
  unchanged.

**Warning signs:** Eval result rows show `source_url` populated with a Tavily search
result URL instead of the original input URL.

### Pitfall 7: `httpx` automatic content-decoding bypasses gzip-bomb defense

**What goes wrong:** `httpx.Client` automatically decompresses gzip/deflate/brotli
responses; `resp.content` returns already-decompressed bytes. Our `_decompress_with_cap`
in `safe_fetch` never sees the compressed form, so the ratio check never fires.

**Why it happens:** httpx default behavior; the decompression cap as written in
Pattern 1 is a defense against MANUAL decompression of `Content-Encoding`-bearing raw
bytes, not against automatic decompression.

**How to avoid:**
- Option A (simpler): rely on the post-decompression size cap (`len(content) > max_bytes`
  → reject) as the only defense; remove the ratio check entirely. A 5 MB cap on
  decompressed bytes IS the bomb defense.
- Option B (defense-in-depth): disable httpx auto-decompression
  (`Accept-Encoding: identity` request header) and decompress manually with the cap.
  Loses transparent compression benefits.
- **Recommendation:** Option A. The post-decompression byte cap is sufficient; the
  ratio check is belt-and-suspenders that adds complexity without much benefit at the
  5 MB cap. Document the choice in `safe_fetch.py` docstring. The Pattern 1 code above
  has the ratio check; planner should evaluate whether to keep or simplify.

**Warning signs:** Tests for gzip-bomb pass against the manual-decompress path but fail
against the real httpx flow.

### Pitfall 8: LangWatch span attribution for `safe_fetch` failures inside `FetchAndScrapeTool`

**What goes wrong:** `safe_fetch` raises inside `FetchAndScrapeTool._run`. The exception
propagates up to LangChain's tool runner, becomes a `ToolMessage(status='error')`. The
agent then tries to extract `response_format=RecipeData` from a state with no successful
tool output → response_format extraction raises → step FAILED. The LangWatch trace
shows the agent's LLM call, but the actual root cause (`SafeFetchError`) may be buried
in the tool's intermediate ToolMessage rather than the span error attribute.

**Why it happens:** Multiple layers between `safe_fetch.raise` and the workflow_runner's
`failure_reason` write.

**How to avoid:**
- `FetchAndScrapeTool._run` does NOT catch `SafeFetchError` per D-03. This lets
  LangChain's tool exception handling capture the full traceback in the trace.
- `_extract_task_output` / `on_step_failed` (Phase 13 wiring) captures `f"{type(exc).__name__}: {exc}"`
  on `WorkflowRunStep.failure_reason` and `WorkflowRun.outcome.failure_reason` (quick task
  260520-kot). Verified: the failure_reason propagates to wake reply.
- LangWatch traces will show the agent invocation + the tool-call ToolMessage(error) —
  operator clicks through to see the SafeFetchError reason.
- Add a structured logger.error in `safe_fetch` raise paths for log-side debugging
  (separate from the trace).

**Warning signs:** Failed workflows lack URL or reason in `WorkflowRun.outcome` — would
indicate the failure_reason wiring (260520-kot) regressed.

## Code Examples

### Verified `recipe-scrapers` usage

```python
# Source: [CITED: STACK.md:37-38, https://github.com/hhursev/recipe-scrapers]
from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import RecipeScrapersExceptions  # base class for catch

scraper = scrape_html(html, org_url=url, wild_mode=True)
# Available methods (per GitHub README): title(), description(), total_time(),
# prep_time(), cook_time(), yields(), ingredients(), instructions(),
# instructions_list(), image(), canonical_url(), author(), nutrients(),
# category(), cuisine(), language(), site_name(), keywords(), ratings(),
# ratings_count(), reviews(), equipment(), cooking_method(), description(),
# host()
# Per-method raises on missing data — wrap each in try/except per Pitfall 2.
```

### Verified `trafilatura` usage

```python
# Source: [CITED: https://trafilatura.readthedocs.io/en/latest/usage-python.html]
from trafilatura import extract

cleaned_text = extract(
    html,                          # raw HTML string (NOT a URL)
    include_comments=False,
    include_tables=True,
    output_format="txt",           # plain text; alternatives: "xml", "json", "markdown"
    no_fallback=False,             # keep fallback algorithms for accuracy
) or ""
# `extract` returns None on extraction failure; coerce to "" to keep typing simple.
```

### V007 forking from V006 (D-05/D-06/D-07)

Fork V006 verbatim. Replace the ambiguity-rule URL example (V006 line 118 currently
deflects URLs as "no soportado") with the new URL detection sections:

```markdown
## URL handling

If a token in the user message looks like a web URL — starts with `http://`,
`https://`, or contains a clear `domain.tld/path` pattern — route THAT token
through `start-workflow(workflow_type="add-recipe-from-url",
input={"url": "<token>"})`. Strip surrounding punctuation; preserve query strings,
paths, and fragments.

If the URL pattern is ambiguous (e.g. a bare hostname like "recetas.com" without
scheme or path), do NOT start a workflow. Call
`respond(text="¿Tenés el link completo de la receta? Mandámelo y la guardo.")`
then `terminate()`.

### Worked example — single URL

User message: "agregá esta receta: https://recetasdesa.com/canelones-de-choclo"

Tool calls:
  1. respond(text="Listo, voy con esa receta. Te aviso cuando termine.")
  2. start-workflow(workflow_type="add-recipe-from-url",
                    input={"url": "https://recetasdesa.com/canelones-de-choclo"})
  3. terminate()

### Worked example — mixed text + URL

User message: "agregá lentejas y https://example.com/pollo-al-horno"

Tool calls:
  1. respond(text="Listo, voy con lentejas y la receta de pollo del link. Te aviso.")
  2. start-workflow(workflow_type="add-recipe-from-query", input={"value": "lentejas"})
  3. start-workflow(workflow_type="add-recipe-from-url",
                    input={"url": "https://example.com/pollo-al-horno"})
  4. terminate()

### Worked example — multiple URLs

User message: "agregá estas dos: https://a.com/r1 y https://b.com/r2"

Tool calls:
  1. respond(text="Listo, las arranco. Te aviso cuando terminen.")
  2. start-workflow(workflow_type="add-recipe-from-url", input={"url": "https://a.com/r1"})
  3. start-workflow(workflow_type="add-recipe-from-url", input={"url": "https://b.com/r2"})
  4. terminate()

### Worked example — ambiguous bare hostname

User message: "agregá lo de paulina.com"

Tool calls:
  1. respond(text="¿Tenés el link completo de la receta? Mandámelo y la guardo.")
  2. terminate()
```

**Update V006's ambiguity-rule URL line:** the existing line "User pastes a URL: 
respond(text='Todavía no manejo enlaces directos…')" MUST be REMOVED in V007 (this
phase enables what V006 deflects).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| V006 deflects URLs as "no soportado" | V007 routes URLs through `add-recipe-from-url` | Phase 23 D-05 | First URL ingestion surface in the project. |
| Single `add-recipe` workflow | Per-source variants: `add-recipe-from-query`, `add-recipe-from-url` | Phase 23 D-01 | Symmetric naming; planner picks the variant; downstream steps identical. |
| `StartWorkflowTool.workflow_type` Literal = `["add-recipe"]`; `input: AddRecipeQueryInput` | Literal = `["add-recipe-from-query", "add-recipe-from-url"]`; `input: AddRecipeQueryInput \| AddRecipeUrlInput` + `@model_validator` | Phase 23 D-01 | LLM-emitted shape mismatch caught at validation time, not at registry lookup. |
| `recipe-scrapers` declared but unused | First actual use: deterministic recipe extraction with `wild_mode=True` | Phase 23 (Phase 8 declared the dep) | Long-tail Spanish recipe coverage now empirically measurable via 23-EVAL-SET.md. |
| Wake helper reads only `shared_context["recipe_query"]` | Reads `recipe_query OR recipe_url` | Phase 23 D-08 | URL workflows surface the URL in failure lines instead of "(receta sin nombre)". |
| No SSRF defenses; no URL fetching anywhere | `safe_fetch` with 6 defenses + gzip-bomb cap | Phase 23 (FIRST commit per ROADMAP) | Closes the SSRF attack surface BEFORE any feature relies on it. Reused by Phase 24 `recipe-image`. |

**Deprecated/outdated:**
- The `"add-recipe"` workflow_type string — REMOVED post-Phase-23. Hard rename, no
  transitional alias.
- V006 — retained on disk for rollback (D-25); `agents.py` stops pointing at it.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `recipe-scrapers` exposes `scrape_html(html, org_url=url, wild_mode=True)` with this exact signature in `>=15.11.0` | Pattern 2 Code Example | Plan must verify by running `uv run python -c "from recipe_scrapers import scrape_html; help(scrape_html)"` at plan time. WebFetch confirmed signature shape (`scrape_html(html, url, best_image=False)` per GitHub README) — but STACK.md:175 uses `wild_mode=True` and `org_url=` keyword; signature may have evolved. Worst case: rename `org_url=` to `url=` (positional). |
| A2 | `recipe_scrapers._exceptions.RecipeScrapersExceptions` is the base class for per-method failures | Pattern 2 Code Example | If the import path / class name has changed, fall back to bare `except Exception:` in per-field try/except (already done in Pattern 2 — safe fallback). |
| A3 | `trafilatura>=1.6` `extract(html, include_comments=False, include_tables=True, output_format="txt")` returns clean text reliably | Pattern 2 + D-04 | If extraction is poor on Spanish blogs, the LLM fallback path's reliability drops. Pitfall 3 covers; eval set is the empirical check. |
| A4 | `httpx.Client` re-resolves DNS per call (no IP pinning by default) | Pitfall 1 mitigation | If httpx pools connections by IP, DNS rebinding window could exist. Verify via httpx docs at plan time; if confirmed pooling, disable connection pool (`httpx.Client(transport=httpx.HTTPTransport(retries=0))` and recreate per call). |
| A5 | `httpx.Client` auto-decompresses gzip/deflate/brotli; `resp.content` returns decompressed bytes | Pitfall 7 | If true (likely), the manual `_decompress_with_cap` in Pattern 1 never sees compressed bytes; the post-decompression size cap is the actual defense. Pattern 1 retains the ratio check as belt-and-suspenders; planner can simplify. |
| A6 | `langchain.agents.create_agent(response_format=RecipeData)` works with a tool that returns a JSON-encoded `FetchAndScrapeResult` string | D-03 + Pattern 2 | Phase 11 verified `response_format=` end-to-end on the 5 artifact-producing agents (`.planning/decisions/response-format-adoption.md`). New agent inherits the same path. |
| A7 | Spanish recipe blogs (Paulina Cocina, Recetas Gratis, Cocinatis, Directo al Paladar) have site-specific scraper coverage in `recipe-scrapers 15.11.0` | D-10 coverage class 1 | If NOT covered, those URLs drop to wild_mode (class 2) — adjusts the class distribution but doesn't invalidate the eval. Operator validates at 23-EVAL-SET.md authoring time by running `scrape_html(html, org_url=url, wild_mode=False)` against each candidate and checking for `WebsiteNotImplementedError`. |
| A8 | The host running the agent in dev is reachable via `localhost`, `127.0.0.1`, AND its RFC1918 LAN IP (e.g. `192.168.x.x`) | Pitfall — dev SSRF surface | Verified via memory `project_local_dev_setup`. `safe_fetch` tests MUST verify rejection of ALL THREE classes (PITFALLS Pitfall 6 + D-18 explicitly covers). |
| A9 | `recipe-scrapers` is installed in the dev environment (already-declared per `pyproject.toml:33`) | Standard Stack | Verify via `uv run python -c "import recipe_scrapers; print(recipe_scrapers.__version__)"` at plan time. If wheel never resolved, `uv sync` resolves on the trafilatura add anyway. |
| A10 | `trafilatura` is NOT already transitively present | Standard Stack | Verify via `uv tree | grep trafilatura` at plan time. Unlikely transitive; treat as new direct dep regardless (explicit > implicit). |

## Open Questions (RESOLVED)

1. **`GatherFromUrlInput` Pydantic model shape (workflow build_input).**
   - What we know: The `gather-from-url` agent needs an input model with `url`,
     `reply_context`, `household_id` (mirrors `RecipeResearchGatherInput`). Not
     mentioned explicitly in CONTEXT.md but implied by D-03 + workflow registry pattern.
   - What's unclear: Whether to name it `GatherFromUrlInput` (matches task type) or
     `RecipeResearchGatherFromUrlInput` (matches sibling naming). Probably the former
     (shorter; task type is the natural key).
   - Recommendation: Planner adds `GatherFromUrlInput {url: str, reply_context:
     ReplyContext, household_id: NonEmptyHouseholdId}` to `task_types.py` alongside
     `AddRecipeUrlInput`. The agent's `to_user_message()` builds the LLM input prompt
     pointing to the URL: `f"Fetch and extract a recipe from this URL: {self.url}"`.

2. **Shared-tail step extraction in `workflows.py`.**
   - What we know: 5 of 6 steps are identical between the two variants. Inline-
     duplicate is OK for Phase 23 per `feedback_avoid_premature_abstraction`. Phase
     24 will extract when `recipe-image` lands in both.
   - What's unclear: Whether the `build_input` for `instructions` should read
     `artifacts["gather"]` (query variant) or `artifacts["gather-from-url"]` (URL
     variant) — these are different keys, so the lambda differs even though the
     downstream agent is identical.
   - Recommendation: Inline-duplicate the 5 tail steps with the right artifact-key
     read per variant. Planner writes both 6-step lists explicitly. Phase 24 unifies.

3. **`recipe-research-metadata` `source_url` collision (Pitfall 6).**
   - What we know: `gather-from-url` populates `source_url`; the metadata step's
     V004 prompt also sets `source_url`.
   - What's unclear: Whether the metadata prompt rule update is sufficient (LLM may
     ignore) or whether a code-level preserve guard is safer.
   - Recommendation: Start with the prompt rule (one line in metadata/V005.md);
     add a test that asserts `source_url` is preserved across the metadata step
     given a fixture RecipeData with `source_url` pre-populated. If the eval shows
     drift, escalate to a code-level guard in `WORKFLOW_REGISTRY['add-recipe-from-
     url'].steps[3].build_input`.

4. **`gather-from-url` agent's `*_API_TOKEN` env var name.**
   - What we know: Project convention is `<TASK_TYPE_UPPER>_API_TOKEN` (e.g.
     `RECIPE_RESEARCH_GATHER_API_TOKEN`). New agent → `GATHER_FROM_URL_API_TOKEN`.
   - What's unclear: Whether to reuse `RECIPE_RESEARCH_GATHER_API_TOKEN` (since
     both gather-from-* paths are conceptually peers) or have a distinct token per
     `feedback_overrides_in_sync`.
   - Recommendation: Distinct token (`GATHER_FROM_URL_API_TOKEN`). Mirrors the
     1:1 agent-to-token convention; lets operators throttle the URL path
     independently if cost rises. Add to `.env.example`.

5. **Whether `safe_fetch` should also reject IPv6 ULA (`fc00::/7`).**
   - What we know: D-16 enumerates "RFC1918, 127/8, ::1, 169.254/16, fe80::/10,
     0.0.0.0, multicast". IPv6 ULA (`fc00::/7`, Unique Local Address per RFC4193)
     is the IPv6 equivalent of RFC1918.
   - What's unclear: Whether ULA is in scope for v1.1 (no IPv6 internal network
     exists in the project deploy targets currently).
   - Recommendation: `ipaddress.ip_address(ip).is_private` covers `fc00::/7` per
     stdlib (`IPv6Address('fc00::1').is_private == True`). Explicit ULA check is
     redundant. Pattern 1 already covers this via `is_private`.

6. **Single-shot fetch vs streaming for content-length enforcement.**
   - What we know: Pattern 1 uses `resp.content` (reads whole response into memory
     after httpx auto-decompression).
   - What's unclear: Whether streaming via `resp.iter_bytes(chunk_size=8192)` and
     aborting mid-stream is materially safer than the post-read size check at 5 MB.
   - Recommendation: Single-shot `resp.content` with post-read cap. 5 MB is well
     below any reasonable RQ-worker memory budget; streaming adds complexity for
     no practical safety win at this cap. Document the choice.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | All | ✓ (project requirement) | per `pyproject.toml:9` | — |
| `recipe-scrapers` | `FetchAndScrapeTool` | ✓ declared (`pyproject.toml:33`) — verify installed | `>=15.11.0` | — |
| `trafilatura` | `FetchAndScrapeTool` LLM-fallback path | ✗ NEW dep | `>=1.6` (latest 2.0.0) | None — install required (`uv add trafilatura`) |
| `httpx` | `safe_fetch` | ✓ (`pyproject.toml:28`) | `>=0.27` (latest 0.28.1) | — |
| `ipaddress` (stdlib) | `safe_fetch` IP check | ✓ | — | — |
| `socket` (stdlib) | `safe_fetch` DNS resolve | ✓ | — | — |
| `langchain` | `gather-from-url` agent factory | ✓ | `>=1.2` | — |
| `langwatch` | Eval harness tracing | ✓ | `>=0.1` | If `LANGWATCH_API_KEY` absent, harness still runs; lose trace IDs. |
| `OPENAI_API_KEY` | OpenAI eval (merge gate per D-12) | operator-provided | — | If absent, Phase 23 stays `human_needed` — operator must run OpenAI eval before Phase merges. |
| `OLLAMA_URL`, Ollama daemon w/ `gpt-oss:20b` | Ollama dev eval | operator-provided | — | If absent, skip Ollama row in `23-SMOKE.md`; informational only per D-12. |
| `GATHER_FROM_URL_API_TOKEN` (or whatever planner names it) | `gather-from-url` agent invocation | operator-provided | — | None — required for the agent to run; add to `.env.example` empty per `feedback_env_example`. |
| `URL_INGESTION_ALLOW_HTTP` env var | `safe_fetch` http override | NEW; default `false` | — | Default secure. Dev/testing only flips to `true`. |
| Internet access from worker host | Eval against live URLs | operator-provided | — | None — Phase 23's whole point is fetching live URLs. Eval cannot run offline. |

**Missing dependencies with no fallback:**
- `trafilatura` (`uv add trafilatura` in Plan 23-03).
- `OPENAI_API_KEY` for the merge-gate eval.
- Internet access from the worker host.

**Missing dependencies with fallback:**
- `OLLAMA_URL` (informational eval only).
- `LANGWATCH_API_KEY` (harness still runs; lose trace IDs).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` + `pytest-asyncio` (per project stack) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/url/ tests/agents/tools/test_fetch_and_scrape_tool.py tests/agents/tools/test_start_workflow_tool.py tests/agents/test_gather_from_url_agent.py tests/queue/test_workflow_registry.py -x` |
| Full suite command | `uv run pytest -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| URL-01 | `safe_fetch` rejects all SSRF vectors | unit (one test per defense + composite scenarios) | `uv run pytest tests/url/test_safe_fetch.py -x` | ❌ Wave 0 |
| URL-02 | `FetchAndScrapeTool` returns scraped_recipe on supported sites; html_text on fallback | unit (with `respx` mocks + fixtures) | `uv run pytest tests/agents/tools/test_fetch_and_scrape_tool.py -x` | ❌ Wave 1 |
| URL-03 | Workflow registry has both variants; rename removed | unit (registry assertions) | `uv run pytest tests/queue/test_workflow_registry.py -x` | EXTEND existing |
| URL-03 | `StartWorkflowArgs` model_validator enforces workflow_type ↔ input pairing | unit (4 cases per D-22) | `uv run pytest tests/agents/tools/test_start_workflow_tool.py -x` | EXTEND existing |
| URL-04 | `gather-from-url` agent passes through scraped_recipe; extracts from html_text on fallback | unit (with mocked LLM and stub tool) | `uv run pytest tests/agents/test_gather_from_url_agent.py -x` | ❌ Wave 1 |
| URL-05 | V007 routes URLs to add-recipe-from-url; ambiguous bare hostnames → respond clarify | manual-only (eval set + V007 worked-example smoke) | operator runs `uv run experiments.gather_from_url --backend openai` + end-to-end Telegram smoke | ❌ Wave 2 |
| URL-06 | 20-URL Spanish-recipe eval ≥85% URL-level pass | manual-only (eval set) | `uv run experiments.gather_from_url --backend openai` then operator commits `23-EVAL-RESULTS-openai.md` + `23-SMOKE.md` | ❌ Wave 2 |
| EXP-02 | `uv run experiments.gather_from_url` runs end-to-end with LangWatch traces | manual-only | same as URL-06 | ❌ Wave 2 |
| AGENT_REGISTRY ↔ overrides/*.json sync | new `gather-from-url` entry in all 3 overrides files | unit (Phase 21 D-12 CI guard) | `uv run pytest tests/agents/test_registry_override_sync.py -x` | ✓ (existing — extends to assert new entry's presence) |
| Dashboard label map | "gather-from-url": "Búsqueda por URL" | unit (template test) | `uv run pytest tests/dashboard/test_macros.py -x` | EXTEND existing |
| Wake helper fallback read | `_check_and_dispatch_wake` reads `recipe_url` when `recipe_query` is absent | unit | `uv run pytest tests/queue/test_wake_helper.py -x` | EXTEND existing |

### Sampling Rate

- **Per task commit:** Quick run command (~ < 10 seconds; covers new files).
- **Per wave merge:** Full suite (`uv run pytest -x`) — catches dashboard / workflow regressions.
- **Phase gate:** Full suite green + operator `23-SMOKE.md` verdict `pass` (load-bearing per D-24).

### Wave 0 Gaps

- [ ] `tests/url/__init__.py` — NEW (empty).
- [ ] `tests/url/test_safe_fetch.py` — NEW. One test per defense per D-18 (~13 tests).
- [ ] `tests/agents/tools/test_fetch_and_scrape_tool.py` — NEW per D-19 (~5 tests).
- [ ] `tests/agents/test_gather_from_url_agent.py` — NEW per D-20 (~3 tests).
- [ ] `tests/queue/test_workflow_registry.py` — EXTEND per D-21 (assert both variants present; assert `add-recipe` key absent).
- [ ] `tests/agents/tools/test_start_workflow_tool.py` — EXTEND per D-22 (4 pairing cases).
- [ ] `tests/agents/test_handle_incoming_message_agent.py` — EXTEND (V007 prompt path).
- [ ] `tests/queue/test_wake_helper.py` — EXTEND (D-08 fallback read; insert WorkflowRun with `shared_context={"recipe_url": "https://x"}` and no `recipe_query` → assert `WorkflowOutcomeSummary.recipe_query == "https://x"`).
- [ ] No framework install needed (`pytest` + `pytest-asyncio` already present).
- [ ] Optional install: `respx` for httpx mocking in `safe_fetch` tests. If not already
      present (`uv tree | grep respx`), `uv add --dev respx`. Alternative: use httpbin.org
      via real network calls in a `@pytest.mark.integration` block — but that's flaky;
      prefer `respx` for unit-level. NEW dev dep candidate.

## Security Domain

Phase 23 introduces the first user-supplied-URL surface in the project. Security is
load-bearing — `safe_fetch` is mandatory infrastructure, not a feature.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No new auth surface. |
| V3 Session Management | no | No session changes. |
| V4 Access Control | no | No new endpoints. |
| V5 Input Validation | yes | `AddRecipeUrlInput.url: str` is Pydantic-validated; `StartWorkflowArgs` `extra='forbid'` + `@model_validator`; `FetchAndScrapeArgs` `extra='forbid'`. `safe_fetch` validates scheme, host, IP, redirect chain, content-length, content-type. |
| V6 Cryptography | no | No new crypto. |
| V12 Files and Resources (URL fetching) | **yes — primary scope** | `safe_fetch` is the single chokepoint. No raw `httpx.get(url)` outside `safe_fetch` — enforce via test or grep gate in CI. |
| V13 API and Web Service | no | No new external API surface. |

### Known Threat Patterns for URL ingestion

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| **SSRF to AWS metadata** (`http://169.254.169.254/`) | Information Disclosure | `safe_fetch` explicit `_BLOCKED_EXTRA_IPS` includes 169.254.169.254 + `is_link_local` covers 169.254/16 in general. Test in D-18. |
| **SSRF to internal services** (`http://postgres:5432/`, `http://redis:6379/`) | Information Disclosure / Tampering | `is_private` covers RFC1918; `is_loopback` covers 127.0.0.0/8 + ::1. Host-mode dev makes localhost reachable from the agent process. Tests must verify rejection (D-18). |
| **DNS rebinding** (TTL=0 flip between public and private IP) | Tampering | Per-call DNS resolution (httpx default); per-redirect-hop IP re-validation. Pitfall 1. |
| **Multi-record DNS rebinding** (A record contains both public and private IPs) | Tampering | `safe_fetch._resolve_and_check` loops through ALL `getaddrinfo` records; rejects if ANY is blocked. |
| **Redirect-chain SSRF** (200 → 302 → `http://169.254...`) | Information Disclosure | `follow_redirects=False` + manual loop with IP check on each hop (≤ 3 hops). D-18 test. |
| **Content-length bomb** (5 GB recipe HTML) | Denial of Service | Pre-check `Content-Length` header > 2 × max_bytes → reject; post-read body cap → reject. |
| **gzip bomb** (compressed-to-decompressed > 20:1) | Denial of Service | Decompression cap with ratio check (caveat: httpx auto-decompresses; Pitfall 7). Post-decompression size cap is the actual structural defense. |
| **Slow-read attack** (server trickles bytes; holds the worker) | Denial of Service | `httpx.Timeout(read=15s)` caps it; concurrency=1 means a slow URL would freeze the queue — 15s freeze is acceptable; longer is not. |
| **Content-type spoofing** (`application/octet-stream` declared as HTML in body) | Tampering | `safe_fetch` content-type sniff REQUIRES the response Content-Type header to be `text/html` or `application/xhtml+xml`. |
| **Prompt injection via URL content** (LLM extracts data from a recipe page that includes "SYSTEM: ignore safety rules") | Tampering | `gather-from-url` agent has `response_format=RecipeData` — output is structurally constrained to RecipeData fields. Worst case: a fabricated recipe gets saved; the LLM has no tool surface to do anything else (no `respond`/`start-workflow`/file IO from `gather-from-url`). |
| **URL in logs leaks PII / session** (URL has `?session=...&token=...`) | Information Disclosure | Log the URL's `httpx.URL` parsed form WITHOUT query string when logging at INFO; full URL only at DEBUG. Apply to `safe_fetch` logger.error paths. |
| **EXIF GPS in recipe-page image** (not in scope for Phase 23, but flagged for Phase 24) | Information Disclosure | Out of Phase 23 scope; document for Phase 24 `recipe-image`. |

**No raw `httpx.get(url)` outside `safe_fetch`** — recommend a grep gate in CI similar
to Phase 21 D-12's AGENT_REGISTRY ↔ overrides sync test: assert that
`grep -rn "httpx\\.get\\|httpx\\.Client.*follow_redirects=True"` finds zero hits outside
`src/robotina/url/safe_fetch.py` and `tests/`. Defer to Plan 23-01 (planner's call).

### Pre-deploy Security Checklist (Plan 23-07 verification)

- [ ] `tests/url/test_safe_fetch.py` GREEN — all 13+ defense tests pass.
- [ ] No raw `httpx.get` / `httpx.Client(..., follow_redirects=True)` outside `safe_fetch.py` (grep gate).
- [ ] `URL_INGESTION_ALLOW_HTTP` is NOT set in production env (verify in deploy runbook).
- [ ] `FetchAndScrapeTool` does NOT catch `SafeFetchError` (verified by test — error propagates).
- [ ] `gather-from-url` agent has `response_format=RecipeData` set in AGENT_REGISTRY (verified by test).

## Sources

### Primary (HIGH confidence)
- `[VERIFIED: codebase]` `src/robotina/agent/tools/start_workflow.py:33-156` — current `StartWorkflowArgs` + tool surface, constructor-injected `invocation_id`/`conversation_id`/`household_id`.
- `[VERIFIED: codebase]` `src/robotina/agent/workflows.py:67-133` — current `WORKFLOW_REGISTRY` with single `add-recipe` entry.
- `[VERIFIED: codebase]` `src/robotina/queue/task_types.py:105-135` — `RecipeData` with `source_url` field; `:175-183` `AddRecipeQueryInput`; `:355-403` `WorkflowOutcomeSummary` + `WakeInvocationInput.to_user_message()` with current dual `recipe_query`/(`recipe_url` fallback to be added) read.
- `[VERIFIED: codebase]` `src/robotina/queue/workflow_runner.py:150-280` — `_check_and_dispatch_wake` Phase 22 D-06/D-08 implementation (line 253: existing `recipe_query` populate; Phase 23 D-08 extends).
- `[VERIFIED: codebase]` `src/robotina/agent/agents.py:70-87` — `handle-incoming-message` registry entry (V006.md path; Phase 23 bumps to V007).
- `[VERIFIED: codebase]` `src/robotina/agent/prompts/robotina/V006.md` — current Robotina prompt (V006 line 118 currently deflects URLs as "no soportado"; V007 replaces).
- `[VERIFIED: codebase]` `pyproject.toml:33` — `recipe-scrapers>=15.11.0` already declared; `:28` `httpx>=0.27`.
- `[VERIFIED: codebase]` `overrides/{anthropic,openai,staging.ollama}.json` — current keys; Phase 23 adds `gather-from-url` block to all three atomically.
- `[VERIFIED: codebase]` `experiments/recipe_research.py`, `experiments/robotina/multi_recipe_eval.py` — eval harness patterns to mirror.
- `[CITED: .planning/research/PITFALLS.md Pitfall 6]` — SSRF defense matrix verbatim; the six defenses + gzip bomb + slow-read in `safe_fetch`.
- `[CITED: .planning/research/PITFALLS.md Pitfall 7]` — `recipe-scrapers` silent partial; per-field try/except + Pydantic validation + LLM fallback ladder.
- `[CITED: .planning/research/STACK.md]` — `recipe-scrapers>=15.11.0`, `httpx>=0.27`; STACK.md:175 confirms `recipe_scrapers.scrape_html(html, url, wild_mode=True)`.
- `[CITED: .planning/phases/22-multi-recipe-per-message-topic-1/22-RESEARCH.md]` — Phase 22 architecture context inherited (multi-call `StartWorkflowTool`, wake helper, eval harness pattern).
- `[CITED: .planning/phases/21-tool-surface-flip-remove-acknowledge-notify/21-CONTEXT.md]` — Phase 21 D-03/D-12 (multi-call surface, CI guard for AGENT_REGISTRY ↔ overrides).
- `[CITED: .planning/phases/20-wake-rule-outcome-plumbing/20-CONTEXT.md]` — D-04 single `_check_and_dispatch_wake` helper.
- `[CITED: .planning/phases/18-robotinainvocation-entity/18-CONTEXT.md]` — D-13 constructor-injected `invocation_id` on tools.
- `[CITED: .planning/REQUIREMENTS.md:44-49]` — URL-01..06 verbatim; `:83` EXP-02 verbatim.
- `[CITED: CLAUDE.md]` — Tech stack pins, LangWatch instrumentation requirement, single-sequential-worker constraint.

### Secondary (MEDIUM confidence)
- `[CITED: https://github.com/hhursev/recipe-scrapers]` README — `scrape_html` signature, available methods (`title`, `instructions`, `ingredients`, `total_time`, `yields`, `image`, etc.), `wild_mode` rationale; WebFetch 2026-05-20.
- `[CITED: https://docs.recipe-scrapers.com/]` — entry-point only; per-method exception names referenced.
- `[CITED: https://trafilatura.readthedocs.io/en/latest/usage-python.html]` — `extract(html, ...)` signature; WebSearch 2026-05-20 confirmed `trafilatura 2.0.0` released, `extract(downloaded)` minimal example; `include_comments`, `include_tables`, `output_format`, `no_fallback` flags. Phase 23 pins `>=1.6` per CONTEXT.md.
- `[CITED: https://www.sourcery.ai/vulnerabilities/python-django-security-injection-ssrf-ssrf-injection-requests]` and `[CITED: https://github.com/Kozea/WeasyPrint/security/advisories/GHSA-983w-rhvv-gwmv]` — confirm redirect re-validation is the most-missed SSRF defense; Pattern 1 explicitly handles.
- `[CITED: https://chs.us/2025/11/writing-secure-python-applications-preventing-ssrf-sql-injection-and-xss/]` — `ipaddress` + `socket` stdlib pattern for IP allowlist post-DNS resolution.

### Tertiary (LOW confidence)
- `[ASSUMED]` `httpx.Client` re-resolves DNS per call by default (Pitfall 1 mitigation). Likely true but planner should verify via httpx changelog/docs at plan time.
- `[ASSUMED]` `recipe_scrapers._exceptions.RecipeScrapersExceptions` is the canonical base class name in 15.11.0. Pattern 2 falls back to `except Exception:` if the import path differs — safe regardless.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — `recipe-scrapers` already declared; `httpx` already used; `trafilatura` is the recommended fallback per PITFALLS Pitfall 7. Versions verified against PyPI search results + STACK.md.
- Architecture: HIGH — all upstream Phase 17/18/20/21/22 contracts landed and verified in code. The new surface (workflow rename + new variant + new tool + new agent) is mechanical addition on top.
- Pitfalls: HIGH — six PITFALLS pitfalls (6, 7) plus four phase-specific pitfalls all identified and mapped to mitigations.
- SSRF defenses: HIGH — PITFALLS.md spec is concrete; Pattern 1 implements every defense; D-18 test suite is the verification gate.
- Spanish blog hit-rate: MEDIUM — no published `recipe-scrapers wild_mode=True` benchmark for Spanish blogs; Phase 23's eval IS the empirical validation. The merge-gate threshold (85%) is conservative.
- Agent prompt quality (V007 URL detection + V001 gather-from-url extraction): MEDIUM — LLM-judgment is inherently fuzzy; eval set is the empirical validation.

**Research date:** 2026-05-20
**Valid until:** 2026-06-19 (30 days — stable phase; `recipe-scrapers` + `trafilatura` are mature; SSRF defense matrix is stable since OWASP cheat sheet finalization)
