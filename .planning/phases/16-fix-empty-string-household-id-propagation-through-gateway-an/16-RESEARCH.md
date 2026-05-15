# Phase 16: Fix empty-string household_id propagation - Research

**Researched:** 2026-05-15
**Domain:** Python env-var validation, Pydantic v2 string constraints, fail-fast module import patterns
**Confidence:** HIGH

## Summary

This is a bug-fix phase with a tight blast radius. All decisions are locked in CONTEXT.md and the SPEC; the research surface is mostly verification: confirming the inventory of `household_id` usage sites, picking between Pydantic v2 non-empty-string idioms, and identifying the test-collection pitfall created by module-level `os.environ["HOUSEHOLD_ID"]` raise.

The bug is real and well-characterized: `src/robotina/gateway/handler.py:43` reads `os.environ.get("HOUSEHOLD_ID", "")` and that empty string flows untouched through `Conversation.household_id` (DB nullable=False but blank-accepting), `IncomingMessageInput.household_id` (`str` with no `min_length`), `WorkflowRun.household_id`, `StartWorkflowTool.household_id`, and `HouseholdManagerApiTool.household_id`. None of these layers reject blank — the corruption is invisible at every layer.

**Primary recommendation:** Move the bracket-form `os.environ["HOUSEHOLD_ID"]` read INSIDE the per-message `handle_message` function (not module-level), back it up with `Field(min_length=1)` on `IncomingMessageInput.household_id`, and add construct-time `ValueError` guards on `HouseholdManagerApiTool.__init__` and `queue_workflow`. Module-import-time raise breaks pytest collection (handler.py is imported by 5 integration tests + send.py is imported by send-notification). The per-message read still gives fail-fast behavior on the first incoming message (boots fine, blows up before any side-effect).

> ⚠️ **SPEC vs CONTEXT.md tension flagged for planner.** The SPEC (16-SPEC.md:24-27) prescribes a **boot-time guard at the gateway entrypoint** (i.e. in `src/robotina/gateway/__init__.py::main()`, before `app.run_polling()`). CONTEXT.md decided "raise `RuntimeError` at handler module import via `os.environ["HOUSEHOLD_ID"]`". These are **different placements** with different test-collection consequences. See Pitfall 1 below — the discrepancy must be resolved before planning.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Detect missing/empty `HOUSEHOLD_ID` at startup | Gateway entrypoint (`gateway/__init__.py::main`) | Gateway handler module | Boot-time guard prevents process from accepting any message; SPEC requirement R1. |
| Reject empty `household_id` on task-input construction | Pydantic models (`queue/task_types.py`) | — | Belt-and-suspenders: any future caller bypassing the gateway still hits this. |
| Reject empty `household_id` on tool construction | Agent tool layer (`agent/tools/household_manager_api.py`, `agent/tools/start_workflow.py`) | — | Last line of defense — `run_task()` injects tools per-job. |
| Reject empty `household_id` in workflow orchestration | Workflow runner (`queue/workflow_runner.py::queue_workflow`) | — | Prevents `WorkflowRun` row with blank `household_id` from ever being written. |
| Document required env var | `.env.example` + PROJECT.md Key Decisions | — | Per project rule `feedback_env_example.md`. |

## Standard Stack

No new libraries. All work uses the existing stack.

### Core (verified versions from pyproject.toml)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | `>=2.7` | Field-level validation via `Field(min_length=1)` | `[VERIFIED: /home/solanoe/code/robotina-gsd/pyproject.toml]` Already used for all task-input models. Project convention is declarative `Field(...)` constraints. |
| python-stdlib `os` | builtin | Env var access | `[VERIFIED]` Project uses inline `os.environ[...]` reads; no helper. |

### Don't add anything else
`[ASSUMED]` Centralizing env reads into a helper (`get_household_id()`) is explicitly deferred per CONTEXT.md "premature abstraction" rule. Single call site in the gateway is sufficient.

## Project Constraints (from CLAUDE.md)

- **Pydantic v2 exclusively** — must use v2 idioms (`Field(min_length=1)`, `Annotated[...]`). Never mix with v1.
- **Always update `.env.example`** — new env vars MUST be reflected. `HOUSEHOLD_ID` addition is mandated.
- **No premature abstraction** — concrete duplicated single-line reads preferred over generic helpers until 3+ instances exist.
- **Pre-existing patterns for env reads:** `os.environ["TELEGRAM_BOT_TOKEN"]` (handler.py uses bracket form already for TELEGRAM_BOT_TOKEN at line 26 of `__init__.py`); `os.environ["HOUSEHOLD_MANAGER_API_KEY"]` (tool, raises KeyError on missing). The convention is bracket form for required vars.
- **Test before handoff** — Nyquist validation enabled (`workflow.nyquist_validation: true` in `.planning/config.json`).
- **SQLAlchemy 2.x `Mapped` syntax** — out of scope here (no schema migration in Phase 16 per SPEC).

## Phase Requirements

CONTEXT.md notes no phase-specific REQ-IDs. SPEC acceptance criteria stand in:

| ID | Description | Research Support |
|----|-------------|------------------|
| SPEC-R1 | Boot-time guard: gateway exits non-zero on unset/empty `HOUSEHOLD_ID` | Fail-fast pattern (Pitfall 1, Pattern 1 below) |
| SPEC-R2 | `.env.example` documents `HOUSEHOLD_ID` with "required" comment | Pattern 4 below |
| SPEC-R3 | End-to-end: with `HOUSEHOLD_ID=hh-xyz` set, `WorkflowRun` row carries that value | Existing flow already does this once the empty default is removed — see Affected Files Inventory |

CONTEXT.md adds these implementation-level requirements beyond the SPEC:

