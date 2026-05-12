# Phase 3: Gateway - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

The Telegram bot is the live front door — it receives user messages via polling, persists them with deduplication, fetches conversation history, enqueues `handle-incoming-message` tasks at the front of the queue, and exposes a `send_message()` function for outgoing messages. No agent logic, no workflow engine, no scheduler. Models (`Conversation`, `StoredMessage`) already exist from Phase 2.

</domain>

<decisions>
## Implementation Decisions

### Bot Mode
- **D-01:** Use PTB `run_polling()` mode — no webhook server needed for Phase 1. Polling is started via the gateway `main()` entry point. Production webhook mode is deferred.
- **D-02:** `python-telegram-bot>=21` is the library (CLAUDE.md mandate). Use `ApplicationBuilder` + async handler pattern (v21 async-native).

### Process Entrypoints
- **D-03:** Add `gateway = "robotina.gateway:main"` to `[project.scripts]` in `pyproject.toml`. Developers run `uv run gateway` to start the bot.
- **D-04:** Add `all = "robotina.all:main"` (or similar) to `[project.scripts]`. The `uv run all` script launches both `uv run agent` and `uv run gateway` as concurrent subprocesses — one command starts the full stack. Implementation (subprocess management, keyboard interrupt handling) is Claude's discretion.

### Incoming Message Handling
- **D-05:** On receiving a message: (1) upsert `Conversation` for `(platform, chat_id)` — get-or-create using the unique constraint; (2) attempt `StoredMessage` insert; if `platform_message_id` already exists (duplicate), skip silently; (3) fetch last N `StoredMessage` rows for the conversation ordered oldest→newest as history; (4) enqueue `handle-incoming-message` at front of queue (`at_front=True`).
- **D-06:** History window size N is read from env var `CONVERSATION_HISTORY_WINDOW`, default value is Claude's discretion (10 is reasonable). Applied as `LIMIT N` on `StoredMessage` ordered by `sent_at DESC`, then reversed for oldest→newest order.
- **D-07:** `household_id` is read from env var `HOUSEHOLD_ID` and populated into `IncomingMessageInput` and `Conversation` by the gateway.

### Outgoing Messages
- **D-08:** Implement `send_message(chat_id: str, text: str, user_id: str) -> str` async function in `robotina/gateway/` (exact file is Claude's discretion — e.g. `robotina/gateway/send.py` or in the main module). Persists a `StoredMessage` with `role=ASSISTANT` and returns the platform-assigned `message_id`. Phase 6's `send-notification` tool calls this function directly.
- **D-09:** The `platform_message_id` for outgoing messages is the Telegram `message_id` returned by `bot.send_message()`.

### Error Handling
- **D-10:** Polling mode — no HTTP 200 concern. Raise exceptions from the handler on DB failure. PTB's polling loop handles retries and error logging. No special error wrapping needed for Phase 1.

### Claude's Discretion
- Default value for `CONVERSATION_HISTORY_WINDOW` (suggest 10)
- `uv run all` subprocess management implementation (Popen, KeyboardInterrupt cleanup)
- File structure within `robotina/gateway/` — e.g. whether `send_message` lives in a separate `send.py` or in the main handler file
- SQLAlchemy session lifecycle in async context — use `sessionmaker` or `with Session(engine) as session` pattern consistent with Phase 1/2 patterns in `db.py`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Gateway spec
- `plans/01-kickoff/spec.md` §"Gateway" — gateway message flow, storage models, outgoing message behavior
- `plans/01-kickoff/spec.md` §"Queue" — `at_front` parameter, `IncomingMessageInput` field definitions

### Requirements
- `.planning/REQUIREMENTS.md` §GW-01 through GW-06 — acceptance criteria for all gateway requirements

### Prior context (locked decisions)
- `.planning/phases/01-developer-tooling-and-infrastructure/01-CONTEXT.md` — D-01 (package layout), D-02 (pyproject.toml script pattern), D-03 (queue name `agent-tasks`)
- `.planning/phases/02-database-models-and-queue-layer/02-CONTEXT.md` — D-01 (gateway/models.py location), D-06 (task_types.py location), D-04 (LoggingWorker)

### Existing models
- `src/robotina/gateway/models.py` — `Conversation`, `StoredMessage`, `Platform`, `MessageRole` — already implemented, do not modify
- `src/robotina/queue/task_types.py` — `IncomingMessageInput`, `Message` — already implemented, do not modify

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/robotina/gateway/models.py` — `Conversation` and `StoredMessage` with correct unique constraints (`(platform, chat_id)` on Conversation, `platform_message_id` unique on StoredMessage). Fully implemented.
- `src/robotina/queue/task_types.py` — `IncomingMessageInput` with `history: list[Message]` already defined. `Message` model has `message_id`, `role`, `text`, `sent_at`.
- `src/robotina/db.py` — shared `Base` and database engine; session factory needs to be added here or consumed from here.
- `src/robotina/queue/runner.py` — example of how a `uv run agent` entrypoint is structured (reads env vars, starts worker). Gateway `main()` follows the same pattern.

### Established Patterns
- Queue name: `agent-tasks` (locked from Phase 1)
- All RQ jobs: `result_ttl=-1`, `failure_ttl=-1` (locked from Phase 1)
- `uv run` shortcuts: defined in `[project.scripts]` in `pyproject.toml` — gateway and all entries follow this pattern
- SQLAlchemy 2.x `Mapped` + `mapped_column` style — no 1.x Column style
- Pydantic v2 syntax throughout — `IncomingMessageInput` already in `task_types.py`

### Integration Points
- Gateway enqueues to `agent-tasks` queue using `rq.Queue("agent-tasks", connection=redis_conn).enqueue(handle_incoming_message, input, at_front=True)`
- `IncomingMessageInput` is the exact type passed to the `handle-incoming-message` job — import from `robotina.queue.task_types`
- `send_message()` will be called by Phase 6's `send-notification` tool — keep its signature stable
- `alembic/versions/` — no new migration needed (models were migrated in Phase 2); verify existing migration covers all gateway model fields

</code_context>

<specifics>
## Specific Ideas

- `uv run all` should start both `uv run agent` and `uv run gateway` as concurrent child processes and handle `KeyboardInterrupt` cleanly (terminate both on Ctrl+C)

</specifics>

<deferred>
## Deferred Ideas

- **Webhook mode (production)**: GW-01 says "via webhook" — this is the intended production mode. Polling is used for Phase 1 development simplicity. Webhook implementation (FastAPI route + PTB webhook mode + HTTPS URL) should be added before production deployment.
- **HTTP 200 always (GW-03)**: This requirement applied to the webhook flow. In polling mode it's N/A. Will need revisiting if webhook mode is added.

</deferred>

---

*Phase: 03-gateway*
*Context gathered: 2026-03-25*
