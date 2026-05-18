# Phase 17: Conversation FK closure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-18
**Phase:** 17-conversation-fk-closure
**Areas discussed:** Orphan-row handling, Migration structure, conversation_id plumbing, Deploy procedure, outcome column shape

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Orphan-row handling | When historical reply_context can't resolve to a Conversation | ✓ |
| Migration file structure | Three revisions vs one revision vs schema+script | (locked by Claude after user input — see "Claude's Discretion" below) |
| conversation_id plumbing | How conversation_id reaches queue_workflow | ✓ |
| In-flight workflow safety at deploy | Pre-deploy gate / advisory / tolerate | ✓ |

---

## Orphan-row handling

| Option | Description | Selected |
|--------|-------------|----------|
| Leave NULL + tolerate | Skip orphans, gate step 3 on COUNT(NULL)=0 | |
| Create synthetic Conversation | Insert placeholder rows for unresolvable | |
| Hard-fail the backfill | Raise on any orphan | |
| You decide | Pick based on codebase conventions | |

**User's choice (free-text):** "I'll clean up the database before the migration. No need for a backfill."

**Notes:** User collapsed the entire orphan-handling problem by committing to pre-clean the production DB before running the migration. This is operationally cheap at household scale (single family, weeks of v1.0 data) and structurally eliminates the need for defensive backfill logic.

---

## Backfill behavior under runtime miss (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Fail loudly | Plain UPDATE; step 3 fails on any remaining NULL | |
| Pre-flight assert | Step 2 raises on unresolvable rows | |
| You decide | | |

**User's choice (free-text):** "why do we need a backfill if the DB will be completely clean? we should be able to grab a clean DB, run migrations, run agent... no need for a backfill... or am I missing something?"

**Notes:** User correctly identified that pre-cleaning makes the entire backfill step a no-op. Claude confirmed the three-step pattern was designed for production-data backfill (ARCH §2.1, PITFALLS #3) and pivoted to migration-structure question below.

---

## Migration structure (replaced original gray area after user input)

| Option | Description | Selected |
|--------|-------------|----------|
| One migration, NOT NULL upfront | Single revision: ADD COLUMN ... NOT NULL on empty table | ✓ |
| Two migrations (nullable now, NOT NULL after soak) | Two revisions; safer if pre-clean is skipped | |
| Keep three-step ceremony | Honor ROADMAP literally with no-op backfill | |

**User's choice:** One migration, NOT NULL upfront

**Notes:** ROADMAP success-criterion #2 mentions "three-step Alembic sequence". With pre-cleaning, the criterion is trivially satisfied (no rows → no orphans). Captured as D-01 with the note that ARCH-01 wording in REQUIREMENTS.md needs a one-line edit during planning to match the implementation.

---

## conversation_id plumbing — where StartWorkflowTool gets it from

| Option | Description | Selected |
|--------|-------------|----------|
| Constructor-injected like household_id | run_task resolves once; passes via Tool(__init__) | ✓ |
| Tool resolves it itself | _run runs the SELECT each call | |
| Read from shared_context only | queue_workflow inspects shared_context | |

**User's choice:** Constructor-injected like household_id

**Notes:** Mirrors the established Phase 16 pattern. Captured as D-03.

---

## conversation_id plumbing — queue_workflow signature

| Option | Description | Selected |
|--------|-------------|----------|
| Required arg | queue_workflow(..., conversation_id, ...) required | ✓ |
| Optional arg, default NULL | conversation_id=None with warning log | |
| Read it from shared_context if absent | Inspect reply_context as fallback | |

**User's choice:** Required arg

**Notes:** Forces the contract at the function boundary. Captured as D-05.

---

## conversation_id plumbing — where the lookup happens

| Option | Description | Selected |
|--------|-------------|----------|
| Lookup in run_task tool-construction; raise on miss | session.query(Conversation)...one() in jobs.py | ✓ |
| Lookup in StartWorkflowTool._run | Tool keeps chat_id/platform; SELECT inside _run | |
| Pass conversation_id through IncomingMessageInput | Gateway propagates conv.id end-to-end | |

**User's choice:** Lookup in run_task tool-construction block; raise on miss

**Notes:** Deduping with Phase 18's RobotinaInvocation lookup site. Gateway always upserts a Conversation before enqueue, so .one() raising means an invariant violation worth failing loud on. Captured as D-04.

---

## Deploy procedure

| Option | Description | Selected |
|--------|-------------|----------|
| Stop worker → truncate → migrate → start worker | Documented runbook in CONTEXT.md | ✓ |
| Add a sanity check in the migration | upgrade() raises on non-empty workflow_runs | |
| No documented procedure | Trust the operator | |

**User's choice:** Stop worker → truncate → migrate → start worker

**Notes:** Captured as D-08. The runbook lives in CONTEXT.md and should appear in PLAN.md plus the final commit message. No code-side gate — Alembic's natural failure on the NOT NULL constraint is sufficient signal.

---

## outcome column shape

| Option | Description | Selected |
|--------|-------------|----------|
| Plain JSON nullable, no constraint | Mapped[Optional[dict]] with no Pydantic stub | |
| Define WorkflowOutcome stub Pydantic model now | Add placeholder in task_types.py | ✓ |
| You decide | Match existing patterns | |

**User's choice:** Define WorkflowOutcome stub Pydantic model now

**Notes:** Gives Phase 20 a code anchor — "fill in the shape" instead of "introduce a new concept". Captured as D-07.

---

## Claude's Discretion

- **Migration file structure** — user did not pick from the gray-areas multi-select. Claude locked it as "three separate Alembic revisions" mid-discussion, then the discussion of orphan-handling collapsed that to **one revision** (per D-01). Final shape: one Alembic revision (`0006`).
- **`NonEmptyConversationId` Pydantic alias** — Claude recommends skipping (FK constraint suffices; `conversation_id` is not LLM-supplied). Planner may revisit.
- **Test layout** — Wave 0 RED stubs + implementation flips per Phase 2 style. Planner finalizes wave boundaries.

---

## Deferred Ideas

- Phase 18: `triggered_by_invocation_id` FK + RobotinaInvocation entity + dashboard surfacing.
- Phase 20: real `AddRecipeOutcome` shape + `finalize-outcome` deterministic step + dashboard outcome rendering.
- Post-v1.1: dropping `chat_id` / `user_id` / `platform` from `StartWorkflowTool`; renaming `shared_context` → `input`; removing `shared_context.reply_context` writes entirely (ARCH-05 deprecation close).
- A CI guard that fails the build if any `queue_workflow` caller passes `conversation_id=None` — overkill at this scale.