| Implementation Decision | Affected Code |
|-------------------------|---------------|
| `Field(min_length=1)` on Pydantic task-input `household_id` fields | `queue/task_types.py` — `IncomingMessageInput`, `RecipeResearchInput`, `RecipeResearchGatherInput`, `RecipeResearchInstructionsInput`, `RecipeResearchIngredientsInput`, `RecipeResearchMetadataInput`, `RecipeLoadInput` (7 models) |
| `HouseholdManagerApiTool.__init__` raises on empty | `agent/tools/household_manager_api.py` — Pydantic `BaseTool` field with validator OR `model_validator(mode="after")` |
| `StartWorkflowTool.__init__` (and/or `_run`) raises on empty | `agent/tools/start_workflow.py` |
| `queue_workflow` raises on empty | `queue/workflow_runner.py:107` |
| Sweep `tests/` for empty-string fixtures (replace with placeholder) | None found in `tests/` for `household_id=""` — verified via grep |
| PROJECT.md Key Decision entry | `.planning/PROJECT.md` — append row to Key Decisions table |
| Remove stale `HOUSEHOLD_ID` docstring from `send.py` | `gateway/send.py:12` |

## Affected Files Inventory (verified)

`[VERIFIED: grep on /home/solanoe/code/robotina-gsd/src and /tests]`

### Sites that READ env `HOUSEHOLD_ID`
| File:line | Code | Action |
|-----------|------|--------|
| `src/robotina/gateway/handler.py:43` | `household_id = os.environ.get("HOUSEHOLD_ID", "")` | Replace with bracket-form read; trim + validate. |
| `src/robotina/gateway/send.py:12` (docstring only) | "`HOUSEHOLD_ID — used for Conversation lookup; defaults ""`" | **Stale docstring** — `send.py` does NOT read `HOUSEHOLD_ID` anywhere in code (verified). Delete the line from the docstring. |
| `src/robotina/gateway/handler.py:11` (docstring) | "`HOUSEHOLD_ID — required for Conversation; defaults ""`" | Update docstring to remove "defaults" wording. |

### Sites that CONSTRUCT `household_id` field on Pydantic models
| File | Models with `household_id: str` |
|------|---------------------------------|
| `src/robotina/queue/task_types.py` | `IncomingMessageInput` (line 114), `RecipeResearchInput` (line 135), `RecipeResearchGatherInput` (line 157), `RecipeResearchInstructionsInput` (line 166), `RecipeResearchIngredientsInput` (line 181), `RecipeResearchMetadataInput` (line 196), `RecipeLoadInput` (line 223) |

All 7 models declare `household_id: str` with no constraint. Apply `Field(min_length=1)` (or `Annotated[str, Field(min_length=1)]` alias) to each.

### Sites that CONSTRUCT tools with `household_id`
| File:line | Caller | Action |
|-----------|--------|--------|
| `src/robotina/queue/jobs.py:138` | `tools.append(HouseholdManagerApiTool(household_id=task_input.household_id))` (handle-incoming-message branch) | Caller — no change. |
| `src/robotina/queue/jobs.py:144-149` | `tools.append(StartWorkflowTool(..., household_id=task_input.household_id))` | Caller — no change. |
| `src/robotina/queue/jobs.py:161` | `HouseholdManagerApiTool(household_id=task_input.household_id)` (ingredients branch) | Caller — no change. |
| `src/robotina/queue/jobs.py:173` | `HouseholdManagerApiTool(household_id=task_input.household_id)` (recipe-load branch) | Caller — no change. |
| `src/robotina/agent/tools/household_manager_api.py:218` | `household_id: str` BaseTool field | **Add `model_validator(mode="after")` or `Field(min_length=1)` on the class field.** |
| `src/robotina/agent/tools/start_workflow.py:99` | `household_id: str = ""` — **literal empty-string default** | **Remove default; add validator.** |
| `experiments/recipe_load.py:35` | `TEST_HOUSEHOLD_ID = "experiment-household"` | Non-empty already — no change. |
| `experiments/recipe_research.py:39` | `TEST_HOUSEHOLD_ID = "experiment-household"` | Non-empty already — no change. |

### Sites that PASS `household_id` to workflow runner
| File:line | Code | Action |
|-----------|------|--------|
| `src/robotina/agent/tools/start_workflow.py:117` | `household_id = shared_context.get("household_id", "")` | Caller fallback to `""` — eliminate, fail loud. |
| `src/robotina/agent/tools/start_workflow.py:126-132` | `workflow_runner.queue_workflow(..., household_id=household_id, ...)` | Callee will raise. |
| `src/robotina/queue/workflow_runner.py:107` | `queue_workflow(household_id: str, ...)` | **Add raise on empty.** |
| `src/robotina/queue/workflow_runner.py:139` | `WorkflowRun(..., household_id=household_id, ...)` | Guarded by validator above. |

### Test fixtures touching `household_id`
`[VERIFIED: grep on /tests]`

No fixtures use `household_id=""` — every existing fixture uses `"h1"`, `"hh-1"`, `"household-1"`, `"household-abc"`, `"h-test"`, `"h-done"`, `"h-running"`, `"house-1"`, or `"hh-test"`. **The sweep CONTEXT.md asks for finds nothing to change in `tests/`.** Still worth a defensive recheck during planning — document the negative result in SUMMARY.

Tests that need updating IF we go module-level-raise route (Pitfall 1):
- `tests/test_gateway.py` — imports `robotina.gateway.handler` at function level via `from robotina.gateway.handler import handle_message` (5 occurrences: lines 19, 35, 49, 84, 143). Only `test_send_message_persists` (line 123) currently sets `HOUSEHOLD_ID` in environ.
- `tests/conftest.py` — does NOT set `HOUSEHOLD_ID`.
- `tests/unit/test_agent_runner.py:49, 204, 303` — uses mocked task_input with `household_id="household-1"` / `"household-abc"`; safe.

## Runtime State Inventory

