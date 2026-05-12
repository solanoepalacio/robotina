# Phase 5: Task Runner and Workflow Engine - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire up workflow orchestration in the task runner: `WorkflowDefinition` / `WorkflowStepDef` registry (`workflows.py`), a dedicated `workflow_runner.py` module that owns all execution-side state management, the `start-workflow` LangChain tool, and the advancement hook in `run_task()`. The DB models (`WorkflowRun`, `WorkflowRunStep`) already exist from Phase 2. No real agents run through this yet — the phase proves the orchestration mechanics using the existing `hello-world` task type.

</domain>

<decisions>
## Implementation Decisions

### Workflow Registry (agent/workflows.py)
- **D-01:** `WorkflowDefinition` and `WorkflowStepDef` live in `src/robotina/agent/workflows.py` alongside `agents.py` — spec §Workflow Registry placement.
- **D-02:** `build_input: Callable[[dict, dict], BaseModel]` signature — receives a frozen copy of `shared_context` (never mutated) and `accumulated_artifacts: dict[str, dict]` keyed by `step_key`. This is the verbatim signature from the spec.
- **D-03:** `add-recipe` workflow registered verbatim per spec: `research` (recipe-research) → `load` (recipe-load) → `notify` (send-notification) with `build_input` lambdas as shown in spec §Workflow Registry.
- **D-04:** A `"hello-world-2step"` test workflow is registered in `WORKFLOW_REGISTRY` alongside `"add-recipe"`. It has two `hello-world` steps (`step1`, `step2`) — used exclusively for Phase 5 integration tests. **Remove this entry (and the `hello-world` agent config) when `send-notification` is added in Phase 6**, just as the `hello-world` agent config placeholder must be removed.

### Workflow Execution Module (queue/workflow_runner.py)
- **D-05:** All execution-side workflow state management is encapsulated in `src/robotina/queue/workflow_runner.py`. This is the single module responsible for workflow lifecycle. It exposes:
  - `start_workflow(workflow_type, shared_context, household_id, queue, session) → str` — creates `WorkflowRun` + all `WorkflowRunStep` records (status `PENDING`), enqueues first step (pre-assigned job ID), stores `task_job_id` on first step, returns `workflow_run_id`.
  - `on_step_start(job_id, session)` — marks the matching `WorkflowRunStep` as `RUNNING`, records `started_at`.
  - `on_step_complete(job_id, output, session, queue)` — writes output to `WorkflowRunStep.artifact` (via `model.model_dump(mode='json')` for Pydantic outputs), marks step `DONE`, records `completed_at`, builds `accumulated_artifacts` from all DONE steps, identifies next PENDING step, calls `build_input()`, enqueues next job (pre-assigned ID), updates `task_job_id` on next step. If no next step, marks `WorkflowRun` DONE.
  - `on_step_failed(job_id, session)` — marks step `FAILED`, cancels all remaining `PENDING` steps (sets status to `CANCELLED`), marks `WorkflowRun` `FAILED`.
- **D-06:** Job linkage — the task runner finds the workflow step by querying `WorkflowRunStep WHERE task_job_id = current_rq_job.id`. If no row found → direct task (not part of a workflow) → skip all workflow state management and run `run_task()` as today.
- **D-07:** Transactional advancement — enqueue the next RQ job **before** committing the Postgres transaction. Use a pre-assigned job ID (`job_id = str(uuid.uuid4()); queue.enqueue(..., job_id=job_id)`) so the ID can be stored in `WorkflowRunStep.task_job_id` in the same transaction. This ensures no job is lost if the commit fails (locked decision from STATE.md Phase 5).

### run_task() Advancement Hook
- **D-08:** `run_task()` in `jobs.py` gains workflow awareness via **inline calls to `workflow_runner`** — no new dispatcher function:
  1. Before agent execution: call `workflow_runner.on_step_start(job.id, session)`. If step not found (direct task), skip and proceed.
  2. After successful agent execution: call `workflow_runner.on_step_complete(job.id, result, session, queue)`.
  3. On exception: call `workflow_runner.on_step_failed(job.id, session)`, then re-raise so RQ can move the job to the failed registry.

### start-workflow Tool
- **D-09:** Lives in `src/robotina/agent/tools/start_workflow.py` as a `BaseTool` subclass (`StartWorkflowTool`). Thin wrapper over `workflow_runner.start_workflow()`. The `tools/` directory is created as a Python package (`__init__.py`).
- **D-10:** `StartWorkflowTool._run(workflow_type: str, shared_context: dict)` — reads `household_id` from `shared_context`, creates its own DB session via `robotina.db.SessionLocal()`, creates RQ queue connection, calls `workflow_runner.start_workflow()`, returns `workflow_run_id` string. Session closed in a `finally` block.

### DB Session Management
- **D-11:** Tools and workflow_runner functions that need DB access create sessions via `robotina.db.SessionLocal()` — consistent with the rest of the codebase. `workflow_runner` functions accept a `session` argument (injected by the caller) to keep the module testable without live DB.

### Verification Tests
- **D-12:** Integration tests use the `hello-world-2step` workflow registered in WORKFLOW_REGISTRY. Tests run jobs through the real queue + DB and assert:
  - Step 1: PENDING → RUNNING → DONE, `artifact` populated.
  - Step 2: PENDING → RUNNING → DONE, `artifact` populated, `accumulated_artifacts` contains step 1 artifact.
  - `WorkflowRun` transitions to DONE after step 2.
  - Failure path: step 1 fails → step 1 FAILED, step 2 CANCELLED, WorkflowRun FAILED.
