---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Phase 15 in progress (Plan 15-01 complete)
stopped_at: Phase 15 Plan 01 complete; Plans 15-02..15-06 = prompt bumps
last_updated: "2026-05-14T21:00:00.000Z"
last_activity: "2026-05-14 - Completed Phase 15 Plan 01: foundational refactor (accumulating RecipeData artifact, validate-foods/units tools, validate-catalog matcher, per-job tool injection)"
progress:
  total_phases: 18
  completed_phases: 13
  total_plans: 63
  completed_plans: 52
  percent: 83
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-25)

**Core value:** Families can delegate household tasks to Robotina in natural language and trust that they get done — even complex multi-step tasks that span multiple agent runs.
**Current focus:** Phase 14 complete — next up Phase 15 (recipe artifact accumulation)

## Current Position

Phase: 15 (recipe-artifact-accumulation-and-food-unit-validation) — IN PROGRESS
Plans: 1 of (TBD; expected 6 — foundation + 5 prompt bumps)

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01-developer-tooling-and-infrastructure P01 | 3 | 1 tasks | 1 files |
| Phase 01-developer-tooling-and-infrastructure P02 | 2 | 2 tasks | 16 files |
| Phase 01-developer-tooling-and-infrastructure P03 | 2 | 2 tasks | 7 files |
| Phase 02-database-models-and-queue-layer P01 | 5 | 2 tasks | 7 files |
| Phase 02-database-models-and-queue-layer P02 | 3 | 1 tasks | 2 files |
| Phase 02-database-models-and-queue-layer P03 | 3 | 2 tasks | 3 files |
| Phase 03-gateway P01 | 57 | 2 tasks | 2 files |
| Phase 03-gateway P03 | 2 | 1 tasks | 3 files |
| Phase 03-gateway P02 | 3 | 2 tasks | 5 files |
| Phase 04-llm-module-and-agent-infrastructure P01 | 2 | 2 tasks | 8 files |
| Phase 04-llm-module-and-agent-infrastructure P03 | 2 | 1 tasks | 2 files |
| Phase 04-llm-module-and-agent-infrastructure P02 | 5 | 1 tasks | 2 files |
| Phase 04-llm-module-and-agent-infrastructure P05 | 2 | 2 tasks | 10 files |
| Phase 04-llm-module-and-agent-infrastructure P04 | 20 | 2 tasks | 4 files |
| Phase 04-llm-module-and-agent-infrastructure P06 | 2 | 2 tasks | 2 files |
| Phase 04-llm-module-and-agent-infrastructure P06 | 19h | 3 tasks | 6 files |
| Phase 05-task-runner-and-workflow-engine P01 | 2min | 2 tasks | 3 files |
| Phase 05-task-runner-and-workflow-engine P02 | 3min | 1 tasks | 2 files |
| Phase 05-task-runner-and-workflow-engine P03 | 5min | 1 tasks | 2 files |
| Phase 05-task-runner-and-workflow-engine P04 | 6min | 2 tasks | 7 files |
| Phase 05-task-runner-and-workflow-engine P05 | 3min | 3 tasks | 6 files |
| Phase 06-send-notification-agent P01 | 3min | 3 tasks | 6 files |
| Phase 06-send-notification-agent P02 | 3min | 2 tasks | 5 files |
| Phase 06-send-notification-agent P03 | 3min | 2 tasks | 6 files |
| Phase 06-send-notification-agent P04 | 1min | 2 tasks | 1 files |
| Phase 07-handle-incoming-message-agent P01 | 2min | 2 tasks | 2 files |
| Phase 07-handle-incoming-message-agent P02 | 3min | 2 tasks | 4 files |
| Phase 07 P03 | 5min | 2 tasks | 3 files |
| Phase 07-handle-incoming-message-agent P04 | 2min | 1 tasks | 6 files |
| Phase 08-recipe-research-agent P02 | 3min | 2 tasks | 11 files |
| Phase 08-recipe-research-agent P01 | 3min | 2 tasks | 6 files |
| Phase 08 P03 | 3min | 2 tasks | 5 files |
| Phase 08-recipe-research-agent P04 | 2min | 2 tasks | 1 files |
| Phase 09 P01 | 2min | 2 tasks | 8 files |
| Phase 09 P02 | 2min | 2 tasks | 1 files |
| Phase 10-langchain-1-x-agent-api-migration P01 | 2min | 2 tasks | 2 files |
| Phase 10-langchain-1-x-agent-api-migration P02 | 7min | 3 tasks | 12 files |
| Phase 10-langchain-1-x-agent-api-migration P03 | 30min | 3 tasks | 5 files |
| Phase 11-structured-agent-output-via-response-format P01 | 5min | 3 tasks | 6 files |
| Phase 11-structured-agent-output-via-response-format P02 | 6min | 2 tasks | 2 files |
| Phase 11-structured-agent-output-via-response-format P03 | 6min | 6 tasks | 9 files |
| Phase 11-structured-agent-output-via-response-format P04 | TBD | 2 tasks | 4 files |
| Phase 12-middleware-based-agent-instrumentation P01 | 4min | 2 tasks | 5 files |
| Phase 13-queue-visibility-dashboard P01 | 25min | 2 tasks | 5 files |
| Phase 13-queue-visibility-dashboard PP02 | 6min | 2 tasks | 21 files |

