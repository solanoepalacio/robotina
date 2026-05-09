---
phase: quick-260509-lcd
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/robotina/llm/__init__.py
autonomous: true
requirements:
  - QUICK-260509-LCD
must_haves:
  truths:
    - "OllamaBackend's chat model is a `_RetryingChatOllama` instance (subclass of ChatOllama)"
    - "Both `_generate` and `_agenerate` retry on `ollama.ResponseError` only when `status_code` is in {500, 502, 503, 504}"
    - "Both `_generate` and `_agenerate` retry on `httpx.ConnectError`, `httpx.ReadTimeout`, `httpx.ConnectTimeout`"
    - "Up to 3 attempts total (1 initial + 2 retries); on exhaustion the original exception is re-raised"
    - "Backoff sleeps ~0.5s then ~1.0s with ±25% jitter; warns at WARN level on each retry"
    - "4xx `ResponseError` (e.g. auth errors) is NOT retried — it propagates on first occurrence"
    - "Subclass remains a `BaseChatModel` so `langgraph.prebuilt.create_react_agent` still accepts it"
  artifacts:
    - path: "src/robotina/llm/__init__.py"
      provides: "_RetryingChatOllama subclass + OllamaBackend wired to it"
      contains: "class _RetryingChatOllama"
  key_links:
    - from: "OllamaBackend.__init__"
      to: "_RetryingChatOllama"
      via: "self._model = _RetryingChatOllama(...)"
      pattern: "_RetryingChatOllama\\("
    - from: "_RetryingChatOllama._generate"
      to: "ChatOllama._generate"
      via: "super()._generate inside retry loop"
      pattern: "super\\(\\)\\._generate"
    - from: "_RetryingChatOllama._agenerate"
      to: "ChatOllama._agenerate"
      via: "super()._agenerate inside retry loop"
      pattern: "super\\(\\)\\._agenerate"
---

<objective>
Add a bounded transient retry to `OllamaBackend` so the worker survives Ollama 5xx errors — particularly the 500 with body `error parsing tool call: ...` Ollama returns when the model emits malformed tool-call JSON.

Purpose: The bad JSON is in the model's *response*, not our request. LangGraph's `create_react_agent` only appends an AIMessage to state *after* `chat_model.invoke()` returns successfully — so a retry re-samples the model with the same conversation history and typically yields valid tool-call JSON on attempt 2. Without this retry, a single transient parser failure cancels every pending step in the WorkflowRun.

Output: A private `_RetryingChatOllama` subclass of `ChatOllama` inside `src/robotina/llm/__init__.py`, with status-code-aware retry overrides on `_generate` / `_agenerate`. `OllamaBackend.__init__` instantiates the subclass instead of `ChatOllama`. Single atomic commit.
</objective>

<execution_context>
@/home/solanoe/code/robotina-gsd/.claude/get-shit-done/workflows/execute-plan.md
@/home/solanoe/code/robotina-gsd/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/260509-lcd-add-bounded-transient-retry-to-ollamabac/260509-lcd-BRIEF.md
@src/robotina/llm/__init__.py
@CLAUDE.md

<interfaces>
<!-- Key signatures and types the executor needs. Use these directly — no codebase exploration required. -->

From `langchain_ollama.chat_models.ChatOllama` (verified at `.venv/lib/python3.12/site-packages/langchain_ollama/chat_models.py`):
```python
# Line 1023:
def _generate(
    self,
    messages: list[BaseMessage],
    stop: list[str] | None = None,
    run_manager: CallbackManagerForLLMRun | None = None,
    **kwargs: Any,
) -> ChatResult: ...

# Line 1201:
async def _agenerate(
    self,
    messages: list[BaseMessage],
    stop: list[str] | None = None,
    run_manager: AsyncCallbackManagerForLLMRun | None = None,
    **kwargs: Any,
) -> ChatResult: ...
```
Both delegate to streaming aggregation helpers that ultimately call the `ollama` HTTP client and can raise `ollama.ResponseError`.

From `ollama._types.ResponseError` (verified at `.venv/lib/python3.12/site-packages/ollama/_types.py:611-630`):
```python
class ResponseError(Exception):
    def __init__(self, error: str, status_code: int = -1):
        ...
        self.error: str         # parsed error message
        self.status_code: int   # HTTP status; -1 if unknown
```
Use `e.status_code in {500, 502, 503, 504}` as the retry predicate. Pass through 4xx (and `status_code == -1`).

Required imports for the new retry code (add to the imports at the top of `src/robotina/llm/__init__.py`):
```python
import asyncio
import logging
import random
import time

import httpx
from ollama import ResponseError as OllamaResponseError
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_ollama import ChatOllama
```

