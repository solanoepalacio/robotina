# Phase 14: Prompt Cleanup and Structural Standardization - Context

**Gathered:** 2026-05-14
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure/refactor phase — no grey areas)

<domain>
## Phase Boundary

All 7 active agent prompts share a single predictable skeleton (Role / Inputs / Tools / Process / Rules / Output), deduplicated language rules, and schema-deferring `## Output` sections — with zero behavioral change across the add-recipe workflow and chit-chat router paths.

Per-prompt version bumps required:
- `robotina/V002 → V003`
- `acknowledge-add-recipe/V001 → V002`
- `recipe-research-gather/V003 → V004`
- `recipe-research-instructions/V002 → V003`
- `recipe-research-ingredients/V002 → V003`
- `recipe-research-metadata/V002 → V003`
- `recipe-load/V003 → V004`

Each version bump touches: prompt file + `AGENT_REGISTRY` in `src/robotina/agent/agents.py` + every `overrides/*.json` (anthropic, openai, staging.ollama) — all atomic in one commit per prompt-bump.

Also delete the orphan `src/robotina/agent/prompts/hello-world/` directory.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
This is a pure refactor with zero behavioral change. All structural/wording choices for the standardized skeleton are at Claude's discretion. Use the ROADMAP scope, success criteria, and the planning context referenced in the ROADMAP (`/home/solanoe/.claude/plans/correct-let-s-focus-this-optimized-ripple.md` if available) to guide the skeleton design. Defer schema descriptions to the Pydantic response models in `src/robotina/queue/task_types.py` rather than re-describing them in prose.

### Locked Constraints (from ROADMAP)
- Zero behavioral change across add-recipe workflow and chit-chat router paths
- Per `feedback_overrides_in_sync.md`: prompt + `agents.py` + 3 `overrides/*.json` committed atomically per prompt-bump
- Sequential plans per prompt-bump (not parallel) to keep diffs reviewable
- System prompts in English (per `feedback_prompts_language.md`); user-facing Spanish rules belong in the dedicated language section

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/robotina/agent/agents.py` — `AGENT_REGISTRY` with `prompt_path` per agent
- `src/robotina/agent/prompts/` — current versioned prompts per agent
- `src/robotina/queue/task_types.py` — Pydantic response models that `## Output` sections must defer to
- `overrides/anthropic.json`, `overrides/openai.json`, `overrides/staging.ollama.json` — three override files that must stay in lockstep with the registry

### Established Patterns
- Versioned prompt files (`Vxxx.md`) — new versions added rather than edited in place
- Atomic commits coupling prompt + registry + overrides per `feedback_overrides_in_sync.md`
- LangWatch trace metadata includes prompt version filename

### Integration Points
- `AGENT_REGISTRY` is the authoritative agent table
- Every `overrides/*.json` mirrors the registry's `prompt_path` field
- Smoke test paths: Hola (chit-chat router) / meal-plan question / add-recipe (full workflow)

</code_context>

<specifics>
## Specific Ideas

Standardized skeleton sections (in order): **Role / Inputs / Tools / Process / Rules / Output**.

Deduplication targets:
- Spanish-language reminders (move to a shared/consistent location per prompt)
- Schema descriptions in `## Output` sections — defer to Pydantic models in `task_types.py`

Out of scope (deferred per ROADMAP):
- Router emitting plain assistant text instead of tool calls
- `recipe-research-gather` over-querying
- `recipe-load` hallucinated `recipe_id` failure mode
- Skill-file cleanup under `src/robotina/agent/skills/household-manager/`
- Pydantic model field-name or schema changes
- Workflow shape changes

</specifics>

<deferred>
## Deferred Ideas

See "Out of scope" above — explicit deferrals per the ROADMAP for this phase.

</deferred>