## Accumulated Context

### Roadmap Evolution

- Phase 07.1 inserted after Phase 7: Deterministic agent termination (URGENT)
- Phase 10 added: LangChain 1.x Agent API Migration (create_react_agent -> create_agent)
- Phase 11 added: Structured Agent Output via response_format (fixes canelones-class parse failures)
- Phase 12 added: Middleware-Based Agent Instrumentation (callbacks -> @before_model/@after_model/@wrap_model_call)
- Phase 13 added: Queue Visibility Dashboard (custom FastAPI dashboard for workflow-grouped task visibility)
- Phase 14 added: Prompt Cleanup and Structural Standardization (re-version all 7 active prompts to a single skeleton; no behavioral change)
- Phase 11 code complete (manual checkpoint pending): response_format adopted on 5 named agents; canelones-class parse failures structurally eliminated for those agents — pending 3-query end-to-end verification (Plan 11-04 Task 4.2)
- Phase 15 added: Recipe artifact accumulation and food/unit validation
- Phase 16 added: Fix empty-string household_id propagation through gateway and workflow_run

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- All phases: Centralized task-runner orchestrates workflows; agents know nothing about the sequence they belong to
- All phases: `reply_context` lives in `WorkflowRun.shared_context`, never in intermediate task inputs
- Phase 4+: `create_react_agent` from `langgraph.prebuilt` required; `AgentExecutor` must not be used
- Phase 5: Enqueue next RQ job before committing Postgres transaction (transactional advancement; pre-assigned job ID)
- Phase 4: All per-job objects must be instantiated inside the job function, never at module level
- [Phase 01-developer-tooling-and-infrastructure]: Redis AOF set via command-line args (--appendonly yes --appendfsync always) not a mounted config — simpler, no extra file needed
- [Phase 01-developer-tooling-and-infrastructure]: RQ Dashboard uses eoranged/rq-dashboard:latest (locked decision D-03), connected to Redis via internal Docker hostname redis://redis:6379
- [Phase 01-developer-tooling-and-infrastructure]: Python 3.12 pinned with <3.13 upper bound in pyproject.toml to prevent uv selecting system Python 3.13
- [Phase 01-developer-tooling-and-infrastructure]: Both src/robotina and experiments declared in hatch packages so uv run experiments.* scripts are importable
- [Phase 01-developer-tooling-and-infrastructure]: Alembic env.py fully replaced to add sys.path injection and DATABASE_URL override before config loading
- [Phase 01-developer-tooling-and-infrastructure]: Queue name is agent-tasks — all downstream phases must enqueue to this exact name
- [Phase 01-developer-tooling-and-infrastructure]: All RQ jobs must use result_ttl=-1 and failure_ttl=-1 per CLAUDE.md no-lost-tasks requirement
- [Phase 02-database-models-and-queue-layer]: Use postgresql.ENUM(create_type=False) in op.create_table — generic sa.Enum fires _on_table_create despite create_type=False in SQLAlchemy 2.0.48
- [Phase 02-database-models-and-queue-layer]: PostgreSQL 15 idempotent ENUM creation requires DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = ...) pattern; CREATE TYPE IF NOT EXISTS is not supported
- [Phase 02-database-models-and-queue-layer]: All 13 task I/O model classes centralized in robotina.queue.task_types — single import point for queue, agents, and task runner
- [Phase 02-database-models-and-queue-layer]: reply_context absent from RecipeResearchInput and RecipeLoadInput — lives in WorkflowRun.shared_context, resolved by task runner in Phase 5
- [Phase 02-database-models-and-queue-layer]: LoggingWorker defined as direct class at module level — clean import, no deferred pattern
- [Phase 02-database-models-and-queue-layer]: Integration tests use burst=True worker in foreground for test-safe job processing without background threads
- [Phase 03-gateway]: pytest.skip() used for stubs (SKIPPED not FAILED) — acceptable since plan goal is test name existence and clean collection
- [Phase 03-gateway]: test_send_message_persists not marked @pytest.mark.integration — uses mocked Bot, no live services required
- [Phase 03-gateway]: Bot used as async context manager (async with bot:) per PTB 22.7 standalone pattern for send_message — avoids PTB Application entanglement
- [Phase 03-gateway]: SQLAlchemy Enum requires values_callable=lambda e: [x.value for x in e] for PostgreSQL native enum columns (enum name vs enum value mismatch)
- [Phase 03-gateway]: Enqueue string function ref 'robotina.queue.jobs.handle_incoming_message' — Phase 4 will create the actual function; RQ resolves at execution time
- [Phase 03-gateway]: Redis connection created per-message inside handler (not module-level) — simplest approach for Phase 1 sequential load
- [Phase 04-llm-module-and-agent-infrastructure]: Gateway enqueue string changed from 'robotina.queue.jobs.handle_incoming_message' to 'robotina.queue.jobs.run_task'; meta=task_type unchanged; run_task reads task_type from meta to dispatch to correct agent (D-09 confirmed)
- [Phase 04-llm-module-and-agent-infrastructure]: AgentConfig uses plain Python dataclass (not Pydantic) — internal config, no external serialization needed
- [Phase 04-llm-module-and-agent-infrastructure]: get_agent_config() re-reads AGENT_OVERRIDES_FILEPATH JSON on every call (hot-reload) — supports prompt experimentation without restart
- [Phase 04-llm-module-and-agent-infrastructure]: AGENT-11/D-03 superseded in Phase 10 by AGENT-12 — all agents now use `langchain.agents.create_agent` (LangGraph V1.0 deprecation; removal in V2.0). Behavior parity (return_direct, state shape, callbacks) verified during Phase 10.
- [Phase 04-llm-module-and-agent-infrastructure]: ChatOpenAI uses model_name= (not model=) and openai_api_base= — verified against langchain-openai 1.1.12 field names
- [Phase 04-llm-module-and-agent-infrastructure]: api_key_env in model_config stores env var NAME not token value; resolved via os.environ at adapter instantiation time for clear misconfiguration errors
- [Phase 04-llm-module-and-agent-infrastructure]: SKILLS_BASE anchored to Path(__file__).parent / 'skills' — absolute path makes SkillSet testable without import manipulation
- [Phase 04-llm-module-and-agent-infrastructure]: ReadSkillTool inherits BaseTool (not @tool) — needs skill_dirs instance state that @tool cannot hold
- [Phase 04-llm-module-and-agent-infrastructure]: Lazy import SkillSet and build_read_skill_tool inside run_task() to allow Plan 04 to run before Plan 05 is complete
- [Phase 04-llm-module-and-agent-infrastructure]: Patch rq.get_current_job at robotina.queue.jobs.get_current_job — from-import creates module-local binding that must be patched at its new location
- [Phase 04-llm-module-and-agent-infrastructure]: LangWatch must be initialized in work-horse subprocess (perform_job), not main process — BatchSpanProcessor thread dies on fork causing silent trace drops
- [Phase 04-llm-module-and-agent-infrastructure]: LangChainInstrumentor dropped; explicit LangChainTracer callback passed via RunnableConfig to agent.invoke() — per LangWatch 0.17.0 recommended pattern
- [Phase 04-llm-module-and-agent-infrastructure]: on_chat_model_start used in AgentLoggingHandler (not on_llm_start) — LangChain routes chat model events to on_chat_model_start
- [Phase 05-task-runner-and-workflow-engine]: Phase 05-01: pytest.skip() stubs for Wave 0 — SKIPPED not FAILED; no module-level imports of not-yet-existing modules; @pytest.mark.integration for tests requiring live services
- [Phase 05-task-runner-and-workflow-engine]: workflows.py: Pydantic ConfigDict(arbitrary_types_allowed=True) required for Callable fields in WorkflowStepDef and WorkflowDefinition
- [Phase 05-task-runner-and-workflow-engine]: workflows.py: load step build_input uses RecipeData(**artifacts['research']['recipe']) to reconstruct from JSON-serialized dict
- [Phase 05-task-runner-and-workflow-engine]: workflow_runner.py: queue injected (not hardcoded) — testable without live Redis; pre-assigned job_id before Postgres commit (D-07); session.flush() before querying DONE steps
- [Phase 05-task-runner-and-workflow-engine]: Workflow hooks are three inline calls in run_task() — no dispatcher function (D-08 confirmed)
- [Phase 05-task-runner-and-workflow-engine]: Unit tests calling run_task() must patch workflow_runner.on_step_* and SessionLocal to avoid live DB queries
- [Phase 05-task-runner-and-workflow-engine]: queue_workflow is the canonical name for workflow initiation; on_step_start is the single PENDING->RUNNING transition point for WorkflowRun
- [Phase 06-send-notification-agent]: pytest.skip() must come before import in stub functions — placing it after causes ImportError before skip, resulting in FAILED not SKIPPED
- [Phase 06-send-notification-agent]: test_prompts.py: 3 failures for missing send-notification/V001.md are intentional — Plan 06-03 creates the prompt file
- [Phase 06-send-notification-agent]: asyncio.run() bridge in SendNotificationTool._run() safe in RQ worker subprocess (no event loop running, D-02)
- [Phase 06-send-notification-agent]: parse_mode defaults to None in send_message() for backward compatibility; only notification tool passes MarkdownV2
- [Phase 06-send-notification-agent]: format-telegram-message skill uses 3 sub-files (escaping, formatting, examples) to minimize context load — agent reads only what it needs
- [Phase 06-send-notification-agent]: Prompt V001 enforces reformat-only constraint with explicit wrong/right examples in Critical Rules section
- [Phase 06-send-notification-agent]: Experiment uses same LangWatch instrumentation path as run_task() (langwatch.trace + LangChainTracer) — OBS-03 requirement
- [Phase 06-send-notification-agent]: SendNotificationTool._run mocked via patch.object in experiment to capture formatted output without TELEGRAM_BOT_TOKEN
- [Phase 07-handle-incoming-message-agent]: pytest.skip() placed before any from-import in each stub (consistent with Phase 6 pattern)
- [Phase 07-handle-incoming-message-agent]: household_id stored at construction but NOT auto-injected into request URLs in Phase 7 — agent passes it in path/query where API requires it (D-02 scope deferral)
- [Phase 07-handle-incoming-message-agent]: QueueTool enqueues at BACK of queue (no at_front=True) — gateway uses at_front because it originates outside the worker; follow-up tasks must not preempt waiting jobs (Pitfall 5)
- [Phase 07-handle-incoming-message-agent]: Redis/Queue imports at module level in queue.py — lazy imports inside _run() make patch() target non-existent and break mocking
- [Phase 07-handle-incoming-message-agent]: Routing prompt does NOT enumerate workflow type names — agent discovers available types from start-workflow tool description (Pitfall 4 avoidance)
- [Phase 07-handle-incoming-message-agent]: shared.md auth section fully removed; household-manager-api tool handles Authorization header transparently
- [Phase 07-handle-incoming-message-agent]: handle-incoming-message uses HANDLE_INCOMING_MESSAGE_API_TOKEN env var; all three tools injected in elif block inside run_task() — never at module level
- [Phase 08-recipe-research-agent]: WebSearchTool uses lazy TavilyClient import inside _run(); include_raw_content=True for HTML to support recipe-scrapers; TAVILY_API_KEY via standard Tavily env var name
- [Phase 08-recipe-research-agent]: Keep old RecipeResearchInput/Output models for backward compat while adding 8 new sub-task I/O models (Pitfall 6)
- [Phase 08-recipe-research-agent]: All build_input lambdas use dict key access on accumulated_artifacts; RecipeStep/RecipeIngredient reconstructed from dicts with **spread
- [Phase 08]: recipe-research-instructions and recipe-research-metadata need no elif blocks in run_task() -- they only use generic read-skill tool injection
- [Phase 08]: WebSearchTool() takes no constructor args (TAVILY_API_KEY read at execution time); HouseholdManagerApiTool needs household_id from task_input
- [Phase 08-recipe-research-agent]: Experiment threads outputs between steps via in-memory accumulated_artifacts dict (no DB/RQ needed)
- [Phase 08-recipe-research-agent]: extract_json_output() handles markdown code blocks and raw JSON from create_react_agent responses (Pitfall 4)
- [Phase 09]: Notification text in Spanish with recipe description and app link via HOUSEHOLD_MANAGER_BASE_URL
- [Phase 09]: Reuse household-manager skill for recipe-load -- no dedicated skill directory (D-08)
- [Phase 09]: Full recipe data included in experiment user message via _build_user_message() so agent can resolve names
- [Phase 10-langchain-1-x-agent-api-migration]: Plan 10-01 — AGENT-12 added to REQUIREMENTS.md as unchecked / "In Progress" supersedes AGENT-11; Plan 10-03 flips it to Complete after manual end-to-end Telegram verification
- [Phase 10-langchain-1-x-agent-api-migration]: Plan 10-01 — Requirement supersession marker pattern '*(superseded by REQ-XX in Phase N)*' tag on the old bullet preserves decision history instead of deleting
- [Phase 10-langchain-1-x-agent-api-migration]: Plan 10-01 — Lock-test-first wave boundary: the source-grep test in tests/unit/test_llm_backend.py is renamed test_create_agent_used_not_agent_executor and its assertions inverted in wave 1 so the test is RED against the unchanged source — Plan 10-02 turns it green via the source rename; the FAILING state at the plan boundary IS the success signal
- [Phase 10-langchain-1-x-agent-api-migration]: Plan 10-01 — Per-adapter test patch targets (patch('robotina.llm.create_react_agent', ...) at lines 24/44/67) are NOT updated in wave 1; Plan 10-02 owns them alongside the source change so the wave boundary stays clean
- [Phase 10-langchain-1-x-agent-api-migration]: Plan 10-02 — Self-recursion guard alias `from langchain.agents import create_agent as _create_agent` is mandatory because the LLMBackend.create_agent METHOD has the same name as the factory function; without aliasing, the method body would recurse infinitely. All call sites in src/robotina/llm/__init__.py use `_create_agent(...)` while the public method signature stays `create_agent`
- [Phase 10-langchain-1-x-agent-api-migration]: Plan 10-02 — Test mock patch targets follow the imported alias name (patch('robotina.llm._create_agent', ...)) not the upstream module path (`langchain.agents.create_agent`); patching the upstream path does not intercept calls because Python resolves the imported name at import time
- [Phase 10-langchain-1-x-agent-api-migration]: Plan 10-02 — AC1 grep-zero gate (no `create_react_agent` / `langgraph.prebuilt` matches under src/ tests/ experiments/) is interpreted by INTENT not literally: the lock test in tests/unit/test_llm_backend.py necessarily contains those tokens in its load-bearing forbidden-strings assertions. The intent (no remaining USAGE outside the lock test) is verified by `grep ... | grep -v test_llm_backend.py | wc -l == 0`
- [Phase 10-langchain-1-x-agent-api-migration]: Plan 10-02 — The Plan-verbatim Protocol docstring phrase `the previous ``create_react_agent`` path` would have failed the renamed source-grep lock test (which forbids the substring `create_react_agent` anywhere in src/robotina/llm/__init__.py); rephrased to `the previous prebuilt ReAct-agent path` — Rule 1 deviation, semantics preserved, lock satisfied
- [Phase 10-langchain-1-x-agent-api-migration]: Plan 10-02 — Pre-existing test pollution from tests/test_pyproject.py::test_experiment_mains_importable (importing experiments/* runs `load_dotenv()` at module top, leaking AGENT_OVERRIDES_FILEPATH=overrides/openai.json into agents_registry tests) fails 9 unit tests on order-dependence; reproduced on Plan 10-01 final commit daf2f7b — out of scope for Plan 10-02, candidate quick task for the future
- [Phase 10-langchain-1-x-agent-api-migration]: Plan 10-03 — AGENT-12 marked complete in REQUIREMENTS.md only AFTER the manual end-to-end Telegram verification approved by user; checkbox flip lives in a separate post-checkpoint task (3.3) from the docs rollover (3.1) so the requirement contract change is atomic and gated on real production behavior, not unit-test parity
- [Phase 10-langchain-1-x-agent-api-migration]: Plan 10-03 — Tangential pydantic optional-field bug (RecipeStep / RecipeIngredient / RecipeData fields without = None defaults) exposed during Task 3.2 end-to-end verification; fixed inline as quick task 260512-pyd (commit 19b3b9d). Pre-existing latent schema bug surfaced by an LLM model swap, NOT caused by the create_agent migration. Out of Plan 10-03 scope but unblocked the Task 3.2 end-to-end gate
- [Phase 10-langchain-1-x-agent-api-migration]: Plan 10-03 — Phase 10 success criterion 4 closed: end-to-end add-recipe Telegram workflow runs to completion under langchain.agents.create_agent with no semantic regression; LangWatch traces appear with spans for each agent invocation; no LangGraphDeprecatedSinceV10 warnings in worker logs. Phase 10 migration functionally complete; Plans 11 and 12 unblocked
- [Phase 11-structured-agent-output-via-response-format]: Per-provider Strategy mapping: Ollama → ToolStrategy (correctness — gpt-oss is in FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT so AutoStrategy would silently route to ProviderStrategy and call bind_tools(strict=True, response_format=...) which Ollama does not honor); Anthropic / OpenAI → ProviderStrategy. Strategy selected inside each LLMBackend adapter, not in run_task.
- [Phase 11-structured-agent-output-via-response-format]: AgentConfig.response_format_model is NOT overridable via AGENT_OVERRIDES_FILEPATH — schema is a code contract, not config. get_agent_config only propagates model_config and prompt_path; the response_format_model field flows directly from AGENT_REGISTRY.
- [Phase 11-structured-agent-output-via-response-format]: _extract_task_output in workflow_runner.py rewritten — prefers result['structured_response'] when expects_structured=True (resolved by on_step_complete via get_agent_config(step.task_type).response_format_model is not None); raises ValueError loudly on missing. The prose-strip / markdown-fence / first-{-scan / json.loads fallback ladder + TEMP DIAGNOSTIC logger.error block are REMOVED. handle-incoming-message and acknowledge-add-recipe continue to use the return_direct tool-message branch (out of scope for Phase 11).
- [Phase ?]: [Phase 12-middleware-based-agent-instrumentation]: Plan 12-01 — Used @wrap_model_call (not @before_model) for the 'LLM stream start | model=%s' line because before_model has no access to the model object; ModelRequest.model is only available in wrap_model_call. type(request.model).__name__ yields 'ChatOllama' / 'ChatAnthropic' / 'ChatOpenAI' for byte-for-byte parity with the legacy on_chat_model_start log.
- [Phase 12-middleware-based-agent-instrumentation]: Plan 12-01 — Coexistence wave boundary intentional. AgentLoggingHandler remains wired in robotina/queue/jobs.py and the three legacy callback tests in test_agent_runner.py:152-176, 325-340 stay green. Plan 12-02 (Wave 2) atomically removes the callback file + jobs.py wiring + the three legacy tests. The new-path-lands-additively-then-old-path-flips boundary mirrors Phase 10's lock-test-flip pattern.
- [Phase 12-middleware-based-agent-instrumentation]: Plan 12-01 — Middleware list is provider-agnostic: the SAME middleware=[log_around_model_call, log_after_model, log_wrap_tool_call] kwarg is passed by all three LLMBackend adapters (Ollama / Anthropic / OpenAI). Decorator-yields-an-instance pattern (RESEARCH.md Pitfall 3) means singletons are imported, not constructed per call.
- [Phase 12-middleware-based-agent-instrumentation]: Plan 12-01 — Bound-method invocation is the testing convention: log_around_model_call.wrap_model_call(request, handler) etc. Sidesteps needing a full create_agent graph (langchain/agents/middleware/types.py:1880-1892).
- [Phase 12-middleware-based-agent-instrumentation]: Plan 12-01 — OBS-06 not yet declared in REQUIREMENTS.md. Plan 12-02 (which actually deletes the legacy path) is the better place to register OBS-06 with 'Complete' status, since OBS-06 success is gated on the legacy callback being gone, not just on the new middleware module existing.
- [Phase ?]: Phase 13-01: step_input column populated via Pydantic .model_dump(mode='json') mirroring artifact pattern; failure_reason format f'{type(exc).__name__}: {exc}' with newline→space sanitization (D-16)
- [Phase ?]: Phase 13-01: on_step_failed signature extended with keyword-only exc: BaseException | None = None; backward-compatible (default None leaves failure_reason NULL for legacy callers)
- [Phase ?]: Phase 13-01: jobs.py threads live exception via 'except Exception as exc' + exc=exc kwarg (not bare except — KeyboardInterrupt/SystemExit must not be persisted)
- [Phase ?]: Phase 13-02: HTMX vendored at 2.0.10 (SHA-256 71ea67…c0de in htmx.version.txt) — no CDN runtime per D-13
- [Phase ?]: Phase 13-02: Polling-halt by attribute-absent re-render on the wrapper element with hx-swap='outerHTML' — wrapper replaces itself trigger-less when run.status in (DONE, FAILED); HTMX's per-element timer ends naturally (D-09 / RESEARCH Pitfall 3)
- [Phase ?]: Phase 13-02: Template + static dirs resolved via Path(__file__).parent (not CWD-relative strings) — Jinja2Templates and StaticFiles both take str(Path(__file__).parent / 'templates'|'static') so the app works under uv run from any directory and under pytest
- [Phase ?]: Phase 13-02: D-01 (USER-LOCKED) enforced by tests/dashboard/test_independence.py — grep gate + inward-only import audit run as normal pytest assertions; cannot be silently bypassed

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 4: LangWatch SDK initialization and OTel trace propagation API — LOW confidence; verify official LangWatch docs before starting Phase 4
- Phase 5: RQ `job_id` parameter behavior for pre-assigned IDs — verify before implementing transactional advancement
- Phase 9: Household-manager API actual endpoint behavior for name resolution edge cases (zero matches, multiple ambiguous matches) — verify before recipe-load implementation

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260327-gio | Commit uncommitted files | 2026-03-27 | 95a8a54 | [260327-gio-commit-uncommitted-files](./quick/260327-gio-commit-uncommitted-files/) |
| 260327-gs5 | Switch LoggingWorker to SimpleWorker, simplify LangWatch setup | 2026-03-27 | ea3c177 | [260327-gs5-switch-loggingworker-to-simpleworker-and](./quick/260327-gs5-switch-loggingworker-to-simpleworker-and/) |
| 260327-j4k | Fix send-notification experiment to use LangWatch Experiment API | 2026-03-27 | c5645b7 | [260327-j4k-fix-send-notification-experiment-use-lan](./quick/260327-j4k-fix-send-notification-experiment-use-lan/) |
| 260330-ggw | Add Spanish language support to Robotina | 2026-03-30 | 128efe8 | [260330-ggw-add-spanish-language-support-to-robotina](./quick/260330-ggw-add-spanish-language-support-to-robotina/) |
| 260330-mgk | Fix recipe-research-gather prompt step 6 to explicitly specify recipes output format instead of ambiguous JSON array | 2026-03-30 | 0b0ed36 | [260330-mgk-fix-recipe-research-gather-prompt-step-6](./quick/260330-mgk-fix-recipe-research-gather-prompt-step-6/) |
| 260430-meh | Fix spec.md line 112: Prisma models -> SQLAlchemy models | 2026-04-30 | 85058b1 | [260430-meh-fix-spec-md-line-112-prisma-models-sqlal](./quick/260430-meh-fix-spec-md-line-112-prisma-models-sqlal/) |
| 260508-tdr | Fix workflow halt after return_direct ack tool: tolerate ToolMessage in _extract_task_output | 2026-05-08 | 7916c4b | [260508-tdr-fix-extract-task-output-toolmessage](./quick/260508-tdr-fix-extract-task-output-toolmessage/) |
| 260508-qx8 | Fix RecipeLoadInput.to_user_message — give the load agent the full structured recipe | 2026-05-08 | 23bc1cd | [260508-qx8-fix-recipe-load-user-message](./quick/260508-qx8-fix-recipe-load-user-message/) |
| 260509-lcd | Add bounded transient retry to OllamaBackend for Ollama 5xx errors | 2026-05-09 | f801814 | [260509-lcd-add-bounded-transient-retry-to-ollamabac](./quick/260509-lcd-add-bounded-transient-retry-to-ollamabac/) |
| 260509-ln9 | Telegram dead-letter notification on terminal workflow failure | 2026-05-09 | 3aacd11 | [260509-ln9-telegram-dead-letter-notification-on-ter](./quick/260509-ln9-telegram-dead-letter-notification-on-ter/) |
| 260509-m46 | Add JSON-literal guidance to dict-arg tool descriptions | 2026-05-09 | 220f9d9 | [260509-m46-add-json-literal-guidance-to-dict-arg-to](./quick/260509-m46-add-json-literal-guidance-to-dict-arg-to/) |
| 260509-m4f | Translate skill files to English and fix null-handling contradictions | 2026-05-09 | 94d8e0e | [260509-m4f-translate-skill-files-to-english-and-fix](./quick/260509-m4f-translate-skill-files-to-english-and-fix/) |
| 260509-nru | Strict args_schema on dict-arg tools — bad LLM tool args become ToolMessage(error) instead of TypeError that kills the workflow | 2026-05-09 | f12c56b | [260509-nru-strict-tool-call-args-validation](./quick/260509-nru-strict-tool-call-args-validation/) |
| 260509-o56 | Inline recipe-research skill files into the 4 sub-agent prompts; delete the bundle (1:1 per-agent runbook content was the wrong abstraction for `skill`) | 2026-05-09 | c018f0d | [260509-o56-inline-recipe-research-skill-files-into-](./quick/260509-o56-inline-recipe-research-skill-files-into-/) |
| 260512-pyd | Make optional RecipeData fields truly optional with `= None` defaults (RecipeStep.title, RecipeIngredient optional fields, RecipeData optional fields) — fixes pydantic ValidationError when LLM omits null-valued fields | 2026-05-12 | 19b3b9d | (fast — no directory) |
| 260513-lcc | Align CLAUDE.md langchain-core row to `>=1.2` (was `>=0.3`) — internal consistency cleanup flagged by Phase 10 VERIFICATION.md | 2026-05-13 | f52533a | (fast — no directory) |
| 260514-ix8 | Remove redundant Output section from 5 recipe research prompts — schema enforced by `response_format_model` in agents.py, prompt-level section was developer-facing | 2026-05-14 | 0bd4062 | [260514-ix8-remove-redundant-output-section-from-5-r](./quick/260514-ix8-remove-redundant-output-section-from-5-r/) |

## Session Continuity

Last activity: 2026-05-14 - Completed quick task 260514-ix8: Remove redundant Output section from 5 recipe research prompts

Last session: 2026-05-14T17:42:28.223Z
Stopped at: Phase 15 context gathered
Resume file: 
.planning/phases/15-recipe-artifact-accumulation-and-food-unit-validation/15-CONTEXT.md
