---
phase: 07-handle-incoming-message-agent
plan: "03"
subsystem: agent
tags: [prompt, skill, markdown, household-manager, routing]

# Dependency graph
requires:
  - phase: 07-01
    provides: queue.py and start_workflow.py tools that the routing prompt references
provides:
  - "Updated household-manager/shared.md with auth section removed"
  - "Updated household-manager/index.md with auth reference removed from preamble"
  - "Robotina routing agent prompt at prompts/robotina/V001.md"
affects:
  - 07-04 (handle-incoming-message agent wiring)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Routing prompt uses tool discovery (start-workflow description) instead of hardcoding workflow keys — Pitfall 4"
    - "Skill shared.md scoped to API conventions only; auth handled entirely by the tool layer"

key-files:
  created:
    - src/robotina/agent/prompts/robotina/V001.md
  modified:
    - src/robotina/agent/skills/household-manager/shared.md
    - src/robotina/agent/skills/household-manager/index.md

key-decisions:
  - "Routing prompt does NOT enumerate workflow type names — agent discovers available types from start-workflow tool description (Pitfall 4 avoidance)"
  - "shared.md auth section fully removed; tool layer (household-manager-api) handles auth transparently"

patterns-established:
  - "Routing prompt pattern: Role → Routing section (direct-reply vs workflow) → Instructions → Critical Rules → Failure Modes to Avoid"

requirements-completed:
  - ROBOT-05
  - ROBOT-06
  - ROBOT-07

# Metrics
duration: 5min
completed: 2026-03-27
---

# Phase 7 Plan 03: Handle Incoming Message Agent — Skill Update and Routing Prompt

**Household-manager skill cleaned of auth scaffolding and Robotina routing prompt created with queue/start-workflow disambiguation**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-27T20:30:00Z
- **Completed:** 2026-03-27T20:35:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Removed Authentication section from household-manager/shared.md (tool handles auth transparently)
- Removed 401 and 403 rows from error codes table in shared.md
- Updated index.md preamble and file table to reflect auth-free skill
- Created prompts/robotina/V001.md with routing principle: `queue` for direct replies, `start-workflow` for multi-step workflows
- Prompt includes concrete examples for both paths and does not leak workflow key names

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite household-manager/shared.md (remove auth) + update index.md** - `f0045ab` (feat)
2. **Task 2: Create robotina/V001.md routing prompt** - `875d20d` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/robotina/agent/skills/household-manager/shared.md` - Removed Authentication section and 401/403 error rows; kept Base URL, Error codes, Error response shape, Pagination, Filtering reference lists
- `src/robotina/agent/skills/household-manager/index.md` - Updated preamble line 5 and shared.md file table description
- `src/robotina/agent/prompts/robotina/V001.md` - New routing agent system prompt; Role, Routing section, Instructions, Critical Rules, Failure Modes to Avoid

## Decisions Made
- Routing prompt does NOT enumerate workflow type names — the agent reads available types from the `start-workflow` tool description at runtime (avoids Pitfall 4: prompt-tool divergence when workflow registry changes)
- shared.md auth section fully removed; `household-manager-api` tool injects the Authorization header transparently, so the agent never needs to know about tokens

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 07-03 content deliverables complete: clean skill and routing prompt ready
- Plan 07-04 can now wire the handle-incoming-message agent using prompts/robotina/V001.md
- No blockers

---
*Phase: 07-handle-incoming-message-agent*
*Completed: 2026-03-27*

## Self-Check: PASSED

- FOUND: src/robotina/agent/skills/household-manager/shared.md
- FOUND: src/robotina/agent/skills/household-manager/index.md
- FOUND: src/robotina/agent/prompts/robotina/V001.md
- FOUND: .planning/phases/07-handle-incoming-message-agent/07-03-SUMMARY.md
- FOUND commit f0045ab: feat(07-03): remove auth from household-manager skill
- FOUND commit 875d20d: feat(07-03): create robotina routing agent prompt V001
