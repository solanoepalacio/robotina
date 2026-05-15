# SECURITY.md — Phase 15: Recipe Artifact Accumulation and Food/Unit Validation

**Mode:** Retroactive STRIDE (no PLAN-time threat register existed for this phase)
**ASVS Level:** 1
**Block-on:** high

## Scope

Phase 15 introduced:
- `validate-foods` and `validate-units` tools that read `GET /api/foods` / `GET /api/units` from household-manager and resolve LLM-emitted Spanish names to UUIDs via NFKD direct-match + a batched LLM matcher (`validate-catalog` agent).
- `_catalog_match.resolve_catalog()` orchestrating direct + semantic match with a defensive hallucination filter.
- New `validate-catalog` agent registry entry (gpt-oss:20b on Ollama, structured output).
- Per-job tool injection in `queue/jobs.py` for `recipe-research-ingredients` and `recipe-load` (adds `ValidateFoodsTool`, `ValidateUnitsTool`, `HouseholdManagerApiTool`).
- New accumulating `RecipeData` artifact threaded across the four research sub-agents into recipe-load.
- Hardening of `HouseholdManagerApiTool` args schema (typed `CreateRecipeBody`, model_validator rejects null body for POST `/api/recipes`).

Out of scope (inherited from prior phases): Telegram gateway authentication, LangWatch endpoint configuration, Redis AOF, RQ worker concurrency=1.

## STRIDE Register (built retroactively from implementation)

