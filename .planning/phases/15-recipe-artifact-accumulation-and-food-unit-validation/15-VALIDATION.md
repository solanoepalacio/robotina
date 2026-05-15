---
phase: 15
slug: recipe-artifact-accumulation-and-food-unit-validation
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-15
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Reconstructed retroactively from artifacts (State B) on 2026-05-15.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (with pytest-asyncio) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/unit/test_household_manager_api_tool.py tests/test_validate_foods.py tests/test_validate_units.py tests/test_catalog_match.py tests/test_task_types.py tests/unit/test_agents_registry.py -x --tb=short` |
| **Full suite command** | `uv run pytest --tb=short` |
| **Estimated runtime** | ~1s for the Phase 15 quick set; full suite includes a Postgres-dependent migration test (`test_migration_0005_upgrades_and_downgrades`) that requires `docker compose up` |

---

## Sampling Rate

- **After every task commit:** Run quick command (Phase 15-relevant tests only).
- **After every plan wave:** Run the full suite.
- **Before `/gsd:verify-work`:** Full suite must be green (Postgres-dependent test is allowed to fail when Postgres is not running locally; CI must run it with the stack up).
- **Max feedback latency:** ~5s.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 15-01-* | 01 | 1 | RRECIPE-04 / RRECIPE-07 | T15-T1 (hallucinated UUID) | `RecipeData` shape stable; sub-agents bind canonical `RecipeData` as `response_format` | unit | `uv run pytest tests/test_task_types.py tests/unit/test_agents_registry.py` | ✅ | ✅ green |
| 15-01-* | 01 | 1 | RLOAD-03 | T15-T1, T15-D1 | `validate-foods` / `validate-units` resolve names via NFKD direct + batched semantic match; defensive `valid_ids` filter rejects hallucinated UUIDs | unit | `uv run pytest tests/test_validate_foods.py tests/test_validate_units.py tests/test_catalog_match.py` | ✅ | ✅ green |
| 15-01-* | 01 | 1 | RRECIPE-04 | — | `build_input` threads `RecipeData` artifact between sub-agent steps | unit | `uv run pytest tests/test_workflows.py tests/test_workflow_runner.py` | ✅ | ✅ green (Postgres-bound migration test fails locally without `docker compose up` — known infra dependency, not Phase 15) |
| 15-02-* | 02 | 2 | RRECIPE-07 | — | `recipe-research-gather` registry pinned to V005; canonical `RecipeData` response_format | unit | `uv run pytest tests/unit/test_agents_registry.py` | ✅ | ✅ green |
| 15-03-* | 03 | 2 | RRECIPE-04 / RRECIPE-07 | — | `recipe-research-instructions` registry pinned to V004; canonical `RecipeData` response_format | unit | `uv run pytest tests/unit/test_agents_registry.py` | ✅ | ✅ green |
| 15-04-* | 04 | 2 | RRECIPE-04 / RRECIPE-07 / RLOAD-03 | T15-T1 | `recipe-research-ingredients` registry pinned to V004; uses `validate-foods` / `validate-units`; per-job tool injection wires both tools + `HouseholdManagerApiTool` | unit | `uv run pytest tests/unit/test_agents_registry.py tests/test_validate_foods.py tests/test_validate_units.py` | ✅ | ✅ green |
| 15-05-* | 05 | 2 | RRECIPE-04 / RRECIPE-07 | — | `recipe-research-metadata` registry pinned to V004; clean-payload emit (`gathered_sources = null`) | unit | `uv run pytest tests/unit/test_agents_registry.py` | ✅ | ✅ green |
| 15-06-* | 06 | 2 | RLOAD-03 / RLOAD-04 / RLOAD-07 | T15-S1, T15-T2, T15-T3, T15-I1, T15-D3, T15-E1 | `recipe-load` agent pinned to V005; `HouseholdManagerApiTool` accepts/refuses POST `/api/recipes` body shapes per `CreateRecipeBody` schema; bearer token never exposed to LLM; method `Literal`-restricted | unit + end-to-end via `create_agent` | `uv run pytest tests/unit/test_household_manager_api_tool.py` | ✅ | ✅ green (16 tests: 11 pre-existing + 5 added 2026-05-15 for the empty-body-loop hardening) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.* No new test framework, fixtures, or Wave 0 scaffolding needed — pytest + the existing `tests/conftest.py` were already in place from prior phases.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end add-recipe via Telegram (acknowledgment → recipe-research pipeline → recipe-load → confirmation) | RRECIPE-04, RLOAD-04 | Spans Telegram polling, OpenAI/Ollama LLM calls, web-search (Tavily), Postgres writes, and the live household-manager API. Mocking the entire surface would re-implement most of the system. The 5-test UAT (`15-UAT.md`) covers this manually and was passed on 2026-05-15. | See `15-UAT.md` Test 1. Send "agregá receta de [name]" via Telegram; confirm Spanish ack within seconds and final notification within ~3 min; verify the recipe appears in household-manager with name, description, ingredients (with resolved foods + units), ordered steps, and metadata. |
| Catalog resolution quality on real recipes | RLOAD-03 | LLM matcher quality is best judged with eyeball checks against real catalog data; not deterministic across runs. | See `15-UAT.md` Test 2. After Test 1 completes, open the recipe in household-manager: foods are catalog entries (not raw strings), units are attached where source mentions them, quantities carried through. |
| Missing-ingredients surfacing on real recipes | RLOAD-03 | Requires a recipe with at least one food not in the household catalog; depends on actual catalog state. | See `15-UAT.md` Test 3. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-15

---

## Validation Audit 2026-05-15

| Metric | Count |
|--------|-------|
| Gaps found | 1 (regression coverage for the 15-06 empty-body-loop hardening) |
| Resolved | 1 |
| Escalated | 0 |

### Resolution
gsd-nyquist-auditor added 5 tests to `tests/unit/test_household_manager_api_tool.py` covering the new validator behaviors:

1. `test_post_recipes_with_null_body_is_rejected_by_validator` — direct ValidationError check.
2. `test_post_recipes_with_null_body_yields_tool_error_message_in_agent_loop` — end-to-end via `create_agent` + `FakeMessagesListChatModel`.
3. `test_post_recipes_with_empty_body_flags_all_required_keys` — verifies all 10 `CreateRecipeBody` keys are flagged as missing.
4. `test_post_recipes_with_full_body_dict_dumps_json_safe_payload` — full body as dict passes through `_run` and httpx receives a JSON-safe dict.
5. `test_post_recipes_with_full_body_model_instance_dumps_json_safe_payload` — full body as `CreateRecipeBody` instance is `model_dump`ed before httpx.

### Maintainer Note (langgraph error-message filtering)
The end-to-end variant (Gap A test 2) confirms that the validator stops the loop and the agent's `ToolMessage` arrives with `status="error"`, but the validator's specific message text does NOT reach the agent's next turn. langgraph's default `ToolNode` filters validator errors with empty `loc=()` (which is what `model_validator(mode="after")` produces). The recovery semantics are still correct (the agent stops looping; status="error" surfaces), but if a future maintainer wants the diagnostic text in front of the model, the validator should attach `loc=("body",)` to the error — e.g. by raising via `PydanticCustomError` on the `body` field rather than at the model level. This is a known langgraph behavior, not a Phase 15 bug.
