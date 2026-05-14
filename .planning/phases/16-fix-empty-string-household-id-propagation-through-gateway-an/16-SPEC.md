# Phase 16: Fix empty-string household_id propagation through gateway and workflow_run — Specification

**Created:** 2026-05-14
**Ambiguity score:** 0.11 (gate: ≤ 0.20)
**Requirements:** 3 locked

## Goal

The gateway must refuse to start when `HOUSEHOLD_ID` is unset or empty, eliminating the silent default that today writes `household_id=""` into `Conversation` and `WorkflowRun` rows.

## Background

Recent runs revealed that `WorkflowRun.household_id` is being persisted as an empty string. Investigation identified the cause:

- `src/robotina/gateway/handler.py:43` reads `household_id = os.environ.get("HOUSEHOLD_ID", "")` — silently defaults to `""` when the env var is missing or empty.
- The empty value flows into `Conversation.household_id` (handler.py:56), `IncomingMessageInput.household_id` (handler.py:112), is then injected into `StartWorkflowTool(household_id="")` from `queue/jobs.py:148`, and ultimately persisted on `WorkflowRun.household_id` via `workflow_runner.queue_workflow` (workflow_runner.py:139).
- Both `Conversation.household_id` and `WorkflowRun.household_id` are declared `nullable=False`, but the NOT NULL constraint does not block empty strings — the corruption is invisible at the DB layer.
- `.env.example` does not list `HOUSEHOLD_ID`, so a fresh checkout / fresh deployment is silently broken by default. (This violates the project's standing rule that every env var be reflected in `.env.example`.)
- The original Phase 3 plan (`03-02-PLAN.md:192`) explicitly described the empty-string default as intentional; this phase reverses that decision.
- A separate backlog item, Phase 999.1 ("Custom state schemas for reply_context and household_id"), proposes a forward-looking refactor of how household context is threaded through LangGraph state. It is **not** the same fix and is out of scope here.

## Requirements

1. **Boot-time guard in gateway**: The gateway process must validate `HOUSEHOLD_ID` is set and non-empty before accepting any messages.
   - Current: `src/robotina/gateway/handler.py:43` reads the env var per-message with `os.environ.get("HOUSEHOLD_ID", "")` and silently substitutes `""` when missing.
   - Target: The gateway entrypoint reads `HOUSEHOLD_ID` once at startup; if it is unset or empty (after `.strip()`), the process logs a clear error to stderr and exits with a non-zero exit code before binding to the Telegram polling/webhook loop.
   - Acceptance: Starting the gateway with `HOUSEHOLD_ID` unset (or set to `""` / whitespace) causes the process to exit non-zero with a stderr message naming the missing variable; starting it with a non-empty value boots normally and the per-message handler reads the validated value (no `os.environ.get(..., "")` fallback in the message path).

2. **`.env.example` documents `HOUSEHOLD_ID`**: The variable must be discoverable from a fresh checkout.
   - Current: `.env.example` contains no `HOUSEHOLD_ID` entry; the variable's existence is only visible by reading `handler.py`.
   - Target: `.env.example` lists `HOUSEHOLD_ID=` with an inline comment marking it as required for the gateway and noting the gateway will refuse to start if it is empty.
   - Acceptance: `grep -E "^HOUSEHOLD_ID" .env.example` returns the variable; the surrounding comment identifies it as required.

3. **End-to-end behavior preserved on the happy path**: A real message round-trip must produce a `WorkflowRun` row with the correct, non-empty `household_id`.
   - Current: With `HOUSEHOLD_ID` unset, sending a message that triggers a workflow produces a `WorkflowRun` row with `household_id=""`.
   - Target: With `HOUSEHOLD_ID=hh-xyz` exported, sending a message that triggers a workflow produces a `WorkflowRun` row with `household_id='hh-xyz'`; the Conversation row created for the chat also carries `household_id='hh-xyz'`.
   - Acceptance: Manual smoke test in the local dev setup — send a Telegram message that triggers `start-workflow`, then query Postgres and confirm the new `Conversation` and `WorkflowRun` rows have `household_id` equal to the env-var value, not `""`.

## Boundaries

**In scope:**
- Boot-time validation of `HOUSEHOLD_ID` in the gateway entrypoint (fail-fast, non-zero exit, stderr message)
- Removal of the silent `""` default in `gateway/handler.py:43` (handler can rely on the boot-time guarantee)
- Adding `HOUSEHOLD_ID` to `.env.example` with a "required" comment
- Manual end-to-end smoke verification documented in the plan

**Out of scope:**
- Backfilling existing `Conversation` / `WorkflowRun` rows that already have `household_id=""` — historical rows are accepted as legacy data; no Alembic data migration in this phase.
- Adding a Postgres `CHECK (household_id <> '')` constraint on `Conversation` or `WorkflowRun` — explicitly excluded to keep the change minimal and avoid migration complexity around existing empty rows.
- Per-message re-validation of `HOUSEHOLD_ID` — the boot-time guard is the single enforcement point; runtime mutation of the env var is not a supported scenario.
- Refactoring how `household_id` is threaded through agent / LangGraph state — that is the Phase 999.1 backlog item and remains separate.
- Changes to the `HOUSEHOLD_MANAGER_*` env vars (different concern, already present in `.env.example`).

## Constraints

- The boot-time guard must run before the Telegram polling/webhook loop is started; it must not require a Telegram message to be received before failing.
- The error message on missing `HOUSEHOLD_ID` must name the variable explicitly (so a fresh-checkout developer can resolve the failure without reading source).
- No Alembic migration is created in this phase (per scope decision above).
- The fix must work in both the host-`uv run` dev setup and the docker-compose'd staging setup (env-var pickup is the same in both, but smoke testing should respect the local dev path).

## Acceptance Criteria

- [ ] Gateway process exits with a non-zero status code when started with `HOUSEHOLD_ID` unset
- [ ] Gateway process exits with a non-zero status code when started with `HOUSEHOLD_ID=""` or whitespace-only
- [ ] Stderr message on failure names `HOUSEHOLD_ID` explicitly
- [ ] Gateway boots normally when `HOUSEHOLD_ID` is a non-empty string
- [ ] `gateway/handler.py` no longer contains `os.environ.get("HOUSEHOLD_ID", "")` in the per-message path
- [ ] `.env.example` contains a `HOUSEHOLD_ID=` line with a "required" comment
- [ ] Smoke test: with `HOUSEHOLD_ID` exported, a real Telegram message that triggers a workflow produces `Conversation` and `WorkflowRun` rows whose `household_id` matches the env-var value (verified via direct SQL query)

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                              |
|--------------------|-------|------|--------|----------------------------------------------------|
| Goal Clarity       | 0.92  | 0.75 | ✓      | Specific remediation surface: boot guard + env doc |
| Boundary Clarity   | 0.92  | 0.70 | ✓      | No backfill, no DB CHECK, no per-message re-check  |
| Constraint Clarity | 0.85  | 0.65 | ✓      | Boot-time enforcement; no migration                |
| Acceptance Criteria| 0.85  | 0.70 | ✓      | 7 pass/fail criteria including smoke test          |
| **Ambiguity**      | 0.11  | ≤0.20| ✓      |                                                    |

## Interview Log

| Round | Perspective                  | Question summary                                   | Decision locked                                                                 |
|-------|------------------------------|----------------------------------------------------|---------------------------------------------------------------------------------|
| 1     | Boundary Keeper              | Where should the fail-fast guard live?             | Gateway boot-time only — not per-message                                        |
| 1     | Boundary Keeper              | Should existing empty-string rows be backfilled?   | No — historical rows left alone                                                 |
| 1     | Boundary Keeper              | Add a Postgres CHECK constraint?                   | Initially yes, then reversed in round 2                                         |
| 2     | Failure Analyst / Simplifier | How should the CHECK migration handle bad rows?    | No CHECK constraint at all — avoid Alembic complexity (user changed mind)        |
| 2     | Seed Closer                  | What proves the fix worked?                        | Boot-time exit + .env.example entry + manual end-to-end smoke test              |

---

*Phase: 16-fix-empty-string-household-id-propagation-through-gateway-an*
*Spec created: 2026-05-14*
*Next step: /gsd-discuss-phase 16 — implementation decisions (where exactly the boot guard lives in the gateway entrypoint, error message wording, smoke-test runbook details)*
