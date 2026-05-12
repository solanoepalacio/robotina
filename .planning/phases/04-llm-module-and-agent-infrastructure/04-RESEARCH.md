# Phase 4: LLM Module and Agent Infrastructure - Research

**Researched:** 2026-03-25
**Domain:** LangChain/LangGraph agent execution, LLMBackend Protocol, skill loading, prompt versioning, LangWatch + OTel instrumentation
**Confidence:** HIGH (verified against installed library versions in the project venv)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### LLM Module (robotina/llm/)
- **D-01:** `LLMBackend` Protocol lives in `src/robotina/llm/` (the stub module already exists). Implement verbatim from spec: `model` property → `BaseChatModel`, `create_agent()` → returns `create_react_agent` runnable.
- **D-02:** Three adapter classes in `robotina/llm/`: `OllamaBackend`, `AnthropicBackend`, `OpenAIBackend`. Each reads connection details (url, model, api_key) from a config dict passed at construction. Each wraps the appropriate LangChain class (`ChatOllama`, `ChatAnthropic`, `ChatOpenAI`).
- **D-03:** `create_agent()` calls `langgraph.prebuilt.create_react_agent` — never `AgentExecutor` (locked CLAUDE.md constraint). All per-job adapter instances are created inside the job function, never at module level (locked Phase 4 decision from STATE.md).

#### agents.py Registry
- **D-04:** `src/robotina/agent/agents.py` defines an `AgentConfig` dataclass with fields: `task_type: str`, `model_config: dict` (provider, url, model, api_key_env), `prompt_path: str`, `skills: list[str]` (skill directory names), `tools: list` (empty list for now — tools added phase by phase).
- **D-05:** `agents.py` exposes a `get_agent_config(task_type: str) -> AgentConfig` lookup function. If `AGENT_OVERRIDES_FILEPATH` env var is set, the JSON file at that path is loaded and its fields override matching task types for `model_config` and `prompt_path` only. Override is applied per lookup (hot-reload without restart).
- **D-06:** Phase 4 registers exactly ONE task type entry: `"hello-world"` — a placeholder that sends a hardcoded "hello world" prompt to the LLM and logs the response. **This entry must be removed when the first real task type (`send-notification`) is added in Phase 6.**
- **D-07:** API tokens are read from env vars named by task type: `{TASK_TYPE_UPPER}_API_TOKEN` (e.g., `HELLO_WORLD_API_TOKEN`). The `model_config` stores the env var name, not the token value. The adapter reads the token via `os.environ` at instantiation time.

#### Universal Job Handler (robotina/queue/jobs.py)
- **D-08:** Create `src/robotina/queue/jobs.py` with a single `run_task(task_input)` function. This is the universal RQ job function for ALL task types. It: (1) reads task type from input, (2) looks up `agents.py` for config, (3) instantiates the LLM backend, (4) builds skill context, (5) loads the versioned prompt, (6) runs the agent, (7) returns output. Phase 5 will wrap this with workflow state management.
- **D-09:** **Update the gateway** (`src/robotina/gateway/handler.py`) to enqueue `"robotina.queue.jobs.run_task"` instead of `"robotina.queue.jobs.handle_incoming_message"`. This fixes the Phase 3 placeholder string ref.

#### Skill Loading
- **D-10:** Canonical skills directory: `src/robotina/agent/skills/`. Move the existing `household-manager` skill from `agent/skills/household-manager/` (project root) to `src/robotina/agent/skills/household-manager/`. Delete the old location.
- **D-11:** `SkillSet` class in `src/robotina/agent/` reads `index.md` from the skill directory at construction and exposes it as `index_content: str`. One `SkillSet` per configured skill in `agents.py`.
- **D-12:** A single `read_skill` LangChain `BaseTool` is constructed at agent setup from all configured `SkillSet` instances. Accepts `skill-name/subfile.md` path format. Resolves skill-name to its directory. **Blocks path traversal** — any `..` or absolute path in the sub-file argument raises a hard error.

#### Prompt Versioning
- **D-13:** System prompts live at `src/robotina/agent/prompts/<task-type>/V001.md`. Old versions are kept (never deleted). The prompt loader reads the file at the path specified in `AgentConfig.prompt_path`.
- **D-14:** Phase 4 creates a placeholder `hello-world/V001.md` prompt. Other prompts (`send-notification/V001.md`, etc.) are created in their respective phases.

