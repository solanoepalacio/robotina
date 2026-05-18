---
phase: quick-260509-lcd
plan: 01
subsystem: llm-adapters
tags:

  - ollama
  - retry
  - resilience
  - langchain

requires: []
provides:

  - _RetryingChatOllama subclass of ChatOllama
  - _is_transient_ollama_error retry predicate
  - _compute_backoff backoff function
  - OllamaBackend wired to use _RetryingChatOllama

affects: [src/robotina/llm/__init__.py]
tech_stack:
  added: []
  patterns:

    - Subclass + override on ChatOllama._generate / _agenerate to add bounded retry while preserving BaseChatModel identity (required by langgraph.prebuilt.create_react_agent)
    - "Status-code-aware retry: 5xx + transient httpx errors retry; 4xx and unknown (-1) propagate immediately"

key_files:
  created: []
  modified: [src/robotina/llm/__init__.py]
decisions:

  - Subclass ChatOllama instead of using Runnable.with_retry() — with_retry filters by exception type only (would also retry 4xx) and produces a RunnableRetry wrapper that langgraph's create_react_agent does not accept
  - Promote langchain_ollama import to module scope — required because _RetryingChatOllama subclasses ChatOllama at class-definition time
  - Hard-code retry constants (3 attempts, 0.5s base, x2 backoff, ±25% jitter) — no env vars per BRIEF
  - Status-code -1 ResponseError treated as non-retryable (fail fast on unknown) rather than retryable

metrics:
  completed: 2026-05-09
  duration: ~2 minutes
  tasks: 2
  files_modified: 1
commit: f801814
status: complete
---

# Quick Task 260509-lcd: Add bounded transient retry to OllamaBackend Summary

Subclass `ChatOllama` as `_RetryingChatOllama` with status-code-aware retry on `_generate` / `_agenerate` so the worker survives Ollama 5xx errors (notably the 500 with body `error parsing tool call: ...` Ollama returns when the model emits malformed tool-call JSON). `OllamaBackend.__init__` instantiates the subclass instead of `ChatOllama` directly. Single atomic commit `f801814`.

## What Changed

### Module-level retry config (constants)

```python
_OLLAMA_RETRY_MAX_ATTEMPTS = 3            # 1 initial + 2 retries
_OLLAMA_RETRY_BASE_DELAY = 0.5            # seconds
_OLLAMA_RETRY_BACKOFF_FACTOR = 2.0
_OLLAMA_RETRY_JITTER = 0.25               # ±25%
_OLLAMA_RETRY_5XX_STATUSES = frozenset({500, 502, 503, 504})
_OLLAMA_RETRY_TRANSIENT_HTTPX = (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout)
```

### `_is_transient_ollama_error(exc) -> bool`

Returns True iff:

- `isinstance(exc, OllamaResponseError)` AND `exc.status_code in {500, 502, 503, 504}`, OR
- `isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout))`.

Returns False for 4xx `ResponseError`, `ResponseError` with `status_code == -1`, and any unrelated exception. Critically, 4xx (auth errors, etc.) propagate without retry.

### `_compute_backoff(attempt_index) -> float`

`delay = 0.5 * (2.0 ** attempt_index)`, then multiplied by `1 + uniform(-0.25, 0.25)`, clamped to ≥ 0. So:

- `attempt_index=0` → ~0.5s ±25% (lies in [0.375, 0.625]s)
- `attempt_index=1` → ~1.0s ±25% (lies in [0.75, 1.25]s)

### `_RetryingChatOllama(ChatOllama)`

Two overrides only — `_generate` (sync) and `_agenerate` (async). Both:

1. Wrap a `for attempt in range(3):` loop around the parent call.
2. Pass `messages`, `stop`, `run_manager`, and `**kwargs` straight through to `super()` (no rebinding).
3. On `_is_transient_ollama_error(exc) is True` AND attempts remaining: log a WARN and sleep (`time.sleep` for sync, `await asyncio.sleep` for async). Sleep duration comes from `_compute_backoff(attempt)`.
4. On non-transient error: re-raise immediately.
5. On exhaustion: re-raise the last exception (the existing `except Exception` in `robotina/queue/jobs.py` still marks the step FAILED on hard failure).

Subclassing keeps `isinstance(model, BaseChatModel)` true, so `langgraph.prebuilt.create_react_agent` still accepts the model. `Runnable.with_retry()` was rejected because (a) it filters by exception type only — would also retry 4xx — and (b) its `RunnableRetry` wrapper does not satisfy `create_react_agent`'s `BaseChatModel | RunnableBinding` requirement.

