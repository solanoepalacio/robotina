# Phase 17: Conversation FK closure - Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** 9 (1 new migration, 5 modified source files, 2 modified test files, 1 modified REQUIREMENTS doc)
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `migrations/versions/0006_conversation_fk_and_outcome.py` (NEW) | migration | schema-DDL | `migrations/versions/0005_dashboard_columns.py` | exact |
| `src/robotina/queue/models.py` (MOD) | model | schema-decl | `src/robotina/queue/models.py:51-55` (Phase 13 additive `WorkflowRunStep.step_input` / `WorkflowRunStep.artifact`) | exact (in-file precedent) |
| `src/robotina/queue/task_types.py` (MOD: add `WorkflowOutcome` stub) | model (Pydantic) | request-response | `src/robotina/queue/task_types.py:105-135` (`RecipeData` BaseModel) + `task_types.py:51-69` (`NonEmptyHouseholdId` Phase 16 banner-comment style) | exact (in-file precedent) |
| `src/robotina/queue/workflow_runner.py::queue_workflow` (MOD: add required arg) | service | CRUD | `src/robotina/queue/workflow_runner.py:106-157` (Phase 16 `household_id` signature + REQ-HID-4 guard) | exact (in-file Phase 16 precedent) |
| `src/robotina/agent/tools/start_workflow.py` (MOD: add ctor field) | tool (BaseTool) | request-response | `src/robotina/agent/tools/start_workflow.py:122-172` (Phase 16 `household_id` constructor-injected field + `_run` propagation) | exact (in-file Phase 16 precedent) |
| `src/robotina/queue/jobs.py::run_task` `handle-incoming-message` branch (MOD: add lookup + ctor arg) | controller (worker) | request-response | `src/robotina/gateway/handler.py:55-72` (existing `.filter_by(platform=…, chat_id=…)` Conversation lookup idiom) + `src/robotina/queue/jobs.py:134-149` (existing tool-injection block, in-file) | exact |
| `tests/test_workflow_runner.py` (MOD: add 6 tests, update 3) | test | unit + integration | `tests/test_workflow_runner.py:531-604` (Phase 13 `test_workflow_run_step_model_has_new_columns` + `test_migration_0005_upgrades_and_downgrades`) + `:799-847` (Phase 16 `test_queue_workflow_rejects_empty_household_id`) | exact (in-file Phase 13 + Phase 16 precedents) |
| `tests/unit/test_start_workflow_tool.py` (MOD: add 3 tests, bulk-update ~15 ctor calls) | test | unit | `tests/unit/test_start_workflow_tool.py:266-297` (Phase 16 `test_constructor_requires_household_id_no_default` family) | exact (in-file Phase 16 precedent) |
| `.planning/REQUIREMENTS.md` (MOD: ARCH-01 wording) | doc | static | n/a — one-line text edit | n/a |

## Pattern Assignments

### `migrations/versions/0006_conversation_fk_and_outcome.py` (NEW — migration, schema-DDL)

**Analog:** `migrations/versions/0005_dashboard_columns.py` (full file, 33 lines)

**Module docstring + revision header** (lines 1-17 of `0005`):
```python
"""workflow_run_steps: add step_input (JSON) and failure_reason (Text)

Phase 13 / Plan 13-01 (DASH-01): persistence layer for the queue visibility
dashboard. Both columns are nullable — historical rows backfill to NULL and
the running worker keeps working after the upgrade.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-14
"""
import sqlalchemy as sa
from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None
```

**Upgrade/downgrade pattern** (lines 20-33 of `0005`):
```python
def upgrade() -> None:
    op.add_column(
        'workflow_run_steps',
        sa.Column('step_input', sa.JSON(), nullable=True),
    )
    op.add_column(
        'workflow_run_steps',
        sa.Column('failure_reason', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('workflow_run_steps', 'failure_reason')
    op.drop_column('workflow_run_steps', 'step_input')
```

