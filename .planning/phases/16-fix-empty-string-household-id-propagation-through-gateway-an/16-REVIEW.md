---
phase: 16-fix-empty-string-household-id-propagation-through-gateway-an
reviewed: 2026-05-15T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - .env.example
  - src/robotina/agent/tools/household_manager_api.py
  - src/robotina/agent/tools/start_workflow.py
  - src/robotina/gateway/__init__.py
  - src/robotina/gateway/handler.py
  - src/robotina/gateway/send.py
  - src/robotina/queue/task_types.py
  - src/robotina/queue/workflow_runner.py
  - tests/conftest.py
  - tests/test_workflow_runner.py
  - tests/unit/test_env_example.py
  - tests/unit/test_gateway_boot.py
  - tests/unit/test_household_id_validation.py
  - tests/unit/test_household_manager_api_tool.py
  - tests/unit/test_start_workflow_tool.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 16: Code Review Report

**Reviewed:** 2026-05-15
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Phase 16 adds a four-layer defence against empty / whitespace `household_id`
propagation: (1) `NonEmptyHouseholdId` Pydantic alias on every task-input
model, (2) `NonEmptyHouseholdId` typing on both LangChain tools'
`household_id` constructor field, (3) runtime guard in
`queue_workflow()` before any DB write, and (4) fail-fast `sys.exit(1)`
at the gateway entrypoint when `HOUSEHOLD_ID` is unset / empty /
whitespace. Tests cover all four layers including the cross-component
agent-loop scenarios.

The implementation is solid, but the layers are not perfectly symmetric:
the boot guard `strip()`s the env value before validating, while the
per-message handler reads the raw env value with `os.environ[...]`. A
whitespace-padded `HOUSEHOLD_ID=" hh-1 "` therefore passes the boot
guard but reaches `IncomingMessageInput` with whitespace intact, which
in turn passes the `pattern=r"\S"` Pydantic check (only requires one
non-whitespace char, does not forbid surrounding whitespace) and is
persisted verbatim into `conversations.household_id` and
`workflow_runs.household_id`. No data corruption, but values diverge
from the "canonical" stripped form the boot guard validated. See WR-01.

Other findings are smaller: a `setdefault` ordering / mutation issue in
`StartWorkflowTool._run()` (WR-02), inconsistent typing between
`queue_workflow(household_id: str, ...)` and the rest of the codebase
that uses `NonEmptyHouseholdId` (WR-03), and a placeholder default
shipped in `.env.example` that — when copied verbatim — would still pass
every validator and silently corrupt the DB with the literal string
`replace-with-your-household-uuid` (WR-04).

## Warnings

### WR-01: Boot guard `strip()`s `HOUSEHOLD_ID` but handler does not, allowing whitespace-padded value into DB

**File:** `src/robotina/gateway/__init__.py:38` and `src/robotina/gateway/handler.py:50`

**Issue:** The boot guard normalises with `.strip()` before checking
emptiness:

```python
# __init__.py:38
household_id = os.environ.get("HOUSEHOLD_ID", "").strip()
if not household_id:
    sys.exit(1)
```

…but the per-message handler reads the raw, unstripped value:

```python
# handler.py:50
household_id = os.environ["HOUSEHOLD_ID"]
```

If the operator sets `HOUSEHOLD_ID=" hh-1 "` (extra whitespace —
realistic for hand-edited `.env` files or shell heredocs), the boot
guard sees `"hh-1"` (passes), logs `"hh-1"` (line 53), but every
`Conversation.household_id` and `WorkflowRun.household_id` row is
written as the literal `" hh-1 "` with surrounding whitespace. Joining
against a stripped tenant table will silently miss rows.

`NonEmptyHouseholdId`'s `pattern=r"\S"` only asserts *at least one*
non-whitespace character exists; it does not forbid leading/trailing
whitespace. So Pydantic accepts `" hh-1 "` too.

**Fix:** Either strip at the handler read site or store the stripped
value in a module-level constant after the boot guard runs. The
simplest fix is symmetry at the handler:

```python
# handler.py:50
household_id = os.environ["HOUSEHOLD_ID"].strip()
if not household_id:
    # defense in depth — boot guard should have caught this
    raise RuntimeError("HOUSEHOLD_ID empty at handler runtime")
```

Or tighten `NonEmptyHouseholdId` to forbid surrounding whitespace
(`pattern=r"^\S(.*\S)?$"`), which makes the Pydantic layer reject
padded values uniformly across every consumer.