### `OllamaBackend.__init__`

Replaced lazy `from langchain_ollama import ChatOllama` with module-level import (required for the subclass to exist at class-definition time), and swapped `ChatOllama(...)` for `_RetryingChatOllama(...)`. Constructor kwargs (`model`, `base_url`, `reasoning`) are unchanged.

`AnthropicBackend`, `OpenAIBackend`, the `LLMBackend` Protocol, and `make_backend` are byte-identical (no behavioral or structural changes).

## Verification Results

### Plan automated check (Task 1 one-liner)

```
$ uv run python -c "from langchain_ollama import ChatOllama; from robotina.llm import OllamaBackend, _RetryingChatOllama, _is_transient_ollama_error, _compute_backoff, _OLLAMA_RETRY_MAX_ATTEMPTS, _OLLAMA_RETRY_5XX_STATUSES; ..."
OK
```

All assertions passed:

- `_RetryingChatOllama` is a subclass of `ChatOllama` and an instance of `BaseChatModel`.
- `_OLLAMA_RETRY_MAX_ATTEMPTS == 3` and `_OLLAMA_RETRY_5XX_STATUSES == frozenset({500, 502, 503, 504})`.
- Retry predicate: True on `ResponseError(500)`, `httpx.ConnectError`, `httpx.ReadTimeout`. False on `ResponseError(401)`, `ResponseError(-1)`, `ValueError`.
- `_compute_backoff(0) ∈ [0.375, 0.625]`, `_compute_backoff(1) ∈ [0.75, 1.25]` (verified across 20 samples in the end-to-end run).
- `OllamaBackend({...}).model` is a `_RetryingChatOllama` instance.

### Live Ollama smoke test (Task 2 step A)

The default smoke model `llama3.2:3b` is not pulled on this machine — the first run got a real 404 from Ollama (`model 'llama3.2:3b' not found (status code: 404)`). That 404 actually exercised the retry predicate's negative path correctly: the retry layer saw a 4xx `ResponseError` and let it propagate immediately without retrying (no log warnings printed).

Re-ran with a model that exists locally (`qwen3:32b`):

```
$ OLLAMA_SMOKE_MODEL='qwen3:32b' uv run python -c "...b.model.invoke('reply with the single word: ok')..."
LIVE OK: 'ok'
```

So the retry layer does not interfere with normal `invoke()` operation against a live Ollama instance.

### Commit verification (Task 2 step B)

- `git log -1 --pretty=format:"%s"` → `fix(llm): retry Ollama 5xx + transient httpx errors in OllamaBackend` (matches `fix(llm): retry Ollama` prefix)
- `git show --name-only HEAD` lists exactly one file: `src/robotina/llm/__init__.py`
- File count = 1 (single-file constraint enforced)
- No deletions in the commit (`git diff --diff-filter=D HEAD~1 HEAD` empty)

### End-to-end verification (plan `<verification>` checks 1-6)

All six checks pass:

1. `_RetryingChatOllama` subclass of `ChatOllama` AND `isinstance(model, BaseChatModel)` ✓
2. Retry predicate correct on all canonical inputs (500/401/-1/ConnectError/ReadTimeout/ConnectTimeout/ValueError) ✓
3. Backoff math: `_compute_backoff(0) ∈ [0.375, 0.625]` and `_compute_backoff(1) ∈ [0.75, 1.25]` across 20 samples ✓
4. `OllamaBackend(...).model` is `_RetryingChatOllama` ✓
5. Single file changed in the commit (`src/robotina/llm/__init__.py`) ✓
6. `AnthropicBackend`, `OpenAIBackend`, `make_backend` are byte-identical (`git diff` shows no edits to those names — only the OllamaBackend body and new top-of-file additions) ✓

## Deviations from Plan

None — plan executed exactly as written.

The live smoke test had to fall back to `qwen3:32b` because `llama3.2:3b` (the default model name in the optional smoke script) isn't pulled locally; the plan explicitly allows this and instructs not to fabricate. The 404 from the unavailable model is *additional* signal that the predicate correctly passes 4xx through without retry.

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `src/robotina/llm/__init__.py` | Modified | +143 / -3 |

## Commit

- `f801814` — `fix(llm): retry Ollama 5xx + transient httpx errors in OllamaBackend`

## Self-Check: PASSED

- File `src/robotina/llm/__init__.py` exists (modified) ✓
- Commit `f801814` exists in `git log` ✓
- All Task 1 + Task 2 + plan-level verification checks passed ✓