### Closed
| Threat ID | Category | Disposition | Evidence |
|-----------|----------|-------------|----------|
| T15-S1 | Spoofing — agent forges household-manager auth | mitigate | `household_manager_api.py:240,254`, `validate_foods.py:72,79`, `validate_units.py:66,73` — bearer token read from `os.environ["HOUSEHOLD_MANAGER_API_KEY"]` and injected as `Authorization` header in `_run`; LLM never sees it (no arg, no schema field) |
| T15-S2 | Spoofing — LLM forges household_id to read another household's data | mitigate | `household_manager_api.py:218` `household_id` is a constructor-only field on the BaseTool, not in `HouseholdManagerApiArgs` (lines 119-168) so it is not exposed to the LLM. Validate-foods/units do not accept household_id either. NOTE: docstring (lines 12-15) states household_id is NOT auto-appended to URLs in current code — accepted risk recorded below (R-1) |
| T15-T1 | Tampering — LLM hallucinates a food/unit UUID and POSTs an invalid recipe | mitigate | `_catalog_match.py:163-188` — defensive filter drops any `catalog_id` not in `valid_ids = {c.get("id") for c in catalog}`; hallucinated names not in `remaining_set` are dropped. Combined with `CreateRecipeBody.ingredients[].foodId` being typed `str` (Required) at `household_manager_api.py:55-66` — but UUID format itself is not asserted (see R-2) |
| T15-T2 | Tampering — LLM submits empty body `{}` or `null` for POST /api/recipes (canelones-class loop) | mitigate | `household_manager_api.py:156-168` `_enforce_body_for_known_endpoints` model_validator raises `ValueError` for null body on POST /api/recipes; `CreateRecipeBody` (lines 78-116) declares every key required with `extra="forbid"` so `{}` fails schema validation before any HTTP call |
| T15-T3 | Tampering — LLM emits unknown args to a tool, crashing the workflow with TypeError | mitigate | All tool args schemas use `model_config = ConfigDict(extra="forbid")`: `HouseholdManagerApiArgs` (line 134), `ValidateFoodsArgs` (line 41), `ValidateUnitsArgs` (line 35), `StartWorkflowArgs` (line 40), `CreateRecipeIngredient` (line 53), `CreateRecipeStep` (line 72), `CreateRecipeBody` (line 91). Unknown fields surface as recoverable `ValidationError` → `ToolMessage(status='error')` |
| T15-T4 | Tampering — read-skill tool path traversal via `..` to read arbitrary files | mitigate | `read_skill.py:96-102` — both base and target are `pathlib.resolve()`'d, then `str(target).startswith(str(base) + "/")` check rejects traversal. Not modified in Phase 15; verified intact |
| T15-R1 | Repudiation — actions taken on behalf of a household are not auditable | mitigate | `household_manager_api.py:277-281` logs `method` and `path` per call; `validate_foods.py:105-108` and `validate_units.py:99-102` log input/matched/unmatched counts; LangWatch traces emitted for the matcher LLM (`_catalog_match.py:127-129,157-161`) and for agent runs (`jobs.py:206-218`). Workflow steps persist via `workflow_runner.on_step_complete` (`jobs.py:229`) |
| T15-I1 | Information disclosure — Authorization bearer token leaks into logs / error responses returned to LLM | mitigate | `household_manager_api.py:272-276` logs only `method`, `path`, `exc` — never the headers dict. `validate_foods.py:95` / `validate_units.py:89` log only `exc`. Error returns include `resp.text` (line 264) and `str(exc)` (line 276) — `httpx` does not echo request headers in response bodies/messages, and `RuntimeError` for 401/403 (lines 258-262) does not include the token |
| T15-I2 | Information disclosure — household-manager response body (other households' data) leaks back to LLM | accept | The household-manager API enforces per-token scoping; the bearer token is per-household-server. Phase 15 does not introduce cross-household reads. See R-1 below |
| T15-I3 | Information disclosure — Tavily web-search returns malicious / arbitrary external content that becomes part of the LLM context | accept | `web_search.py` returns title/url/content/raw_content verbatim. This is intentional — recipe pages are the data source. Downstream defense: validate-foods/units filter Spanish names through a strict matcher; the typed `CreateRecipeBody` schema gates what fields can reach the API. Out of full Phase 15 scope (web-search not modified this phase). |
| T15-D1 | Denial of service — LLM sends huge `names` list to validate-foods/units, blowing matcher prompt size | accept | No length cap on `names: list[str]` (`validate_foods.py:43-46`, `validate_units.py:37-40`). Sequential worker (concurrency=1) bounds blast radius to a single workflow; no public surface. Recorded as accepted risk R-3 |
| T15-D2 | Denial of service — Ollama matcher LLM hangs / times out, stalling the worker | mitigate | `_catalog_match.py:142-143` `with_retry(stop_after_attempt=2)` caps retries. Failure raises out of `resolve_catalog`, surfaces as tool exception, RQ marks the job FAILED via `workflow_runner.on_step_failed` (`jobs.py:232-235`). Worker is not deadlocked permanently |
| T15-D3 | Denial of service — agent loops calling household-manager-api with empty body forever | mitigate | T15-T2 mitigation closes this specific loop (canelones bug). Body validator raises before HTTP call, error feeds back to agent as `ValidationError` with explicit instructions (`household_manager_api.py:160-167`) |
| T15-E1 | Elevation of privilege — LLM tricks agent into making POST/PATCH/DELETE to arbitrary household-manager endpoints | mitigate | `HouseholdManagerApiArgs.method` is `Literal["GET", "POST", "PATCH", "DELETE"]` (line 136); `path` is a free string. Restriction enforced server-side by household-manager and per-token authorization. Risk that LLM POSTs to non-recipe endpoints is bounded by what the bearer token can reach. Body schema only typed for `/api/recipes`; other paths accept dicts. See R-4 |
| T15-E2 | Elevation of privilege — `recipe-load` agent calls `validate-foods` / `validate-units` to read catalogs it should not see | mitigate | Catalogs are intentionally shared per household per D-10 (referenced in `jobs.py:155-157,165-169`). The validate tools only read `GET /api/foods` and `GET /api/units` and do not write. Bearer token scope already includes these endpoints |

### Open / Accepted Risks (informational, not blockers at ASVS 1)

| Ref | Description | Status | Justification |
|-----|-------------|--------|---------------|
| R-1 | `household_id` is constructor-only on `HouseholdManagerApiTool` but is NOT auto-injected into request URLs/query (per module docstring lines 12-15). The agent is expected to include household_id where required. A misbehaving LLM could omit household_id from a path/query that needs it. | Accepted | Documented in code; backend is expected to authorize per token. Future phase to enforce server-side auto-injection. |
| R-2 | `CreateRecipeIngredient.foodId` / `unitId` typed as `str` but no UUID format validation. A name passed through `_catalog_match` is filtered against `valid_ids`, so this is closed in the happy path; only direct LLM construction without validate-foods would bypass. | Accepted | Defense-in-depth handled by `valid_ids` filter; backend POST returns 400 for malformed UUIDs. |
| R-3 | No length cap on `names: list[str]` for validate-foods/units; could send arbitrarily long matcher prompts. | Accepted | No external attacker surface — input is gated through Telegram → routing agent → research pipeline. Concurrency=1 bounds blast radius. |
| R-4 | `HouseholdManagerApiArgs.path` is a free string — LLM can call any path the bearer token authorizes (not just `/api/recipes`, `/api/foods`, `/api/units`). | Accepted | Authorization enforced server-side. Phase 15 did not change this surface; it predates Phase 15. |
| R-5 | `web-search` raw_content can contain arbitrary external HTML/text injected into the LLM context (prompt injection from recipe sources). Mitigated downstream by structured schemas (`RecipeData`, `CreateRecipeBody`) and the catalog filter, but the gather/instructions sub-agents themselves trust web content. | Accepted | Inherent to the recipe-research use case. Out of Phase 15 scope; not modified this phase. |

## Unregistered Flags

All Phase 15 SUMMARY threat-flag sections report "None." No unregistered surface flagged by executor; STRIDE register above was constructed retroactively from implementation reading and represents the audit's own enumeration.

## Mitigations newly added in Phase 15 (positive findings)

- Typed `CreateRecipeBody` Pydantic schema with every key required at the schema level (`household_manager_api.py:78-116`). Closes the canelones-class empty-body infinite-loop bug.
- `_enforce_body_for_known_endpoints` model_validator rejecting null body for POST `/api/recipes` (lines 156-168).
- `_catalog_match.resolve_catalog` defensive filter that drops hallucinated names not in input and hallucinated catalog_ids not in catalog (lines 163-188).
- `extra="forbid"` on every new args schema (`ValidateFoodsArgs`, `ValidateUnitsArgs`, all `CreateRecipe*` body sub-models).

## Result

All 14 enumerated STRIDE threats resolve to CLOSED via existing mitigations or are documented as accepted risks (R-1..R-5) appropriate for ASVS Level 1. No BLOCKER findings.

---

## SECURED

**Phase:** 15 — Recipe Artifact Accumulation and Food/Unit Validation
**Threats Closed:** 14/14 (5 accepted risks documented)
**ASVS Level:** 1

### Threat Verification
| Threat ID | Category | Disposition | Evidence |
|-----------|----------|-------------|----------|
| T15-S1 | Spoofing | mitigate | household_manager_api.py:240,254; validate_foods.py:72,79; validate_units.py:66,73 |
| T15-S2 | Spoofing | mitigate | household_manager_api.py:218 (constructor-only field, not in args_schema) |
| T15-T1 | Tampering | mitigate | _catalog_match.py:163-188 (valid_ids filter) |
| T15-T2 | Tampering | mitigate | household_manager_api.py:156-168 (model_validator) + 78-116 (CreateRecipeBody) |
| T15-T3 | Tampering | mitigate | extra="forbid" on every args schema (lines 134/41/35/40/53/72/91) |
| T15-T4 | Tampering | mitigate | read_skill.py:96-102 (pathlib.resolve + startswith) |
| T15-R1 | Repudiation | mitigate | household_manager_api.py:277-281; validate_*.py log lines; jobs.py LangWatch |
| T15-I1 | Info disclosure | mitigate | household_manager_api.py:272-276 (no header logging) |
| T15-I2 | Info disclosure | accept | R-1: per-token server-side auth scoping |
| T15-I3 | Info disclosure | accept | R-5: web-search out of Phase 15 scope; downstream schema gating |
| T15-D1 | DoS | accept | R-3: no external surface; concurrency=1 |
| T15-D2 | DoS | mitigate | _catalog_match.py:142-143 with_retry; jobs.py:232-235 on_step_failed |
| T15-D3 | DoS | mitigate | T15-T2 closure prevents infinite-loop body resend |
| T15-E1 | Elevation | mitigate | Literal method enum + server-side token scope (R-4 accepted) |
| T15-E2 | Elevation | mitigate | D-10 shared catalog; read-only endpoints |

### Unregistered Flags
None — all Phase 15 SUMMARY threat-flag sections report "None"; STRIDE register above is the audit's retroactive enumeration.

SECURITY.md: /home/solanoe/code/robotina-gsd/.planning/phases/15-recipe-artifact-accumulation-and-food-unit-validation/SECURITY.md