- **D-13:** Unit tests cover `workflow_runner.py` functions in isolation — mocked SQLAlchemy session (MagicMock) and mocked RQ queue — verifying advancement logic independent of live infrastructure. Tests cover: step not found (direct task), normal advancement, final step completion, step failure propagation.

### Claude's Discretion
- Exact `WorkflowStepDef` model configuration (Pydantic BaseModel vs dataclass — spec shows Pydantic, use that)
- `on_step_start` / `on_step_complete` exact function signatures beyond what's specified above
- SQLAlchemy query patterns for looking up WorkflowRunStep by `task_job_id`
- How `accumulated_artifacts` is built (query all DONE steps for the workflow_run_id)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Workflow Engine Spec
- `plans/01-kickoff/spec.md` §"Workflows" (line ~69) — design philosophy, centralized orchestrator pattern, why agents know nothing about sequences
- `plans/01-kickoff/spec.md` §"Workflow Registry" (line ~384) — `WorkflowStepDef`, `WorkflowDefinition`, `WORKFLOW_REGISTRY` verbatim Python definitions including the full `add-recipe` workflow with `build_input` lambdas
- `plans/01-kickoff/spec.md` §"Artifact Flow" (line ~490) — advancement steps: mark RUNNING, write artifact, build accumulated_artifacts, enqueue next, mark DONE
- `plans/01-kickoff/spec.md` §"Failure Handling" (line ~503) — step FAILED, cancel PENDING, WorkflowRun FAILED; no automatic retry
- `plans/01-kickoff/spec.md` §"Task Runner" (line ~372) — task runner description, inline workflow check approach
- `plans/01-kickoff/spec.md` §"Tools" (line ~550) — `start-workflow` tool spec: creates WorkflowRun + all steps, enqueues first step, returns workflow_run_id

### Requirements
- `.planning/REQUIREMENTS.md` §WF-02 through WF-09 — all workflow engine acceptance criteria for Phase 5
- `.planning/REQUIREMENTS.md` §WF-01 — confirms WorkflowRun/WorkflowRunStep models already exist (Phase 2 complete)

### Prior context (locked decisions)
- `.planning/phases/02-database-models-and-queue-layer/02-CONTEXT.md` — D-01/D-02: WorkflowRun/WorkflowRunStep models, WorkflowStatus/WorkflowStepStatus enums — no schema changes needed in Phase 5
- `.planning/phases/04-llm-module-and-agent-infrastructure/04-CONTEXT.md` — D-08: run_task() structure to wrap; D-06: hello-world placeholder entry stays until Phase 6; D-03 (queue name `agent-tasks`); D-07 (API token env var pattern)

### Existing code the planner must read
- `src/robotina/queue/jobs.py` — run_task() to wrap with workflow hook calls
- `src/robotina/queue/models.py` — WorkflowRun, WorkflowRunStep, WorkflowStatus, WorkflowStepStatus (already implemented)
- `src/robotina/queue/task_types.py` — RecipeResearchInput, RecipeLoadInput, SendNotificationInput used in add-recipe build_input lambdas
- `src/robotina/queue/runner.py` — LoggingWorker.perform_job() — no changes needed but context for how jobs flow
- `src/robotina/agent/agents.py` — AgentConfig and get_agent_config() — hello-world config is here; hello-world-2step workflow needs its task type registered

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/robotina/queue/models.py`: `WorkflowRun`, `WorkflowRunStep` — fully implemented with all columns including `task_job_id`, `artifact`, `started_at`, `completed_at`. No schema changes needed.
- `src/robotina/queue/task_types.py`: All Pydantic I/O models — `RecipeResearchInput`, `RecipeLoadInput`, `SendNotificationInput` — ready to use in `workflows.py` `build_input` lambdas.
- `src/robotina/db.py`: `SessionLocal()` factory — use for DB session creation in `workflow_runner.py` and `StartWorkflowTool`.
- `src/robotina/queue/jobs.py`: `run_task()` — receives `get_current_job()` for `job.id`; already imports from `robotina.agent.agents` and `robotina.llm`. Phase 5 adds imports from `robotina.queue.workflow_runner`.
- `src/robotina/agent/agents.py`: `hello-world` agent config entry — Phase 5 also registers `hello-world` in the workflow registry for the test workflow.

### Established Patterns
- All per-job objects instantiated inside the job function, never at module level (locked Phase 4)
- Queue name: `agent-tasks`; `result_ttl=-1`, `failure_ttl=-1` on all enqueued jobs
- `BaseTool` subclass pattern (from `ReadSkillTool` in Phase 4) — use for `StartWorkflowTool`
- SQLAlchemy 2.x `Mapped` + `mapped_column` style (for any model changes — none needed here)
- Pydantic v2 syntax throughout
- `get_current_job()` from `rq` for reading job metadata inside a job function

### Integration Points
- `workflow_runner.py` is called by: (1) `run_task()` in `jobs.py` for advancement; (2) `StartWorkflowTool._run()` for workflow initiation
- `agent/workflows.py` is imported by: (1) `workflow_runner.start_workflow()` to look up WorkflowDefinition; (2) no direct agent imports (agents never know about workflows)
- `agent/tools/start_workflow.py` is registered in `agents.py` under the `handle-incoming-message` task type (Phase 7). For Phase 5, it exists but is not yet wired to any production agent.

</code_context>

<specifics>
## Specific Ideas

- The `hello-world-2step` test workflow has TWO `hello-world` steps so both step advancement (step 1 → step 2) and final-step completion (step 2 → WorkflowRun DONE) are exercised in a single test run.
- Unit tests for `workflow_runner.py` must cover the "step not found = direct task, no-op" path explicitly — this is the normal path for all current production jobs.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-task-runner-and-workflow-engine*
*Context gathered: 2026-03-26*
