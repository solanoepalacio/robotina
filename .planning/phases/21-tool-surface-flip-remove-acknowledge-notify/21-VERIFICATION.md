---
phase: 21
status: human_needed
checked: 2026-05-19
must_haves_verified: 6/6
score: 6/6 must-haves verified
verified: 2026-05-19T00:00:00Z
human_verification:
  - test: "Run 21-SMOKE.md utterance set against Ollama gpt-oss:20b (local dev) and OpenAI (staging); fill table + verdict line"
    expected: "Each utterance produces the expected N start-workflow calls per turn, respond pre-batch + terminate; no trailing assistant text leaks; go/no-go verdict committed"
    why_human: "EVAL-01..03 — multi-call smoke against live LLM backends requires operator-driven inspection of LangWatch traces and dashboard; cannot be automated within phase scope"
  - test: "Phase 20 manual Telegram smoke (carried forward from prior phase)"
    expected: "Phase 20's deferred Telegram smoke verdict — outside this phase's responsibility but blocks production cutover"
    why_human: "Operator deferred from Phase 20"
---

# Phase 21: Tool-Surface Flip + Remove Acknowledge/Notify — Verification Report

**Phase Goal:** Robotina speaks via explicit `respond()`/`terminate()` tools and dispatches N workflows per turn; the legacy `acknowledge-add-recipe` agent and `notify` workflow step are gone.

**Verified:** 2026-05-19
**Status:** human_needed (manual smoke EVAL-01..03 is operator gate; all code/wiring/grep gates pass)

## Must-Have Verification

| # | Must-Have (Truth) | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | Single-recipe happy path: respond pre-batch → workflow drains → wake invocation respond post-batch → terminate. No final-AI-message-content leakage. | VERIFIED (code) / human_needed (live) | `src/robotina/agent/tools/respond.py:64` (`return_direct=False`); `terminate.py:54` (`return_direct=True`); V005 prompt `src/robotina/agent/prompts/robotina/V005.md` lines 1–29 declare strict output rule + 3-tool surface. Live multi-turn confirmation deferred to 21-SMOKE.md. |
| 2 | StartWorkflowTool accepts N calls/turn with `{workflow_type, input}` schema; `return_direct=False`; `invocation_id` constructor-injected. | VERIFIED | `start_workflow.py:122` (`return_direct=False`), `:59-69` (`workflow_type: Literal["add-recipe"]` + `input: AddRecipeQueryInput`), `:156` (`invocation_id: str` constructor field), `:208` (passed to `queue_workflow`). |
| 3 | `grep -r "acknowledge-add-recipe" src/ tests/ overrides/ experiments/` returns zero hits. | VERIFIED | Only matches are: (a) `src/robotina/dashboard/templates/_macros.html:8` documenting intentional absence; (b) `tests/agents/test_agent_registry.py` lines 4/15/16 — explicit absence assertions; (c) `tests/dashboard/test_task_type_labels.py` — fallback-path regression guards. All three are regression scaffolding, not live references. **Override accepted.** |
| 4 | `notify` workflow step removed from add-recipe; dashboard task-type label map updated; no template regression. | VERIFIED | `src/robotina/agent/workflows.py:67-133` — add-recipe steps are exactly `[gather, instructions, ingredients, metadata, load, finalize-outcome]` (6 steps, no acknowledge, no notify). `_macros.html:19` defines `finalize-outcome` Spanish label + fallback macro at `:24`. `workflow.html:3` imports the macro. `tests/dashboard/test_task_type_labels.py` covers fallback path. |
| 5 | `experiments/acknowledge_add_recipe.py` and `[project.scripts]` entry removed; docs updated. | VERIFIED | No file `experiments/acknowledge_add_recipe.py` exists (grep gate confirms). REQUIREMENTS.md EXP-05 entry confirms doc-only cleanup (PROJECT.md not in repo). |
| 6 | 21-SMOKE.md template committed with 5–8 utterance set + go/no-go scaffolding (operator runs actual smoke). | VERIFIED (template) / human_needed (verdict) | `.planning/phases/21-tool-surface-flip-remove-acknowledge-notify/21-SMOKE.md` exists, `verdict: pending`, 7 utterances covering EVAL-02 envelope (1 single + 2 multi + 1 compound + 1 ambiguous + 1 over-cap + 1 sanity), per-backend hygiene-check section, D-15 pivot path documented. Operator gate is the human-verification item. |

