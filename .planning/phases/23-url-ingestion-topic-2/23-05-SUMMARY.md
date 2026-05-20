---
phase: 23-url-ingestion-topic-2
plan: 05
subsystem: agent/prompts
tags: [prompt, robotina, url-detection, url-routing]
requires:
  - 23-02 (add-recipe-from-url workflow + StartWorkflowArgs union, present in WORKFLOW_REGISTRY)
provides:
  - V007 robotina prompt with URL detection + per-source routing rules
  - agents.py handle-incoming-message wired to V007.md
affects:
  - src/robotina/agent/agents.py (prompt_path bump V006 → V007)
  - tests/agents/test_agent_registry.py (V006 → V007 assertion)
tech-stack:
  added: []
  patterns:
    - "Prompt versioning V00N with prior version retained for rollback (D-25)"
key-files:
  created:
    - src/robotina/agent/prompts/robotina/V007.md
    - tests/agents/test_handle_incoming_message_agent.py
  modified:
    - src/robotina/agent/agents.py
    - tests/agents/test_agent_registry.py
decisions:
  - "V007 forked verbatim from V006; only changes are (a) remove URL-deflection line, (b) append `## URL handling` section, (c) update tools section to mention both variant Literals, (d) extend soft-cap rule to count queries + URLs combined, (e) add wake-context worked example for URL failure"
  - "V006 retained on disk per Phase 23 D-25 rollback policy"
  - "URL detection is LLM-judgment per D-05 (no regex in prompt); bare hostnames without scheme trigger clarification turn"
  - "One start-workflow call per URL/recipe item per D-06/D-07; mixed text+URL produces N calls each routed to its variant"
metrics:
  duration: "~10 min"
  completed: "2026-05-20"
  tasks_completed: 1
  files_changed: 4
---

# Phase 23 Plan 05: Robotina V007 prompt — URL detection + per-source routing Summary

**One-liner:** V007 forks V006 verbatim and appends four worked URL-handling cases (single URL, mixed text+URL, multi-URL, ambiguous bare hostname) plus an updated tools section that exposes both `add-recipe-from-query` and `add-recipe-from-url` Literals, with agents.py bumped to V007 and V006 retained for rollback.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fork V006 to V007 with URL handling sections + bump prompt_path | 992ac66 | V007.md, agents.py, test_handle_incoming_message_agent.py, test_agent_registry.py |

## What Was Built

- **`src/robotina/agent/prompts/robotina/V007.md`** — new prompt. Verbatim copy of V006 with these targeted changes:
  - Tools section now lists `workflow_type` as `"add-recipe-from-query"` or `"add-recipe-from-url"` (was: only `"add-recipe-from-query"`).
  - User-message-turns section step 3 now describes per-item routing.
  - Multi-recipe section clarifies the soft cap of 5 is across queries + URLs combined.
  - V006's URL-deflection bullet ("Todavía no manejo enlaces directos…") is removed.
  - New `## URL handling` section with four worked cases (single URL, mixed, multi-URL, ambiguous bare hostname) and an explicit "what NOT to do" list.
  - Wake-context worked-example block gains a URL-failure example (`https://blog-a.com/pollo — no logré extraerla`).
  - Header comment notes Phase 23 design refs (D-05/D-06/D-07/D-25) and inherits the V006 design notes verbatim.
- **`src/robotina/agent/agents.py`** — `AGENT_REGISTRY["handle-incoming-message"].prompt_path` bumped from `V006.md` to `V007.md`.
- **`tests/agents/test_handle_incoming_message_agent.py`** (NEW) — seven assertions:
  1. `prompt_path` ends with `V007.md`.
  2. V007.md exists.
  3. Contains `URL handling` heading.
  4. Contains `add-recipe-from-url` literal.
  5. Contains `add-recipe-from-query` literal.
  6. No bare `"add-recipe"` workflow_type literal remains (legacy-leak guard, D-01).
  7. URL-deflection line absent.
  8. V006.md still on disk (D-25 rollback).
- **`tests/agents/test_agent_registry.py`** — renamed `test_handle_incoming_message_uses_v006` → `test_handle_incoming_message_uses_v007`; same shape, updated literal.

## Verification

- `uv run pytest tests/agents/test_handle_incoming_message_agent.py tests/agents/test_agent_registry.py -q` → **11 passed**.
- All acceptance criteria in PLAN.md hand-verified:
  - `test -f V007.md` ✓
  - `test -f V006.md` ✓
  - `grep robotina/V007.md agents.py` ✓
  - `! grep robotina/V006.md agents.py` ✓
  - `grep add-recipe-from-url V007.md` ✓
  - `grep add-recipe-from-query V007.md` ✓
  - `grep "URL handling" V007.md` ✓
  - `grep -E '"add-recipe"[^-]' V007.md | wc -l` = 0 ✓

## Deviations from Plan

None — plan executed as written. The plan called out updating examples that used `workflow_type="add-recipe"` to `"add-recipe-from-query"`; V006 already used `"add-recipe-from-query"` in all examples (the rename landed in 23-02), so step (c) in the action list was a no-op verified by the `test_v007_drops_legacy_add_recipe_literal` assertion.

## Known Stubs

None. V007 references both `add-recipe-from-url` and `add-recipe-from-query` workflow variants; both are registered in `WORKFLOW_REGISTRY` (per 23-02 / 23-04). The LLM has a wired path for every routing decision the prompt describes.

## Threat Flags

None new. The plan's `<threat_model>` already covered:

- T-23-URL-DETECT-MISS — mitigated by the four worked examples + clarification turn for ambiguous bare hostnames.
- T-23-CROSS-VARIANT-MISROUTE — mitigated by per-case routing in the prompt; backstopped by `StartWorkflowArgs.@model_validator` (23-02).
- T-23-LEGACY-LITERAL-LEAK — mitigated by `test_v007_drops_legacy_add_recipe_literal` (now green).
- T-23-PROMPT-INJECT-USER-MSG — accepted; out of scope per plan.

No new security-relevant surface introduced by this prompt-only change.

## Self-Check: PASSED

- `src/robotina/agent/prompts/robotina/V007.md`: FOUND
- `src/robotina/agent/prompts/robotina/V006.md`: FOUND (retained)
- `tests/agents/test_handle_incoming_message_agent.py`: FOUND
- Commit `992ac66`: FOUND in `git log --oneline`