---

### WR-02: `StartWorkflowTool._run` uses `setdefault` for `household_id`, allowing LLM-injected `shared_context` value to win over constructor

**File:** `src/robotina/agent/tools/start_workflow.py:121`

**Issue:**

```python
shared_context.setdefault("household_id", self.household_id)
household_id = shared_context["household_id"]
```

`setdefault` only writes if the key is absent. The LLM controls the
`shared_context` argument (`StartWorkflowArgs.shared_context: dict` is
unvalidated nested content). If the model hallucinates
`{"household_id": ""}` or `{"household_id": "wrong-house"}` in its
tool call, `self.household_id` (the trusted constructor value) is
silently shadowed.

The empty-string case is caught downstream by `queue_workflow`'s
guard, so the workflow fails cleanly. But:

1. A non-empty *wrong* value (e.g. another household's UUID
   hallucinated by the LLM) passes every guard and is persisted to
   `WorkflowRun.household_id`. This is a tenant-isolation defect once
   multi-household support is added.
2. The same applies to `reply_context` on line 116 — an LLM-emitted
   `reply_context` shadows the constructor identity, so a hallucinated
   `chat_id` could redirect the eventual `send-notification` reply.

This is documented in the inline comment ("falls through to
queue_workflow's raise") but the comment only addresses the empty case.

**Fix:** Make the constructor identity authoritative — overwrite
unconditionally instead of `setdefault`:

```python
shared_context["reply_context"] = {
    "platform": self.platform,
    "chat_id": self.chat_id,
    "user_id": self.user_id,
}
shared_context["household_id"] = self.household_id
household_id = self.household_id  # avoid the dict round-trip
```

Also consider not mutating the caller's dict in place (langgraph may
retain the original arg dict across retries):

```python
shared_context = {
    **shared_context,
    "reply_context": {...},
    "household_id": self.household_id,
}
```

---

### WR-03: `queue_workflow(household_id: str, ...)` annotation skips `NonEmptyHouseholdId`, leaving the guard as the only enforcement

**File:** `src/robotina/queue/workflow_runner.py:107`

**Issue:** Every other surface in Phase 16 uses
`NonEmptyHouseholdId` (the Pydantic-validated alias), but
`queue_workflow`'s parameter is annotated as plain `str`:

```python
def queue_workflow(
    workflow_type: str,
    shared_context: dict,
    household_id: str,        # <-- inconsistent with everything else
    queue,
    session: Session,
) -> str:
```

The runtime guard at line 136 (`if not household_id or not
household_id.strip():`) catches the empty / whitespace case at call
time, so behaviour is correct today. But:

- New callers don't get a type hint signaling the constraint.
- A future refactor that drops the runtime guard (deduplication
  attempt) would silently lose the check — type-checkers wouldn't
  catch it.
- The whitespace strip happens here but isn't reflected in what's
  persisted: the guard checks `household_id.strip()` for emptiness but
  then writes the *un*stripped `household_id` to `WorkflowRun`
  (line 152). Pairs with WR-01.

**Fix:** Annotate as `NonEmptyHouseholdId` to match the rest of the
codebase, and either strip the value at the top of the function or
trust it (one place of truth):

```python
from robotina.queue.task_types import NonEmptyHouseholdId

def queue_workflow(
    workflow_type: str,
    shared_context: dict,
    household_id: NonEmptyHouseholdId,
    queue,
    session: Session,
) -> str:
    household_id = household_id.strip()
    if not household_id:
        raise ValueError(...)
```

Note: `NonEmptyHouseholdId` is an `Annotated[str, Field(...)]`, so it
will still pass through plain-string call sites — but type-checkers
will surface the intent.

---

### WR-04: `.env.example` ships a placeholder that passes every validator and would silently corrupt rows if copied verbatim

**File:** `.env.example:20`

**Issue:**

```
HOUSEHOLD_ID=replace-with-your-household-uuid
```

The string `replace-with-your-household-uuid` is non-empty,
non-whitespace, and matches `pattern=r"\S"`. An operator who runs
`cp .env.example .env` and forgets to edit the value will:

1. Boot the gateway successfully (no `sys.exit(1)`).
2. Persist `replace-with-your-household-uuid` into every
   `Conversation.household_id` and `WorkflowRun.household_id` row.
3. Need a DB cleanup before pointing at a real backend, because
   household-manager-api lookups by that string will 404.

