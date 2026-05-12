# Phase 7: handle-incoming-message Agent - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the discussion.

**Date:** 2026-03-27
**Phase:** 07-handle-incoming-message-agent
**Mode:** discuss
**Areas discussed:** queue tool interface, household-manager-api tool, Routing prompt strategy, Skill auth update scope

## Gray Areas Presented

| Area | Options Presented |
|------|------------------|
| queue tool interface | Text only / Text + task_type / Structured payload |
| household-manager-api household_id | Constructor injection / Env var at call time |
| Routing prompt strategy | Enumerate workflows by name / General principle only / Intent examples + principle |
| Skill auth update scope | Remove auth section + 401/403 / Remove auth section only / Rewrite shared.md entirely |

## Decisions Made

### queue tool interface
- **Decision:** Text only
- **Rationale:** Covers 100% of Phase 1 use cases; keeps agent interface minimal; consistent with "invisible routing" principle

### household-manager-api tool — household_id sourcing
- **Decision:** Constructor injection from task_input.household_id
- **Rationale:** Consistent with SendNotificationTool pattern; task_input already has the right household_id per-job; keeps agent unaware of household routing

### Routing prompt strategy
- **Decision:** Intent examples + principle
- **Rationale:** Both the general rule (direct vs workflow) AND 2-3 concrete examples per path; best routing accuracy without leaking workflow key names into the prompt

### Skill auth update scope
- **Decision:** Full rewrite of shared.md
- **Rationale:** Remove all auth references and restructure cleanly; keep base URL and recoverable error codes (400, 404, 422, 500); agent will never see 401/403 so no need to advise on them