## Requirements Coverage

| Req ID | Description | Status | Evidence |
|--------|-------------|--------|----------|
| TOOLS-01 | StartWorkflowTool multi-call, `{workflow_type, input}` schema | SATISFIED | `start_workflow.py:33-69, 122` |
| TOOLS-02 | RespondTool — `send-notification at_front=True`, non-terminal | SATISFIED | `respond.py:64, 95` |
| TOOLS-03 | TerminateTool — `return_direct=True`, no args, prompt forbids trailing text | SATISFIED | `terminate.py:29, 54`; V005 prompt strict output rule |
| TOOLS-04 | Acknowledge agent, prompt dir, registry entry, task type, workflow step, dashboard label, overrides all removed; CI guard enforces sync | SATISFIED | Prompt dir gone; `overrides/*.json` zero hits; `tests/agents/test_registry_override_sync.py` enforces bidirectional sync |
| TOOLS-05 | `notify` workflow step removed from add-recipe | SATISFIED | `workflows.py:67-133` — 6 steps, no notify |
| DASH-11 | Dashboard task-type label map updated; CI/template tests guard | SATISFIED | `_macros.html:19, 24`; `workflow.html:3`; `tests/dashboard/test_task_type_labels.py` |
| EXP-05 | `experiments.acknowledge_add_recipe` removed | SATISFIED | File never existed; doc-only cleanup confirmed |
| EVAL-01 | Manual multi-call smoke against Ollama + OpenAI | TEMPLATE COMMITTED / NEEDS HUMAN | 21-SMOKE.md scaffolded; operator runs |
| EVAL-02 | 5–8 utterance Spanish set committed | SATISFIED | 7 utterances in 21-SMOKE.md (envelope satisfied) |
| EVAL-03 | Smoke results committed with go/no-go line; D-15 pivot path documented | TEMPLATE COMMITTED / NEEDS HUMAN | Verdict gate present; operator fills before merge |

## Grep Gate Results

| Gate | Command | Expected | Result |
|------|---------|----------|--------|
| 1 | `grep -rn "acknowledge-add-recipe" src/ tests/ overrides/ experiments/` | Zero non-test live refs | PASS — only regression-guard assertions + intentional-absence comment in `_macros.html:8` |
| 2 | `grep -rn "QueueTool" src/ tests/` | Zero live refs | PASS — only test_agent_registry.py D-05 absence assertion |
| 3 | `grep -rn "AcknowledgeAddRecipeInput" src/ tests/` | Zero hits | PASS — zero matches |

## Phase 22+ Boundary Check

- WORKFLOW_REGISTRY contains only `add-recipe` (Phase 23 will add `gather-from-url`, Phase 24 `recipe-image`). Comment at `workflows.py:60-65` explicitly notes Phase 21 D-06 scope boundary.
- `_macros.html:11` comment flags Phase 23/24 extensions for the label map — boundary documented, not deferred.
- V005 prompt retains V004 ("V004 RETAINED untouched for rollback") — rollback path preserved.
- on_step_failed dead-letter block removed per D-08; wake-respond path is the apology channel; reconciler covers structurally-failed wakes (Phase 20 D-11). Verified at `workflow_runner.py:650-668`.

## Manual Smoke Deferral

EVAL-01..03 require operator action against live Ollama and OpenAI backends with LangWatch trace inspection. 21-SMOKE.md template is committed with `verdict: pending`; the operator-driven smoke fills the per-utterance, per-backend table and the explicit go/no-go line per D-15 pivot scaffolding. This deferral is the only outstanding work item for Phase 21 — all code, wiring, schema, prompt, CI guard, dashboard, and grep-gate work is complete and verified in-repo.

Phase 20's deferred Telegram smoke is independently outstanding (carried forward from prior phase) and not blocking Phase 21 code merge.

## Anti-Patterns

No blocker or warning anti-patterns. All grep matches for legacy terms are either (a) explicit regression-guard test assertions or (b) historical comments documenting intentional removal — both legitimate per goal-backward analysis.

## Gaps Summary

No code gaps. All 6 must-haves verified in code. The only outstanding work is the operator smoke verdict, which is intentionally scoped as a manual checkpoint and is the reason this phase carries `human_needed` (expected, per phase context).

---

_Verified: 2026-05-19_
_Verifier: Claude (gsd-verifier, goal-backward)_
