---
phase: 22-multi-recipe-per-message-topic-1
plan: 02
subsystem: agent-prompt
tags: [prompt, agent-registry, multi-recipe, over-cap, ambiguity, V006]
requires:
  - V005.md (retained for rollback per D-16)
  - StartWorkflowTool multi-call surface (Phase 21 D-03/D-04)
  - RespondTool non-terminal (Phase 21 D-01)
  - TerminateTool terminal (Phase 21 D-02)
provides:
  - V006 Robotina prompt with multi-recipe extraction, ambiguity handling, over-cap ask-to-split, expanded wake-reply worked examples
  - handle-incoming-message agent now loads V006.md
  - Registry assertion locked to V006.md
affects:
  - All future handle-incoming-message invocations (production + experiments)
tech-stack:
  added: []
  patterns:
    - prompt-fork verbatim then insert (V001..V005 → V006)
    - Spanish user-facing payloads, English prompt body (memory feedback_prompts_language)
key-files:
  created:
    - src/robotina/agent/prompts/robotina/V006.md
  modified:
    - src/robotina/agent/agents.py
    - tests/agents/test_agent_registry.py
decisions:
  - D-09 V006 = V005 + multi-recipe extraction + ambiguity-via-respond + over-cap ask-to-split
  - D-01 over-cap N>5 handled at prompt level (no defensive code cap)
  - D-10 ambiguity uses respond()+terminate() (no new ask_user tool)
  - D-11 compound dishes prefer FEWER workflows (1 workflow with compound name)
  - D-12 sauce-on-recipe is 1 workflow ("y" inside noun phrase is not a list separator)
  - D-16 V005 retained untouched for rollback
metrics:
  duration_seconds: 161
  completed: 2026-05-20
  tasks_completed: 2
  files_touched: 3
requirements_progress:
  - BATCH-01 (prompt teaches N start-workflow calls per multi-recipe message — pending Wave 2 eval validation)
  - BATCH-02 (prompt teaches ONE pre-batch respond ack — pending Wave 2 eval validation)
  - BATCH-05 (prompt teaches over-cap ask-to-split — pending Wave 2 eval validation)
---

# Phase 22 Plan 02: Robotina V006 prompt fork (multi-recipe / ambiguity / over-cap) Summary

V006 forks V005 verbatim, adds multi-recipe extraction worked examples (N=1, N=3),
recipe-boundary anti-patterns (sauce-on-recipe, compound dish, English noun-phrases),
ambiguity rule with URL deflection, over-cap ask-to-split for N>5, and four expanded
wake-context reply worked examples (single-success, multi-success, partial-failure,
all-failure). agents.py registry bumped from V005 → V006; test assertion bumped to
match. V005.md retained untouched for rollback.

## What was done

### Task 1 — Fork V005 to V006 (commit fe56902)

Created `src/robotina/agent/prompts/robotina/V006.md` (208 lines, well above the
≥140 floor). Preserved V005's Role / Inputs / Tools / Strict Output Rule / Process /
User-message turns / Rules / Forbidden behaviors / Language rule / Output sections.

Added new sections:

- **Multi-recipe extraction** — explains N-call fan-out, ordering, ≤5 cap, mandatory
  single pre-batch `respond()`. Includes N=1 and N=3 happy-path worked examples
  (all `respond()` payloads in Argentine Spanish).
- **Recipe-boundary rules (anti-patterns)** — sauce-on-recipe, compound dish,
  English noun-phrases, multi-word names. Each as 1 workflow, not split.
- **Ambiguity rule** — `respond(clarify) + terminate()`, zero workflows. Includes
  URL-deflection example (Phase 22 explicitly does NOT teach URL handling — Phase 23 scope).
- **Over-cap (more than 5 recipes)** — `respond("Son muchas recetas a la vez...") + terminate()`, zero `start-workflow` calls. Worked example with 7-recipe utterance.
- **Wake-context replies — worked examples** — four scenarios in order: single-success,
  multi-success (3 recipes), partial-failure (2 done, 1 failed — BATCH-04 mitigation),
  all-failure (2 failed). All payloads in Spanish, all preserve preamble order, all use
  ONE consolidated `respond()` then `terminate()`. Includes a closing rule about
  surfacing `Workflow start failed` results naturally.

