---
phase: 10-langchain-1-x-agent-api-migration
plan: 03
subsystem: agent-infrastructure
tags: [langchain, langchain-agents, langgraph, create_agent, documentation, decision-record, agent-12, end-to-end, telegram, langwatch]

# Dependency graph
requires:
  - phase: 10-langchain-1-x-agent-api-migration
    provides: "Plan 02: all three LLMBackend adapters migrated to langchain.agents.create_agent via the _create_agent self-recursion-guard alias; four real-agent parity test files migrated; return_direct + strict-args parity preserved; 148 non-integration tests green"
provides:
  - "CLAUDE.md tech-stack tables, Alternatives Considered table polarity, What NOT to Use entry, Confidence Notes row, and Sources line all reflect LangChain 1.x agent API (langchain.agents.create_agent) as the recommended path"
  - "STATE.md line 130 records AGENT-11/D-03 superseded by AGENT-12 in Phase 10 with parity verification noted"
  - "PROJECT.md Key Decisions table has a new — Active row recording the create_agent migration with rationale linking to Phases 11 and 12"
  - ".planning/decisions/agent-12-migrate-to-create-agent.md exists mirroring the switch-to-simple-worker.md section layout (Context / What X buys us / Why those benefits don't apply here / Proposed change / Files to change / Risk)"
  - "AGENT-12 flipped to [x] in REQUIREMENTS.md and traceability row updated In Progress -> Complete"
  - "REQUIREMENTS.md footer last-updated marker updated to reflect Phase 10 completion"
  - "Phase 10 success criterion 4 closed: end-to-end add-recipe Telegram workflow runs to completion under langchain.agents.create_agent with no semantic regression (manually verified by user 2026-05-13)"
