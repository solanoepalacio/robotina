# Phase 8: recipe-research Agent - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 08-recipe-research-agent
**Areas discussed:** Search strategy, Missing data handling, Language & locale

---

## Search strategy

### Workflow Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Single best source | Agent picks the most complete source, extracts RecipeData from one page | |
| Merge from multiple sources | Agent cross-references multiple sites, combines best info | |
| Search then verify | One primary source + second search to verify key fields | |

**User's choice:** Free-text — user provided a detailed description of a 4-step pipeline architecture:
1. `recipe-research-gather`: 3 Spanish search terms, Tavily API, recipe-scrapers + LLM fallback
2. `recipe-research-instructions`: Consensus-based baseline from gathered recipes
3. `recipe-research-ingredients`: Extract from instructions, verify against household-manager API
4. `recipe-research-metadata`: Estimate times/servings from instructions + scraped data

**Notes:** This fundamentally changed the architecture from a single recipe-research task to 4 sequential sub-tasks within the workflow.

### Phase scope

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, all 4 in Phase 8 | All 4 sub-tasks delivered in Phase 8 | ✓ |
| Slim Phase 8, rest later | Only 1-2 sub-tasks in Phase 8 | |

**User's choice:** Yes, all 4 in Phase 8

### Ingredient verification tool

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse HouseholdManagerApiTool (Recommended) | Inject existing tool for ingredient verification | ✓ |
| Skip API verification for now | Defer verification to recipe-load | |

**User's choice:** Reuse HouseholdManagerApiTool (Recommended)

### Artifact storage

| Option | Description | Selected |
|--------|-------------|----------|
| Accumulated artifacts (Recommended) | Use existing workflow engine artifact accumulation | ✓ |
| shared_context field | Store draft_recipe in WorkflowRun.shared_context | |

**User's choice:** Accumulated artifacts (Recommended)

### Skill structure

| Option | Description | Selected |
|--------|-------------|----------|
| One shared skill (Recommended) | Single recipe-research skill with sub-files per step | ✓ |
| Separate skills per step | 4 skill directories | |
| No skills needed | Instructions directly in prompts | |

**User's choice:** One shared skill (Recommended)

### Experiment approach

| Option | Description | Selected |
|--------|-------------|----------|
| One combined experiment (Recommended) | Single script running all 4 steps in sequence | ✓ |
| Separate experiments per step | 4 experiment scripts | |
| Combined + individual | One pipeline + per-step experiments | |

**User's choice:** One combined experiment (Recommended)

---

## Missing data handling

### Metadata estimation

| Option | Description | Selected |
|--------|-------------|----------|
| LLM estimates from instructions (Recommended) | Always produce estimates, never null | ✓ |
| Null if no evidence | Leave null when uncertain | |
| Flag for user review | Add uncertainty notes in output | |

**User's choice:** LLM estimates from instructions (Recommended)

### Sparse source data

| Option | Description | Selected |
|--------|-------------|----------|
| Skip and continue (Recommended) | Drop unusable sources, fail only if ALL are unusable | ✓ |
| Retry with different queries | Construct alternative search terms | |
| Fail fast | Fail step if fewer than 2 usable sources | |

**User's choice:** Skip and continue (Recommended)

---

## Language & locale

### Output language

| Option | Description | Selected |
|--------|-------------|----------|
| All Spanish (Recommended) | Search terms, output, ingredient names all in Spanish | ✓ |
| Spanish search, English output | Search Spanish, translate output to English | |
| Follow source language | Keep whatever language the source uses | |

**User's choice:** All Spanish (Recommended)

### Ingredient API lookup language

| Option | Description | Selected |
|--------|-------------|----------|
| Spanish names directly (Recommended) | Send Spanish food names to household-manager API | ✓ |
| Normalize first | Strip qualifiers before lookup | |

**User's choice:** Spanish names directly (Recommended)

---

## Claude's Discretion

- WebSearchTool implementation details (Tavily API parameters)
- Exact Pydantic I/O model field names for 4 new task types
- Prompt wording for all 4 V001.md files
- Skill sub-file content depth and formatting
- recipe-scrapers integration details
- Experiment evaluation criteria and output formatting

## Deferred Ideas

None — discussion stayed within phase scope.