V005.md untouched (`git diff src/robotina/agent/prompts/robotina/V005.md` empty —
verified before commit).

### Task 2 — Bump agents.py to V006 + flip registry test (commits 82ea495, 0d28ef3)

TDD flow:

1. **RED** (82ea495): Renamed `test_handle_incoming_message_uses_v005` →
   `test_handle_incoming_message_uses_v006` and flipped the assertion to
   `prompt_path.endswith("V006.md")`. Confirmed RED:
   `AssertionError: handle-incoming-message prompt_path is '...V005.md', expected to end with V006.md`.
2. **GREEN** (0d28ef3): One-line edit in `src/robotina/agent/agents.py`:
   `prompt_path="src/robotina/agent/prompts/robotina/V005.md"` →
   `prompt_path="src/robotina/agent/prompts/robotina/V006.md"`. Also cleaned the
   `tests/agents/test_agent_registry.py` module-level docstring to reflect the
   Phase 22 bump (previously listed Phase 21 D-10's V004→V005 bump). All 3 tests
   in `tests/agents/test_agent_registry.py` pass.

Other V005.md references in `agents.py` (lines 97, 153 — recipe-research-gather and
recipe-load prompts) are unrelated to this plan and were left untouched, as required.

## Verification

- `uv run pytest tests/agents/test_agent_registry.py -x -q` → 3 passed
- `uv run pytest tests/agents/ -q` → 7 passed
- All Task 1 acceptance grep checks pass (Multi-recipe extraction, Over-cap section,
  Spanish over-cap text, all three anti-pattern names, Ambiguity rule, all three new
  wake worked-example anchor strings, URL deflection)
- V005.md unchanged (`git diff` empty)
- V006.md = 208 lines (≥140 required)
- `grep -c 'V005.md' src/robotina/agent/agents.py` = 2 (both are unrelated
  recipe-research-gather and recipe-load entries, not handle-incoming-message)
- `grep -c 'V006.md' src/robotina/agent/agents.py` = 1 (handle-incoming-message)
- `grep -c 'def test_handle_incoming_message_uses_v006' tests/agents/test_agent_registry.py` = 1
- `grep -c 'def test_handle_incoming_message_uses_v005' tests/agents/test_agent_registry.py` = 0

The `grep -c 'V005.md' tests/agents/test_agent_registry.py` returns 2 — both are in
comments/docstrings (the module docstring mentions "from V005.md to V006.md" and the
test function docstring does the same). Neither is an assertion on `prompt_path`. The
acceptance criterion's intent ("no V005 ASSERTION on prompt_path") is met.

## Deviations from Plan

None. Plan executed exactly as written. The cleanup of the module-level docstring in
`tests/agents/test_agent_registry.py` (removing stale Phase 21 D-10/D-20 wording in
favor of a Phase 22 reference) is a tidy-as-you-go edit within the file the plan
already authorized to modify, not a deviation.

## Authentication Gates

None.

## Known Stubs

None. V006 is a complete prompt that the production registry now points at. The
load-bearing acceptance for BATCH-01/02/05 is the eval set (Wave 2 / plan 22-03+),
which validates the LLM actually follows the new V006 instructions — but the V006
prompt itself is not a stub.

## Out-of-Scope Findings (Deferred)

- The full pytest suite (`uv run pytest -x`) hit pre-existing infrastructure
  failures unrelated to this plan: `tests/dashboard/test_detail_view.py`
  fails with `psycopg2.OperationalError: password authentication failed for user "robotina"`
  because Postgres is not running locally. This is a pre-existing environment
  state, not a regression introduced by Plan 22-02. Logged here per the scope
  boundary rule (only auto-fix issues directly caused by current task changes).

## Self-Check: PASSED

Verified:
- `src/robotina/agent/prompts/robotina/V006.md` FOUND
- `src/robotina/agent/prompts/robotina/V005.md` FOUND (unchanged — `git diff` empty)
- Commit fe56902 FOUND (V006 creation)
- Commit 82ea495 FOUND (RED test)
- Commit 0d28ef3 FOUND (GREEN — agents.py bump)