`[VERIFIED]` This is a behavior-change phase, not a rename. Per SPEC:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Existing `Conversation` and `WorkflowRun` rows with `household_id=""` in dev Postgres | **None — SPEC out-of-scope says no backfill.** Legacy rows remain. |
| Live service config | None — `HOUSEHOLD_ID` is read only by gateway from env | None. |
| OS-registered state | None — no Task Scheduler / launchd / systemd unit references `HOUSEHOLD_ID` | None. |
| Secrets/env vars | `HOUSEHOLD_ID` itself — currently absent from `.env.example`, present in operator-managed `.env` | **Add to `.env.example`** (SPEC R2). Operator `.env` already has it if the deployment was working; if not, the gateway will now refuse to start (the desired outcome). |
| Build artifacts | None | None. |

The canonical question (after-source-edit): runtime impact is **zero on the happy path** (boot continues if env is set), **gateway boot fails** if `.env` is missing/empty (intended), **legacy `household_id=""` rows remain queryable** (SPEC accepts this).

## Architecture Patterns

### Pattern 1: Fail-fast env-var read at module scope (NOT recommended in this codebase)
```python
# Source: existing code in src/robotina/gateway/__init__.py:26 (TELEGRAM_BOT_TOKEN)
# Bracket form raises KeyError on missing — fail-fast for free.
HOUSEHOLD_ID = os.environ["HOUSEHOLD_ID"]
if not HOUSEHOLD_ID.strip():
    raise RuntimeError("HOUSEHOLD_ID env var is empty — gateway refuses to start")
```

**Why NOT module-level in `handler.py`:** Test collection imports `robotina.gateway.handler` (verified — see `tests/test_gateway.py:19,35,49,84,143`). Module-level raise breaks `pytest --collect-only` before any test mocking can intervene. Pytest produces `ERRORS in collection` not `FAILED`, and the whole file gets skipped.

### Pattern 2: Fail-fast inside `main()` entrypoint (SPEC-aligned, recommended)
```python
# Source: idiomatic; mirrors how src/robotina/gateway/__init__.py already reads TELEGRAM_BOT_TOKEN
# File: src/robotina/gateway/__init__.py::main()
def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    household_id = os.environ.get("HOUSEHOLD_ID", "").strip()
    if not household_id:
        sys.stderr.write(
            "FATAL: HOUSEHOLD_ID env var is unset or empty. "
            "The gateway refuses to start. "
            "Set HOUSEHOLD_ID in your .env (see .env.example) and retry.\n"
        )
        sys.exit(1)

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    # ... rest of main()
```

**Why recommended:** (1) Tests import `handler.handle_message` but not `main()`. (2) SPEC R1 specifies entrypoint-level check. (3) Exit code is a clean `1`, not a Python traceback — operator-friendly. (4) `sys.exit(1)` is more idiomatic for a CLI entrypoint than `raise RuntimeError` (which prints traceback to stderr, also non-zero exit, but messier).

### Pattern 3: Per-handler-call bracket-form read (CONTEXT.md decision, but module-import-time)
```python
# CONTEXT.md says: "raise RuntimeError at handler module import via os.environ['HOUSEHOLD_ID']"
# File: src/robotina/gateway/handler.py — module scope
HOUSEHOLD_ID = os.environ["HOUSEHOLD_ID"]  # KeyError on missing
if not HOUSEHOLD_ID.strip():
    raise RuntimeError("HOUSEHOLD_ID is empty — see .env.example")

# Then inside handle_message:
async def handle_message(update, context):
    household_id = HOUSEHOLD_ID  # already validated
```

**Risk:** Breaks test collection. Mitigation: wrap with `try`/`except` is not viable (defeats fail-fast). Real mitigation: set `HOUSEHOLD_ID` in `tests/conftest.py` via `os.environ.setdefault("HOUSEHOLD_ID", "test-household")` at module top, BEFORE any `from robotina.gateway.handler import ...` occurs. This makes the module-level raise effectively no-op during testing.

**Recommendation to planner:** Use **Pattern 2** (entrypoint guard in `main()`) for SPEC R1 compliance + **Pattern 4** (per-message bracket read with no default) for handler.py to back it up. This is the cleanest interpretation that satisfies both documents.

### Pattern 4: Per-message bracket-form read (no module-level state)
```python
# File: src/robotina/gateway/handler.py:43 — inside handle_message body
async def handle_message(update, context):
    # ... msg/chat extraction ...
    household_id = os.environ["HOUSEHOLD_ID"]  # KeyError if main() guard was bypassed
    # No fallback. If the gateway booted via main(), this always succeeds.
```

**Why this works:** Module loads cleanly during test collection (no top-level raise). Tests that exercise `handle_message` directly set `HOUSEHOLD_ID` in `os.environ` (only `test_send_message_persists` currently does — others need updating). Production path is guarded by main() (Pattern 2), so the bracket read is a paranoid backstop.

### Pattern 5: Pydantic v2 non-empty string constraint
```python
# Source: pydantic docs (https://docs.pydantic.dev/2.7/concepts/fields/#string-constraints)
# Option A: inline Field
from pydantic import BaseModel, Field

class IncomingMessageInput(BaseModel):
    household_id: str = Field(min_length=1, description="Household UUID; must be non-empty")
    # ... other fields ...

# Option B: type alias (cleaner when applied to 7 models)
from typing import Annotated
from pydantic import BaseModel, Field

NonEmptyStr = Annotated[str, Field(min_length=1)]

class IncomingMessageInput(BaseModel):
    household_id: NonEmptyStr
    # ... other fields ...
```

**Recommendation:** `Annotated[str, Field(min_length=1)]` aliased as `NonEmptyHouseholdId = Annotated[str, Field(min_length=1, description="...")]` at the top of `task_types.py`. Cleaner across 7 models, single source of truth for the constraint, easy to grep. `[VERIFIED: pydantic 2.7+ supports Annotated metadata fully]`.

**Note on `StrictStr`:** `StrictStr` enforces "must be exactly a `str`, not a subclass / coercion target" — it does NOT enforce non-empty. Don't use it for this; combine with `min_length` if both are wanted, but for empty-rejection alone `min_length=1` is sufficient.

