# Phase 15: Recipe Artifact Accumulation and Food/Unit Validation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-14
**Phase:** 15-recipe-artifact-accumulation-and-food-unit-validation
**Areas discussed:** Accumulating artifact shape, Validation tools shape, Semantic match fallback, Recipe-load's new role

---

## Accumulating artifact shape

### Q1: What's the shape of the growing artifact each sub-agent emits?

| Option | Description | Selected |
|--------|-------------|----------|
| One RecipeData, all fields Optional | Mutate the existing RecipeData so every field is Optional except a tiny core. All 5 sub-agents bind response_format=RecipeData and emit a copy with more fields populated. Simplest plumbing. | ✓ |
| Two models: WorkingRecipe + RecipeData | Loose intermediate model + strict final. Coercion at metadata→load boundary. | |
| Per-step extending schemas (typed chain) | Each step has its own response_format that adds fields. Strongest typing, most code churn. | |

**User's choice:** One RecipeData with optional fields.
**Notes:** "Two things to make sure: 1. the artifacts plumbing continues as is (each step's snapshot still lands on workflow_run_steps.artifact for DB-level troubleshooting). 2. We probably need a field for the original data so ingredients, instructions and metadata agents have a source to get the data they need to parse." → captured as D-02 and D-04.

### Q2: Where do resolved foodId / unitId values live on the artifact?

| Option | Description | Selected |
|--------|-------------|----------|
| Add food_id/unit_id on RecipeIngredient | Optional fields; agent populates them; recipe-load uses them; names stay for traceability. | ✓ |
| Sidecar resolution map at artifact root | RecipeData gains resolved_foods/resolved_units dict; ingredient stays unchanged. | |
| Replace food_name/unit_name with id-bearing structs | Strongest invariant; biggest churn (every reader/prompt updates). | |

**User's choice:** Add ids on RecipeIngredient.
**Notes:** "Ideally the recipe in the artifact is already shaped with whatever data the recipe-load agent will need to actually load the data. If the name is not required it's just noise for the recipe-load agent and shouldn't be present." → captured as D-03 + reinforced in D-19.

### Q3: Where does the gathered_recipes raw data live?

| Option | Description | Selected |
|--------|-------------|----------|
| Field on artifact, stripped before recipe-load | gathered_sources: list[dict] \| None on RecipeData. Gather populates. Stripped (None) by metadata step. | ✓ |
| Field on artifact, kept all the way through | Never stripped. Maximum debuggability; recipe-load ignores it. | |
| Wrapper WorkingArtifact(recipe, sources) | Keep RecipeData clean; add sibling field. More plumbing. | |

**User's choice:** Field on artifact, stripped before recipe-load.
**Notes:** none.

### Q4: Where do names of dropped/unmatched ingredients live (for the notification)?

| Option | Description | Selected |
|--------|-------------|----------|
| Field on artifact: missing_ingredients: list[str] | Ingredients step populates; notification reads from final artifact. | ✓ |
| Notification step recomputes from artifacts | Diff gather-extracted vs final to discover dropped. More fragile. | |
| Keep on RecipeLoadOutput only | Status quo; recipe-load would have to re-derive (worst of both). | |

**User's choice:** Field on artifact.
**Notes:** none.

---

## Validation tools shape

### Q1: How are the validation tools surfaced to the ingredients agent?

| Option | Description | Selected |
|--------|-------------|----------|
| Two distinct tools: validate-foods, validate-units | Cleanest schemas; unambiguous tool choice; share an internal helper. | ✓ |
| One tool with a category param | category: Literal['food','unit'] + names. Less surface, prompt must explain category. | |
| Bake into the ingredients step's build_input | Pre-fetch + match before agent runs; agent only handles semantic gaps. Couples workflow_runner to validation. | |

**User's choice:** Two distinct tools.

### Q2: How does each tool fetch the catalog from household-manager?

| Option | Description | Selected |
|--------|-------------|----------|
| Full-list fetch per tool call | GET /api/foods / GET /api/units. Whole catalog client-side. Matches existing skill. | ✓ |
| Per-name filtered queries | One HTTP per ingredient. Higher latency. Defeats batch premise. | |
| Full-list fetch + per-workflow cache | Same as option 1 + cache. Extra plumbing for a one-shot tool. | |

