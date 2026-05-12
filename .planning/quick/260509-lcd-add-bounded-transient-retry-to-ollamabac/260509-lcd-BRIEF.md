# Quick Task 260509-lcd — Detailed Brief

**Goal:** Add bounded transient retry to `OllamaBackend` in `src/robotina/llm/__init__.py` so the worker survives Ollama 5xx errors — especially the 500 with body `error parsing tool call: ...` that Ollama returns when the model emits malformed tool-call JSON like `"query": none`.

## Background (why)

Recent failure: a workflow run was killed because Ollama returned a 500 from `POST /api/chat` with:

```
error parsing tool call: raw='{"body":null,"method":"GET","path":"/api/foods?name=azucar%20glasé","query":none}', err=invalid character 'o' in literal null (expecting 'u')
```

The exception path:
- Raised inside `ChatOllama.invoke()` as `ollama.ResponseError`.
- Propagated through `agent.invoke()` at `src/robotina/queue/jobs.py:183-188`.
- Caught by the bare `except Exception` at `src/robotina/queue/jobs.py:201-204`.
- That handler called `workflow_runner.on_step_failed` (`src/robotina/queue/workflow_runner.py:331-383`), which marked the WorkflowRun FAILED and cancelled all 3 pending steps.

Why a retry helps here: the bad JSON is in the model's *response*, not in our request. LangGraph's `create_react_agent` only appends an AIMessage to state *after* `chat_model.invoke()` returns successfully. So a retry sends the identical conversation history and the model is re-sampled — typically yielding valid tool-call JSON on the second attempt. The malformed prior attempt is not in the retry context (it never reached LangGraph state).

## Scope (what to implement)

Subclass `ChatOllama` as a private `_RetryingChatOllama` inside `src/robotina/llm/__init__.py`, overriding `_generate` and `_agenerate` with a status-code-aware retry loop. `OllamaBackend.__init__` instantiates the subclass instead of `ChatOllama`. This keeps `isinstance(model, BaseChatModel)` true so `langgraph.prebuilt.create_react_agent` accepts it (it requires `BaseChatModel | RunnableBinding`; `RunnableRetry` does not satisfy this).

**Why not `Runnable.with_retry()`:** LangChain's `with_retry` filters by exception type only — no status-code predicate — so it would also retry 4xx (auth errors, etc.), which we don't want.

### Retry policy

- Catch `ollama.ResponseError` only when `status_code in {500, 502, 503, 504}`. Pass through 4xx untouched.
- Catch `httpx.ConnectError`, `httpx.ReadTimeout`, `httpx.ConnectTimeout`.
- 3 attempts total (1 initial + 2 retries).
- Backoff: 0.5s base, exponential ×2, ±25% jitter (so retry 1 sleeps ~0.5s ±25%, retry 2 sleeps ~1s ±25%).
- Log each retry at WARN via `logging.getLogger(__name__)`: `"Ollama transient error, retrying (attempt N/3): <error summary>"`.
- On exhaustion, re-raise the original exception so the existing FAILED-step path still works.

### Out of scope

- Do NOT touch `AnthropicBackend` or `OpenAIBackend` (user preference: avoid premature abstraction until 3+ instances).
- Do NOT add env vars; hard-code the numbers.
- Do NOT touch `workflow_runner.py` or `jobs.py`.
- Do NOT add RQ-level retry (separate decision).
- Do NOT add the Telegram dead-letter notification (separate change coming next).

## Verification

- Import `OllamaBackend` and instantiate it; confirm the chat model is the `_RetryingChatOllama` subclass.
- If the local Ollama is reachable, run a single chat through it and confirm normal operation. If not, say so explicitly — don't fabricate test results.

## Reference files

- `src/robotina/llm/__init__.py` — `OllamaBackend` at lines ~50-79; `ChatOllama` constructed at ~57-64; `create_agent` at ~75-79.
- `.venv/.../ollama/_types.py:611-630` — `ResponseError` carries `.status_code`.
- `.venv/.../langchain_ollama/chat_models.py` — `_generate` at ~1023, `_agenerate` at ~1201 (clean override points).
- `.venv/.../langgraph/prebuilt/chat_agent_executor.py` — confirms `_get_model` requires `BaseChatModel | RunnableBinding`.

Single atomic commit at the end. Project commit-message style: see `git log --oneline -10` (look for `fix(...)` / `feat(...)` prefixes with short scope).