### Pattern 6: Pydantic v2 BaseTool validator
```python
# Source: pydantic v2 docs — model_validator(mode="after")
# File: src/robotina/agent/tools/household_manager_api.py
from pydantic import model_validator

class HouseholdManagerApiTool(BaseTool):
    # ... existing fields ...
    household_id: str

    @model_validator(mode="after")
    def _require_non_empty_household_id(self) -> "HouseholdManagerApiTool":
        if not self.household_id or not self.household_id.strip():
            raise ValueError(
                "HouseholdManagerApiTool requires non-empty household_id; "
                "received empty string. Check IncomingMessageInput.household_id."
            )
        return self
```

**Why model_validator vs `Field(min_length=1)` here:** `BaseTool` from `langchain_core` is a Pydantic v2 model under the hood (verified — `HouseholdManagerApiArgs` already uses `model_validator` in the same file at line 156). `Field(min_length=1)` on the `household_id` class attribute also works; `model_validator(mode="after")` is preferred when raising a more useful error message at the tool layer is desirable (since that's exactly the "blast radius layer" we want to surface in logs).

**Pick one and be consistent:** Recommend `Field(min_length=1)` for compactness, matching the Pydantic model pattern. The error message comes from Pydantic's standard validation and still mentions the field name.

### Pattern 7: queue_workflow guard
```python
# File: src/robotina/queue/workflow_runner.py:107
def queue_workflow(
    workflow_type: str,
    shared_context: dict,
    household_id: str,
    queue,
    session: Session,
) -> str:
    if not household_id or not household_id.strip():
        raise ValueError(
            "queue_workflow refuses empty household_id; "
            "this indicates HOUSEHOLD_ID was not propagated from the gateway. "
            "Check gateway/__init__.py boot guard and IncomingMessageInput validation."
        )
    # ... existing body ...
```

### Anti-Patterns to Avoid
- **Don't add a CHECK constraint** — SPEC and CONTEXT.md both forbid Alembic data migration in Phase 16.
- **Don't centralize env reads into a helper module** — CONTEXT.md flags this as premature abstraction.
- **Don't backfill existing empty rows** — SPEC out-of-scope.
- **Don't read `HOUSEHOLD_ID` at module top of `handler.py`** without a corresponding `conftest.py` `setdefault` — breaks test collection.
- **Don't rely on `nullable=False` DB column to catch empties** — already in place, didn't help.
- **Don't use `StrictStr` for non-empty** — wrong semantics; doesn't reject `""`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Non-empty string validation | Custom validator function comparing `== ""` | `Field(min_length=1)` or `Annotated[str, Field(min_length=1)]` | Declarative, raises `ValidationError` at model construction with field path included; tested in pydantic core. |
| Env-var presence + non-empty check | Bespoke `validate_env(name)` helper | `os.environ["X"]` (raises `KeyError`) + `.strip()` check | Avoid the helper per CONTEXT.md "no centralization". Bracket form gives KeyError-on-missing for free. |
| Failure messaging | Re-raise generic `Exception` | `sys.exit(1)` with stderr write in entrypoint; `raise ValueError(specific message)` in libraries | Operator skimming logs needs to see the env-var name; tracebacks are fine for the library layers but noisy for the entrypoint. |

## Common Pitfalls

### Pitfall 1: Module-level raise in handler.py breaks pytest collection
**What goes wrong:** Placing `os.environ["HOUSEHOLD_ID"]` at module scope in `src/robotina/gateway/handler.py` causes `KeyError` at import time. Pytest imports the module during collection (5 test files do `from robotina.gateway.handler import handle_message`), so collection fails with `ImportError`/`KeyError` before any test runs. Symptom: test suite cannot even start.

**Why it happens:** Python evaluates module-scope statements at import. Pytest collection imports every test module, which transitively imports `handler.py`.

**How to avoid:**
- **Option A (recommended):** Put the guard in `gateway/__init__.py::main()` (Pattern 2). `main()` is called by `uv run gateway`, never during test collection.
- **Option B:** Keep module-level raise but seed `tests/conftest.py` with `os.environ.setdefault("HOUSEHOLD_ID", "test-household")` at the top, BEFORE any conftest imports that pull in `handler.py`. Brittle — ordering matters.
- **Option C:** Read in the handler function body (Pattern 4). Test files that exercise `handle_message` set the env var per-test.

**Warning signs:** `pytest --collect-only tests/test_gateway.py` exits non-zero before any test ID is printed; CI fails at "collection" not "tests".

### Pitfall 2: Pydantic Field(min_length=1) on RQ-serialized models breaks in-flight jobs at deploy boundary
**What goes wrong:** If an RQ job was enqueued (pickled) with `household_id=""` before the deploy and is dequeued AFTER the deploy, the worker calls `IncomingMessageInput.model_validate(...)` (or unpickling triggers `__init__`-equivalent path) and the validator rejects the empty string. The job lands in `FailedJobRegistry` with a `ValidationError`.

**Why it happens:** RQ pickles the entire `task_input` Pydantic object onto Redis. Pydantic v2 re-validates on `__setstate__` for picked models? `[ASSUMED — verify against pydantic 2.7]` — by default, `model_config = ConfigDict(validate_assignment=False)` and **pickle unpickling does NOT re-run validators**. So existing in-flight jobs likely survive — but `model_validate` paths in workflow_runner or build_input lambdas WILL fail if they re-construct from a dict with empty string.

**How to avoid:**
- Drain the queue before deploying. In a single-worker sequential setup (concurrency=1, per CLAUDE.md), this is normally clean at any quiet moment.
- Use `monitoring/redis-cli LLEN rq:queue:agent-tasks` to confirm `0` before flipping the deploy.
- The task input shape change is backward-COMPATIBLE for already-pickled non-empty objects; only empties fail. Probability of empty `household_id` in an in-flight job equals the bug rate this phase fixes — likely zero in staging, possibly one in dev.

**Warning signs:** Worker logs `pydantic.ValidationError: household_id should have at least 1 character` immediately after deploy.

**Mitigation if it happens:** Drain `rq:queue:agent-tasks` manually (`rq empty agent-tasks` or via rq-dashboard), accept the failed-job-registry rows as known-loss-during-bugfix.

### Pitfall 3: `send.py` docstring drift after rename / removal
**What goes wrong:** CONTEXT.md says to delete the `HOUSEHOLD_ID — used for Conversation lookup; defaults ""` line from `send.py`'s docstring. The code path in `send.py` does NOT use `HOUSEHOLD_ID` — verified by grep. Leaving the line creates a false-positive search hit in future audits.

**How to avoid:** Delete the line in the planning task explicitly; verify with `grep HOUSEHOLD_ID src/robotina/gateway/send.py` returning zero lines after edit.

### Pitfall 4: StartWorkflowTool's `shared_context.get("household_id", "")` fallback masks the guard
**What goes wrong:** `start_workflow.py:117` reads `household_id = shared_context.get("household_id", "")`. Even if every other layer rejects empty, this `.get("household_id", "")` silently substitutes empty if the LLM didn't populate it (it can't — it's auto-injected at line 115, but a defensive coding bug in the inject path would silently hide).

**How to avoid:** Replace with `shared_context["household_id"]` (bracket form, raises KeyError) AND let `queue_workflow` raise on empty. Two failure points; redundant by design.

### Pitfall 5: Empty default on `StartWorkflowTool.household_id: str = ""` class attribute
**What goes wrong:** `start_workflow.py:99` declares `household_id: str = ""` as a class-default. If anyone constructs `StartWorkflowTool(chat_id=..., user_id=..., platform=...)` without passing `household_id`, Pydantic accepts the empty default. The tool stores `self.household_id = ""`, and the agent later auto-injects it via `shared_context.setdefault("household_id", self.household_id)` at line 115.

**How to avoid:** Remove the `= ""` default. Either make it required (no default), or apply `Field(min_length=1)` so the default fails validation. Removing the default is cleaner — every construction site already passes `household_id` (verified — `jobs.py:148`).

### Pitfall 6: Test fixtures that mock handle_message bypass the env-var read
**What goes wrong:** Several integration tests in `test_gateway.py` call `handle_message` directly. They currently rely on the silent `""` default and never set `HOUSEHOLD_ID`. After the fix, those tests will raise `KeyError` on the `os.environ["HOUSEHOLD_ID"]` read inside the function.

**How to avoid:** Add `monkeypatch.setenv("HOUSEHOLD_ID", "hh-test")` (or equivalent `os.environ` patch) to every `test_gateway.py` test that calls `handle_message`. Simpler: add a module-scope `autouse=True` fixture in `tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def _set_household_id(monkeypatch):
    monkeypatch.setenv("HOUSEHOLD_ID", "hh-test")
```

This is the cleanest mitigation and survives future test additions.

## Code Examples

### Pydantic NonEmptyStr alias (top of task_types.py)
```python
# Source: pydantic 2.7 documentation
from typing import Annotated
from pydantic import BaseModel, Field

NonEmptyHouseholdId = Annotated[
    str,
    Field(min_length=1, description="Household UUID. Empty string is rejected at construction.")
]

class IncomingMessageInput(BaseModel):
    # ... other fields ...
    household_id: NonEmptyHouseholdId
    # ... other fields ...
```

### Gateway entrypoint guard
```python
# File: src/robotina/gateway/__init__.py
import logging
import os
import sys

from telegram.ext import ApplicationBuilder, MessageHandler, filters

from robotina.gateway.handler import handle_message


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    household_id = os.environ.get("HOUSEHOLD_ID", "").strip()
    if not household_id:
        sys.stderr.write(
            "FATAL: HOUSEHOLD_ID environment variable is unset or empty.\n"
            "  The gateway refuses to start because every Conversation and "
            "WorkflowRun row would otherwise carry an empty household_id.\n"
            "  Set HOUSEHOLD_ID in your .env file (see .env.example) and retry.\n"
        )
        sys.exit(1)

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.getLogger(__name__).info("Starting Telegram gateway (polling mode)...")
    app.run_polling()
```

### Handler per-message bracket read (backstop)
```python
# File: src/robotina/gateway/handler.py — inside handle_message
# Replace line 43:
household_id = os.environ["HOUSEHOLD_ID"]  # was: os.environ.get("HOUSEHOLD_ID", "")
```

### .env.example addition
```
# Household identity (Phase 16+)
# REQUIRED. The gateway will refuse to start if HOUSEHOLD_ID is unset or empty.
# Replace the placeholder below with the actual household UUID for this deployment.
HOUSEHOLD_ID=replace-with-your-household-uuid
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2+ with pytest-asyncio 1.3.0+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths=["tests"]`, `asyncio_mode="auto"`, marker `integration` for tests needing live Postgres/Redis |
| Quick run command | `uv run pytest tests/unit -x -q` (skips integration tests) |
| Full suite command | `uv run pytest -x -q` (requires `docker compose up`) |
| Phase 16 gate | Full suite green + manual smoke test per SPEC R3 |

### Phase Requirements → Test Map

| Req | Behavior | Test Type | Automated Command | File Exists? |
|-----|----------|-----------|-------------------|-------------|
| SPEC-R1a | Gateway exits non-zero when HOUSEHOLD_ID unset | unit (subprocess) | `pytest tests/unit/test_gateway_boot.py::test_main_exits_on_missing_household_id -x` | ❌ Wave 0 |
| SPEC-R1b | Gateway exits non-zero when HOUSEHOLD_ID="" | unit (subprocess) | `pytest tests/unit/test_gateway_boot.py::test_main_exits_on_empty_household_id -x` | ❌ Wave 0 |
| SPEC-R1c | Gateway exits non-zero when HOUSEHOLD_ID="   " (whitespace) | unit (subprocess) | `pytest tests/unit/test_gateway_boot.py::test_main_exits_on_whitespace_household_id -x` | ❌ Wave 0 |
| SPEC-R1d | Stderr message names "HOUSEHOLD_ID" explicitly | unit (subprocess, capture stderr) | `pytest tests/unit/test_gateway_boot.py::test_main_stderr_mentions_household_id -x` | ❌ Wave 0 |
| SPEC-R1e | Gateway boots normally with non-empty HOUSEHOLD_ID | unit (mock ApplicationBuilder) | `pytest tests/unit/test_gateway_boot.py::test_main_boots_with_valid_household_id -x` | ❌ Wave 0 |
| IMPL-Pyd-1 | IncomingMessageInput rejects household_id="" | unit | `pytest tests/unit/test_task_types_household_id.py::test_incoming_message_rejects_empty -x` | ❌ Wave 0 |
| IMPL-Pyd-2 | All 7 Recipe*Input models reject household_id="" | unit (parametrized) | `pytest tests/unit/test_task_types_household_id.py::test_all_inputs_reject_empty_household_id -x` | ❌ Wave 0 |
| IMPL-Pyd-3 | Non-empty household_id accepted on every model | unit (parametrized) | `pytest tests/unit/test_task_types_household_id.py::test_inputs_accept_non_empty_household_id -x` | ❌ Wave 0 |
| IMPL-Tool-1 | HouseholdManagerApiTool() rejects empty household_id | unit | `pytest tests/unit/test_household_manager_api_tool.py::test_constructor_rejects_empty_household_id -x` | ❌ Wave 0 (add to existing file) |
| IMPL-Tool-2 | StartWorkflowTool() rejects empty household_id | unit | `pytest tests/unit/test_start_workflow_tool.py::test_constructor_rejects_empty_household_id -x` | ❌ Wave 0 (add to existing file) |
| IMPL-WR-1 | queue_workflow() raises ValueError on empty household_id | unit | `pytest tests/test_workflow_runner.py::test_queue_workflow_rejects_empty_household_id -x` | ❌ Wave 0 (add to existing file) |
| IMPL-WR-2 | queue_workflow() succeeds with valid household_id (smoke) | unit | covered by existing test_workflow_runner.py:93 path (regression check) | ✅ |
| IMPL-Hdlr-1 | handle_message reads HOUSEHOLD_ID via bracket form (raises if unset) | integration | `pytest tests/test_gateway.py::test_handler_raises_when_household_id_unset -x -m integration` | ❌ Wave 0 (or modify existing) |
| SPEC-R2 | `.env.example` contains `HOUSEHOLD_ID=` line with comment marker | unit (file read + regex) | `pytest tests/unit/test_env_example.py::test_household_id_documented -x` | ❌ Wave 0 |
| SPEC-R3 | End-to-end: WorkflowRun row carries env-var household_id | manual UAT | (manual smoke test per SPEC) | N/A — manual |

### Unit-level validations (detail)

1. **Pydantic model validators (7 models)** — Parametrized test: `@pytest.mark.parametrize("model_cls", [IncomingMessageInput, RecipeResearchInput, RecipeResearchGatherInput, RecipeResearchInstructionsInput, RecipeResearchIngredientsInput, RecipeResearchMetadataInput, RecipeLoadInput])`. For each model, construct with `household_id=""` and assert `pydantic.ValidationError` with `min_length` in message. Then construct with `household_id="hh-1"` and assert success.

2. **Tool constructors** — `HouseholdManagerApiTool(household_id="")` and `StartWorkflowTool(chat_id="c1", user_id="u1", platform="telegram", household_id="")` both raise `pydantic.ValidationError` (since `BaseTool` is Pydantic-based). Use `pytest.raises(ValidationError)`.

3. **queue_workflow** — Call `queue_workflow(workflow_type="add-recipe", shared_context={"reply_context": {...}}, household_id="", queue=MagicMock(), session=MagicMock())` and assert `pytest.raises(ValueError, match="empty household_id")`. No DB needed.

### Integration-level validation

**Gateway boot test** (`tests/unit/test_gateway_boot.py`, new file):

```python
# Source: standard pytest subprocess pattern
import subprocess
import sys
import pytest

def _run_gateway_main(env: dict) -> subprocess.CompletedProcess:
    """Run `python -c 'from robotina.gateway import main; main()'` with the given env."""
    return subprocess.run(
        [sys.executable, "-c", "from robotina.gateway import main; main()"],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )

def test_main_exits_on_missing_household_id():
    env = {"PATH": "/usr/bin:/bin", "TELEGRAM_BOT_TOKEN": "x"}  # HOUSEHOLD_ID absent
    result = _run_gateway_main(env)
    assert result.returncode == 1, result.stderr
    assert "HOUSEHOLD_ID" in result.stderr

def test_main_exits_on_empty_household_id():
    env = {"PATH": "/usr/bin:/bin", "TELEGRAM_BOT_TOKEN": "x", "HOUSEHOLD_ID": ""}
    result = _run_gateway_main(env)
    assert result.returncode == 1
    assert "HOUSEHOLD_ID" in result.stderr

def test_main_exits_on_whitespace_household_id():
    env = {"PATH": "/usr/bin:/bin", "TELEGRAM_BOT_TOKEN": "x", "HOUSEHOLD_ID": "   "}
    result = _run_gateway_main(env)
    assert result.returncode == 1
    assert "HOUSEHOLD_ID" in result.stderr
```

**Why subprocess:** `main()` calls `sys.exit(1)` which terminates the Python process. Subprocess isolation is the standard way to test exit codes without killing the pytest runner.

**Mock-based alternative for boot success:** Run `main()` in-process with `monkeypatch.setattr` on `ApplicationBuilder.build` and friends; assert no `SystemExit` is raised when `HOUSEHOLD_ID="hh-1"` is set. Cheaper than subprocess; lives in `test_gateway_boot.py` alongside the subprocess tests.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit -x -q` (sub-30s, runs all non-integration tests)
- **Per wave merge:** `uv run pytest -x -q` (full suite; requires `docker compose up`)
- **Phase gate:** Full suite green + manual smoke (SPEC R3 UAT)

### Wave 0 Gaps

Files that must exist before Wave 1 task execution:

- [ ] `tests/unit/test_gateway_boot.py` — covers SPEC-R1a..e via subprocess.
- [ ] `tests/unit/test_task_types_household_id.py` — covers IMPL-Pyd-1..3 (parametrized over 7 models).
- [ ] `tests/unit/test_env_example.py` — covers SPEC-R2 (file regex grep).
- [ ] `tests/conftest.py` — add `autouse=True` `_set_household_id` fixture that calls `monkeypatch.setenv("HOUSEHOLD_ID", "hh-test")` so the new handler bracket read (Pattern 4) doesn't break existing integration tests.
- [ ] Add tests to existing files (no new file needed):
  - [ ] `tests/unit/test_household_manager_api_tool.py` — add `test_constructor_rejects_empty_household_id`.
  - [ ] `tests/unit/test_start_workflow_tool.py` — add `test_constructor_rejects_empty_household_id`.
  - [ ] `tests/test_workflow_runner.py` — add `test_queue_workflow_rejects_empty_household_id`.

### Manual UAT (SPEC R3)

| # | Step | Expected |
|---|------|----------|
| 1 | Run gateway with `unset HOUSEHOLD_ID; uv run gateway` | Process exits with code 1; stderr names `HOUSEHOLD_ID` and references `.env.example` |
| 2 | Run gateway with `HOUSEHOLD_ID="" uv run gateway` | Same as #1 |
| 3 | Run gateway with `HOUSEHOLD_ID="   " uv run gateway` | Same as #1 |
| 4 | Set `HOUSEHOLD_ID=hh-smoke-1` in `.env`, start `uv run gateway` and `uv run agent` | Both processes start without error |
| 5 | Send a Telegram message "add carbonara recipe" | Workflow starts; recipe-research kicks off |
| 6 | Query Postgres: `SELECT household_id FROM conversations WHERE chat_id = '<chat_id>' ORDER BY created_at DESC LIMIT 1;` | Returns `hh-smoke-1` |
| 7 | Query Postgres: `SELECT household_id FROM workflow_runs ORDER BY created_at DESC LIMIT 1;` | Returns `hh-smoke-1` |
| 8 | Confirm misconfigured-deploy stderr is human-readable | Operator can identify the env-var name without reading source |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Pydantic v2.7+ does NOT re-run validators on pickle unpickling (RQ-stored task inputs) | Pitfall 2 | HIGH — if validators DO re-run, every in-flight job from before the deploy with old empty `household_id` will land in FailedJobRegistry. Mitigation: drain queue before deploy. **Verify before execution.** |
| A2 | `langchain_core.tools.BaseTool` is a Pydantic v2 model that honors `Field(min_length=1)` on class attributes | Pattern 6 | MEDIUM — if BaseTool uses a different validation path, `Field(min_length=1)` may be ignored and `model_validator` becomes necessary. Verify by running the new tool-constructor test against an empty string. |
| A3 | `os.environ["HOUSEHOLD_ID"]` inside `handle_message` raises `KeyError` (not silently fails) when the entrypoint guard was bypassed (e.g., tests importing the handler directly) | Pattern 4 | LOW — this is well-established Python stdlib behavior. |
| A4 | `tests/conftest.py` `autouse=True` fixture with `monkeypatch.setenv` runs BEFORE any test that imports `handle_message` and exercises it | Pitfall 6 | LOW — pytest fixtures with `autouse=True` are well-documented. |
| A5 | Pydantic v2 validators on `BaseTool` raise `ValidationError`, not `ValueError`. Tool construction sites in tests must expect `ValidationError` | Pattern 6 | LOW — verifiable in test execution. CONTEXT.md mentions "raises ValueError" in Defensive Validation section but pydantic raises ValidationError; the planner should reconcile by either keeping pydantic-native or wrapping with explicit `raise ValueError(...)` in `__init__` (less clean). |
| A6 | The dev/prod Redis queue is normally empty at quiet times so the deploy-boundary risk in Pitfall 2 is small | Pitfall 2 | LOW — operator confirms before deploy. |

## Open Questions

1. **SPEC vs CONTEXT.md placement discrepancy** (CRITICAL — planner must resolve)
   - SPEC R1: "boot-time guard at gateway entrypoint" (i.e., `__init__.py::main()`)
   - CONTEXT.md Failure Strategy: "raise RuntimeError at handler module import"
   - These are different files and different mechanisms.
   - **Recommendation:** Implement BOTH — entrypoint guard in `main()` (Pattern 2, primary fail-fast for SPEC R1), backed by bracket-form per-message read in `handler.py` (Pattern 4) for defense in depth. The handler bracket read does not trigger at import time; it only triggers at message dispatch, so test collection stays clean.

2. **`ValueError` vs `pydantic.ValidationError` on tool construction**
   - CONTEXT.md: "`HouseholdManagerApiTool.__init__` raises `ValueError` on empty `household_id`"
   - Pydantic-native: `Field(min_length=1)` raises `pydantic.ValidationError`
   - `ValidationError` is a subclass of `ValueError` (`pydantic.ValidationError` inherits from `ValueError` in pydantic v2 — `[ASSUMED]` verify). If true, `pytest.raises(ValueError)` matches both. Either approach satisfies CONTEXT.md.
   - **Recommendation:** Use `Field(min_length=1)` (pydantic-native). The test asserts `pytest.raises(ValueError)` which catches `ValidationError`.

3. **Auto-use conftest fixture vs per-test setenv**
   - Auto-use: cleaner, survives future tests. Slight risk of hiding bugs where a test SHOULD verify behavior with empty env.
   - Per-test: explicit, but requires touching every test in `test_gateway.py`.
   - **Recommendation:** Auto-use, plus one targeted "negative" test (`test_handler_raises_when_household_id_unset`) that explicitly `monkeypatch.delenv("HOUSEHOLD_ID")` to verify the bracket-form raises.

4. **Whitespace handling: `.strip()` or accept verbatim?**
   - SPEC R1 acceptance: "(after `.strip()`)" → must strip and check empty.
   - CONTEXT.md: silent on whitespace.
   - **Recommendation:** Strip in the entrypoint guard (SPEC R1 mandates). Do NOT strip in Pydantic validators — `Field(min_length=1)` rejects `""` but accepts `" "`. That's a minor leak. Either add `Field(min_length=1, pattern=r"^\S")` (regex requiring at least one non-whitespace char) OR accept that whitespace-only is caught at the gateway entrypoint and not propagated downstream. The latter is simpler. **Pick at planning time.**

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | ✓ | 3.12 (pyproject pin) | — |
| pydantic | Validators | ✓ | >=2.7 (pyproject) | — |
| pytest | Tests | ✓ | >=9.0.2 (dev group) | — |
| pytest-asyncio | Async tests | ✓ | >=1.3.0 | — |
| python-telegram-bot | Gateway entrypoint test | ✓ | >=21 | mock in test |
| Postgres (docker) | Integration test of handler | ✓ | 15 | skip integration tests with `-m "not integration"` |
| Redis (docker) | Integration test of enqueue | ✓ | 7 | skip integration tests |

No missing dependencies. No external services needed for unit tests.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `os.environ.get("X", "")` then silently propagating empty | `os.environ["X"]` (bracket-form, KeyError on missing) + Pydantic `Field(min_length=1)` defense | This phase (Phase 16) | Failures move from "confusing 4xx from downstream API" to "loud crash at gateway startup or model construction" |
| Pydantic v1 `Field(..., min_length=1)` syntax | Pydantic v2 `Field(min_length=1)` or `Annotated[str, Field(min_length=1)]` | Pydantic 2.0 (Jan 2023) | Already migrated project-wide — no new work |

**Deprecated/outdated:**
- `pydantic.constr(min_length=1)` — superseded in pydantic v2 by `Annotated[str, Field(min_length=1)]` (still works but warned-deprecated path); don't introduce.

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — this is a config-correctness fix, not auth |
| V3 Session Management | no | N/A |
| V4 Access Control | partial | `household_id` is the multi-tenant separator (forward-looking per FUTURE-01); an empty value bypasses tenant isolation. This phase eliminates that bypass for new rows. |
| V5 Input Validation | yes | `Field(min_length=1)` on Pydantic models + entrypoint env-var check |
| V6 Cryptography | no | N/A |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Tenant-isolation bypass via empty/missing tenant ID | Tampering (T) / Information Disclosure (I) | Reject empty at every boundary — gateway entrypoint, Pydantic models, tool constructors, workflow runner. |
| Confusing error messages to operator (silent default fallback) | Repudiation (R) | Bracket-form env reads + named env-var in stderr message. |
| Stale env-var docs causing fresh-deploy failures | Denial of Service (D) | `.env.example` mandatory sync (project rule). |

**Note:** Phase 1 is single-household (per CLAUDE.md). Multi-household tenancy is FUTURE-01. The threat-mitigation is forward-looking — even though Phase 1 has one tenant, the fix prevents the corruption that would make a multi-household migration hazardous.

## Sources

### Primary (HIGH confidence)
- `[VERIFIED]` `/home/solanoe/code/robotina-gsd/src/robotina/gateway/handler.py:43` — current bug location
- `[VERIFIED]` `/home/solanoe/code/robotina-gsd/src/robotina/gateway/send.py:12` — stale docstring line
- `[VERIFIED]` `/home/solanoe/code/robotina-gsd/src/robotina/queue/task_types.py` — 7 Pydantic models declaring `household_id: str`
- `[VERIFIED]` `/home/solanoe/code/robotina-gsd/src/robotina/agent/tools/start_workflow.py:99` — `household_id: str = ""` default
- `[VERIFIED]` `/home/solanoe/code/robotina-gsd/src/robotina/queue/workflow_runner.py:107` — `queue_workflow` signature
- `[VERIFIED]` `/home/solanoe/code/robotina-gsd/.env.example` — no `HOUSEHOLD_ID` line
- `[VERIFIED]` `/home/solanoe/code/robotina-gsd/tests/test_gateway.py` — 5 import sites for `handler.handle_message`
- `[VERIFIED]` `/home/solanoe/code/robotina-gsd/pyproject.toml` — pydantic >=2.7, pytest >=9.0.2

### Secondary (MEDIUM confidence)
- `[CITED]` Pydantic v2 docs — `Field(min_length=1)` and `Annotated[str, Field(...)]` patterns (training data; not refetched in this session)
- `[CITED]` Phase 3 plan `.planning/phases/03-gateway/03-02-PLAN.md:224` confirms the empty-default was intentional in Phase 3; Phase 16 reverses it.

### Tertiary (LOW confidence / assumed)
- `[ASSUMED]` RQ + pydantic-v2 pickle round-trip does NOT re-run validators — Pitfall 2 hinges on this. **Planner should verify with a one-shot test** before assuming queue-drain is unnecessary.
- `[ASSUMED]` `pydantic.ValidationError` inherits from `ValueError` in v2 — affects how tool-constructor tests are written.

## Metadata

**Confidence breakdown:**
- Affected files inventory: HIGH — grep-verified end-to-end
- Pydantic validation pattern: HIGH — well-established v2 idiom, already in use across the codebase
- Module-import-time pitfall (test collection): HIGH — verified via grep that 5+ tests import `handler.py` at function scope
- SPEC vs CONTEXT.md placement: MEDIUM — discrepancy flagged; recommendation given but planner must resolve
- RQ pickle re-validation behavior: LOW — assumed safe; needs verification
- BaseTool pydantic field behavior: MEDIUM — convention is well-documented but unverified for this specific case in this codebase

**Research date:** 2026-05-15
**Valid until:** 2026-06-15 (stable bug-fix; no fast-moving deps)

## RESEARCH COMPLETE