The boot guard documentation block (lines 14–19) explains that
HOUSEHOLD_ID is required but does not warn about the placeholder
itself being a *valid-looking* sentinel. This is exactly the
"silent-empty-default" class of bug Phase 16 set out to prevent, just
moved one layer outward (config file instead of code default).

**Fix:** Make the placeholder obviously invalid so misconfiguration
fails loudly. Either leave it empty (forces the boot guard to fire):

```
HOUSEHOLD_ID=
```

…or pick a sentinel the boot guard explicitly rejects:

```python
# __init__.py
if not household_id or household_id == "replace-with-your-household-uuid":
    sys.stderr.write("FATAL: HOUSEHOLD_ID still set to the .env.example placeholder.\n")
    sys.exit(1)
```

The empty-string version is simpler and self-consistent with the rest
of the phase's design philosophy.

## Info

### IN-01: Module-level imports placed after class definition

**File:** `src/robotina/gateway/send.py:27-28`

**Issue:** Imports for `SessionLocal` and gateway models are placed
*after* the `@dataclass class SendResult` block, violating PEP 8
(imports at top of module). Pre-existing — not introduced by Phase 16
— but visible in the diff because the file was opened during review.

**Fix:** Move the two `from robotina...` imports to the top of the
file with the other imports.

---

### IN-02: Whitespace-only `household_id` regex is permissive

**File:** `src/robotina/queue/task_types.py:55`

**Issue:** `pattern=r"\S"` requires at least one non-whitespace char
*anywhere* in the string. It does not pin to start / end:

- Accepts: `"  hh-1  "`, `"\thh-1\n"`, `"hh-1 \n"`
- Rejects: `""`, `"   "`, `"\t\n "`

Combined with WR-01 (handler doesn't strip), this is the precise
escape hatch for whitespace-padded env values. If the project's intent
is "non-empty, non-whitespace, and trimmed", pin the pattern:

**Fix:**

```python
pattern=r"^\S+(.*\S+)?$"
# or
pattern=r"^[^\s].*[^\s]$|^\S$"
```

Either form forbids surrounding whitespace. Re-run the Pydantic
parametrised tests with `"  hh-1  "` to confirm rejection.

---

### IN-03: `queue_workflow`'s error message references plan numbers and file paths

**File:** `src/robotina/queue/workflow_runner.py:137-142`

**Issue:** The `ValueError` raised when `household_id` is empty
contains a long debugging story referencing internal file paths
("`gateway/__init__.py boot guard, IncomingMessageInput.household_id
validation, and StartWorkflowTool.household_id field`"). When this
exception propagates to `step.failure_reason` via `on_step_failed`
(line 452 — D-16 format), the dashboard cell will render this internal
narrative to anyone with dashboard access.

`failure_reason` is capped at 500 chars (line 33) so it won't overflow,
but the message ends up wasting roughly half the cap on a debugging
note that's only useful to engineers reading source anyway.

**Fix:** Shorten the user-facing exception text and move the
"check X/Y/Z" content to a log line emitted right before the raise:

```python
if not household_id or not household_id.strip():
    logger.error(
        "queue_workflow: empty household_id; check gateway boot guard, "
        "IncomingMessageInput validation, StartWorkflowTool field"
    )
    raise ValueError("queue_workflow received empty household_id")
```

---

### IN-04: `_set_household_id` autouse fixture masks tests that intend to verify the env-var-absent path

**File:** `tests/conftest.py:14-22`

**Issue:** The `_set_household_id` fixture is `autouse=True` and sets
`HOUSEHOLD_ID=test-household` in every test. The docstring instructs
authors who need the unset case to call
`monkeypatch.delenv("HOUSEHOLD_ID", raising=False)` inside the test
body. This is fine for in-process tests, but:

- `tests/unit/test_gateway_boot.py` already avoids the issue by
  shelling out to a subprocess with a hand-built env dict, so the
  autouse fixture doesn't reach the subprocess. Good.
- Any future test that wants to verify the empty / unset case
  *in-process* must remember the delenv dance. A reviewer might miss
  this and ship a test that silently passes because the fixture set
  the env first.

**Fix:** Either drop `autouse=True` and require explicit opt-in via a
named fixture (`household_id_set`), or add a comment in the test file
header reminding authors to delenv when testing the absent branch.
This is style, not a bug — flagging because it's a pattern that
typically rots.

---

_Reviewed: 2026-05-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
