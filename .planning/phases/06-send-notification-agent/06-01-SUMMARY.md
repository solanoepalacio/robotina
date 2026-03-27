---
phase: 06-send-notification-agent
plan: 01
subsystem: testing
tags: [pytest, agent-registry, workflows, send-notification, hello-world-cleanup]

requires:
  - phase: 05-task-runner-and-workflow-engine
    provides: WORKFLOW_REGISTRY, AGENT_REGISTRY with hello-world placeholder, test patterns using pytest.skip()

provides:
  - AGENT_REGISTRY with send-notification entry (task_type, model_config, prompt_path, skills, tools)
  - WORKFLOW_REGISTRY without hello-world-2step (add-recipe preserved)
  - 6 Wave 0 stub tests for SendNotificationTool (all SKIPPED, zero FAILED)
  - test_hello_world_removed_from_registry assertion (NOTIF-01)

affects:
  - 06-02 (implements SendNotificationTool — stubs become real tests)
  - 06-03 (creates send-notification/V001.md prompt — test_prompt_file_exists_for_send_notification goes green)
  - 06-04 (experiment script uses send-notification registry entry)

tech-stack:
  added: []
  patterns:
    - "Wave 0 stub tests: pytest.skip() placed BEFORE the import to avoid ImportError on not-yet-existing modules"

key-files:
  created:
    - tests/unit/test_send_notification_tool.py
  modified:
    - src/robotina/agent/agents.py
    - src/robotina/agent/workflows.py
    - tests/unit/test_agents_registry.py
    - tests/unit/test_prompts.py
    - tests/unit/test_agent_runner.py

key-decisions:
  - "pytest.skip() must come before any import in stub functions — placing it after causes ImportError before skip is reached"
  - "3 test_prompts.py failures are expected and intentional — prompt file send-notification/V001.md does not exist until Plan 06-03"

patterns-established:
  - "Stub pattern: pytest.skip() first in function body, import after (unreachable) — prevents ImportError from masking skip"

requirements-completed:
  - NOTIF-01
  - NOTIF-05

duration: 3min
completed: 2026-03-27
---

# Phase 6 Plan 1: Wave 0 Registry Cleanup and Test Stubs Summary

**AGENT_REGISTRY replaced hello-world with send-notification, WORKFLOW_REGISTRY stripped hello-world-2step, and 6 SendNotificationTool stub tests created with correct skip-before-import pattern**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-27T15:57:26Z
- **Completed:** 2026-03-27T16:00:00Z
- **Tasks:** 3
- **Files modified:** 5 (3 test files updated, 2 source files updated, 1 test file created)

## Accomplishments
- Replaced hello-world placeholder in AGENT_REGISTRY with send-notification entry (skills: format-telegram-message, SEND_NOTIFICATION_API_TOKEN, prompt V001.md)
- Removed hello-world-2step test scaffold from WORKFLOW_REGISTRY; add-recipe workflow preserved intact
- Created 6 Wave 0 stub tests for SendNotificationTool that collect as SKIPPED (zero FAILED, zero ERROR)
- Updated 3 existing test files to use send-notification instead of hello-world; added test_hello_world_removed_from_registry asserting KeyError

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test_send_notification_tool.py stubs** - `8a5e8c7` (test)
2. **Task 2: Update registry files — remove hello-world, add send-notification** - `c884d48` (feat)
3. **Task 3: Update existing tests — replace hello-world references with send-notification** - `6edc4c0` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `tests/unit/test_send_notification_tool.py` - 6 Wave 0 stub tests for NOTIF-04 behaviors; all SKIPPED
- `src/robotina/agent/agents.py` - AGENT_REGISTRY replaced hello-world with send-notification; module docstring updated
- `src/robotina/agent/workflows.py` - WORKFLOW_REGISTRY: hello-world-2step removed; module docstring updated
- `tests/unit/test_agents_registry.py` - All 5 tests updated to use send-notification; new test_hello_world_removed_from_registry added
- `tests/unit/test_prompts.py` - test_prompt_file_exists_for_send_notification (renamed); skill_index test updated to use send-notification registry key
- `tests/unit/test_agent_runner.py` - task_type updated to send-notification in test_run_task_reads_task_type_from_job_meta

## Decisions Made
- `pytest.skip()` must be placed BEFORE the import in stub functions — placing it after causes ImportError before the skip is reached, resulting in FAILED instead of SKIPPED
- 3 test_prompts.py failures (test_prompt_file_exists_for_send_notification, test_prompt_loaded_from_agent_config_path, test_skill_index_appended_to_prompt) are expected and intentional; the send-notification/V001.md prompt file doesn't exist yet — Plan 06-03 creates it

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Moved pytest.skip() before import to fix FAILED instead of SKIPPED**
- **Found during:** Task 1 (Create test_send_notification_tool.py stubs)
- **Issue:** Plan template showed import before pytest.skip(); when the module doesn't exist, ImportError is raised before skip is reached, causing FAILED not SKIPPED
- **Fix:** Reversed order — pytest.skip() first in function body, import after (unreachable) — consistent with the intent documented later in the plan's IMPORTANT note
- **Files modified:** tests/unit/test_send_notification_tool.py
- **Verification:** All 6 stubs collect as SKIPPED with zero FAILED
- **Committed in:** 8a5e8c7 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug in stub order)
**Impact on plan:** Fix necessary for correct SKIPPED behavior. No scope creep.

## Issues Encountered
- test_prompts.py: 3 tests now fail because send-notification/V001.md does not exist. This is acceptable per plan — Plan 06-03 creates the prompt file and these tests should go green then.

## Known Stubs
- `tests/unit/test_send_notification_tool.py` (all 6 functions) — stub tests for SendNotificationTool; will be implemented in Plan 06-02

## Next Phase Readiness
- AGENT_REGISTRY and WORKFLOW_REGISTRY are clean: send-notification registered, hello-world scaffolding removed
- Plan 06-02 can implement SendNotificationTool and run_task() injection; stubs are ready to become real tests
- Plan 06-03 must create src/robotina/agent/prompts/send-notification/V001.md to fix 3 test_prompts.py failures

## Self-Check: PASSED

- FOUND: tests/unit/test_send_notification_tool.py
- FOUND: src/robotina/agent/agents.py
- FOUND: src/robotina/agent/workflows.py
- FOUND: .planning/phases/06-send-notification-agent/06-01-SUMMARY.md
- FOUND: commit 8a5e8c7 (Task 1)
- FOUND: commit c884d48 (Task 2)
- FOUND: commit 6edc4c0 (Task 3)

---
*Phase: 06-send-notification-agent*
*Completed: 2026-03-27*