**User's choice:** Full-list fetch per tool call.

### Q3: What counts as a "direct match" in the programmatic pre-LLM pass?

| Option | Description | Selected |
|--------|-------------|----------|
| Normalized exact match (lowercase + accent-strip) | unicodedata.normalize('NFKD') + casefold + strip on both sides. | ✓ |
| Strict case-sensitive exact match | Only name == catalog.name. Anything else → LLM. | |
| Substring containment (either direction) | Risk of false positives (sal ↔ salame). | |

**User's choice:** Normalized exact match.

### Q4: What's the tool's return shape?

| Option | Description | Selected |
|--------|-------------|----------|
| Single list pairing each input with id-or-null | [{name, id-or-null, matched_via, canonical_name}] — same order/length as input. | |
| Three buckets: matched, unmatched, ambiguous | Surfaces semantic candidate list separately; agent handles three cases. | |
| Per-item map keyed by input name | {input_name: {id, source, canonical_name}}. Loses ordering; collapses duplicates. | |
| **User's freeform: object with matched + unmatched lists, both id-aware** | **Object with two lists: matched: [{name, id}] / unmatched: [{name, id: null}]. Agent maps matched into ingredients, unmatched into missing.** | ✓ |

**User's choice:** "Mix of option 1 and option 2 with a twist": object with two lists (matched + unmatched). All matched items have an id; all unmatched have null id. No matched_via, no canonical_name.
**Notes:** captured as D-09.

### Q5: Where do the tools live and do they reuse existing API client wiring?

| Option | Description | Selected |
|--------|-------------|----------|
| New files in tools/, reusing httpx/auth setup | validate_foods.py / validate_units.py + shared internal helper. | ✓ |
| Methods on HouseholdManagerApiTool | Smaller diff; breaks "one BaseTool = one tool" convention. | |
| Single module + two thin BaseTool wrappers | Strongest internal sharing; more files for small surface. | |

**User's choice:** New files in tools/.

---

## Semantic match fallback

### Q1: Which structured-output library powers the LLM semantic match?

User asked for a comparison between instructor and LangChain. Assistant produced a tradeoff table (dependency, fit with existing LLMBackend abstraction, retry behavior, LangWatch/middleware integration, alignment with Phase 11) — see the discussion above this log.

| Option | Description | Selected |
|--------|-------------|----------|
| LangChain with_structured_output via LLMBackend | Reuses existing 3-provider abstraction, AGENT_REGISTRY, overrides, LangWatch + Phase 12 middleware. No new dep. | ✓ |
| 567-labs/instructor | Cleaner API, built-in retry; parallel config layer outside LLMBackend. Adds one dependency. | |

**User's choice:** LangChain with_structured_output via LLMBackend.

### Q2: Which LLM backend does the matcher call?

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated AGENT_REGISTRY entry 'validate-catalog' | Own model_config + overrides + API_TOKEN env. Independently swappable. | ✓ |
| Piggyback on ingredients agent's backend | No new config; couples matcher quality to ingredients model. | |
| Hardcoded inside the tool | Hides config from AGENT_REGISTRY; worst for runtime swap. | |

**User's choice:** Dedicated registry entry.

### Q3: No-match policy for the LLM fallback?

| Option | Description | Selected |
|--------|-------------|----------|
| Binary: id-or-null per item | Response model = list of {name, catalog_id: str \| null}. LLM decides "good enough". | ✓ |
| Confidence-scored, drop below threshold | Adds a tuning knob + calibration problem. | |
| Ranked candidates top-3 | Most flexibility, most engineering for an unproven problem. | |

**User's choice:** Binary.

### Q4: What does the LLM see — full catalog or pre-filtered shortlist?

| Option | Description | Selected |
|--------|-------------|----------|
| Full catalog | Reliable; no silent-filter-blocks-right-answer risk. Catalog is small enough. | ✓ |
| rapidfuzz/difflib shortlist | Smaller prompt; tuning N is another knob. | |
| Embedding similarity shortlist | Adds embedding model dep + index. Overkill at this size. | |

**User's choice:** Full catalog.

### Q5: Single batched call vs one call per unmatched item?