#### Observability
- **D-15:** LangWatch + OTel instrumentation initializes at process startup in `run_task` (or in `runner.py`'s `main()`). Reads `LANGWATCH_ENDPOINT` and `LANGWATCH_API_KEY` from env vars. If either is missing, log a warning and continue (non-fatal) — allows running locally without LangWatch credentials.
- **D-16:** **Verification is manual only** for Phase 4. No automated test for LangWatch traces. Developer runs `uv run agent` + triggers a `hello-world` job and checks LangWatch UI.

### Claude's Discretion
- Exact `AgentConfig` field names and whether `model_config` is a nested dataclass or plain dict
- How `run_task` identifies task type from input (could be a `task_type` field on all Pydantic input models, or metadata from the RQ job)
- SQLAlchemy session handling in `run_task` if any DB reads are needed in Phase 4 (likely none needed until Phase 5 workflow integration)
- Whether `read_skill` tool is a standalone `@tool` function or a class inheriting from `BaseTool`

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AGENT-01 | `LLMBackend` Protocol abstraction exists with `model` property and `create_agent()` method | Protocol definition verbatim from spec; `@runtime_checkable` decorator; `BaseChatModel` import from `langchain_core.language_models` |
| AGENT-02 | Three LLM adapters implemented: Ollama, Anthropic, OpenAI | Exact field names verified: `ChatOllama(model=, base_url=)`, `ChatAnthropic(model=, anthropic_api_url=, anthropic_api_key=)`, `ChatOpenAI(model_name=, openai_api_base=, openai_api_key=)` |
| AGENT-03 | `agents.py` defines per-task-type configuration | `AgentConfig` dataclass + `get_agent_config()` + AGENT_OVERRIDES_FILEPATH hot-reload pattern |
| AGENT-04 | Agent model API tokens read from env vars named by task type | `{TASK_TYPE_UPPER}_API_TOKEN` pattern; stored as env var name in `model_config`, resolved at adapter instantiation |
| AGENT-05 | Developer can override model or prompt per task type at runtime via `AGENT_OVERRIDES_FILEPATH` | JSON file loaded per lookup (not at startup); only `model_config` and `prompt_path` overridable |
| AGENT-06 | Each skill is a directory under `src/agent/skills/` with `index.md`; `index_content` pre-loaded | `SkillSet` class reads `index.md` at construction; content appended to system prompt |
| AGENT-07 | Agent loads skill sub-files on demand via `read-skill` tool; path traversal blocked | `BaseTool` subclass with state (skill directories map); path traversal check via `pathlib.Path.resolve()` comparison |
| AGENT-08 | System prompts are versioned markdown files at `src/agent/prompts/<task-type>/V001.md`; old versions kept | File-based versioning; loader reads path from `AgentConfig.prompt_path` |
| AGENT-09 | Debug log level can be enabled independently per module | Standard Python per-module `logging.getLogger(__name__)` + env var per module (e.g. `ROBOTINA_LOG_LEVEL_AGENT`) |
| AGENT-10 | All agent actions logged (LLM stream start, tool calls and results) | `BaseCallbackHandler` subclass with `on_llm_start`, `on_tool_start`, `on_tool_end` methods; passed via `config={'callbacks': [...]}` |
| AGENT-11 | `create_react_agent` from `langgraph.prebuilt` is used for all agents | **CRITICAL: Deprecated in LangGraph v1.1.3** — emits `LangGraphDeprecatedSinceV10` at call time; still functional. Replacement is `langchain.agents.create_agent`. Per CONTEXT.md D-03, spec requires `create_react_agent` — **planner must decide whether to use deprecated API or upgrade** |
| OBS-01 | LangWatch + OTel instrumentation active on all agents | `langwatch.setup(instrumentors=[LangChainInstrumentor()])` — `openinference-instrumentation-langchain` is a transitive dep (pulled by `langwatch`) |
| OBS-02 | LangWatch endpoint and API key read from environment variables | `langwatch.setup(api_key=os.getenv('LANGWATCH_API_KEY'), endpoint_url=os.getenv('LANGWATCH_ENDPOINT'))` |
</phase_requirements>

---

## Summary

Phase 4 builds the general-purpose agent execution foundation for Robotina. Research revealed one critical discrepancy: `create_react_agent` from `langgraph.prebuilt` (required by AGENT-11 and CONTEXT.md D-03) emits a `LangGraphDeprecatedSinceV10` warning at call time in the installed version (LangGraph 1.1.3). The replacement `langchain.agents.create_agent` is available and functionally equivalent. Since CONTEXT.md explicitly locks `create_react_agent from langgraph.prebuilt`, the planner should use the locked API and note the deprecation warning in the implementation plan — the API remains functional and the decision to upgrade belongs to a future phase.

All other libraries are correctly installed and verified at their actual versions. LangWatch setup is straightforward: `langwatch.setup()` with `openinference-instrumentation-langchain` (already a transitive dep) auto-instruments LangChain/LangGraph calls. The `read_skill` tool must be a `BaseTool` subclass (not a `@tool` function) because it needs to hold skill directory state. The task type should be read from `get_current_job().meta['task_type']` rather than adding a field to all Pydantic models, since the gateway already sets this metadata.

**Primary recommendation:** Use `create_react_agent` from `langgraph.prebuilt` as locked (accept the deprecation warning, it remains functional in v1.1.3). Use `langwatch.setup(api_key=..., endpoint_url=..., instrumentors=[LangChainInstrumentor()])` for auto-instrumentation. Read task type from `get_current_job().meta['task_type']` inside `run_task`.

---

## Standard Stack

### Core (verified installed in project venv)
| Library | Installed Version | Purpose | Notes |
|---------|-------------------|---------|-------|
| langchain | 1.2.13 | Agent orchestration, `create_agent` factory | `langchain.agents.create_agent` is the new preferred API |
| langchain-core | 1.2.22 | `BaseChatModel`, `BaseTool`, `BaseCallbackHandler` | Import from `langchain_core` wherever possible |
| langgraph | 1.1.3 | `create_react_agent` (deprecated but functional) | Locked per AGENT-11/D-03; emits `LangGraphDeprecatedSinceV10` at call time |
| langchain-anthropic | 1.4.0 | `ChatAnthropic` adapter | Fields: `model`, `anthropic_api_url`, `anthropic_api_key` |
| langchain-openai | 1.1.12 | `ChatOpenAI` adapter | Fields: `model_name`, `openai_api_base`, `openai_api_key` |
| langchain-ollama | 1.0.1 | `ChatOllama` adapter | Fields: `model`, `base_url` (no api_key — Ollama is unauthenticated) |
| langwatch | 0.17.0 | LLM trace collection | `langwatch.setup()` API verified |
| opentelemetry-sdk | 1.40.0 | OTel SDK | Auto-pulled by langwatch |
| opentelemetry-api | 1.40.0 | OTel API | Import from `opentelemetry.trace` |
| openinference-instrumentation-langchain | 0.1.61 | LangChain OTel auto-instrumentation | Transitive dep of langwatch; not in pyproject.toml directly |

### Supporting
| Library | Purpose | When to Use |
|---------|---------|-------------|
| `rq.get_current_job` | Access RQ job metadata inside a job function | Reading `task_type` from `job.meta` in `run_task` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `langgraph.prebuilt.create_react_agent` | `langchain.agents.create_agent` | `create_agent` is the successor (no deprecation warning); uses `system_prompt=` kwarg instead of `prompt=`; functionally equivalent output (messages list). Per CONTEXT.md D-03, `create_react_agent` is locked — use that. |
| `@tool` decorator for read_skill | `BaseTool` subclass | `@tool` cannot hold instance state (skill directories). `BaseTool` subclass is required to close over the skill map. |
| `get_current_job().meta['task_type']` | `task_type: Literal[...]` field on input models | Adding `task_type` to all input models would require modifying `task_types.py` (Phase 2 code). Using `get_current_job()` is zero-model-change and already populated by the gateway. |

---

## Architecture Patterns

### Recommended Project Structure
```
src/robotina/
├── llm/
│   └── __init__.py         # LLMBackend Protocol + OllamaBackend, AnthropicBackend, OpenAIBackend
├── agent/
│   ├── __init__.py         # SkillSet class
│   ├── agents.py           # AgentConfig dataclass + get_agent_config() + AGENT_OVERRIDES_FILEPATH
│   ├── skills/
│   │   └── household-manager/
│   │       ├── index.md    # (moved from agent/skills/household-manager/)
│   │       └── *.md        # sub-files
│   └── prompts/
│       └── hello-world/
│           └── V001.md     # placeholder prompt
└── queue/
    ├── jobs.py             # run_task() universal RQ job function
    └── runner.py           # existing — LangWatch init added to main()
```

### Pattern 1: LLMBackend Protocol (verbatim from spec)
**What:** Runtime-checkable Protocol that all adapters implement. Consumers depend only on this interface.
**When to use:** Any code that instantiates or calls an agent.
```python
# Source: plans/01-kickoff/spec.md §LLM
from typing import Any, Protocol, runtime_checkable
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

@runtime_checkable
class LLMBackend(Protocol):
    """Interface for LLM adapters. Each agent run holds its own backend instance."""

    @property
    def model(self) -> BaseChatModel:
        """The underlying LangChain chat model."""
        ...

    def create_agent(
        self,
        system_prompt: str,
        tools: list[BaseTool] | None = None,
    ) -> Any:
        """Return a runnable LangChain agent bound to this model."""
        ...
```

### Pattern 2: Adapter Implementation (verified field names)
**What:** Concrete adapter classes wrapping LangChain chat models.
**When to use:** Inside `create_agent()` implementations in each adapter class.
```python
# Source: verified against installed langchain-ollama 1.0.1, langchain-anthropic 1.4.0,
#          langchain-openai 1.1.12
from langgraph.prebuilt import create_react_agent  # locked per AGENT-11/D-03

class OllamaBackend:
    def __init__(self, config: dict) -> None:
        from langchain_ollama import ChatOllama
        api_key_env = config.get("api_key_env", "")
        self._model = ChatOllama(
            model=config["model"],
            base_url=config.get("url"),  # None = default http://localhost:11434
        )

    @property
    def model(self) -> BaseChatModel:
        return self._model

    def create_agent(self, system_prompt: str, tools: list[BaseTool] | None = None):
        return create_react_agent(
            model=self._model,
            tools=tools or [],
            prompt=system_prompt,  # 'prompt' kwarg (not 'system_prompt') in create_react_agent
        )

class AnthropicBackend:
    def __init__(self, config: dict) -> None:
        from langchain_anthropic import ChatAnthropic
        api_key = os.environ[config["api_key_env"]]  # hard error if missing
        self._model = ChatAnthropic(
            model=config["model"],
            anthropic_api_url=config.get("url"),
            anthropic_api_key=api_key,
        )
    # ... model property + create_agent same pattern

class OpenAIBackend:
    def __init__(self, config: dict) -> None:
        from langchain_openai import ChatOpenAI
        api_key = os.environ[config["api_key_env"]]
        self._model = ChatOpenAI(
            model_name=config["model"],      # NOTE: model_name not model
            openai_api_base=config.get("url"),
            openai_api_key=api_key,
        )
    # ... model property + create_agent same pattern
```

**Key field name gotcha (HIGH confidence — verified):**
- `ChatOpenAI`: `model_name` (not `model`), `openai_api_base` (not `base_url`), `openai_api_key`
- `ChatAnthropic`: `model`, `anthropic_api_url`, `anthropic_api_key`
- `ChatOllama`: `model`, `base_url` (no api_key field — Ollama is unauthenticated)

### Pattern 3: AgentConfig + Registry
**What:** Dataclass holding per-task-type config; `get_agent_config()` with hot-reload from JSON override file.
```python
# Source: CONTEXT.md D-04/D-05
from dataclasses import dataclass, field
import json, os

@dataclass
class AgentConfig:
    task_type: str
    model_config: dict          # {provider, url, model, api_key_env}
    prompt_path: str
    skills: list[str] = field(default_factory=list)
    tools: list = field(default_factory=list)

AGENT_REGISTRY: dict[str, AgentConfig] = {
    "hello-world": AgentConfig(
        task_type="hello-world",
        model_config={
            "provider": "ollama",
            "url": "http://localhost:11434",
            "model": "llama3.2",
            "api_key_env": "HELLO_WORLD_API_TOKEN",
        },
        prompt_path="src/robotina/agent/prompts/hello-world/V001.md",
        skills=[],
        tools=[],
    )
}

def get_agent_config(task_type: str) -> AgentConfig:
    config = AGENT_REGISTRY[task_type]          # KeyError = unsupported task type
    overrides_path = os.getenv("AGENT_OVERRIDES_FILEPATH")
    if overrides_path:
        with open(overrides_path) as f:
            overrides = json.load(f)
        if task_type in overrides:
            o = overrides[task_type]
            if "model_config" in o:
                config = AgentConfig(**{**vars(config), "model_config": o["model_config"]})
            if "prompt_path" in o:
                config = AgentConfig(**{**vars(config), "prompt_path": o["prompt_path"]})
    return config
```

### Pattern 4: SkillSet + read_skill Tool
**What:** `SkillSet` loads `index.md` at construction. `ReadSkillTool` is a `BaseTool` subclass that closes over the skill-directory map.
**When to use:** Inside `run_task()` when building agent context.
```python
# Source: spec §Skills, CONTEXT.md D-11/D-12
from pathlib import Path
from langchain_core.tools import BaseTool
from pydantic import Field

SKILLS_BASE = Path(__file__).parent / "skills"

class SkillSet:
    def __init__(self, skill_name: str) -> None:
        self.skill_name = skill_name
        self.skill_dir = SKILLS_BASE / skill_name
        index_path = self.skill_dir / "index.md"
        self.index_content: str = index_path.read_text()

class ReadSkillTool(BaseTool):
    name: str = "read-skill"
    description: str = (
        "Load a skill sub-file. Accept path in 'skill-name/subfile.md' format "
        "(e.g. 'household-manager/api-endpoints.md')."
    )
    skill_dirs: dict[str, Path] = Field(default_factory=dict)  # skill_name -> Path

    def _run(self, path: str) -> str:
        # Validate format
        parts = path.split("/", 1)
        if len(parts) != 2:
            raise ValueError("Path must be 'skill-name/subfile.md'")
        skill_name, subfile = parts
        if skill_name not in self.skill_dirs:
            raise ValueError(f"Unknown skill: {skill_name!r}")
        # Block path traversal
        base = self.skill_dirs[skill_name].resolve()
        target = (base / subfile).resolve()
        if not str(target).startswith(str(base)):
            raise ValueError("Path traversal outside skill directory is not allowed")
        return target.read_text()

def build_read_skill_tool(skill_sets: list[SkillSet]) -> ReadSkillTool:
    return ReadSkillTool(
        skill_dirs={ss.skill_name: ss.skill_dir for ss in skill_sets}
    )
```

### Pattern 5: LangWatch Initialization
**What:** One-time setup at process startup. Non-fatal if credentials missing.
```python
# Source: langwatch 0.17.0 API verified via introspection
import os
import logging
import langwatch
from openinference.instrumentation.langchain import LangChainInstrumentor

logger = logging.getLogger(__name__)

def setup_langwatch() -> None:
    """Initialize LangWatch + OTel. Non-fatal if credentials are absent."""
    api_key = os.getenv("LANGWATCH_API_KEY")
    endpoint_url = os.getenv("LANGWATCH_ENDPOINT")
    if not api_key or not endpoint_url:
        logger.warning(
            "LangWatch credentials not set (LANGWATCH_API_KEY, LANGWATCH_ENDPOINT) "
            "— traces will not be sent"
        )
        return
    langwatch.setup(
        api_key=api_key,
        endpoint_url=endpoint_url,
        instrumentors=[LangChainInstrumentor()],
    )
    logger.info("LangWatch instrumentation initialized (endpoint=%s)", endpoint_url)
```

### Pattern 6: run_task Universal Job Function
**What:** Single RQ job function for all task types. Reads task type from RQ job metadata.
```python
# Source: CONTEXT.md D-08; get_current_job() from rq
from rq import get_current_job

def run_task(task_input) -> object:
    """Universal RQ job function for all task types."""
    job = get_current_job()
    task_type = job.meta.get("task_type") if job else None
    if not task_type:
        raise ValueError("run_task: job has no task_type in meta")

    config = get_agent_config(task_type)

    # Instantiate LLM backend (always per-job, never module-level — STATE.md constraint)
    backend = _make_backend(config.model_config)

    # Build skill context
    skill_sets = [SkillSet(s) for s in config.skills]
    skill_index = "\n\n".join(ss.index_content for ss in skill_sets)
    tools = list(config.tools)
    if skill_sets:
        tools.append(build_read_skill_tool(skill_sets))

    # Load versioned prompt
    prompt_text = Path(config.prompt_path).read_text()
    if skill_index:
        prompt_text = prompt_text + "\n\n" + skill_index

    # Create and invoke agent
    agent = backend.create_agent(system_prompt=prompt_text, tools=tools)
    callback_handler = AgentLoggingHandler()  # AGENT-10
    result = agent.invoke(
        {"messages": [{"role": "user", "content": _extract_user_message(task_input)}]},
        config={"callbacks": [callback_handler]},
    )
    return result
```

### Pattern 7: Agent Logging Callback (AGENT-10)
**What:** LangChain callback handler for structured action logging.
```python
# Source: langchain_core.callbacks verified
from langchain_core.callbacks import BaseCallbackHandler

class AgentLoggingHandler(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kwargs):
        logger.info("LLM stream start | model=%s", serialized.get("name"))

    def on_tool_start(self, serialized, input_str, **kwargs):
        logger.info("Tool call | tool=%s input=%s", serialized.get("name"), input_str[:200])

    def on_tool_end(self, output, **kwargs):
        logger.info("Tool result | output=%s", str(output)[:200])
```

### Pattern 8: Per-Module Debug Logging (AGENT-09)
**What:** Each module uses `logging.getLogger(__name__)` and log level is configurable via env var.
```python
# Standard Python pattern, no new framework needed
import logging
import os

def configure_logging() -> None:
    """Called at process startup in runner.main()."""
    modules = ["gateway", "queue", "agent", "llm"]
    for module in modules:
        env_key = f"ROBOTINA_LOG_LEVEL_{module.upper()}"
        level_str = os.getenv(env_key, "")
        if level_str:
            level = getattr(logging, level_str.upper(), None)
            if level:
                logging.getLogger(f"robotina.{module}").setLevel(level)
```

### Anti-Patterns to Avoid
- **Module-level adapter instantiation:** Never create `ChatOllama()`, `ChatAnthropic()`, or `ChatOpenAI()` at import time or module level. All per-job objects must be created inside `run_task()` (locked STATE.md decision).
- **Hardcoded API tokens in agents.py:** `model_config` stores the env var NAME, not the value. Adapter reads `os.environ[config["api_key_env"]]` at instantiation.
- **Using `AgentExecutor`:** Deprecated since LangChain 0.2, must not be used. Both spec and CLAUDE.md lock this.
- **Path traversal in read_skill:** Do not use `str.startswith()` on un-resolved paths — always call `.resolve()` on both base and target before comparison to defeat symlinks and `..` segments.
- **Single langwatch.setup() call with hard-fail:** Missing credentials must be non-fatal (log warning, return). Allows local development without LangWatch account.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Agent tool-call loop | Custom LLM call loop | `create_react_agent` / `create_agent` | ReAct loop handles retry, tool output re-injection, loop termination |
| LLM streaming + callback | Custom streaming parser | `BaseCallbackHandler.on_llm_start` / `on_tool_start` | LangChain callback system handles all lifecycle events |
| OTel trace propagation | Custom trace context | `langwatch.setup(instrumentors=[LangChainInstrumentor()])` | Auto-instruments all LangChain/LangGraph calls transparently |
| Per-job provider selection | `if provider == 'ollama': ...` in run_task | `LLMBackend` Protocol + adapter registry | Protocol isolates consumer from provider; adding a 4th provider requires zero `run_task` changes |

**Key insight:** The entire adapter + Protocol design exists to avoid conditional provider dispatch in the hot path. `run_task` never calls `langchain_openai` directly — it only calls `backend.create_agent()`.

---

## Common Pitfalls

### Pitfall 1: create_react_agent Deprecation Warning Noise
**What goes wrong:** LangGraph 1.1.3 emits `LangGraphDeprecatedSinceV10` at every call to `create_react_agent`. Tests using `pytest -W error` will fail.
**Why it happens:** LangGraph v1.0 moved the recommended API to `langchain.agents.create_agent`.
**How to avoid:** In `pyproject.toml` or `pytest.ini`, add `filterwarnings = ["ignore::DeprecationWarning:langgraph"]` if warning noise is unacceptable. The API remains fully functional through at least LangGraph v1.x (removal scheduled for v2.0).
**Warning signs:** Test output containing `LangGraphDeprecatedSinceV10` or deprecation warnings in CI.

### Pitfall 2: ChatOpenAI Field Name Mismatch
**What goes wrong:** `ChatOpenAI(model="gpt-4o")` fails with a Pydantic validation error.
**Why it happens:** The field is `model_name`, not `model`. This differs from `ChatAnthropic` and `ChatOllama` which both use `model`.
**How to avoid:** Always use `ChatOpenAI(model_name=config["model"], ...)`. Verified in langchain-openai 1.1.12.
**Warning signs:** `pydantic_core.ValidationError: model field not found`.

### Pitfall 3: Unresolved Path Traversal in read_skill
**What goes wrong:** `path.resolve()` is not called before `str.startswith()`, allowing symlink-based escapes or `../sibling-dir/..` attacks.
**Why it happens:** `str.startswith()` on unreleased paths is not traversal-safe.
**How to avoid:** Always: `base = skill_dir.resolve()`, `target = (base / subfile).resolve()`, `assert str(target).startswith(str(base))`.
**Warning signs:** `../../etc/passwd` in subfile arg passes the check.

### Pitfall 4: AGENT_OVERRIDES_FILEPATH Loaded at Module Import
**What goes wrong:** Override file is read once at import time; changes to the file require process restart.
**Why it happens:** Putting `json.load()` in module-level code.
**How to avoid:** Read the file inside `get_agent_config()` on every call — the override is intentionally hot-reloadable per D-05.
**Warning signs:** Override changes require `uv run agent` restart to take effect.

### Pitfall 5: LangWatch init called inside job function (per-job overhead)
**What goes wrong:** `langwatch.setup()` called inside `run_task()` re-registers OTel tracer provider on every job execution, causing memory leaks or duplicate trace exporters.
**Why it happens:** Misreading D-15 "initializes at process startup in `run_task`" as calling setup() inside the function body on every invocation.
**How to avoid:** Call `langwatch.setup()` once in `runner.main()` before the worker starts, OR use a module-level sentinel (`_langwatch_initialized = False`) + call-once guard.
**Warning signs:** Multiple `TracerProvider` registrations in logs; memory growing across job executions.

### Pitfall 6: task_type not set in meta for hello-world enqueue
**What goes wrong:** `run_task` calls `get_current_job().meta.get('task_type')` but the test enqueue of `hello-world` doesn't set `meta={"task_type": "hello-world"}`.
**Why it happens:** Test code copies gateway enqueue pattern but omits the meta dict.
**How to avoid:** All `q.enqueue(run_task, ...)` calls must include `meta={"task_type": task_type}`. Fallback in `run_task` should raise `ValueError` with clear message, not silently use `None`.
**Warning signs:** `ValueError: run_task: job has no task_type in meta`.

---

## Code Examples

### Verified: create_react_agent signature (LangGraph 1.1.3)
```python
# Source: verified via introspection on installed langgraph 1.1.3
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(
    model=chat_model,           # BaseChatModel instance
    tools=tools_list,           # list[BaseTool | Callable | dict]
    prompt=system_prompt_str,   # str | SystemMessage | None — kwarg is 'prompt' not 'system_prompt'
)
# Returns: langgraph.graph.state.CompiledStateGraph
# Invoke: result = agent.invoke({"messages": [{"role": "user", "content": "..."}]})
# Output: {"messages": [...]} — last message is the agent's final response
```

### Verified: langwatch.setup() (langwatch 0.17.0)
```python
# Source: verified via introspection on installed langwatch 0.17.0
import langwatch
from openinference.instrumentation.langchain import LangChainInstrumentor

langwatch.setup(
    api_key="...",               # str | None — reads LANGWATCH_API_KEY if None
    endpoint_url="...",          # str | None — reads LANGWATCH_ENDPOINT if None
    instrumentors=[LangChainInstrumentor()],  # auto-instruments all LangChain calls
)
```

### Verified: ChatAnthropic field names (langchain-anthropic 1.4.0)
```python
from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    anthropic_api_url="https://api.anthropic.com",  # NOT base_url
    anthropic_api_key="sk-ant-...",                 # NOT api_key
)
```

### Verified: ChatOpenAI field names (langchain-openai 1.1.12)
```python
from langchain_openai import ChatOpenAI

model = ChatOpenAI(
    model_name="gpt-4o",          # NOT model — critical difference from other adapters
    openai_api_base="https://...", # NOT base_url
    openai_api_key="sk-...",       # NOT api_key
)
```

### Verified: ChatOllama field names (langchain-ollama 1.0.1)
```python
from langchain_ollama import ChatOllama

model = ChatOllama(
    model="llama3.2",
    base_url="http://localhost:11434",  # None = default
    # No api_key field — Ollama is unauthenticated by default
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `create_react_agent` from `langgraph.prebuilt` | `create_agent` from `langchain.agents` | LangGraph v1.0 | Deprecation warning at call time; `prompt=` kwarg renamed to `system_prompt=`; both return `CompiledStateGraph` |
| `AgentExecutor` from `langchain.agents` | `create_react_agent` / `create_agent` | LangChain 0.2 | Must not be used; deprecated and pending removal |
| Manual OTel setup | `langwatch.setup(instrumentors=[LangChainInstrumentor()])` | langwatch ~0.10+ | One call auto-instruments all LangChain/LangGraph calls |

**Deprecated/outdated:**
- `AgentExecutor`: Must not be used per CLAUDE.md and spec. Removed from recommended path LangChain 0.2+.
- `langchain.prebuilt.create_react_agent` (the old path): Moved to `langgraph.prebuilt` and now deprecated from there too. The permanent home is `langchain.agents.create_agent`.
- `rq-scheduler` (PyPI package): Superseded by native RQ 2.5 scheduler. Not needed here.

---

## Open Questions

1. **create_react_agent deprecation — suppress or migrate?**
   - What we know: `create_react_agent` from `langgraph.prebuilt` emits `LangGraphDeprecatedSinceV10` at call time in langgraph 1.1.3. It remains functional. The replacement `langchain.agents.create_agent` is installed and working. `create_agent` uses `system_prompt=` kwarg instead of `prompt=`.
   - What's unclear: CONTEXT.md D-03 locks `create_react_agent from langgraph.prebuilt`. Should Phase 4 use the locked (deprecated) API or upgrade to `create_agent`?
   - Recommendation: **Planner decision.** If staying with `create_react_agent`: add `filterwarnings` in pytest config. If upgrading: change D-03 in CONTEXT.md and use `langchain.agents.create_agent(model=..., tools=..., system_prompt=...)`. Either works functionally. Upgrading now is cleaner than carrying a deprecation warning into all future phases.

2. **`run_task` — is `get_current_job()` available in all execution contexts?**
   - What we know: `rq.get_current_job()` works inside RQ job functions (work-horse subprocess). `LoggingWorker.perform_job` runs in the forked work-horse; `run_task` runs there too.
   - What's unclear: Does `get_current_job()` work in unit tests that call `run_task` directly (not via RQ)?
   - Recommendation: `run_task` should handle `get_current_job()` returning `None` gracefully — allow `task_type` to be passed as a keyword argument fallback for testing.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| langchain | LLMBackend Protocol, adapters | Yes | 1.2.13 | — |
| langgraph | `create_react_agent` | Yes | 1.1.3 | — |
| langchain-anthropic | AnthropicBackend | Yes | 1.4.0 | — |
| langchain-openai | OpenAIBackend | Yes | 1.1.12 | — |
| langchain-ollama | OllamaBackend | Yes | 1.0.1 | — |
| langwatch | OBS-01/OBS-02 | Yes | 0.17.0 | — |
| openinference-instrumentation-langchain | LangChain OTel auto-instrumentation | Yes (transitive) | 0.1.61 | — |
| opentelemetry-sdk/api | OTel spans | Yes | 1.40.0 | — |
| Ollama (local server) | OllamaBackend in dev | Not verified (runtime) | — | Use AnthropicBackend or OpenAIBackend with valid creds |

**Missing dependencies with no fallback:** None — all code dependencies are installed.

**Runtime note:** The `hello-world` task type requires a running LLM provider (Ollama local or API credentials). Phase 4 itself does not verify Ollama availability — that is a developer configuration step documented in the phase README.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (in dev deps) + pytest-asyncio |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AGENT-01 | `LLMBackend` Protocol importable; class-check via `isinstance` | unit | `uv run pytest tests/test_llm.py -x` | No — Wave 0 |
| AGENT-02 | Three adapter classes importable; each implements `LLMBackend` Protocol | unit | `uv run pytest tests/test_llm.py -x` | No — Wave 0 |
| AGENT-03 | `agents.py` importable; `get_agent_config("hello-world")` returns `AgentConfig` | unit | `uv run pytest tests/test_agents.py -x` | No — Wave 0 |
| AGENT-04 | `model_config["api_key_env"]` is a string; adapter raises `KeyError` if env var missing | unit | `uv run pytest tests/test_agents.py -x` | No — Wave 0 |
| AGENT-05 | `get_agent_config()` with `AGENT_OVERRIDES_FILEPATH` set returns overridden values | unit | `uv run pytest tests/test_agents.py -x` | No — Wave 0 |
| AGENT-06 | `SkillSet("household-manager").index_content` is a non-empty string | unit | `uv run pytest tests/test_agent_skills.py -x` | No — Wave 0 |
| AGENT-07 | `ReadSkillTool._run("household-manager/shared.md")` returns content; `_run("../../etc/passwd")` raises `ValueError` | unit | `uv run pytest tests/test_agent_skills.py -x` | No — Wave 0 |
| AGENT-08 | `prompts/hello-world/V001.md` exists and is readable | unit | `uv run pytest tests/test_agents.py -x` | No — Wave 0 |
| AGENT-09 | `ROBOTINA_LOG_LEVEL_AGENT=DEBUG` changes logger level | unit | `uv run pytest tests/test_logging.py -x` | No — Wave 0 |
| AGENT-10 | `AgentLoggingHandler` fires `on_llm_start` and `on_tool_start` | unit | `uv run pytest tests/test_agent_logging.py -x` | No — Wave 0 |
| AGENT-11 | `create_react_agent` invoked in `create_agent()` (source inspection) | unit | `uv run pytest tests/test_llm.py -x` | No — Wave 0 |
| OBS-01 | `langwatch.setup()` called in `runner.main()` source | unit | `uv run pytest tests/test_runner.py -x` | Partial (file exists, new test needed) |
| OBS-02 | `setup_langwatch()` reads `LANGWATCH_API_KEY` and `LANGWATCH_ENDPOINT` | unit | `uv run pytest tests/test_observability.py -x` | No — Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_llm.py` — covers AGENT-01, AGENT-02, AGENT-11
- [ ] `tests/test_agents.py` — covers AGENT-03, AGENT-04, AGENT-05, AGENT-08
- [ ] `tests/test_agent_skills.py` — covers AGENT-06, AGENT-07
- [ ] `tests/test_logging.py` — covers AGENT-09
- [ ] `tests/test_agent_logging.py` — covers AGENT-10
- [ ] `tests/test_observability.py` — covers OBS-01, OBS-02

---

## Project Constraints (from CLAUDE.md)

Directives that all plans and implementation MUST follow:

| Directive | Impact on Phase 4 |
|-----------|------------------|
| Tech Stack: Python, LangChain, Postgres (SQLAlchemy + Alembic), Redis + RQ, uv — no deviations | No new dependencies allowed beyond those already in pyproject.toml |
| Concurrency = 1 (sequential worker) | `run_task` must be synchronous; no `asyncio.run()` inside the job function |
| Full connection details per task type (url, model, api_token) | `model_config` dict must include all three; `AgentConfig` must not allow partial config |
| API tokens read from env vars named by task type | `{TASK_TYPE_UPPER}_API_TOKEN` pattern locked |
| Redis persistence: AOF `appendfsync always` | No change for Phase 4 — Redis config set in Phase 1 |
| LangWatch instrumentation active during both production and experiment runs | `setup_langwatch()` must be called in `runner.main()` AND in experiment scripts |
| SQLAlchemy 2.x `Mapped` + `mapped_column` style | No SQLAlchemy changes in Phase 4, but pattern must be respected if any models are touched |
| Pydantic v2 exclusively | `AgentConfig` can use `@dataclass` (simpler) or Pydantic `BaseModel` — both are v2-compatible |
| `create_react_agent` from `langgraph.prebuilt` (CLAUDE.md + CONTEXT.md D-03) | Must use this import path despite deprecation warning in LangGraph 1.1.3 |
| `result_ttl=-1, failure_ttl=-1` on all RQ jobs | The `hello-world` enqueue in gateway must keep these values |

---

## Sources

### Primary (HIGH confidence)
- Installed venv — `langchain 1.2.13`, `langchain-core 1.2.22`, `langgraph 1.1.3`, `langchain-anthropic 1.4.0`, `langchain-openai 1.1.12`, `langchain-ollama 1.0.1`, `langwatch 0.17.0` — all verified via `introspection` + `importlib.metadata`
- `plans/01-kickoff/spec.md` §Agent, §LLM — authoritative for `LLMBackend` Protocol definition, `SkillSet` pattern, `read-skill` tool spec, `agents.py` structure
- `.planning/phases/04-llm-module-and-agent-infrastructure/04-CONTEXT.md` — locked decisions D-01 through D-16
- `CLAUDE.md` — stack constraints, concurrency constraint, token naming convention

### Secondary (MEDIUM confidence)
- `uv run python -c "from langgraph.prebuilt import create_react_agent; inspect..."` — deprecation warning text, signature, v1→v2 migration note
- `uv run python -c "from langchain.agents import create_agent; inspect..."` — replacement API signature
- `uv run python -c "import langwatch; inspect.signature(langwatch.setup)"` — verified parameter names

### Tertiary (LOW confidence)
- None — all findings verified against installed library versions.

---

## Metadata

**Confidence breakdown:**
- Standard stack versions: HIGH — verified from installed venv via `importlib.metadata`
- Architecture patterns: HIGH — derived from spec verbatim + verified field names via introspection
- LangWatch instrumentation: HIGH — `setup()` signature verified, `LangChainInstrumentor` verified as `BaseInstrumentor` subclass
- create_react_agent deprecation: HIGH — deprecation warning text captured from live execution
- Pitfalls: HIGH (field name gotchas verified) / MEDIUM (path traversal: standard security pattern, not tested end-to-end)

**Research date:** 2026-03-25
**Valid until:** 2026-04-24 (30 days — stable library versions, no fast-moving APIs)
