# Roadmap: Robotina

## Milestones

- ✅ **v1.0 MVP** — Phases 1–16 + decimal 07.1 (shipped 2026-05-18)
- 📋 **v1.1 (next)** — Recipe input modalities (shared link + related), Scheduler track (planned)

See `.planning/MILESTONES.md` for shipped-milestone details.
See `.planning/milestones/v1.0-ROADMAP.md` for the full v1.0 phase detail at close.

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–16 + 07.1) — SHIPPED 2026-05-18</summary>

- [x] Phase 1: Developer Tooling and Infrastructure (3/3 plans)
- [x] Phase 2: Database Models and Queue Layer (3/3 plans)
- [x] Phase 3: Gateway (3/3 plans)
- [x] Phase 4: LLM Module and Agent Infrastructure (6/6 plans)
- [x] Phase 5: Task Runner and Workflow Engine (5/5 plans)
- [x] Phase 6: send-notification Agent (4/4 plans)
- [x] Phase 7: handle-incoming-message Agent (4/4 plans)
- [x] Phase 07.1 (INSERTED): Deterministic Agent Termination (3/3 plans)
- [x] Phase 8: recipe-research Agent (4/4 plans)
- [x] Phase 9: recipe-load Agent and End-to-End Integration (2/2 plans)
- [x] Phase 10: LangChain 1.x Agent API Migration (3/3 plans)
- [x] Phase 11: Structured Agent Output via response_format (4/4 plans)
- [x] Phase 12: Middleware-Based Agent Instrumentation (2/2 plans)
- [x] Phase 13: Queue Visibility Dashboard (3/3 plans)
- [x] Phase 14: Prompt Cleanup and Structural Standardization (8/8 plans)
- [x] Phase 15: Recipe Artifact Accumulation and Food/Unit Validation (6/6 plans)
- [x] Phase 16: Fix empty-string household_id propagation (7/7 plans)

</details>

### 📋 v1.1 (Planned)

Next-milestone phases will be defined via `/gsd:new-milestone`. Known intent:

- Shared-link recipe ingestion ("agregá esta receta: <url>") + related recipe-input modalities
- Scheduler track (carried over from v1.0): scheduled-tasks queue + worker, RQ cron / `enqueue_at`, scheduler tool, Scheduler HTTP API

## Progress

| Phase                                            | Milestone | Plans | Status   | Completed  |
| ------------------------------------------------ | --------- | ----- | -------- | ---------- |
| 1. Developer Tooling and Infrastructure          | v1.0      | 3/3   | Complete | 2026-03-25 |
| 2. Database Models and Queue Layer               | v1.0      | 3/3   | Complete | 2026-03-25 |
| 3. Gateway                                       | v1.0      | 3/3   | Complete | 2026-03-26 |
| 4. LLM Module and Agent Infrastructure           | v1.0      | 6/6   | Complete | 2026-03-27 |
| 5. Task Runner and Workflow Engine               | v1.0      | 5/5   | Complete | 2026-03-27 |
| 6. send-notification Agent                       | v1.0      | 4/4   | Complete | 2026-03-27 |
| 7. handle-incoming-message Agent                 | v1.0      | 4/4   | Complete | 2026-03-27 |
| 07.1. Deterministic Agent Termination (INSERTED) | v1.0      | 3/3   | Complete | 2026-03-30 |
| 8. recipe-research Agent                         | v1.0      | 4/4   | Complete | 2026-03-30 |
| 9. recipe-load Agent and End-to-End Integration  | v1.0      | 2/2   | Complete | 2026-05-12 |
| 10. LangChain 1.x Agent API Migration            | v1.0      | 3/3   | Complete | 2026-05-13 |
| 11. Structured Agent Output via response_format  | v1.0      | 4/4   | Complete | 2026-05-13 |
| 12. Middleware-Based Agent Instrumentation       | v1.0      | 2/2   | Complete | 2026-05-14 |
| 13. Queue Visibility Dashboard                   | v1.0      | 3/3   | Complete | 2026-05-14 |
| 14. Prompt Cleanup and Structural Standardization| v1.0      | 8/8   | Complete | 2026-05-14 |
| 15. Recipe Artifact Accumulation                 | v1.0      | 6/6   | Complete | 2026-05-15 |
| 16. household_id propagation fix                 | v1.0      | 7/7   | Complete | 2026-05-15 |

## Backlog

Unsequenced ideas that aren't ready for active planning. Promote with `/gsd-review-backlog` when promotion criteria are met.

### Phase 999.1: Custom state schemas for reply_context and household_id (BACKLOG)

**Goal:** Lift `reply_context: ReplyContext` and `household_id: str` from per-task `*Input` Pydantic models into a typed `AgentState` schema passed to `create_agent(state_schema=...)`. Tools access these via `InjectedState` rather than runtime kwargs. The job dispatcher in `run_task()` (`src/robotina/queue/jobs.py`) maps `WorkflowRun.shared_context` -> agent state at invocation time.

**Why this is a backlog item, not an active phase:** This refactor changes the contract between the workflow runner / job dispatcher and the agent -- a meaningful structural shift. Real ergonomic value (removes the "thread `household_id` through every `*Input` model and every tool signature" plumbing) but no current production pain forces it. Adding new ambient fields today is annoying-but-rare, not blocking.

**Requirements:** TBD

**Depends on:** Phase 10 (requires `langchain.agents.create_agent`; `langgraph.prebuilt.create_react_agent` does not cleanly support `state_schema=`). Independent of Phases 11 and 12 -- they make this phase nicer when promoted, but neither requires it.

**Promotion criteria** -- promote to an active phase via `/gsd-review-backlog` when ANY of:
  1. Three or more tools need ambient context (currently only `household_id` is threaded; if `user_id`, `locale`, or workflow-scoped flags get added, this triggers)
  2. Adding a new ambient field becomes a recurring chore (touched in 2+ phases of work over a quarter)
  3. A future phase wants middleware that needs typed state reads (Phase 12 follow-on, e.g. enriching spans with `reply_context.platform` automatically)

**Scope estimate when promoted:** 1-2 days. Touches: agent construction in `src/robotina/llm/__init__.py` (3 backends); tool signatures (`household_manager_api.py`, `queue.py`, `start_workflow.py`, `web_search.py`); job dispatcher in `src/robotina/queue/jobs.py`; the 4 test files that build real agents.

**Source decision:** Sequencing discussion 2026-05-12, conversation following the canelones de choclo parse failure analysis (2026-05-13 logs). User opted to land A/B/C (Phases 10/11/12) and defer D as backlog.

**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