User asked explicitly: "are you planning to match all missing ingredients in one call or make one llm inference call for all missing ingredients? why?" Assistant produced a tradeoff explanation (catalog prompt cost is the dominant cost; latency / traces / cost all scale linearly with per-item; independent matches don't need cross-item reasoning, but batching gives the option for free).

| Option | Description | Selected |
|--------|-------------|----------|
| One batched call | Catalog passed once; single trace; structured output is the full list. | ✓ |
| One call per item | N× cost / latency / traces / retry surface. | |

**User's choice:** One batched call.

---

## Recipe-load's new role

### Q1: What does recipe-load do now that the artifact arrives insert-ready?

| Option | Description | Selected |
|--------|-------------|----------|
| Replace with a deterministic non-LLM step | No agent; workflow_runner POSTs the artifact. Removes from AGENT_REGISTRY. | |
| Slim agent: rename + POST | Agent kept; minimal scope; still hallucinates risk. | |
| Defensive agent: re-validate then POST | Most defensive; mostly duplicates ingredients-step work. | |
| **User's freeform: slim agent + targeted error recovery** | **Happy path = simple POST. Agent retained so it can read meaningful API errors and recover.** | ✓ |

**User's choice:** "Let's still use an agent. The work should be in most cases simply call the household api and be done. But if the agent gets a meaningful error about a mistake on the pipeline the agent may be able to fix it and get the recipe included either way." → captured as D-16.

### Q2: Which tools does the slim recipe-load agent have access to?

| Option | Description | Selected |
|--------|-------------|----------|
| household-manager-api + read-skill + validate-foods + validate-units | Standard happy-path tools + the same validation tools the ingredients step uses for re-resolution. | ✓ |
| household-manager-api + read-skill only (status quo) | Can't re-resolve; limited recovery. | |
| household-manager-api only | No skill access. Brittle when API evolves. | |

**User's choice:** Full tool surface incl. validate-foods/validate-units.

### Q3: Where do snake_case → camelCase field renames happen?

| Option | Description | Selected |
|--------|-------------|----------|
| Inside the recipe-load prompt + agent reasoning (status quo from V004) | Same rename table as today. Minimal change. | ✓ |
| Pydantic alias on the artifact models | model_dump(by_alias=True). Zero hallucination on field names. Couples models to wire format. | |
| workflow_runner does the rename before passing to recipe-load | Pulls work out of the agent; couples build_input to wire format. | |

**User's choice:** Status quo (in the prompt).

### Q4: Where does the notification step read missing_ingredients from?

| Option | Description | Selected |
|--------|-------------|----------|
| Notification reads from metadata-step artifact; load output keeps only API response fields | Cleanest. RecipeLoadOutput drops missing_ingredients. | ✓ |
| Recipe-load echoes missing_ingredients into RecipeLoadOutput (status quo shape) | Duplicated field; agent has to remember to echo. | |
| Workflow_runner merges metadata into load artifact post-hoc | Magical, surprising. | |

**User's choice:** Notification reads from metadata artifact.

---

## Claude's Discretion

- Wording of all 5 prompt-version bumps (gather V004→V005, instructions V003→V004, ingredients V003→V004, metadata V003→V004, recipe-load V004→V005) — following the Phase 14 standardized skeleton.
- Module layout of `_catalog_match.py` (helper hosting fetch + normalize-match + LLM-fallback orchestration).
- Tool `description` strings for `validate-foods` / `validate-units` (≤4 sentences, no schema duplication).
- Test surface and test file layout — unit tests for the matcher's three paths (direct, semantic-hit, semantic-miss); integration test for each tool against a mocked household-manager; end-to-end via the existing experiment script.
- Whether to delete or alias the now-unused intermediate output models (`RecipeResearchGatherOutput`, etc.) — they conceptually become RecipeData.

## Deferred Ideas

- In-memory catalog cache shared across workflow runs (revisit if profiling shows fetch latency is meaningful).
- `POST /api/foods` / `POST /api/units` to auto-onboard novel ingredients — same posture as today (we never invent catalog entries).
- Embedding-based semantic match (only if catalogs grow into thousands of items).
- Confidence-threshold matcher (only if binary matcher starts producing wrong-but-plausible answers in practice).
- Phase 999.1 custom state schemas — already in backlog; orthogonal to this phase's artifact accumulation.