Note: the existing module imports `ChatOllama` lazily inside `OllamaBackend.__init__`. We are intentionally moving it to module scope because `_RetryingChatOllama` must subclass it at class-definition time. This is a deliberate change — module import of `langchain_ollama` is cheap and already pulled in by the rest of the LangChain stack.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add _RetryingChatOllama subclass and wire OllamaBackend to it</name>
  <files>src/robotina/llm/__init__.py</files>
  <action>
Modify `src/robotina/llm/__init__.py` ONLY. Do NOT touch `AnthropicBackend`, `OpenAIBackend`, `make_backend`, `workflow_runner.py`, or `jobs.py`.

1. Promote the lazy `from langchain_ollama import ChatOllama` import in `OllamaBackend.__init__` to a module-level import, and add the new module-level imports listed in `<interfaces>` above (`asyncio`, `logging`, `random`, `time`, `httpx`, `ollama.ResponseError as OllamaResponseError`, `BaseMessage`, `ChatResult`, `CallbackManagerForLLMRun`, `AsyncCallbackManagerForLLMRun`).

2. Add `logger = logging.getLogger(__name__)` at module scope (just below the imports), if not already present.

3. Define module-level retry constants ABOVE `OllamaBackend` (hard-coded, no env vars per BRIEF):
   ```python
   _OLLAMA_RETRY_MAX_ATTEMPTS = 3            # 1 initial + 2 retries
   _OLLAMA_RETRY_BASE_DELAY = 0.5            # seconds
   _OLLAMA_RETRY_BACKOFF_FACTOR = 2.0
   _OLLAMA_RETRY_JITTER = 0.25               # ±25%
   _OLLAMA_RETRY_5XX_STATUSES = frozenset({500, 502, 503, 504})
   _OLLAMA_RETRY_TRANSIENT_HTTPX = (
       httpx.ConnectError,
       httpx.ReadTimeout,
       httpx.ConnectTimeout,
   )
   ```

4. Add a private helper `def _is_transient_ollama_error(exc: BaseException) -> bool:` that returns True iff:
   - `isinstance(exc, OllamaResponseError) and exc.status_code in _OLLAMA_RETRY_5XX_STATUSES`, OR
   - `isinstance(exc, _OLLAMA_RETRY_TRANSIENT_HTTPX)`.
   Anything else returns False. Critically, a 4xx `OllamaResponseError` returns False — it MUST propagate without retry.

5. Add a private helper `def _compute_backoff(attempt_index: int) -> float:` where `attempt_index` is 0 for the first retry, 1 for the second, etc.:
   - `delay = _OLLAMA_RETRY_BASE_DELAY * (_OLLAMA_RETRY_BACKOFF_FACTOR ** attempt_index)`
   - jitter ratio `= random.uniform(-_OLLAMA_RETRY_JITTER, _OLLAMA_RETRY_JITTER)`
   - return `max(0.0, delay * (1 + jitter ratio))`

   So attempt_index=0 gives ~0.5s ±25%, attempt_index=1 gives ~1.0s ±25%.

6. Define `class _RetryingChatOllama(ChatOllama):` with two overrides only — `_generate` and `_agenerate`. Both must:
   - Use the EXACT same signatures as the parent (copy from `<interfaces>`).
   - Call `super()._generate(...)` / `await super()._agenerate(...)` inside a retry loop.
   - On `_is_transient_ollama_error(exc) is True` AND attempts remaining: log a WARN via the module logger using the message `"Ollama transient error, retrying (attempt %d/%d): %s"` with `(next_attempt_number, _OLLAMA_RETRY_MAX_ATTEMPTS, exc)`, then sleep `_compute_backoff(retry_index)` (use `time.sleep` in `_generate`, `await asyncio.sleep` in `_agenerate`), then loop.
   - On non-transient error: re-raise immediately (no retry, no swallow).
   - On exhaustion (used all attempts): re-raise the LAST exception so the existing `except Exception` in `jobs.py` still marks the step FAILED.
   - Pass `messages`, `stop`, `run_manager`, and `**kwargs` through to `super()` unmodified — do not re-bind or copy them.

   Skeleton (fill in following the rules above; this is illustrative, not a full impl):
   ```python
   class _RetryingChatOllama(ChatOllama):
       """ChatOllama with bounded retry on Ollama 5xx and transient httpx errors.

       Status-code-aware: 4xx errors (auth, etc.) propagate without retry. 5xx
       (including the 'error parsing tool call' 500 from malformed tool-call JSON)
       and httpx connect/read timeouts are retried up to 3 attempts total with
       exponential backoff + ±25% jitter. On exhaustion the original exception
       is re-raised so the existing FAILED-step path in queue/jobs.py still works.
       """

       def _generate(self, messages, stop=None, run_manager=None, **kwargs):
           last_exc: BaseException | None = None
           for attempt in range(_OLLAMA_RETRY_MAX_ATTEMPTS):
               try:
                   return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
               except Exception as exc:
                   last_exc = exc
                   if not _is_transient_ollama_error(exc):
                       raise
                   if attempt + 1 >= _OLLAMA_RETRY_MAX_ATTEMPTS:
                       raise
                   delay = _compute_backoff(attempt)
                   logger.warning(
                       "Ollama transient error, retrying (attempt %d/%d): %s",
                       attempt + 2, _OLLAMA_RETRY_MAX_ATTEMPTS, exc,
                   )
                   time.sleep(delay)
           # Defensive: loop exits only via return or raise; if reached, re-raise.
           assert last_exc is not None
           raise last_exc

       async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
           # Same shape as _generate but with `await super()._agenerate(...)` and `await asyncio.sleep(...)`.
           ...
   ```

