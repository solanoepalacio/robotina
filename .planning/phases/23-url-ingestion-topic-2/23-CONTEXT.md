# Phase 23: URL ingestion (Topic 2) — Context

**Gathered:** 2026-05-20
**Status:** Ready for planning
**Mode:** `--auto` (Auto Mode active — every D-NN below is Claude's call with rationale; user can redirect any decision before `/gsd:plan-phase 23` runs.)

<domain>
## Phase Boundary

Add URL-pointed recipe ingestion alongside the existing free-text recipe path.
Concretely:

1. **`safe_fetch` helper** (FIRST commit, per ROADMAP) — single Python module
   under `src/robotina/url/safe_fetch.py` with six SSRF/abuse defenses
   (URL-01). Reused later by Phase 24's `recipe-image` step.
2. **`add-recipe-from-url` workflow variant** — register as a peer of
   the renamed `add-recipe-from-query` in `WORKFLOW_REGISTRY`. Steps 2-N
   (instructions/ingredients/metadata/load/finalize-outcome) are identical;
   inline-duplicate now, extract a helper in Phase 24 when `recipe-image`
   inserts a step in both variants (per `feedback_avoid_premature_abstraction`).
3. **`gather-from-url` task type + agent** — first step of the URL variant.
   LLM agent with `response_format=RecipeData` (Phase 11 contract preserved)
   and one new tool `FetchAndScrapeTool(url) -> dict` that deterministically
   runs `safe_fetch` + `recipe-scrapers` (`wild_mode=True`) + per-field
   try/except + Pydantic partial-validation. Agent's prompt handles the
   "pass scraped data through" vs "LLM-extract from cleaned HTML" branch
   internally (see D-02). New prompt `src/robotina/agent/prompts/gather-from-url/V001.md`.
4. **`AddRecipeUrlInput`** Pydantic model `{url: str}` (mirrors the
   `AddRecipeQueryInput {value: str}` shape from Phase 21).
5. **`StartWorkflowTool` schema extension** — extend `workflow_type` Literal to
   `["add-recipe-from-query", "add-recipe-from-url"]` (rename existing
   `"add-recipe"` → `"add-recipe-from-query"` in the same commit per D-01);
   `input: AddRecipeQueryInput | AddRecipeUrlInput`; add
   `@model_validator(mode='after')` enforcing the `workflow_type ↔ input`
   shape pairing.
6. **Robotina V007 prompt** — V006 + URL detection rule (D-03) + worked
   examples for URL, mixed text+URL, and multiple URLs. `agents.py` bump
   V006 → V007. V006 retained for rollback.
7. **`experiments/gather_from_url.py`** (EXP-02) — automated eval harness
   that runs each URL through the new agent, scores per-field coverage,
   emits per-backend markdown report. `pyproject.toml` `[project.scripts]`
   adds `experiments.gather_from_url`.
8. **`23-EVAL-SET.md`** — 20 Spanish recipe blog URLs + 1 known-difficult
   site, with per-URL expected populated fields. **`23-EVAL-RESULTS-<backend>.md`**
   per-backend results (operator-run). **`23-SMOKE.md`** final verdict.
9. **REQUIREMENTS.md ticks** for URL-01..06, EXP-02 in the final smoke commit.
10. **Wake-helper polish (lightweight carry-over from Phase 22 D-08)** —
    `_check_and_dispatch_wake` reads `shared_context.get("recipe_query")`
    OR `shared_context.get("recipe_url")` to populate
    `WorkflowOutcomeSummary.recipe_query` (the user-facing display label).
    See D-08.

**Out of scope (deferred):**

- `recipe-image` step (IMG-*) — Phase 24. The 6-step add-recipe-from-url
  variant lands without recipe-image; Phase 24 inserts it before `load`
  in BOTH variants and extracts the shared-tail helper at that time.
- Vision-LLM "is this the right page?" validation (Pitfall 8) — Phase 24
  follow-up; Phase 23 trusts the scraper + LLM fallback.
- Spike-driven `recipe-scrapers` `wild_mode` hit-rate validation (research
  gap flagged in SUMMARY.md) — folded INTO Phase 23's eval set. The
  20-URL eval IS the empirical validation.
- Household-manager API recipe-rehost decision (research gap) — out of
  scope for Phase 23. `RecipeData.source_url` already carries the original
  URL; Phase 24 will decide image rehost vs pin.
- A `hint` field on `AddRecipeUrlInput` (e.g. user-provided context
  about the URL) — kept minimal in v1.1; revisit if real users surface
  the need.
- CDN/HTML caching — deferred per FEATURES.md.
- Cross-source batches inside a single message ("agregá lentejas y
  https://x") — V007 SUPPORTS this (one start-workflow per item, each
  routed to its variant) but does not collapse into a single "mixed
  batch" abstraction. Phase 22's multi-recipe semantics carry over.
- Renaming `WorkflowOutcomeSummary.recipe_query` to `recipe_source`
  (universal label) — naming churn deferred (per
  `feedback_avoid_premature_abstraction`; document the field's dual
  semantic in code comments instead).
- LLM-judge or vision-model field-correctness scoring on the eval set —
  v1.1 ships with field-presence-based scoring; LLM-judge is v1.2.

</domain>

<decisions>
## Implementation Decisions

> **Auto-mode note:** Every D-NN below is Claude's call under the no-stopping
> system reminder. The user can redirect any decision before `/gsd:plan-phase 23` runs.

### Workflow variant shape (URL-03)

- **D-01: Per-source workflow types — rename `add-recipe` → `add-recipe-from-query`;
  add `add-recipe-from-url` as a peer entry in `WORKFLOW_REGISTRY`.**
  Both variants are equally first-class. `StartWorkflowTool.workflow_type` becomes
  `Literal["add-recipe-from-query", "add-recipe-from-url"]`. The input field is
  a non-discriminated union `AddRecipeQueryInput | AddRecipeUrlInput` — pydantic
  resolves it by shape (one field `value: str`, the other `url: str`; mutually
  exclusive, no need for an explicit `kind` discriminator). A
  `@model_validator(mode='after')` on `StartWorkflowArgs` enforces the pairing
  (workflow_type=add-recipe-from-query ↔ input=AddRecipeQueryInput, and likewise
  for url) to catch LLM-emitted mismatches at validation time.
  - **Why not (A') keep `add-recipe` for query + add URL peer:** asymmetric
    naming creates a "the default one is implicitly query, except when it
    isn't" cognitive trap in V007 and in tests. Symmetry is worth the
    one-commit rename churn.
  - **Why not (B) source-discriminator on a single `add-recipe`:** would
    require the first step to be a runtime-branched dispatcher; conflicts
    with the project's "WorkflowDefinition.steps is a static list" mental
    model (ARCHITECTURE.md §2.5 explicitly recommends per-source variants
    for V1).
  - **Rename scope (planner picks final wave):** `WORKFLOW_REGISTRY` key +
    `StartWorkflowTool.args_schema.workflow_type` Literal + every test that
    references `"add-recipe"` as a workflow_type string + V006 prompt
    worked examples (re-written as V007) + dashboard label map (NO impact
    — labels are per-task-type, not per-workflow-type; verified Phase 21 D-11).
  - **No transitional alias.** Hard rename in one commit. Tests + smoke
    catch any miss; no surface area is large enough to warrant a
    deprecation window in a private codebase pre-launch.

- **D-02: `AddRecipeUrlInput { url: str }` only — no `hint` field.**
  Mirrors `AddRecipeQueryInput {value: str}` shape exactly. If user
  hint context becomes load-bearing, revisit; meanwhile V007 lets
  Robotina capture intent in the pre-batch `respond()` ack ("voy con la
  receta de canelones que mandaste"), not in the tool args.
  `model_config = ConfigDict(extra="forbid")`.

### gather-from-url + LLM fallback shape (URL-02, URL-04)

- **D-03: `gather-from-url` is an LLM agent with `response_format=RecipeData`
  and one new deterministic tool `FetchAndScrapeTool`.**
  - **Tool surface** (`src/robotina/agent/tools/fetch_and_scrape.py`):
    ```python
    class FetchAndScrapeResult(BaseModel):
        scraped_recipe: dict | None   # populated only when scraper produced a Pydantic-valid RecipeData with ≥2 ingredients
        html_text: str | None         # populated when scraped_recipe is None (trafilatura-cleaned plain text)
        source_url: str               # the final URL after redirects (returned by safe_fetch)
    class FetchAndScrapeTool(BaseTool):
        name: str = "fetch-and-scrape"
        args_schema = ...  # {url: str}
        # constructor-injected: none for now
        def _run(self, url: str) -> str:  # returns FetchAndScrapeResult JSON
            ...
    ```
    Internals: `safe_fetch(url)` → on success: `recipe_scrapers.scrape_html(html, wild_mode=True, org_url=url)` → per-field try/except into a partial dict → `RecipeData.model_validate(partial)` → if validation passes AND `len(ingredients) >= 2` AND `len(steps) >= 1`: return with `scraped_recipe=<dump>`; ELSE clean html with `trafilatura.extract(html, include_comments=False, include_tables=True, output_format="txt")` and return with `html_text=<cleaned>, scraped_recipe=None`.
  - **safe_fetch failures re-raise** — `FetchAndScrapeTool._run` does NOT
    catch `SafeFetchError`. The exception propagates up to LangChain's
    tool runner, which converts it to a ToolMessage(status='error'). The
    agent has no recovery path with `response_format=RecipeData` mandatory
    → response_format extraction fails → `_extract_task_output` (Phase 11)
    raises → step marked FAILED. `WorkflowRunStep.failure_reason` carries
    the exception text; the wake reply (Phase 22 D-08) surfaces the URL
    in the failure line: "✗ https://… falló: <reason>".
  - **Why one agent, not two task types or one deterministic-only step:**
    keeps LangWatch instrumentation, response_format, and AGENT_REGISTRY
    patterns uniform. The agent's "decision" is trivial (`if scraped:
    pass-through else extract`) but the LLM-extract path needs response_format
    enforcement anyway; using an agent unifies them.
  - **Agent prompt `gather-from-url/V001.md`** (the planner writes the
    final text; this is the rule shape):
    - "Call `fetch-and-scrape(url)` exactly once with the URL provided in
      `input.url`."
    - "If the tool returns `scraped_recipe` (non-null), output it via
      `response_format` verbatim. Add `source_url` from the tool result
      if absent."
    - "If the tool returns `html_text` (non-null) and `scraped_recipe`
      is null, extract a complete `RecipeData` from `html_text`. Set
      `source_url` from the tool result. Required fields: `name`,
      `ingredients` (≥ 2), `steps` (≥ 1). All units MUST be in the
      project canonical set (see existing recipe-research-* prompts for
      reference)."
    - "Never fabricate data. If `html_text` clearly is not a recipe
      page, you may emit a minimal RecipeData with just `name` (extracted
      from page title) — downstream validation will reject it and the
      workflow will fail with a clear reason."
    - English prompt body; emitted RecipeData fields in Spanish (recipe
      content language matches source; metadata field names per existing
      schema).

- **D-04: HTML preprocessing = `trafilatura>=1.6` (new dependency).**
  - **Why trafilatura over readability-lxml / BeautifulSoup:**
    purpose-built for plain-text extraction from HTML; strips
    nav/footer/scripts/comments; single function call
    (`trafilatura.extract(html, ...)`); maintained; recommended by
    Pitfall 7 verbatim ("via `trafilatura` or `readability-lxml`"). Pin
    `trafilatura>=1.6` in `pyproject.toml`.
  - **Why not raw HTML for the LLM fallback:** token cost. A typical
    recipe page is 50-200 KB of HTML; trafilatura output is 1-5 KB of
    plain text — 10-50× cheaper. Also reduces the LLM's tendency to
    extract data from page-chrome (nav links, comments) instead of the
    recipe body.

### Robotina V007 URL detection (URL-05)

- **D-05: URL detection is LLM-judgment, not regex.** V007 teaches:
  "If a token in the user message looks like a web URL (starts with
  `http://`, `https://`, or contains a clear `domain.tld/path` pattern),
  route THAT token through `start-workflow(workflow_type='add-recipe-from-url',
  input={url: <token>})`. Strip surrounding punctuation; preserve query
  strings, paths, and fragments. If the URL pattern is ambiguous (e.g.
  bare `recetas.com` without scheme or path), ask the user via `respond()`
  with a Spanish clarifying question; do not start a workflow on
  ambiguous bare hostnames."
  - **Why LLM-judgment:** the LLM already does URL detection well, and a
    regex enshrines fragility (Punycode IDNs, encoded paths, percent-
    encoded URIs, regional TLDs like `.com.ar`). The eval set's URL
    detection rows validate this empirically.

- **D-06: One `start-workflow` per URL.** Multi-URL messages
  ("agregá esta receta y esta otra: https://a y https://b") emit
  TWO `start-workflow(add-recipe-from-url)` calls. Phase 22's
  multi-recipe carry-over: the same per-recipe-per-call pattern
  applies to URLs. Soft cap of 5 (Phase 22 D-01) applies across
  the combined query + URL count.

- **D-07: Mixed text + URL → one workflow per item, each routed to its
  variant.** "agregá lentejas y https://x" emits
  `start-workflow(add-recipe-from-query, {value: "lentejas"})` +
  `start-workflow(add-recipe-from-url, {url: "https://x"})`. V007 has
  an explicit worked example. No "mixed batch" abstraction; each item is
  independent.

- **D-08: Wake-reply unification — wake helper reads BOTH
  `recipe_query` and `recipe_url` from `shared_context`.**
  `_check_and_dispatch_wake` populates
  `WorkflowOutcomeSummary.recipe_query` (Phase 22 D-08 field name —
  kept verbatim, despite the naming friction) via:
  `r.shared_context.get("recipe_query") or r.shared_context.get("recipe_url")`.
  No schema change to `WorkflowOutcomeSummary`. V007's wake-context
  worked examples include URL-based failure lines.
  - **Why not rename to `recipe_source`:** premature renaming churn
    (`feedback_avoid_premature_abstraction`). Document the dual
    semantic in a code comment on the field.

### Eval set + harness (URL-06, EXP-02)

- **D-09: One concrete eval harness `experiments/gather_from_url.py`.**
  Same pattern as Phase 22's `experiments/robotina/multi_recipe_eval.py`:
  reads `23-EVAL-SET.md` (or sibling YAML), iterates URLs through the
  `gather-from-url` agent, captures the emitted RecipeData, scores
  per-field presence, emits a per-backend markdown report. Single file,
  no framework (`feedback_avoid_premature_abstraction`).
  - **`pyproject.toml` `[project.scripts]`**: add
    `"experiments.gather_from_url" = "experiments.gather_from_url:main"`.
  - **LangWatch instrumentation active** per CLAUDE.md (experiment
    metadata tags: `phase=23`, `url=<the url>`, `backend=<backend>`).

- **D-10: Eval set composition — 20 Spanish recipe blog URLs + 1
  known-difficult site (21 total).**
  - Coverage classes (planner picks exact URLs to satisfy):
    1. **Well-supported by `recipe-scrapers`** (5+ URLs) — e.g.
       Paulina Cocina, AllRecipes-es, Cocinatis, Recetas Gratis,
       Directo al Paladar. JSON-LD or microdata present.
    2. **`wild_mode=True` schema.org Recipe** (5+ URLs) — long-tail
       Spanish blogs with schema.org/Recipe JSON-LD but no scraper
       site adapter.
    3. **LLM-fallback territory** (5+ URLs) — Spanish blogs with
       inconsistent or absent schema.org markup; recipe-scrapers
       returns insufficient data; LLM has to extract from cleaned
       HTML.
    4. **Locale-specific units** (3+ URLs) — Argentine/Uruguayan/
       Mexican blogs with regional measure ("½ taza", "1 cda",
       "100 grs").
    5. **Known-difficult site** (1 URL) — a deliberately challenging
       site (e.g. recipe nested in a multi-paragraph blog post; or
       a site that returns recipe content only after JS execution —
       which our sync fetcher can't handle; expected outcome: workflow
       FAILED with a clear "URL no extraíble" reason).
    6. **Sanity** (1+ URL) — non-recipe URL (a news article, a Wikipedia
       page) — expected: gather-from-url returns minimal RecipeData;
       downstream Pydantic validation rejects; workflow FAILED.

- **D-11: Field-level success metric (URL-06).** Per-URL scoring
  evaluates presence of 8 expected fields per `23-EVAL-SET.md`:
  `name`, `description`, `ingredients (≥3 items)`, `steps (≥2 items)`,
  `servings_qty`, `prep_time | cook_time | total_time` (any one),
  `source_url`, `gathered_sources` (legacy field — should be present
  but may be optional). Each URL has expected-populated fields marked
  in the set; the harness counts populated-vs-expected. Per-URL pass
  = "≥ 6/8 expected-populated fields are populated AND non-empty".
  Aggregate pass = "≥ 17/21 URLs pass" (≈ 85% URL-level success
  satisfies URL-06's "≥ 85% field-level success at v1.1 ship";
  the metric is operationalized at the URL level for clarity).
  - **Why URL-level scoring as the merge gate (vs strict
    field-aggregate):** noisier signal from a single bad URL
    doesn't tank the aggregate by 5%; reviewers see per-URL pass/fail
    rows; matches the "no automated CI gate" pattern of Phase 21/22.

- **D-12: Pass thresholds + backends.**
  - **OpenAI staging — merge gate:** ≥ 85% URL-level pass per D-11.
  - **Ollama dev — informational only.** Documented in
    `23-EVAL-RESULTS-ollama.md`; not blocking.
  - **Anthropic — optional.** Operator runs if desired.

- **D-13: Results file structure.** Three files per phase:
  - `23-EVAL-SET.md` — canonical URLs + per-URL expected-populated
    fields. Committed in the eval-harness plan.
  - `23-EVAL-RESULTS-<backend>.md` — operator's per-backend run output
    (table with URL, expected fields, observed fields, pass/fail,
    LangWatch trace link, notes). Committed by operator post-run.
  - `23-SMOKE.md` — final verdict. References the per-backend
    results; ends with a `verdict: pass/fail/needs-revision` line.
    Mirrors Phase 21 D-13 / Phase 22 D-05.

### `safe_fetch` design (URL-01, FIRST commit per ROADMAP)

- **D-14: Location `src/robotina/url/safe_fetch.py`.** New top-level
  package `src/robotina/url/` (sibling to `src/robotina/queue/`,
  `src/robotina/agent/`, etc.) for URL-related utilities. Phase 24's
  `recipe-image` step imports from the same module.
  - **Why a top-level package, not inside `agent/tools/`:** `safe_fetch`
    is a utility used by tools (FetchAndScrapeTool, Phase 24
    recipe-image tool); it's not itself a tool. Putting it under
    `agent/tools/` mixes layers. The `url/` package is the natural
    home — single responsibility "user-supplied URL handling".

- **D-15: Sync, not async.** RQ workers are sync. Use `httpx.Client`
  in sync mode. Aligns with existing project patterns; avoids the
  sync/async boundary that Pitfall 13 calls out.

- **D-16: Signature shape.**
  ```python
  class SafeFetchResult(BaseModel):
      final_url: str            # after manual redirect re-validation
      content_bytes: bytes
      content_type: str
      status_code: int

  class SafeFetchError(Exception):
      """Raised by safe_fetch on any defense violation. Message contains the reason."""

  def safe_fetch(
      url: str,
      *,
      expected_content_type: str = "text/html",   # caller asserts; for images "image/*"
      max_bytes: int = 5_000_000,                 # URL-01 default cap
      timeout_s: float = 15.0,
      allow_http: bool = False,
  ) -> SafeFetchResult:
      ...
  ```
  - **Six defenses per URL-01:** scheme allowlist (https-only unless
    `allow_http=True`), post-DNS private/loopback/link-local IP block
    (RFC1918, 127/8, ::1, 169.254/16, fe80::/10, 0.0.0.0, multicast)
    via stdlib `ipaddress` + `socket.getaddrinfo`, manual redirect
    re-validation (`follow_redirects=False`, max 3 hops, IP-check each
    Location), configurable timeout (`httpx.Timeout(connect=5,
    read=timeout_s, write=5, pool=5)`), content-length cap
    (pre-check `Content-Length` header reject > 2 × max_bytes; stream
    with `iter_bytes()` and abort if accumulated > max_bytes),
    content-type sniff (the response Content-Type starts-with
    `expected_content_type`; for "text/html", `text/html` or
    `application/xhtml+xml` both accepted; for "image/*", any
    `image/...`).
  - **gzip-bomb defense (Pitfall 6):** decompress incrementally with
    size cap; reject if expanded ratio > 20:1.

- **D-17: `allow_http` env-gated.** Reads `URL_INGESTION_ALLOW_HTTP`
  env var (truthy values "true"/"1"/"yes"); defaults to False
  (https-only). Use the env var in `experiments/gather_from_url.py`
  when targeting test URLs that lack TLS. Add the var to `.env.example`
  with a comment "Dev/testing only — never set in production." Per
  memory `feedback_env_example`.

### Test strategy (Claude's Discretion)

- **D-18: `safe_fetch` unit tests are the load-bearing safety net.**
  `tests/url/test_safe_fetch.py` — one test per defense (httpbin /
  inline `respx` mocks):
  - Reject `http://` (default), accept with `allow_http=True`.
  - Reject `ftp://`, `file://`, `javascript:`, `data:`.
  - Reject `http://169.254.169.254/` (AWS metadata), `http://localhost/`,
    `http://127.0.0.1/`, `http://[::1]/`, `http://10.0.0.1/`,
    `http://172.16.0.1/`, `http://192.168.0.1/`, `http://0.0.0.0/`.
  - Reject IPv6 private addresses (`fe80::1`), IPv4-mapped IPv6
    (`::ffff:127.0.0.1`).
  - Reject redirect-chain to private IP (200 → 302 → 169.254).
  - Reject redirect chain > 3 hops.
  - Reject Content-Length > 2×max_bytes.
  - Reject streaming body > max_bytes (mid-response abort).
  - Reject Content-Type mismatch (e.g. `application/octet-stream` for
    `expected_content_type="text/html"`).
  - Reject gzip-bomb (ratio > 20:1).
  - Accept valid `https://example.com/recipe` with `text/html` body.
  - Re-resolve DNS per call (no rebinding window) — verify by checking
    the call to `httpx.Client` doesn't pin an IP.

- **D-19: `FetchAndScrapeTool` integration tests** with
  `recipe-scrapers` fixtures:
  - Well-supported site → `scraped_recipe` populated, `html_text` None.
  - Site with `wild_mode` JSON-LD → `scraped_recipe` populated.
  - Insufficient scrape (e.g. < 2 ingredients) → `scraped_recipe` None,
    `html_text` populated (trafilatura output).
  - Total scraper failure (no JSON-LD, no microdata) → same as insufficient.
  - `safe_fetch` raises → tool re-raises.

- **D-20: `gather-from-url` agent integration test** with mocked LLM:
  - Tool returns `scraped_recipe` → agent passes through to
    response_format.
  - Tool returns `html_text` only → agent's LLM extracts RecipeData;
    response_format succeeds.
  - Tool raises → agent fails; step marked FAILED.

- **D-21: Workflow registry tests:**
  - `WORKFLOW_REGISTRY['add-recipe-from-query'].steps` has 6 entries
    in the post-Phase-22 order (gather, instructions, ingredients,
    metadata, load, finalize-outcome).
  - `WORKFLOW_REGISTRY['add-recipe-from-url'].steps` has 6 entries:
    gather-from-url, instructions, ingredients, metadata, load,
    finalize-outcome.
  - `WORKFLOW_REGISTRY` no longer has a key `"add-recipe"`.

- **D-22: `StartWorkflowTool` schema tests:**
  - `workflow_type="add-recipe-from-query"` + `input={value: "x"}` passes.
  - `workflow_type="add-recipe-from-url"` + `input={url: "https://x"}` passes.
  - `workflow_type="add-recipe-from-query"` + `input={url: "x"}`
    fails the model_validator (mismatch).
  - `workflow_type="add-recipe-from-url"` + `input={value: "x"}`
    fails the model_validator.
  - `workflow_type="add-recipe"` (old name) fails (Literal mismatch).

- **D-23: AGENT_REGISTRY + overrides sync** — the new `gather-from-url`
  agent gets entries in `AGENT_REGISTRY` AND every `overrides/*.json`
  file in the SAME commit (per memory `feedback_overrides_in_sync` and
  Phase 21 D-12 CI guard). Same model_config keys as `recipe-research-gather`
  (initial default; tunable per backend).

- **D-24: Manual eval is the load-bearing user-facing gate** — D-09..D-13
  above. Operator-driven. Phase 23 verification routes as `human_needed`
  until the operator commits `23-SMOKE.md` with `verdict: pass`. Same
  pattern as Phase 21 D-24 / Phase 22 D-15.

- **D-25: V006 retained for rollback.** V007 forks V006 verbatim and
  adds URL detection sections. Project convention (V001..V006 all in
  `src/robotina/agent/prompts/robotina/`).

### Claude's Discretion

- **Tool naming:** `FetchAndScrapeTool` in `src/robotina/agent/tools/fetch_and_scrape.py`.
  Co-located with the rest of `agent/tools/`.
- **Pydantic discriminated union vs plain union for `input`:** plain
  union (`AddRecipeQueryInput | AddRecipeUrlInput`) is sufficient —
  the field shapes `{value: str}` vs `{url: str}` are mutually
  exclusive at the JSON level, so pydantic resolves them without a
  `kind` discriminator. The `@model_validator(mode='after')` on the
  OUTER `StartWorkflowArgs` enforces the workflow_type ↔ input
  pairing — that's the actual safety net.
- **Renaming `add-recipe` → `add-recipe-from-query`:** done in a
  SINGLE commit per `feedback_overrides_in_sync` (atomic registry +
  Literal + V007 prompt + tests + dashboard label map if needed).
- **Dashboard task-type labels:** the new `gather-from-url` task type
  gets a Spanish label in `src/robotina/dashboard/templates/_macros.html`:
  `"gather-from-url": "Búsqueda por URL"`. Phase 21 D-11 pattern.
  No workflow_type label changes (the dashboard's label map is
  per-task-type, not per-workflow-type).
- **EXP-01 carry-over (Phase 24 boundary):** Phase 23 leaves Phase 23's
  experiments runnable on existing task input schemas. New
  experiment `gather_from_url` is additive. The Phase 24 source-discriminator
  default-preserves-happy-path requirement (EXP-01) is satisfied
  because Phase 23 does NOT touch the `recipe-research-*` agents' input
  schemas — those stay 1:1 with their Phase 11 contracts.
- **Order of plan execution (planner final):**
  - **Plan 23-01 (FIRST commit per ROADMAP):** `safe_fetch` module +
    comprehensive test suite (D-18).
  - **Plan 23-02:** `AddRecipeUrlInput` + `StartWorkflowArgs` rename +
    union + model_validator + workflow_type rename in
    `WORKFLOW_REGISTRY` + new `add-recipe-from-url` entry (steps inline-
    duplicated; helper deferred to Phase 24) + dashboard label entry.
  - **Plan 23-03:** `FetchAndScrapeTool` + `recipe-scrapers` integration +
    trafilatura preprocess + per-field try/except + tests (D-19).
  - **Plan 23-04:** `gather-from-url` agent + prompt V001 +
    AGENT_REGISTRY entry + every `overrides/*.json` (D-23) + tests (D-20).
  - **Plan 23-05:** Robotina V007 prompt + `agents.py` V006 → V007 bump
    + V007 worked examples (URL, mixed, multi-URL) + tests.
  - **Plan 23-06:** `experiments/gather_from_url.py` + `23-EVAL-SET.md`
    (21 URLs) + `pyproject.toml` `[project.scripts]` entry + harness
    self-test (runs against a single fixture URL in CI to assert the
    script doesn't crash; not the eval merge gate).
  - **Plan 23-07 (autonomous=false):** Operator runs eval against
    OpenAI staging (merge gate) + Ollama dev (informational); commits
    `23-EVAL-RESULTS-openai.md` + `23-EVAL-RESULTS-ollama.md` +
    `23-SMOKE.md` (verdict line); ticks REQUIREMENTS.md URL-01..06 +
    EXP-02.
- **New env var:** `URL_INGESTION_ALLOW_HTTP=false` default; added to
  `.env.example` per `feedback_env_example`.
- **New dependency:** `trafilatura>=1.6`; `recipe-scrapers>=15.11.0`
  (already in pyproject.toml per Phase 8 — verify and bump if needed).
- **No new Alembic revision.** Pure code + prompt + new dep.
- **No schema changes** to `WorkflowRun`, `WorkflowRunStep`,
  `RobotinaInvocation`. The `shared_context` dict gains a `recipe_url`
  key for URL workflows (data-only change, no DDL).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` §"Phase 23: URL ingestion (Topic 2)" — phase goal, 5 success criteria, dependency on Phase 22, the FIRST-commit `safe_fetch` requirement.
- `.planning/REQUIREMENTS.md` URL-01..06, EXP-02 — the seven requirements this phase delivers.

### Architecture and pitfalls (load-bearing context)
- `.planning/research/PITFALLS.md` Pitfall 6 "SSRF and resource-exhaustion via user-supplied URL" — `safe_fetch` is the FIRST commit in this phase; six defenses (D-16). Same helper reused by Phase 24.
- `.planning/research/PITFALLS.md` Pitfall 7 "`recipe-scrapers` failure modes — silent partial extraction" — per-field try/except + Pydantic validation + LLM fallback ladder (D-03); trafilatura preprocessing for the fallback (D-04).
- `.planning/research/PITFALLS.md` Pitfall 9 "Robotina context bloat" — RecipeData artifact passed between steps stays compact; `WorkflowRun.outcome` schema unchanged from Phase 22.
- `.planning/research/PITFALLS.md` Pitfall 12 "Multi-recipe LLM parsing" — V007 inherits Phase 22 V006's multi-recipe rules + adds URL detection (D-05..D-07).
- `.planning/research/PITFALLS.md` "Security Mistakes" table (rows 1-3) — `safe_fetch` mandates apply to every URL fetch; URL in tool args, never in prompt template directly; URL sanitization for logging.
- `.planning/research/ARCHITECTURE.md` §"Phase G — URL ingestion (Topic 2)" — Phase 23 IS Phase G with the ROADMAP's renumbering. Files touched, exit criteria, risk profile.
- `.planning/research/ARCHITECTURE.md` §2.5 "workflows.py diff" — per-source workflow variants recommendation (option A). Phase 23 implements verbatim with the V006 → V007 prompt evolution.
- `.planning/research/ARCHITECTURE.md` §2.6 "StartWorkflowTool refactor table" — discriminated union for input (D-01).
- `.planning/research/STACK.md` — `recipe-scrapers>=15.11.0`, `httpx>=0.27`, `trafilatura>=1.6` (new dep).
- `.planning/research/SUMMARY.md` §"Phase G" + §"Gaps to Address" — Spanish blog hit-rate is the largest unknown; Phase 23's eval (D-10) is the empirical validation.
- `.planning/research/FEATURES.md` §"URL-Pointed Recipe (Topic 2)" — must-have feature shape.

### Prior phase context (carries forward — do NOT re-decide)
- `.planning/phases/22-multi-recipe-per-message-topic-1/22-CONTEXT.md` — Phase 22 decisions. Phase 23 inherits:
  - D-01 over-cap "ask to split" — V007 carries this rule; soft cap of 5 applies across combined query + URL count.
  - D-08 `WorkflowOutcomeSummary.recipe_query` semantic — Phase 23 D-08 extends the wake helper to read `recipe_url` as a fallback for the same field.
  - D-09 wake-context reply rule (single `respond()` summarizing all outcomes) — V007 inherits with worked examples for URL outcomes.
  - D-10 NO `ask_user` tool — V007 uses `respond()` for URL ambiguity escalation (D-05 bare-hostname case).
- `.planning/phases/21-tool-surface-flip-remove-acknowledge-notify/21-CONTEXT.md` — Phase 21 decisions. Phase 23 inherits:
  - D-01..D-03 RespondTool / TerminateTool / StartWorkflowTool — KEEP. Phase 23 extends `StartWorkflowTool.args_schema.workflow_type` Literal and changes the input union.
  - D-11 dashboard label map — Phase 23 adds `"gather-from-url": "Búsqueda por URL"`.
  - D-12 AGENT_REGISTRY ↔ overrides CI guard — Phase 23 satisfies by adding the new agent in BOTH AGENT_REGISTRY AND every `overrides/*.json` in the same commit.
- `.planning/phases/20-wake-rule-outcome-plumbing/20-CONTEXT.md` — D-04 single `_check_and_dispatch_wake` helper. Phase 23 D-08 extends what it reads from shared_context.
- `.planning/phases/18-robotinainvocation-entity/18-CONTEXT.md` D-13 — constructor-injected `invocation_id` on StartWorkflowTool. KEEP unchanged.
- `.planning/phases/17-conversation-fk-closure/17-CONTEXT.md` D-03/D-04 — constructor-injected `conversation_id`. KEEP.
- `.planning/phases/16-fix-empty-string-household-id-propagation-through-gateway-an/` — `NonEmptyHouseholdId` on `StartWorkflowTool`. KEEP.
- `.planning/phases/11-structured-agent-output-via-response-format/11-CONTEXT.md` — `response_format=<Pydantic class>` on `create_agent`. `gather-from-url` agent uses this with `response_format=RecipeData` (D-03).
- `.planning/phases/12-middleware-based-agent-instrumentation/12-CONTEXT.md` — middleware-based LangWatch instrumentation. `gather-from-url` inherits automatically.

### Existing codebase contracts (current state)
- `src/robotina/queue/task_types.py:105` `RecipeData` — already has `source_url: str | None` field (Phase 15). `gather-from-url` agent populates it.
- `src/robotina/queue/task_types.py:175` `AddRecipeQueryInput` — schema reference for `AddRecipeUrlInput` (NEW, mirror shape: `{url: str}`).
- `src/robotina/queue/task_types.py:355` `WorkflowOutcomeSummary` — Phase 22 added `recipe_query: str | None`. Phase 23 D-08 extends the wake helper's read logic; no schema change.
- `src/robotina/agent/tools/start_workflow.py:33` `StartWorkflowArgs` — Phase 23 D-01 modifies: rename Literal, add union, add model_validator.
- `src/robotina/agent/tools/start_workflow.py:181` `shared_context` build — Phase 23 D-08 adds `recipe_url` key for URL variant.
- `src/robotina/agent/workflows.py:67` `WORKFLOW_REGISTRY` — Phase 23 renames `add-recipe` → `add-recipe-from-query` and adds peer `add-recipe-from-url` entry.
- `src/robotina/agent/agents.py` — `handle-incoming-message` loads V006 today (Phase 22 D-09 will have bumped it). Phase 23 bumps V006 → V007. New `gather-from-url` agent entry alongside `recipe-research-gather`.
- `src/robotina/agent/prompts/robotina/V006.md` — fork to V007.
- `src/robotina/agent/prompts/gather-from-url/V001.md` (NEW) — agent prompt for the new task type.
- `src/robotina/queue/jobs.py` — `run_task` dispatches to AGENT_REGISTRY entries; no new branch needed for `gather-from-url` (standard agent path).
- `src/robotina/queue/workflow_runner.py:195` `_check_and_dispatch_wake` — Phase 23 D-08 modifies the `shared_context.get` read to fall back to `recipe_url`.
- `src/robotina/dashboard/templates/_macros.html` — Phase 23 adds `"gather-from-url": "Búsqueda por URL"` to TASK_TYPE_LABELS.
- `overrides/anthropic.json`, `overrides/openai.json`, `overrides/staging.ollama.json` — Phase 23 adds `gather-from-url` block to each (per `feedback_overrides_in_sync`).
- `experiments/recipe_research.py`, `experiments/recipe_load.py` — existing experiment script pattern. `experiments/gather_from_url.py` follows.
- `pyproject.toml` `[project.scripts]` — Phase 23 adds `experiments.gather_from_url`.
- `pyproject.toml` `[project.dependencies]` — Phase 23 adds `trafilatura>=1.6`; verify `recipe-scrapers>=15.11.0` (already declared per Phase 8).
- `.env.example` — Phase 23 adds `URL_INGESTION_ALLOW_HTTP=false` with comment.

### Project conventions
- `CLAUDE.md` "LangWatch instrumentation must be active during both production and experiment runs" — the eval harness MUST tag traces (`phase=23`, `url=…`, `backend=…`).
- Memory `feedback_avoid_premature_abstraction` — D-01 (per-source variants concrete-named), D-09 (one harness script not a framework), D-08 (no `recipe_source` rename — wait for 3+ workflow source kinds).
- Memory `feedback_prompts_language` — V007 + V001 (`gather-from-url`) bodies in English; user-facing strings + emitted RecipeData (Spanish recipe content) follow recipe-language convention.
- Memory `feedback_overrides_in_sync` — D-23 atomic registry + overrides commit.
- Memory `feedback_env_example` — D-17 `URL_INGESTION_ALLOW_HTTP` added to `.env.example`.
- Memory `feedback_test_before_handoff` — D-24 operator runs eval before reporting Phase 23 complete.
- Memory `feedback_queue_at_front` — unchanged; URL ingestion doesn't touch the notification path.
- Memory `feedback_no_task_id_in_code` — no "Phase 23" / quick-task tags; D-NN refs in comments are durable.
- Memory `project_compose_agent_vision` — V007 keeps Robotina as decider AND composer.
- Memory `project_local_dev_setup` — agent runs on host; Ollama is dev backend, OpenAI is staging; the eval harness runs from host via `uv run experiments.gather_from_url`. **CRITICAL for safe_fetch:** since the agent runs on the host, `localhost` and 127.0.0.1 ARE reachable — the SSRF defenses must actually fire on these hostnames in tests (D-18 covers).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`response_format=<Pydantic class>` on `create_agent` (Phase 11)** — `gather-from-url` reuses this pattern with `response_format=RecipeData`. No new infrastructure.
- **Middleware-based LangWatch instrumentation (Phase 12)** — new agents are automatically instrumented; no per-agent setup.
- **`RecipeData` artifact accumulation (Phase 15)** — `source_url` field is already present; `gather-from-url` populates it; downstream steps (`recipe-research-instructions`, `-ingredients`, `-metadata`) consume a `RecipeData` accumulator irrespective of source.
- **`StartWorkflowTool` constructor injection of `invocation_id` / `conversation_id` / `household_id`** — KEEP unchanged for the URL variant.
- **`recipe-scrapers>=15.11.0`** — already declared in pyproject.toml per Phase 8 (verify; bump to latest if drift).
- **Existing experiment script pattern** (`experiments/recipe_research.py`, `experiments/recipe_load.py`) — `experiments/gather_from_url.py` clones the LangWatch-instrumented agent-dispatch shape.
- **AGENT_REGISTRY + overrides/*.json sync pattern (Phase 21 D-06/D-12)** — new agent additions follow the same atomic-commit + CI-guard rules.
- **Dashboard `_macros.html` TASK_TYPE_LABELS (Phase 21 D-11)** — extend with one new entry.
- **Phase 22 V006 prompt structure** — V007 forks verbatim; the multi-recipe + ambiguity sections from V006 carry forward; the URL detection sections are additive.
- **Phase 22 D-08 wake helper enrichment** — D-08 here extends the read logic to fall back to `recipe_url`.

### Established Patterns
- **Prompt versioning (V001..V006 robotina; V001..V005 recipe-research-* sub-agents)** — concrete, never abstract. V001 for `gather-from-url`; V007 for `robotina`.
- **Manual smoke pattern (Phase 21 D-13, Phase 22 D-05)** — `<phase>-EVAL-SET.md` + `<phase>-EVAL-RESULTS-<backend>.md` + `<phase>-SMOKE.md` verdict.
- **One concrete script per experiment** (`feedback_avoid_premature_abstraction`) — `experiments/gather_from_url.py` is one file.
- **English prompt body + Spanish user-facing strings** — V007 + V001 follow.
- **Constructor-injection pattern on tools** — `FetchAndScrapeTool` has no constructor-injected fields (its only argument is `url` from the LLM); no new pattern.
- **`@model_validator(mode='after')` on Pydantic args schemas** — used elsewhere in the codebase for cross-field invariants; new in `StartWorkflowArgs` for workflow_type ↔ input pairing.

### Integration Points
- `src/robotina/url/__init__.py` (NEW) — empty.
- `src/robotina/url/safe_fetch.py` (NEW) — `safe_fetch`, `SafeFetchResult`, `SafeFetchError` (D-14..D-17).
- `src/robotina/queue/task_types.py` — add `AddRecipeUrlInput {url: str}` (mirror AddRecipeQueryInput). Document `WorkflowOutcomeSummary.recipe_query`'s dual semantic (D-08) in a code comment.
- `src/robotina/agent/tools/start_workflow.py` — D-01 schema changes (Literal rename, union, model_validator); D-08 shared_context `recipe_url` write for URL variant.
- `src/robotina/agent/tools/fetch_and_scrape.py` (NEW) — `FetchAndScrapeTool`, `FetchAndScrapeResult` (D-03).
- `src/robotina/agent/workflows.py` — D-01 rename + new `add-recipe-from-url` WorkflowDefinition entry; 6-step list inline-duplicated.
- `src/robotina/agent/agents.py` — V006 → V007 path bump; add `gather-from-url` AgentConfig entry (D-23).
- `src/robotina/agent/prompts/robotina/V007.md` (NEW) — fork of V006 + URL sections (D-05..D-07).
- `src/robotina/agent/prompts/gather-from-url/V001.md` (NEW) — D-03 rule shape.
- `src/robotina/queue/workflow_runner.py:195` — D-08 wake-helper shared_context fallback.
- `src/robotina/dashboard/templates/_macros.html` — D-11 add `"gather-from-url": "Búsqueda por URL"`.
- `overrides/anthropic.json`, `overrides/openai.json`, `overrides/staging.ollama.json` — D-23 add `gather-from-url` block to each.
- `experiments/gather_from_url.py` (NEW) — D-09 eval harness.
- `pyproject.toml` `[project.scripts]` — D-09 add `experiments.gather_from_url`.
- `pyproject.toml` `[project.dependencies]` — add `trafilatura>=1.6`.
- `.env.example` — D-17 `URL_INGESTION_ALLOW_HTTP=false`.
- `.planning/phases/23-url-ingestion-topic-2/23-EVAL-SET.md` (NEW) — 21 URLs with per-URL expected fields.
- `.planning/phases/23-url-ingestion-topic-2/23-EVAL-RESULTS-openai.md` (NEW — operator) — per-backend.
- `.planning/phases/23-url-ingestion-topic-2/23-EVAL-RESULTS-ollama.md` (NEW — operator) — per-backend.
- `.planning/phases/23-url-ingestion-topic-2/23-SMOKE.md` (NEW — operator) — final verdict.
- `tests/url/test_safe_fetch.py` (NEW) — D-18 comprehensive defense tests.
- `tests/agents/tools/test_fetch_and_scrape_tool.py` (NEW) — D-19.
- `tests/agents/test_gather_from_url_agent.py` (NEW) — D-20.
- `tests/queue/test_workflow_registry.py` (extend) — D-21 6-step assertions for both variants.
- `tests/agents/tools/test_start_workflow_tool.py` (extend) — D-22 union + model_validator tests.
- `tests/agents/test_handle_incoming_message_agent.py` (extend) — V007 prompt path.
- `tests/queue/test_wake_helper.py` (extend) — D-08 fallback read.
- `.planning/REQUIREMENTS.md` — tick URL-01..06 + EXP-02 in the final smoke commit.

</code_context>

<specifics>
## Specific Ideas

- **`safe_fetch` is the load-bearing safety net.** Plan 23-01 lands it FIRST,
  with comprehensive tests, before any code that imports it. Pitfall 6's
  full defense matrix is mandatory. The host-dev environment (per memory
  `project_local_dev_setup`) makes `localhost`/`127.0.0.1` real attack
  surfaces — the SSRF tests MUST verify these are rejected.
- **PITFALL 7 is the secondary risk.** Per-field try/except + Pydantic
  partial validation + LLM fallback (D-03) is the layered mitigation;
  the 20-URL eval set (D-10) is the empirical validation. The
  "Spanish blog hit-rate" gap from SUMMARY.md is closed by D-10.
- **The agent-side LLM fallback is intentionally simple.** D-03's prompt
  is essentially `if scraped: pass-through else extract`. The complexity
  lives in `FetchAndScrapeTool` (deterministic pre-processing); the LLM
  is just the variable extractor. Keeps response_format enforcement and
  LangWatch instrumentation uniform.
- **The workflow-variant rename has a single atomic commit risk window.**
  Once `WORKFLOW_REGISTRY` key changes from `"add-recipe"` to
  `"add-recipe-from-query"`, any in-flight workflow in PENDING state
  with `workflow_type="add-recipe"` will fail to resolve a definition.
  The deploy runbook MUST drain in-flight workflows before the deploy
  (or accept the failure — in pre-launch private env, queue should be
  empty on deploy). Document this in the plan-23-02 deploy steps.
- **No new Alembic revision.** Phase 23 is code + prompt + new dep.
  shared_context dict gains a `recipe_url` key for URL workflows
  (JSON; no DDL).
- **`feedback_overrides_in_sync` applies to the gather-from-url addition.**
  Atomic commit: AGENT_REGISTRY entry + every `overrides/*.json` block
  (anthropic, openai, staging.ollama) + the CI guard test (Phase 21 D-12)
  stays green.

</specifics>

<deferred>
## Deferred Ideas

- **`recipe-image` step** (IMG-*) — Phase 24. Insertion before `load` in
  both add-recipe variants; the shared-tail helper extraction happens
  alongside.
- **Vision-LLM "is this the right page?" validation** (Pitfall 8) —
  Phase 24 may add this for image source-page validation; URL recipe
  pages don't need it in v1.1.
- **CDN / HTML caching** — deferred per FEATURES.md. Re-fetch every
  ingestion in v1.1.
- **Recipe-rehost vs source-URL-pin decision** (RecipeData.source_url
  is enough for v1.1; image rehosting decision is Phase 24's call).
- **`hint` field on `AddRecipeUrlInput`** — user-provided URL context;
  revisit if real users surface the need.
- **`recipe_source` field rename** (`recipe_query` ∪ `recipe_url` →
  unified `recipe_source`) — premature renaming churn; document the
  dual semantic on `WorkflowOutcomeSummary.recipe_query` instead. Revisit
  in v1.2 if a third source kind lands.
- **LLM-judge / vision-model field-correctness scoring** — v1.1 ships
  with field-presence-based scoring (D-11). v1.2 may add per-field
  correctness scoring (e.g. "are the ingredients actually what's on
  the page?").
- **JS-rendered recipe pages** (`recipe-scrapers` + sync fetcher can't
  handle them) — out of scope for v1.1; documented in the eval set
  as "expected failure" for the known-difficult URL.
- **Spanish translation of foreign-language recipe URLs** —
  per FEATURES.md "Should have (P2)"; not v1.1 launch.
- **Inline dedup check** (P2 per FEATURES.md) — "este nombre ya está
  guardado, ¿reemplazo?" — deferred to v1.2.
- **`recipe-scrapers` site-list expansion** — out of scope; we use
  what the library ships with.
- **HTTPS-only as a hard constraint (no env-var escape hatch)** —
  considered but `URL_INGESTION_ALLOW_HTTP` is needed for dev/testing
  against local fixture servers. Production never sets the var; the
  default is secure.

</deferred>

---

*Phase: 23-URL ingestion (Topic 2)*
*Context gathered: 2026-05-20*