**How to adapt for `0006`:**
- Bump `revision = '0006'`, `down_revision = '0005'`.
- Docstring summary: `"workflow_runs: add conversation_id (FK, NOT NULL) and outcome (JSON, nullable)"`. Cite ARCH-01 + D-01 (single revision, pre-cleaned table per D-08 runbook).
- Two `op.add_column` calls. First column adds `sa.Column('conversation_id', sa.String(), sa.ForeignKey('conversations.id'), nullable=False)` — note the inline `sa.ForeignKey('conversations.id')` as the second positional arg of `sa.Column`. Second column adds `sa.Column('outcome', sa.JSON(), nullable=True)`.
- `downgrade()` drops in reverse order: `outcome` first, then `conversation_id`.

**FK syntax note:** No existing `0001`–`0005` migration uses `op.add_column` + inline FK (Phase 16 migration was a no-op; `0002_models.py:67` uses `sa.ForeignKeyConstraint` inside `create_table`, not `add_column`). Inline `sa.ForeignKey()` inside `sa.Column()` is documented Alembic syntax and the simplest single-statement form (RESEARCH §"Open Questions" #2). Leave the constraint unnamed — Postgres autonames as `workflow_runs_conversation_id_fkey`, matching the unnamed-FK precedent in `0002` (`stored_messages.conversation_id` FK).

---

### `src/robotina/queue/models.py::WorkflowRun` (MOD — add two columns)

**Analog:** Same file, `WorkflowRunStep` rows 51-55 (Phase 13 additive columns) and existing `WorkflowRun` body lines 28-37.

**Mapped/mapped_column style for additive NOT-NULL FK column** (analog: `WorkflowRunStep.workflow_run_id` line 44):
```python
workflow_run_id: Mapped[str] = mapped_column(String, ForeignKey("workflow_runs.id"), nullable=False)
```

**Mapped/mapped_column style for additive nullable JSON column** (analog: `WorkflowRunStep.artifact` line 51 and `WorkflowRunStep.step_input` line 54):
```python
artifact: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
# Phase 13 / Plan 13-01 (DASH-01): dashboard persistence columns. Both nullable
# so historical rows backfill to NULL and the migration is non-blocking.
step_input: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
```

**Imports already present in file (line 6) — no new imports needed:**
```python
from sqlalchemy import String, DateTime, Enum, JSON, ForeignKey, UniqueConstraint, Text
from typing import Optional
```

**How to adapt:** Insert two new columns into the existing `WorkflowRun` class body. Suggested placement: immediately after `household_id` (line 32) for `conversation_id` and immediately after `shared_context` (line 34) for `outcome` — keep related identity fields adjacent. Add a banner comment `# Phase 17 / ARCH-01: …` for `conversation_id` and `# Phase 17 / D-06 — slot for Phase 20 outcome shape` for `outcome`, mirroring the Phase 13 banner at lines 52-53.

---

### `src/robotina/queue/task_types.py` (MOD — add `WorkflowOutcome` stub + `ConfigDict` import)

**Analog 1 (banner-comment + Annotated alias):** lines 38-69 (`NonEmptyHouseholdId` block).

```python
# ---------------------------------------------------------------------------
# Phase 16 — non-empty household_id constraint (REQ-HID-2)
# ---------------------------------------------------------------------------
# Centralized constraint applied to every task-input model that carries a
# household_id. ``min_length=1`` rejects the empty string; …

NonEmptyHouseholdId = Annotated[
    str,
    Field(
        min_length=1,
        pattern=r"^\S(.*\S)?$",
        description=(…),
    ),
]
```

**Analog 2 (BaseModel with rich docstring):** lines 105-135 (`RecipeData`).

```python
class RecipeData(BaseModel):
    """Shared accumulating artifact across the recipe-research pipeline.

    Only ``name`` is required …
    """

    name: str
    description: str | None = None
    …
```

**Imports already present (line 35):**
```python
from pydantic import BaseModel, Field
```

**How to adapt:** Add `ConfigDict` to the pydantic import line (line 35 becomes `from pydantic import BaseModel, ConfigDict, Field`). At the END of the file (after `AcknowledgeAddRecipeInput`, line 325), append a section banner + `WorkflowOutcome` class:

```python
# ---------------------------------------------------------------------------
# Phase 17 / D-07 — WorkflowOutcome stub
# Placeholder shape; Phase 20 will define per-workflow-type concrete shapes
# (AddRecipeOutcome, etc.). Not imported by workflow_runner.py or any agent
# in Phase 17 — the stub exists so Phase 20 reads as "fill in the shape"
# rather than "introduce a new concept."
# ---------------------------------------------------------------------------


class WorkflowOutcome(BaseModel):
    """Placeholder — Phase 20 defines the per-workflow-type shape."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["pending"] = "pending"
```

`Literal` is already imported at line 33; no additional imports beyond `ConfigDict`. Per RESEARCH "Open Questions" #1, place at end of file (workflow-level scope, not task-level).

**Skip `NonEmptyConversationId`:** Per CONTEXT D-03 / RESEARCH Pattern 2, do NOT create a `NonEmptyConversationId` Annotated alias — `conversation_id` is system-generated (UUID resolved via `.one()`), not LLM-supplied, so the LLM-shadowing motivation that justified `NonEmptyHouseholdId` does not apply. FK NOT NULL + `.one()` raise carry the invariant.

---

### `src/robotina/queue/workflow_runner.py::queue_workflow` (MOD — add required `conversation_id` arg)

**Analog:** Same function, Phase 16 `household_id` precedent (lines 106-157).

**Signature pattern** (lines 106-112):
```python
def queue_workflow(
    workflow_type: str,
    shared_context: dict,
    household_id: NonEmptyHouseholdId,
    queue,
    session: Session,
) -> str:
```

**Docstring pattern** (lines 113-132 of `queue_workflow`):
```python
"""Create a WorkflowRun as PENDING and all WorkflowRunStep records, enqueue the first step.

…

Args:
    workflow_type: Key in WORKFLOW_REGISTRY (e.g. "add-recipe").
    shared_context: …
    household_id: Stored on WorkflowRun for filtering/monitoring.
    queue: RQ Queue instance connected to "agent-tasks".
    session: SQLAlchemy session (injected for testability — D-11).
"""
```

**REQ-HID-4 guard pattern** (lines 138-144) — **KEEP UNCHANGED; do NOT add a parallel guard for `conversation_id`** (per RESEARCH "Anti-Patterns to Avoid" and CONTEXT "Established Patterns"):
```python
if not household_id or not household_id.strip():
    raise ValueError(
        "queue_workflow refuses empty household_id; this indicates "
        "HOUSEHOLD_ID was not propagated from the gateway. Check "
        "gateway/__init__.py boot guard, IncomingMessageInput.household_id "
        "validation, and StartWorkflowTool.household_id field."
    )
```

**WorkflowRun construction pattern** (lines 152-157):
```python
run = WorkflowRun(
    workflow_type=workflow_type,
    household_id=household_id,
    shared_context=shared_context,
    status=WorkflowStatus.PENDING,
)
```

**How to adapt:**
1. Insert `conversation_id: str,` after `household_id: NonEmptyHouseholdId,` in the signature (no default — required positional). Plain `str` type, not an `Annotated` alias (per D-03 skip).
2. Extend the docstring `Args:` block with `conversation_id: FK to Conversation that originated this workflow run (ARCH-01).`.
3. **Do not** insert a `if not conversation_id` guard — RESEARCH §"Don't Hand-Roll" explicitly forbids it; FK NOT NULL + upstream `.one()` raise cover the invariant.
4. Add `conversation_id=conversation_id,` to the `WorkflowRun(…)` kwargs at line 152-157. Do NOT pass `outcome=…` — `Mapped[Optional[dict]]` defaults to `None` per assumption A1 in RESEARCH.

---

### `src/robotina/agent/tools/start_workflow.py::StartWorkflowTool` (MOD — add `conversation_id` ctor field + propagate in `_run`)

**Analog:** Same class, Phase 16 `household_id` field at line 130 and `_run` call at lines 166-172.

**Constructor field pattern** (lines 122-130):
```python
# Injected by run_task() at construction time
# Phase 16 (REQ-HID-3 / RESEARCH Pitfall 5): household_id has NO default —
# caller MUST pass a non-empty value. NonEmptyHouseholdId rejects '' and
# whitespace at pydantic validation. chat_id / user_id / platform defaults
# are intentionally LEFT as '' — out of scope for Phase 16.
chat_id: str = ""
user_id: str = ""
platform: str = ""
household_id: NonEmptyHouseholdId
```

**`_run` propagation pattern** (lines 166-172):
```python
workflow_run_id = workflow_runner.queue_workflow(
    workflow_type=workflow_type,
    shared_context=shared_context,
    household_id=household_id,
    queue=queue,
    session=session,
)
```

**How to adapt:**
1. Insert `conversation_id: str` immediately after `household_id: NonEmptyHouseholdId` at line 130. **No default** (required; mirrors `household_id` D-03 precedent). Add a banner comment block above explaining the field is constructor-injected by `run_task` and never reaches `args_schema` (so the LLM cannot supply it).
2. In `_run` (line 166-172), add `conversation_id=self.conversation_id,` as a kwarg in the `queue_workflow(…)` call, placed immediately after `household_id=household_id,`.
3. **Do NOT remove** the `shared_context["reply_context"]` write at lines 144-152 — RESEARCH "Anti-Patterns to Avoid" and ARCH-05 explicitly preserve this. The dead-letter `send-notification` block (`workflow_runner.py:495-515`) and every step's `build_input` (`agent/workflows.py:105-159`) still read it.

---

### `src/robotina/queue/jobs.py::run_task` `handle-incoming-message` branch (MOD — add lookup + ctor arg)

**Analog 1 (Conversation lookup idiom):** `src/robotina/gateway/handler.py:55-72` (the upsert site that guarantees the row exists by the time `run_task` sees the job).

Existing `.filter_by(platform=…, chat_id=…).first()` calls live in `handler.py`; for `run_task` we switch `.first()` → `.one()` because the row MUST exist (gateway commits before enqueue per `handler.py:110`, then enqueues at lines 125-132). `.one()` raises `sqlalchemy.exc.NoResultFound` on miss = fail loud = correct contract per D-04.

**Analog 2 (existing tool-injection block in same branch):** `src/robotina/queue/jobs.py:134-149`:
```python
if task_type == "handle-incoming-message":
    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    from robotina.agent.tools.queue import QueueTool
    from robotina.agent.tools.start_workflow import StartWorkflowTool
    tools.append(HouseholdManagerApiTool(household_id=task_input.household_id))
    tools.append(QueueTool(
        chat_id=task_input.chat_id,
        user_id=task_input.user_id,
        platform=task_input.platform,
    ))
    tools.append(StartWorkflowTool(
        chat_id=task_input.chat_id,
        user_id=task_input.user_id,
        platform=task_input.platform,
        household_id=task_input.household_id,
    ))
```

**Session source pattern:** `_session = SessionLocal()` is already opened at line 76 of `jobs.py`. Reuse it — do NOT open a second session for the Conversation lookup.

**How to adapt:**
1. Add `from robotina.gateway.models import Conversation, Platform` to the inline imports inside this branch (mirrors the existing per-branch lazy-import style on lines 135-137).
2. Before the three `tools.append(…)` calls, insert:
   ```python
   conversation = (
       _session.query(Conversation)
       .filter_by(
           platform=Platform(task_input.platform),
           chat_id=task_input.chat_id,
       )
       .one()  # raises NoResultFound on miss — fail loud (gateway upserts before enqueue)
   )
   ```
3. Extend the `StartWorkflowTool(…)` constructor call with `conversation_id=conversation.id,`.
4. `Platform(task_input.platform)` coercion is safe because `IncomingMessageInput.platform: Literal["telegram"]` (task_types.py:144) — see RESEARCH Pitfall 7.

---

### `tests/test_workflow_runner.py` (MOD — add 6 tests, update 3 call sites)

**Analog 1 (schema introspection test):** `tests/test_workflow_runner.py:531-544` (`test_workflow_run_step_model_has_new_columns`):
```python
# step_input is JSON-typed (python_type is dict)
assert cols["step_input"].type.python_type is dict
# both columns are nullable (migration safety: no full-table rewrite)
assert cols["step_input"].nullable is True
assert cols["failure_reason"].nullable is True
```

**Analog 2 (integration migration test):** `tests/test_workflow_runner.py:547-604` (`test_migration_0005_upgrades_and_downgrades`) — full template covering upgrade → assert columns present → downgrade → assert columns gone → re-upgrade to restore head. Uses `@pytest.mark.integration`, `alembic.command.upgrade/downgrade`, and `information_schema.columns` SELECT.

**Analog 3 (signature-rejection test):** `tests/test_workflow_runner.py:799-847` (`test_queue_workflow_rejects_empty_household_id` / `test_queue_workflow_rejects_whitespace_household_id`) — uses `MagicMock()` for session and queue, asserts `pytest.raises(ValueError)`, asserts `mock_session.add.assert_not_called()` to prove no DB writes happened before the guard fired.

**How to adapt:**

*New tests to add (Wave 0 RED stubs):*
- `test_workflow_run_has_conversation_id_column` — mirror lines 540-544 pattern; assert column exists, `python_type is str`, `nullable is False`, FK target is `conversations.id`.
- `test_workflow_run_has_outcome_column` — mirror lines 540-544; assert `python_type is dict`, `nullable is True`.
- `test_migration_0006_upgrades_and_downgrades` — clone lines 547-604 verbatim, change table to `workflow_runs`, column names to `conversation_id` / `outcome`, expected `data_type` to `character varying` (string) / `json`, expected `is_nullable` to `'NO'` / `'YES'`. **Decorate with `@pytest.mark.integration`** — needs live Postgres.
- `test_queue_workflow_persists_conversation_id` — mocked-session pattern from lines 619-679; assert the `WorkflowRun` MagicMock receives `conversation_id="conv-1"`.
- `test_queue_workflow_requires_conversation_id` — mirror lines 799-823 but expect `TypeError` (missing positional arg) instead of `ValueError`, since `conversation_id` is enforced at the Python signature level (no Python-level guard per RESEARCH §"Don't Hand-Roll").
- `test_shared_context_reply_context_still_written` — ARCH-05 regression guard; assert `WorkflowRun.shared_context["reply_context"]` is still populated after `queue_workflow` runs through `StartWorkflowTool`.

*Existing tests to update (Wave 1, atomic with source change):*
- `test_step_input_persisted_on_first_enqueue` (line ~619) — add `conversation_id="conv-1"` to the `queue_workflow(…)` kwargs.
- `test_queue_workflow_rejects_empty_household_id` (line 799-823) — add `conversation_id="conv-1"` (test focuses on household_id; conversation_id must be valid so the household_id guard is reached).
- `test_queue_workflow_rejects_whitespace_household_id` (line 826-847) — same change.

---

### `tests/unit/test_start_workflow_tool.py` (MOD — add 3 tests, bulk-update ~15 ctor calls)

**Analog:** `tests/unit/test_start_workflow_tool.py:266-297` (Phase 16 `test_constructor_rejects_empty_household_id` / `test_constructor_requires_household_id_no_default` / `test_constructor_accepts_non_empty_household_id`).

**Field-required test pattern** (lines 278-287):
```python
def test_constructor_requires_household_id_no_default():
    """StartWorkflowTool() without household_id must fail — proves '' default was removed (Pitfall 5)."""
    import pytest
    from pydantic import ValidationError

    from robotina.agent.tools.start_workflow import StartWorkflowTool

    with pytest.raises(ValidationError) as exc_info:
        StartWorkflowTool(chat_id="c1", user_id="u1", platform="telegram")
    assert "household_id" in str(exc_info.value)
```

**Field-accepted regression-guard test pattern** (lines 290-297):
```python
def test_constructor_accepts_non_empty_household_id():
    """Regression guard: existing call site pattern still works."""
    from robotina.agent.tools.start_workflow import StartWorkflowTool

    tool = StartWorkflowTool(
        chat_id="c1", user_id="u1", platform="telegram", household_id="h1"
    )
    assert tool.household_id == "h1"
```

**How to adapt:**

*New tests to add (Wave 0 RED stubs):*
- `test_constructor_requires_conversation_id_no_default` — mirror lines 278-287; omit `conversation_id` kwarg, expect `ValidationError` with `"conversation_id"` in message. The other kwargs MUST include `household_id="h1"` so the test only fails on the missing `conversation_id`.
- `test_constructor_accepts_non_empty_conversation_id` — mirror lines 290-297; assert `tool.conversation_id == "conv-1"`.
- `test_run_passes_conversation_id_to_queue_workflow` — extend the existing reply_context propagation test pattern at lines 78-113; mock `workflow_runner.queue_workflow` and assert it was called with `conversation_id="conv-1"`.

*Bulk update (Wave 1):* The research enumerates ~15 sites at lines 18-20, 28-30, 56-58, 83-85, 127-129, 176-178, 202-204, 222-224, 255-257, 271-273, 285-287, 294-296, 315-317, 343-345. Each currently looks like:
```python
StartWorkflowTool(chat_id="c1", user_id="u1", platform="telegram", household_id="h1")
```
becomes:
```python
StartWorkflowTool(chat_id="c1", user_id="u1", platform="telegram", household_id="h1", conversation_id="conv-1")
```

Per RESEARCH Pitfall 3, this is mechanical — same shape as the Phase 16 bulk-add of `household_id`.

*Note on `tests/unit/test_agent_runner.py`:* RESEARCH also flags `test_run_task_injects_all_three_tools_for_handle_incoming_message` at line 271-349 needs extension (assert `sw_tools[0].conversation_id == <expected>`) and two new tests (`test_run_task_resolves_and_injects_conversation_id`, `test_run_task_raises_when_conversation_missing`). The mocked-session-returning-MagicMock-Conversation pattern is the substrate. This file was not enumerated in CONTEXT's file list but IS named in RESEARCH §"Wave 0 Gaps"; planner should include it.

---

### `.planning/REQUIREMENTS.md` (MOD — one-line ARCH-01 wording update)

Per D-01: replace `"column is migrated nullable → backfill → NOT NULL via a three-step Alembic sequence; existing rows are backfilled"` with `"as a single Alembic revision (table is pre-cleaned before deploy)"`.

No code analog — this is a documentation edit that MUST be atomic with the migration commit (per RESEARCH §"Locked Decisions" D-01 and CONTEXT §"Specific Ideas").

---

## Shared Patterns

### Pattern A: Phase 16 four-layer identity-field topology (PARTIAL — skip layer 1)

**Source:** Phase 16 `household_id` precedent across the same five files Phase 17 touches.

**Apply to:** `conversation_id` plumbing across `task_types.py` (SKIP), `workflow_runner.py`, `start_workflow.py`, `jobs.py`.

**Layer 1 — Pydantic Annotated alias (SKIP):** `task_types.py:51-69` `NonEmptyHouseholdId`. **Phase 17 does NOT add a `NonEmptyConversationId` alias** per CONTEXT "Claude's Discretion" + RESEARCH §"Anti-Patterns to Avoid". `conversation_id` is system-generated (UUID from `.one()` on a uniquely-keyed row), not LLM-supplied. The LLM-shadowing attack surface that motivated the Phase 16 alias does not exist here.

**Layer 2 — Tool constructor field with no default (APPLY):** `start_workflow.py:130` `household_id: NonEmptyHouseholdId`. Phase 17 adds `conversation_id: str` (plain `str` since Layer 1 is skipped). No default → caller MUST pass.

**Layer 3 — Service function signature required arg (APPLY):** `workflow_runner.py:109` `household_id: NonEmptyHouseholdId,`. Phase 17 adds `conversation_id: str,` to `queue_workflow` — no default, no fallback.

**Layer 4 — Service function defensive guard (SKIP):** `workflow_runner.py:138-144` REQ-HID-4 `if not household_id or not household_id.strip()` ValueError. **Phase 17 does NOT add a parallel `conversation_id` guard** — FK NOT NULL constraint + upstream `.one()` raise cover the invariant. The guard pattern stays in place for `household_id` (unchanged).

**New Layer 5 — DB FK NOT NULL constraint (APPLY):** The migration's `nullable=False` + `sa.ForeignKey('conversations.id')` IS the contract enforcement for `conversation_id`. Unique to Phase 17 because `household_id` is a plain String (no FK target — household lives in the backend API, not the local DB).

### Pattern B: `.one()` for invariant lookups (NEW use site)

**Source:** `src/robotina/gateway/handler.py:55-72` uses `.filter_by(platform=…, chat_id=…).first()` for the upsert-tolerant gateway path.

**Apply to:** `jobs.py::run_task` `handle-incoming-message` branch (D-04).

**Why `.one()` not `.first()`:** Gateway commits the Conversation row BEFORE enqueuing (`handler.py:110` then `:125-132`), so by the time `run_task` runs the row IS guaranteed present. `.one()` (`sqlalchemy.exc.NoResultFound` on miss, `MultipleResultsFound` on duplicate) treats absence as an invariant violation, matching the contract. `.first()` would silently return `None` and break the downstream FK INSERT with an opaque NULL-violation rather than the explicit `NoResultFound`.

### Pattern C: Additive nullable JSON column for forward-compatibility slots

**Source:** `models.py:51` (`WorkflowRunStep.artifact: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)`) and `models.py:54` (Phase 13 `step_input`).

**Apply to:** `WorkflowRun.outcome` (D-06).

**Why nullable + no default + no constraint:** Phase 17 does NOT populate `outcome`; Phase 20 will. Nullable JSON with no server default = no migration risk, no Python-side construction friction (model __init__ accepts construction without the kwarg — verified by `WorkflowRunStep` precedent per RESEARCH Assumption A1).

### Pattern D: Lazy per-branch imports in `run_task`

**Source:** `jobs.py:135-137` and `:151-152` and `:158-159` (every branch lazy-imports its tool dependencies inside the `if task_type == …` block).

**Apply to:** The new Conversation lookup in the `handle-incoming-message` branch — add `from robotina.gateway.models import Conversation, Platform` inside the branch, NOT at module top. Matches the existing lazy-import discipline (avoids paying import cost for non-applicable task types).

---

## No Analog Found

None. Every Phase 17 change has a direct in-codebase analog:
- Phase 13 `0005_dashboard_columns.py` is the migration template.
- Phase 13 `WorkflowRunStep` additive columns are the ORM template.
- Phase 16 `household_id` plumbing across `task_types.py` / `workflow_runner.py` / `start_workflow.py` is the four-layer topology template (Phase 17 applies layers 2, 3, 5; skips 1, 4).
- Phase 13 `test_migration_0005_upgrades_and_downgrades` is the integration migration test template.
- Phase 16 `test_constructor_requires_household_id_no_default` family is the unit-test template.
- `gateway/handler.py:55-72` is the `.filter_by` Conversation lookup template (Phase 17 swaps `.first()` → `.one()`).

The REQUIREMENTS.md wording edit is the only non-code-pattern action; it is a one-line documentation change with no analog needed.

---

## Metadata

**Analog search scope:**
- `migrations/versions/` (5 files: `0001`–`0005`)
- `src/robotina/queue/{models,workflow_runner,jobs,task_types}.py`
- `src/robotina/agent/tools/start_workflow.py`
- `src/robotina/gateway/{models,handler}.py`
- `tests/test_workflow_runner.py`, `tests/unit/test_start_workflow_tool.py`

**Files scanned:** ~12 (all named in CONTEXT canonical_refs and RESEARCH primary sources)

**Pattern extraction date:** 2026-05-18

**Phase:** 17 — Conversation FK closure