affects: [11-structured-agent-output-via-response-format, 12-middleware-based-agent-instrumentation, AGENT-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Post-checkpoint atomic marking: AGENT-12 traceability row and checkbox are flipped in a SINGLE post-checkpoint task (3.3) with a dedicated commit — keeps the audit trail clean (the requirement state changed exactly once at the verification gate, not during code migration)"
    - "Decision-record mirror pattern: new .planning/decisions/agent-12-migrate-to-create-agent.md follows the established switch-to-simple-worker.md section layout verbatim, including the 'What X actually buys us' / 'Why those benefits do not apply here' inversion structure"

key-files:
  created:
    - .planning/decisions/agent-12-migrate-to-create-agent.md
  modified:
    - CLAUDE.md
    - .planning/STATE.md
    - .planning/PROJECT.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "AGENT-12 marked Complete only AFTER the manual end-to-end Telegram verification, never during code migration — the requirement contract is gated on real production behavior, not on unit tests passing"
  - "REQUIREMENTS.md last-updated footer date is 2026-05-12 (phase completion date per plan), even though the final commit lands on 2026-05-13 — the plan-as-written specified the user-visible completion date"
  - "Tangential pydantic schema fix (commit 19b3b9d — RecipeStep/RecipeIngredient/RecipeData optional fields with = None defaults) is OUT OF SCOPE for Plan 10-03. It surfaced during the Task 3.2 end-to-end checkpoint when the LLM omitted null-valued fields, but the root cause is a pre-existing schema bug unrelated to the create_agent migration. Tracked as quick task 260512-pyd"

patterns-established:
  - "Checkpoint-gated requirement completion: the 'AGENT-12 marked complete' edit lives in a SEPARATE post-checkpoint task from the docs rollover. The docs (CLAUDE.md, STATE.md, PROJECT.md, decision record) can land before verification; the REQUIREMENTS.md flip only lands after the human verifies end-to-end behavior"

requirements-completed:
  - AGENT-12

# Metrics
duration: ~30min (across 3 calendar days — Task 3.1 + 3.2 setup 2026-05-12, human verification 2026-05-13)
completed: 2026-05-13
---

# Phase 10 Plan 03: CLAUDE.md / STATE.md / PROJECT.md / Decision Record + End-to-End Checkpoint + AGENT-12 Completion Summary

**Rolled over CLAUDE.md, STATE.md, PROJECT.md, and created the AGENT-12 decision record; the human end-to-end Telegram verification (Task 3.2) succeeded against a live add-recipe run; AGENT-12 is now marked complete in REQUIREMENTS.md. Phase 10 migration is functionally complete — LangChain 1.x `langchain.agents.create_agent` is the active agent API surface across all three LLMBackend adapters.**

## Performance

- **Duration:** ~30 min across 3 days (docs rollover + decision record committed 2026-05-12; manual end-to-end Telegram verification + AGENT-12 completion commit 2026-05-13)
- **Tasks:** 3 of 3 (Task 3.1 auto, Task 3.2 human-verify checkpoint APPROVED, Task 3.3 post-checkpoint auto)
- **Files modified:** 4 (CLAUDE.md, STATE.md, PROJECT.md, REQUIREMENTS.md)
- **Files created:** 1 (.planning/decisions/agent-12-migrate-to-create-agent.md)

## Accomplishments

- **CLAUDE.md rolled over to LangChain 1.x stance** (Task 3.1):
  - Core Technologies table: LangChain row bumped to `langchain>=1.2`, `langchain-core>=1.2`, repurposed as "Agent orchestration via `langchain.agents.create_agent`"; langgraph row demoted to `>=1.0` with the rationale "Underlying graph engine for `create_agent` ... not the agent API surface anymore."
  - Alternatives Considered table: the `LangGraph create_react_agent` row polarity inverted — `langchain.agents.create_agent` is now the recommended path; `create_react_agent` is the alternative-to-never-use, noting the V1.0 deprecation / V2.0 removal trajectory.
  - What NOT to Use table: new row added beneath `AgentExecutor` for `langgraph.prebuilt.create_react_agent`, pointing readers to `langchain.agents.create_agent`.
  - Confidence Notes: row title updated to "LangChain package split (core / langgraph / agents)" with the empirical verification note ("verified empirically against installed `langchain 1.2.13`, 2026-05-12").
  - Sources section: the old "moved to `langgraph.prebuilt` in LangChain 0.2+" line replaced with the new "LangChain 1.x agent API: `create_agent` lives in `langchain.agents` as of LangChain 1.x; `langgraph.prebuilt.create_react_agent` is the prior-generation API that this project migrated away from in Phase 10."

- **STATE.md line 130 rewritten** (Task 3.1): the old AGENT-11/D-03 decision-log entry "Use create_react_agent from langgraph.prebuilt despite LangGraphDeprecatedSinceV10 warning — locked per AGENT-11/D-03, API remains functional in v1.1.3" was replaced with "AGENT-11/D-03 superseded in Phase 10 by AGENT-12 — all agents now use `langchain.agents.create_agent` (LangGraph V1.0 deprecation; removal in V2.0). Behavior parity (return_direct, state shape, callbacks) verified during Phase 10."

- **PROJECT.md Key Decisions table** (Task 3.1) gained a new row: "`create_agent` from `langchain.agents` is used for all agents" with rationale linking to Phase 11 (`response_format`) and Phase 12 (middleware) and status `— Active`.

- **New decision record file created** (Task 3.1): `.planning/decisions/agent-12-migrate-to-create-agent.md` mirrors the section layout of `switch-to-simple-worker.md` — Context / What `create_react_agent` actually buys us / Why those benefits don't apply here / Proposed change / Files to change / Risk. Content lifted verbatim from `10-RESEARCH.md` "AGENT-11 / D-03 Decision Record Update" and `10-PATTERNS.md` "Files Touched."

- **Manual end-to-end Telegram add-recipe run APPROVED by user** (Task 3.2, 2026-05-13): the human verification checkpoint succeeded. The full workflow (acknowledge-add-recipe → recipe-research sub-agents → recipe-load → send-notification) ran end-to-end on a real Telegram message using the migrated `langchain.agents.create_agent` factory. The final recipe confirmation reached the user via Telegram. LangWatch traces appeared in the configured collection. No `LangGraphDeprecatedSinceV10` warnings in worker logs. **This closes Phase 10 success criterion 4** (end-to-end add-recipe workflow runs to completion on at least one real recipe query with no semantic regression versus the pre-migration baseline) and locks down Assumption A1 from RESEARCH.md (LangWatch trace delivery under the new factory).

- **AGENT-12 flipped to checked / Complete in REQUIREMENTS.md** (Task 3.3):
  - The Agent Infrastructure bullet went from `[ ] AGENT-12` to `[x] AGENT-12`.
  - The traceability row went from `| AGENT-12 | Phase 10 | In Progress |` to `| AGENT-12 | Phase 10 | Complete |`.
  - The footer last-updated marker was updated from "2026-03-25 after roadmap creation" to "2026-05-12 after Phase 10 — added AGENT-12 (LangChain 1.x agent API migration), marked AGENT-11 superseded."

- **Phase-level test suite is green:** `uv run pytest -q -m "not integration" --deselect tests/test_pyproject.py::test_experiment_mains_importable` → **148 passed, 15 deselected**. (The deselected test is the pre-existing `tests/test_pyproject.py::test_experiment_mains_importable` env-pollution case documented in Plan 10-02's summary; orthogonal to this plan.)

- **Grep-zero intent holds:** `grep -rn "create_react_agent\|langgraph.prebuilt" src/ tests/ experiments/ | grep -v "tests/unit/test_llm_backend.py" | wc -l` → **0**. The five remaining literal matches under `tests/unit/test_llm_backend.py` are all load-bearing assertion strings inside the source-grep lock test `test_create_agent_used_not_agent_executor` — see Plan 10-02 Summary's "Lock-test exemption" decision.

## Task Commits

Each task was committed atomically on branch `use-new-agent-version`:

1. **Task 3.1: Update CLAUDE.md, STATE.md, PROJECT.md, and create the decision record file** — `705f511` (`docs`)
2. **Task 3.2: Manual end-to-end add-recipe Telegram run (checkpoint)** — APPROVED by user 2026-05-13. No commit (user-driven verification only). See note below on tangential commit `19b3b9d`.
3. **Task 3.3: Mark AGENT-12 complete in REQUIREMENTS.md** — `386374b` (`docs`)

**Plan metadata:** to be added in the final docs commit below (this SUMMARY.md + STATE.md + ROADMAP.md).

### Note on tangential commits between Task 3.1 and Task 3.3

While running the Task 3.2 end-to-end Telegram verification on 2026-05-12, the LLM produced a recipe payload that omitted null-valued optional fields on `RecipeStep`, `RecipeIngredient`, and `RecipeData`. Pydantic v2 rejected the payload with `ValidationError: field required` because those optional fields had no `= None` defaults. **This is a pre-existing latent bug in the Pydantic schemas, exposed by an LLM model swap — not caused by the LangChain 1.x migration.** It was fixed inline as a separate quick task to unblock the end-to-end verification, and tracked as:

- `19b3b9d` (`fix`) — `fix: make optional RecipeData fields truly optional with = None defaults`
- `47e0ac9` (`chore`) — `chore: log RecipeData optional-field fix in STATE.md quick-tasks table` (registered as quick task `260512-pyd`)

These two commits **are not part of Plan 10-03's scope** (they touch `src/robotina/queue/task_types.py`, not the four files Plan 10-03 modifies) but they are mentioned here for full audit-trail clarity: the end-to-end verification of Task 3.2 required them to succeed.

## Files Created/Modified

- `CLAUDE.md` — Core Technologies table: LangChain + langgraph rows rewritten. Alternatives Considered: polarity row inverted. What NOT to Use: new `langgraph.prebuilt.create_react_agent` row added. Confidence Notes: package-split row updated. Sources: line 141 rewritten to reflect LangChain 1.x.
- `.planning/STATE.md` — line 130 (AGENT-11/D-03 decision log entry) rewritten to mark supersession by AGENT-12 in Phase 10.
- `.planning/PROJECT.md` — new Key Decisions row appended documenting the create_agent migration with — Active status.
- `.planning/decisions/agent-12-migrate-to-create-agent.md` — CREATED. Mirrors switch-to-simple-worker.md section layout. Content sourced from 10-RESEARCH.md and 10-PATTERNS.md.
- `.planning/REQUIREMENTS.md` — AGENT-12 checkbox flipped `[ ]` → `[x]`; traceability row updated to `Complete`; footer last-updated marker updated.

## Decisions Made

- **AGENT-12 completion is gated on real production behavior, not on unit tests.** The `[x]` mark in REQUIREMENTS.md was deliberately deferred to Task 3.3 (post-checkpoint) — the unit-test parity proven in Plan 10-02 was insufficient to declare the contract complete. The end-to-end Telegram run with LangWatch trace delivery is what closes the requirement.

- **Footer last-updated date follows the plan-as-written (2026-05-12), not the commit date (2026-05-13).** The plan specified `2026-05-12 after Phase 10` verbatim. Leaving it as 2026-05-12 keeps the file consistent with the rest of the documentation that landed in commit `705f511`.

- **The pydantic optional-field fix (commit 19b3b9d) is OUT OF SCOPE for Plan 10-03.** It is a pre-existing latent schema bug unrelated to the create_agent migration. The migration itself is sound — verified by the fact that once the orthogonal schema fix landed, the same Plan 10-02 migrated code ran the full workflow end-to-end without further changes. The bug surfaced because a different LLM (during the verification run) omitted null-valued fields the previous model had included; either model is valid per the (now-fixed) schema.

## Deviations from Plan

### Auto-fixed Issues

None during Task 3.3. Task 3.1's deviations (if any) are documented in commit `705f511`'s body.

### Out-of-Scope Discoveries (handled as quick tasks, not deviations)

**1. Pre-existing pydantic optional-field bug exposed by end-to-end verification**

- **Found during:** Task 3.2 end-to-end Telegram add-recipe run (2026-05-12)
- **Issue:** `RecipeStep.title`, several `RecipeIngredient` fields, and several `RecipeData` fields were declared as `Optional[...]` without `= None` defaults. Pydantic v2 treats `Optional[X]` without a default as required. When the LLM omitted these null-valued fields in its recipe payload, Pydantic raised `ValidationError: field required` and the workflow halted.
- **Root cause:** Latent schema bug from earlier phases (Phase 8 or 9, before the Pydantic v2 strictness was fully understood). Unrelated to Phase 10.
- **Resolution:** Fixed inline in commit `19b3b9d` as quick task `260512-pyd`; logged in STATE.md quick-tasks table in commit `47e0ac9`.
- **Why this is not a Plan 10-03 deviation:** The fix touches `src/robotina/queue/task_types.py`, not any of the four files Plan 10-03 modifies. It is the pre-existing class of bug that any model-swap (not specific to create_agent) could expose. Plan 11 (response_format / structured output) is the planned long-term mitigation for this class of failure.

---

**Total deviations:** 0 within Plan 10-03 scope. 1 out-of-scope discovery handled as a quick task (commit `19b3b9d` + STATE update commit `47e0ac9`).

## Issues Encountered

- **End-to-end Telegram verification briefly blocked by the pydantic optional-field bug** described above. The blocker was resolved by a 5-minute inline schema fix (committed as quick task `260512-pyd` / `19b3b9d`). After the fix, the user re-ran the end-to-end add-recipe flow and approved Task 3.2 on 2026-05-13.

- **No `LangGraphDeprecatedSinceV10` warnings observed in worker logs during the end-to-end verification** — confirming Plan 10-02's source migration was complete and no stale `create_react_agent` call sites remained at runtime.

## User Setup Required

None — this plan only requires the user to have:
1. The local Docker stack (Postgres + Redis) running for the Task 3.2 end-to-end verification (already in place).
2. A Telegram bot configured against the staging or local-tunnel gateway (already in place).
3. LangWatch credentials in env (already in place from earlier phases).

All three were already present from prior phases; no new setup was introduced by Plan 10-03.

## Phase 10 Final Verification (closing all 5 success criteria)

1. **All three LLMBackend adapters use `langchain.agents.create_agent`** ✓ (Plan 10-02 Task 2.1 / commit `ecdfa02`)
2. **`return_direct=True` short-circuit preserved** ✓ (Plan 10-02 Task 2.2 — renamed parity tests `test_queue_tool_short_circuits_create_agent` + `test_start_workflow_tool_short_circuits_create_agent` both green)
3. **All four real-agent test files use `create_agent`; `uv run pytest` green** ✓ (Plan 10-02 Task 2.2/2.3 — 148 passed in non-integration suite; lock test green)
4. **End-to-end add-recipe workflow runs to completion with no semantic regression** ✓ (Plan 10-03 Task 3.2 — APPROVED by user 2026-05-13)
5. **CLAUDE.md reflects LangChain 1.x as the agent API surface** ✓ (Plan 10-03 Task 3.1 — 6 edits landed: Core Technologies, Alternatives Considered, What NOT to Use, Confidence Notes, Sources)

**Phase 10 is functionally complete.** Plans 11 and 12 are unblocked.

## Telegram message + LangWatch trace context

- **Telegram message used:** A real recipe-add request issued by the user from the household Telegram chat. Exact wording not recorded (it was a live user-initiated message, not a scripted test fixture).
- **LangWatch trace URL:** Not captured in the plan output — the trace was visually verified by the user against the configured LangWatch project. Per Task 3.2's `how-to-verify` section, the pass criterion was "a trace appears in the correct collection with spans for each agent invocation" — which the user confirmed before issuing the `approved` resume signal.

## TDD Gate Compliance

Not applicable — Plan 10-03 is type `execute`. The plan-level lock-test pattern from Plan 10-01 (RED) → Plan 10-02 (GREEN) was satisfied at the Plan 10-02 boundary. Plan 10-03 is documentation rollover + manual verification gate, neither of which is TDD-shaped.

## Self-Check: PASSED

Files verified to exist on disk:
- `CLAUDE.md` — FOUND (6 LangChain 1.x edits landed in commit `705f511`)
- `.planning/STATE.md` — FOUND (line 130 rewritten in commit `705f511`)
- `.planning/PROJECT.md` — FOUND (Key Decisions row added in commit `705f511`)
- `.planning/decisions/agent-12-migrate-to-create-agent.md` — FOUND (created in commit `705f511`)
- `.planning/REQUIREMENTS.md` — FOUND (AGENT-12 marked complete in commit `386374b`)
- `.planning/phases/10-langchain-1-x-agent-api-migration/10-03-SUMMARY.md` — FOUND (this file)

Commits verified to exist in git history:
- `705f511` (Task 3.1) — FOUND
- `386374b` (Task 3.3) — FOUND
- `19b3b9d` (out-of-scope pydantic fix, listed for audit trail) — FOUND
- `47e0ac9` (out-of-scope STATE.md quick-task log, listed for audit trail) — FOUND

Plan-level verification (from `<verification>` block of 10-03-PLAN.md):
1. **CLAUDE.md tech-stack tables (5 grep gates)** — all match: `langchain>=1.2` (1), `langgraph | >=1.0` cell (1), inverted Alternatives Considered row (1), new What NOT to Use row (1), package-split confidence row (1) ✓
2. **CLAUDE.md Sources section line rewritten (2 grep gates)** — presence of new wording (1) and absence of old wording (0) ✓
3. **STATE.md line 130 rewritten (1 grep gate)** — `grep -c "AGENT-11/D-03 superseded in Phase 10 by AGENT-12" .planning/STATE.md` → 1 ✓
4. **PROJECT.md Key Decisions row added (1 grep gate)** — `grep -c "create_agent from langchain.agents is used for all agents" .planning/PROJECT.md` → 1 ✓
5. **Decision-record file with all 6 sections (7 grep gates)** — file exists; all 6 section headers present ✓
6. **Full test suite green** — `uv run pytest -q -m "not integration" --deselect tests/test_pyproject.py::test_experiment_mains_importable` → **148 passed, 15 deselected** ✓
7. **Human approval of end-to-end Telegram run** — APPROVED 2026-05-13 ✓
8. **AGENT-12 marked complete (3 grep gates)** — checkbox `[x]` (1), traceability `Complete` (1), footer marker (1) ✓

---
*Phase: 10-langchain-1-x-agent-api-migration*
*Plan: 03*
*Completed: 2026-05-13*
