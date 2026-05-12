# Phase 4: LLM Module and Agent Infrastructure - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the general-purpose agent execution foundation: `LLMBackend` Protocol abstraction, three provider adapters (Ollama, Anthropic, OpenAI), a universal job runner (`run_task`), skill loading (`SkillSet` + `read-skill` tool), versioned prompt loading, runtime override via `AGENT_OVERRIDES_FILEPATH`, and LangWatch + OTel instrumentation wired up. No real agent logic yet — the placeholder "hello-world" task type proves the pipeline end-to-end. Gateway updated to enqueue the universal handler.

</domain>

<decisions>
## Implementation Decisions

### LLM Module (robotina/llm/)
- **D-01:** `LLMBackend` Protocol lives in `src/robotina/llm/` (the stub module already exists). Implement verbatim from spec: `model` property → `BaseChatModel`, `create_agent()` → returns `create_react_agent` runnable.
- **D-02:** Three adapter classes in `robotina/llm/`: `OllamaBackend`, `AnthropicBackend`, `OpenAIBackend`. Each reads connection details (url, model, api_key) from a config dict passed at construction. Each wraps the appropriate LangChain class (`ChatOllama`, `ChatAnthropic`, `ChatOpenAI`).
- **D-03:** `create_agent()` calls `langgraph.prebuilt.create_react_agent` — never `AgentExecutor` (locked CLAUDE.md constraint). All per-job adapter instances are created inside the job function, never at module level (locked Phase 4 decision from STATE.md).

### agents.py Registry
- **D-04:** `src/robotina/agent/agents.py` defines an `AgentConfig` dataclass with fields: `task_type: str`, `model_config: dict` (provider, url, model, api_key_env), `prompt_path: str`, `skills: list[str]` (skill directory names), `tools: list` (empty list for now — tools added phase by phase).
- **D-05:** `agents.py` exposes a `get_agent_config(task_type: str) -> AgentConfig` lookup function. If `AGENT_OVERRIDES_FILEPATH` env var is set, the JSON file at that path is loaded and its fields override matching task types for `model_config` and `prompt_path` only. Override is applied per lookup (hot-reload without restart).
- **D-06:** Phase 4 registers exactly ONE task type entry: `"hello-world"` — a placeholder that sends a hardcoded "hello world" prompt to the LLM and logs the response. **This entry must be removed when the first real task type (`send-notification`) is added in Phase 6.**
- **D-07:** API tokens are read from env vars named by task type: `{TASK_TYPE_UPPER}_API_TOKEN` (e.g., `HELLO_WORLD_API_TOKEN`). The `model_config` stores the env var name, not the token value. The adapter reads the token via `os.environ` at instantiation time.

### Universal Job Handler (robotina/queue/jobs.py)
- **D-08:** Create `src/robotina/queue/jobs.py` with a single `run_task(task_input)` function. This is the universal RQ job function for ALL task types. It: (1) reads task type from input, (2) looks up `agents.py` for config, (3) instantiates the LLM backend, (4) builds skill context, (5) loads the versioned prompt, (6) runs the agent, (7) returns output. Phase 5 will wrap this with workflow state management.
- **D-09:** **Update the gateway** (`src/robotina/gateway/handler.py`) to enqueue `"robotina.queue.jobs.run_task"` instead of `"robotina.queue.jobs.handle_incoming_message"`. This fixes the Phase 3 placeholder string ref.

### Skill Loading
- **D-10:** Canonical skills directory: `src/robotina/agent/skills/`. Move the existing `household-manager` skill from `agent/skills/household-manager/` (project root) to `src/robotina/agent/skills/household-manager/`. Delete the old location.
- **D-11:** `SkillSet` class in `src/robotina/agent/` reads `index.md` from the skill directory at construction and exposes it as `index_content: str`. One `SkillSet` per configured skill in `agents.py`.
- **D-12:** A single `read_skill` LangChain `BaseTool` is constructed at agent setup from all configured `SkillSet` instances. Accepts `skill-name/subfile.md` path format. Resolves skill-name to its directory. **Blocks path traversal** — any `..` or absolute path in the sub-file argument raises a hard error.

### Prompt Versioning
- **D-13:** System prompts live at `src/robotina/agent/prompts/<task-type>/V001.md`. Old versions are kept (never deleted). The prompt loader reads the file at the path specified in `AgentConfig.prompt_path`.
- **D-14:** Phase 4 creates a placeholder `hello-world/V001.md` prompt. Other prompts (`send-notification/V001.md`, etc.) are created in their respective phases.

