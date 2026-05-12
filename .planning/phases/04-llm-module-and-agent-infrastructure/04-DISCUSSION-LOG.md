# Phase 4: LLM Module and Agent Infrastructure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the discussion.

**Date:** 2026-03-25
**Phase:** 04-llm-module-and-agent-infrastructure
**Mode:** discuss
**Areas discussed:** Skills directory, LangWatch verification depth, Job function location / universal handler, agents.py scaffold depth

---

## Gray Areas Identified

Four genuine gray areas were identified — everything else was locked in the spec, CLAUDE.md, or prior phase context.

| Area | Why it was a gray area |
|------|------------------------|
| Skills directory | Existing household-manager skill at project root `agent/skills/`; spec says `src/agent/skills/` |
| LangWatch verification | Success criterion requires "a trace for a test agent invocation"; STATE.md flagged LangWatch SDK as LOW confidence |
| Job function location | Phase 3 committed to string ref `robotina.queue.jobs.handle_incoming_message`; correct architecture is a universal handler |
| agents.py scaffold depth | Tools (phases 5-9) don't exist yet; unclear how much of the registry to fill in Phase 4 |

---

## Decisions Made

### Skills Directory
- **Decision:** Move `household-manager` from `agent/skills/household-manager/` (project root) to `src/robotina/agent/skills/household-manager/`. Canonical location is `src/robotina/agent/skills/`.
- **Options considered:** Keep at root / configure SkillSet to find both / move to canonical location
- **Chosen:** Move to canonical location

### LangWatch Verification
- **Decision:** Manual verification only — no automated test for LangWatch traces in Phase 4.
- **Options considered:** Live Ollama integration test / OTel span only test / manual verification
- **Chosen:** Manual verification. Developer runs the stack, triggers a hello-world job, checks LangWatch UI.

### Job Function Location — Key Architecture Clarification
- **User clarification:** The architecture has ONE universal handler for all task types. The task runner uses `agents.py` + `workflows.py` to dispatch. Individual job functions per task type are incorrect.
- **Decision:** Create `robotina.queue.jobs.run_task` as the universal RQ job function. Update the gateway to enqueue `"robotina.queue.jobs.run_task"` (fixes the Phase 3 placeholder `handle_incoming_message` string ref).

### agents.py Scaffold Depth
- **Decision:** Config-driven skeleton with one placeholder entry: `"hello-world"` task type. Sends "hello world" to LLM, logs response. Proves the full pipeline end-to-end.
- **User note:** Remove the hello-world placeholder when the first real task (`send-notification`) is added in Phase 6.

---

## No Corrections to Prior Decisions

All locked decisions from Phases 1-3 remain valid for Phase 4.