7. Update `OllamaBackend.__init__` to instantiate `_RetryingChatOllama` instead of `ChatOllama`. Remove the now-redundant `from langchain_ollama import ChatOllama` line inside `__init__` (it's at module scope now). The constructor kwargs (`model`, `base_url`, `reasoning`) stay identical. Keep the docstring; optionally extend it with a one-sentence note: "Wraps ChatOllama in a `_RetryingChatOllama` to survive Ollama 5xx tool-call-parse errors."

8. Do NOT change `AnthropicBackend`, `OpenAIBackend`, the `LLMBackend` Protocol, `make_backend`, or any other file.
  </action>
  <verify>
    <automated>uv run python -c "from langchain_ollama import ChatOllama; from robotina.llm import OllamaBackend, _RetryingChatOllama, _is_transient_ollama_error, _compute_backoff, _OLLAMA_RETRY_MAX_ATTEMPTS, _OLLAMA_RETRY_5XX_STATUSES; from ollama import ResponseError; import httpx; assert issubclass(_RetryingChatOllama, ChatOllama), 'subclass check'; assert _OLLAMA_RETRY_MAX_ATTEMPTS == 3; assert _OLLAMA_RETRY_5XX_STATUSES == frozenset({500,502,503,504}); assert _is_transient_ollama_error(ResponseError('boom', 500)) is True; assert _is_transient_ollama_error(ResponseError('nope', 401)) is False; assert _is_transient_ollama_error(ResponseError('huh', -1)) is False; assert _is_transient_ollama_error(httpx.ConnectError('x')) is True; assert _is_transient_ollama_error(httpx.ReadTimeout('x')) is True; assert _is_transient_ollama_error(ValueError('not transient')) is False; d0 = _compute_backoff(0); d1 = _compute_backoff(1); assert 0.375 <= d0 <= 0.625, f'd0={d0}'; assert 0.75 <= d1 <= 1.25, f'd1={d1}'; b = OllamaBackend({'model': 'llama3.2:3b', 'url': 'http://localhost:11434'}); assert isinstance(b.model, _RetryingChatOllama), f'got {type(b.model).__name__}'; from langchain_core.language_models import BaseChatModel; assert isinstance(b.model, BaseChatModel); print('OK')"</automated>
  </verify>
  <done>
    - `src/robotina/llm/__init__.py` defines `_RetryingChatOllama(ChatOllama)` with `_generate` and `_agenerate` overrides only.
    - `_is_transient_ollama_error` returns True for `ResponseError` with `status_code in {500, 502, 503, 504}` and for `httpx.ConnectError` / `httpx.ReadTimeout` / `httpx.ConnectTimeout`; False for 4xx, status_code=-1, and unrelated exceptions.
    - `_compute_backoff(0)` lies in [0.375, 0.625]s and `_compute_backoff(1)` in [0.75, 1.25]s (±25% of 0.5 / 1.0).
    - `OllamaBackend(...).model` is a `_RetryingChatOllama` instance and remains a `BaseChatModel`.
    - The verification one-liner prints `OK` and exits 0.
    - `AnthropicBackend`, `OpenAIBackend`, `make_backend`, `workflow_runner.py`, `jobs.py` are unchanged (`git diff --stat` shows only `src/robotina/llm/__init__.py`).
  </done>
</task>

<task type="auto">
  <name>Task 2: Optional live smoke test, then atomic commit</name>
  <files>(no file changes; commit only)</files>
  <action>
Step A — Optional live smoke test (best-effort; do NOT fabricate results):

If `OLLAMA_HOST` is reachable (default `http://localhost:11434`), run a single chat through the wrapped backend to confirm normal operation is unaffected by the retry layer:

```bash
uv run python -c "
import os, httpx
from robotina.llm import OllamaBackend
url = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
try:
    httpx.get(url, timeout=2.0)
except Exception as e:
    print(f'SKIP: Ollama not reachable at {url}: {e}')
    raise SystemExit(0)
b = OllamaBackend({'model': os.environ.get('OLLAMA_SMOKE_MODEL', 'llama3.2:3b'), 'url': url})
out = b.model.invoke('reply with the single word: ok')
print('LIVE OK:', repr(out.content[:80]))
"
```

If the script prints `SKIP:` (Ollama not reachable) or the model isn't pulled locally, that is acceptable — write a single line in the SUMMARY noting the smoke test was skipped. Do NOT fabricate output. Do NOT add new env vars to `.env.example` (this script just reads optional env hints; the runtime adapter still does not read any new env vars per BRIEF).

Step B — Single atomic commit (only if Task 1 verification passes):

```bash
git add src/robotina/llm/__init__.py
git commit -m "$(cat <<'EOF'
fix(llm): retry Ollama 5xx + transient httpx errors in OllamaBackend

Subclass ChatOllama as _RetryingChatOllama and override _generate/_agenerate
with a status-code-aware retry loop (3 attempts, 0.5s base, x2 backoff, ±25%
jitter). Retries OllamaResponseError when status_code in {500,502,503,504}
and httpx.{ConnectError,ReadTimeout,ConnectTimeout}; 4xx propagates as before.

Motivation: Ollama returns a 500 ("error parsing tool call: ... err=invalid
character 'o' in literal null") when the model emits malformed tool-call JSON.
LangGraph's create_react_agent only appends an AIMessage after invoke()
returns, so a retry re-samples the model with identical conversation state
and typically succeeds on attempt 2. Previously a single transient parse
error killed the WorkflowRun and cancelled all pending steps.

Scope: src/robotina/llm/__init__.py only. Anthropic/OpenAI backends and
queue/workflow_runner code are unchanged. No new env vars (numbers
hard-coded per BRIEF).
EOF
)"
```

Verify the commit landed and only one file changed:
```bash
git show --stat HEAD
```
  </action>
  <verify>
    <automated>git log -1 --pretty=format:"%s" | grep -q "fix(llm): retry Ollama" &amp;&amp; git show --name-only HEAD | grep -E "^(src/robotina/llm/__init__\.py)$" &amp;&amp; test "$(git show --name-only --pretty=format: HEAD | grep -v '^$' | wc -l)" = "1"</automated>
  </verify>
  <done>
    - Live smoke either printed `LIVE OK: ...` or was skipped with a clear `SKIP:` line; no fabricated output.
    - Exactly one commit was created with subject starting `fix(llm): retry Ollama`.
    - `git show --name-only HEAD` lists exactly one file: `src/robotina/llm/__init__.py`.
  </done>
</task>

</tasks>

<verification>
End-to-end checks for the plan:

1. `_RetryingChatOllama` is a subclass of `ChatOllama` and an instance of `BaseChatModel`.
2. Retry predicate is correct on the four canonical inputs:
   - `ResponseError('x', 500)` → retry
   - `ResponseError('x', 401)` → no retry
   - `ResponseError('x', -1)` → no retry (unknown status, fail fast)
   - `httpx.ConnectError('x')` → retry
   - `ValueError('x')` → no retry
3. Backoff math: `_compute_backoff(0)` ∈ [0.375, 0.625]s; `_compute_backoff(1)` ∈ [0.75, 1.25]s.
4. `OllamaBackend(...).model` is a `_RetryingChatOllama`.
5. `git diff main -- src/robotina/llm/__init__.py` is the ONLY diff in the commit.
6. `AnthropicBackend`, `OpenAIBackend`, and `make_backend` behavior is byte-identical (no diff in their code paths beyond moved imports).
</verification>

<success_criteria>
- A single atomic commit `fix(llm): retry Ollama ...` modifies only `src/robotina/llm/__init__.py`.
- Importing `OllamaBackend` and instantiating it yields a model whose class is `_RetryingChatOllama`.
- Transient Ollama 5xx and httpx connect/read timeouts retry up to 3 attempts; 4xx and other exceptions do not.
- `langgraph.prebuilt.create_react_agent` still accepts the model (BaseChatModel invariant preserved).
- No new env vars were added; no other file in the repo was modified.
</success_criteria>

<output>
After completion, create `.planning/quick/260509-lcd-add-bounded-transient-retry-to-ollamabac/260509-lcd-SUMMARY.md` describing:
- The two new helpers (`_is_transient_ollama_error`, `_compute_backoff`) and constants.
- The `_RetryingChatOllama` subclass and how it wraps `_generate` / `_agenerate`.
- Whether the live Ollama smoke test ran or was skipped (do NOT fabricate).
- The single commit hash.
</output>