### Observability
- **D-15:** LangWatch + OTel instrumentation initializes at process startup in `run_task` (or in `runner.py`'s `main()`). Reads `LANGWATCH_ENDPOINT` and `LANGWATCH_API_KEY` from env vars. If either is missing, log a warning and continue (non-fatal) — allows running locally without LangWatch credentials.
- **D-16:** **Verification is manual only** for Phase 4. No automated test for LangWatch traces. Developer runs `uv run agent` + triggers a `hello-world` job and checks LangWatch UI. A note in the phase README documents this manual step.

### Claude's Discretion
- Exact `AgentConfig` field names and whether `model_config` is a nested dataclass or plain dict
- How `run_task` identifies task type from input (could be a `task_type` field on all Pydantic input models, or metadata from the RQ job)
- SQLAlchemy session handling in `run_task` if any DB reads are needed in Phase 4 (likely none needed until Phase 5 workflow integration)
- Whether `read_skill` tool is a standalone `@tool` function or a class inheriting from `BaseTool`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Agent infrastructure spec
- `plans/01-kickoff/spec.md` §"Agent" — `LLMBackend` Protocol verbatim definition, `SkillSet` pattern, `read-skill` tool spec, `AGENT_OVERRIDES_FILEPATH` override behavior, `agents.py` registry structure
- `plans/01-kickoff/spec.md` §"LLM" — Protocol class verbatim, adapter list, connection config requirements
- `plans/01-kickoff/spec.md` §"Non-functional Requirements" — prompt versioning format, LangWatch + OTel requirements

### Requirements
- `.planning/REQUIREMENTS.md` §AGENT-01 through AGENT-11 — all agent infrastructure acceptance criteria
- `.planning/REQUIREMENTS.md` §OBS-01, OBS-02 — LangWatch + OTel requirements in scope for Phase 4

### Prior context (locked decisions)
- `.planning/phases/01-developer-tooling-and-infrastructure/01-CONTEXT.md` — D-02 (pyproject.toml script pattern), D-03 (queue name `agent-tasks`)
- `.planning/phases/02-database-models-and-queue-layer/02-CONTEXT.md` — D-06 (task_types.py location)
- `.planning/phases/03-gateway/03-CONTEXT.md` — D-03/D-04 (gateway entry points), D-05 (enqueue pattern)

### Existing code to update
- `src/robotina/gateway/handler.py` — enqueue string ref to change from `handle_incoming_message` to `run_task`
- `src/robotina/queue/runner.py` — LoggingWorker, `main()` entry point — LangWatch init may attach here
- `src/robotina/llm/__init__.py` — empty stub, receives Protocol + adapters
- `src/robotina/agent/__init__.py` — empty stub, receives SkillSet, agents.py, jobs.py
- `agent/skills/household-manager/` — move to `src/robotina/agent/skills/household-manager/`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/robotina/queue/runner.py` — `LoggingWorker`, `main()` pattern; LangWatch init should follow the same startup pattern
- `src/robotina/queue/task_types.py` — all Pydantic input/output models; `run_task` dispatches based on these types
- `src/robotina/llm/__init__.py` — empty stub, ready to receive `LLMBackend` Protocol + adapters
- `src/robotina/agent/__init__.py` — empty stub, ready to receive agent infrastructure
- `agent/skills/household-manager/` — fully implemented skill; move to canonical location in Phase 4

### Established Patterns
- All per-job objects instantiated inside the job function, never at module level (locked from STATE.md)
- Queue name: `agent-tasks` (locked Phase 1)
- All RQ jobs: `result_ttl=-1`, `failure_ttl=-1` (locked Phase 1)
- SQLAlchemy 2.x `Mapped` + `mapped_column` style
- Pydantic v2 syntax throughout
- `uv run` scripts in `[project.scripts]` — no new scripts needed for Phase 4

### Integration Points
- `robotina.queue.jobs.run_task` — the new universal RQ job function; gateway and future task runner both reference this string
- `agents.py` — looked up by `run_task` at job execution time; hot-reloaded via `AGENT_OVERRIDES_FILEPATH`
- `src/robotina/agent/skills/` — canonical location for all skills; `SkillSet` resolves from here
- Phase 5 will wrap `run_task` with workflow state management — keep `run_task` interface clean and single-purpose

</code_context>

<specifics>
## Specific Ideas

- The `hello-world` task type placeholder sends "hello world" to the LLM and logs the response — exists only to prove the full pipeline (agents.py lookup → adapter instantiation → agent invocation → output logged). **Remove it when `send-notification` is added in Phase 6.**
- LangWatch missing credentials should be non-fatal — log a warning, allow local development without a LangWatch account.
- `AGENT_OVERRIDES_FILEPATH` override is hot-reload (applied per lookup, not at startup) — supports prompt experimentation without redeploy.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-llm-module-and-agent-infrastructure*
*Context gathered: 2026-03-25*
