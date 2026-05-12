# Phase 3: Gateway - Research

**Researched:** 2026-03-25
**Domain:** python-telegram-bot v21+, async message handling, SQLAlchemy session lifecycle, RQ enqueueing, subprocess process management
**Confidence:** HIGH (all key claims verified against installed packages in project venv)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Use PTB `run_polling()` mode — no webhook server needed for Phase 1. Polling is started via the gateway `main()` entry point. Production webhook mode is deferred.
- **D-02:** `python-telegram-bot>=21` is the library (CLAUDE.md mandate). Use `ApplicationBuilder` + async handler pattern (v21 async-native).
- **D-03:** Add `gateway = "robotina.gateway:main"` to `[project.scripts]` in `pyproject.toml`. Developers run `uv run gateway` to start the bot.
- **D-04:** Add `all = "robotina.all:main"` (or similar) to `[project.scripts]`. The `uv run all` script launches both `uv run agent` and `uv run gateway` as concurrent subprocesses.
- **D-05:** On receiving a message: (1) upsert `Conversation` for `(platform, chat_id)`; (2) attempt `StoredMessage` insert; if `platform_message_id` already exists (duplicate), skip silently; (3) fetch last N `StoredMessage` rows for the conversation ordered oldest→newest as history; (4) enqueue `handle-incoming-message` at front of queue (`at_front=True`).
- **D-06:** History window size N read from env var `CONVERSATION_HISTORY_WINDOW`, default value is Claude's discretion (10 is reasonable).
- **D-07:** `household_id` read from env var `HOUSEHOLD_ID` and populated into `IncomingMessageInput` and `Conversation` by the gateway.
- **D-08:** Implement `send_message(chat_id: str, text: str, user_id: str) -> str` async function. Persists a `StoredMessage` with `role=ASSISTANT` and returns the platform-assigned `message_id`.
- **D-09:** The `platform_message_id` for outgoing messages is the Telegram `message_id` returned by `bot.send_message()`.
- **D-10:** Polling mode — no HTTP 200 concern. Raise exceptions from the handler on DB failure. PTB's polling loop handles retries and error logging.

### Claude's Discretion

- Default value for `CONVERSATION_HISTORY_WINDOW` (suggest 10)
- `uv run all` subprocess management implementation (Popen, KeyboardInterrupt cleanup)
- File structure within `robotina/gateway/` — e.g. whether `send_message` lives in a separate `send.py` or in the main handler file
- SQLAlchemy session lifecycle in async context — use `sessionmaker` or `with Session(engine) as session` pattern consistent with Phase 1/2 patterns in `db.py`

### Deferred Ideas (OUT OF SCOPE)

- **Webhook mode (production):** GW-01 says "via webhook" — this is the intended production mode. Polling is used for Phase 1 development simplicity. Webhook implementation should be added before production deployment.
- **HTTP 200 always (GW-03):** This requirement applied to the webhook flow. In polling mode it's N/A.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GW-01 | Telegram bot receives user messages via webhook and persists them to Postgres (`StoredMessage`) | PTB `run_polling()` mode confirmed working; `ApplicationBuilder` + `MessageHandler(filters.TEXT, callback)` pattern; `StoredMessage` model already exists |
| GW-02 | Gateway deduplicates incoming messages using `platform_message_id` unique constraint | `StoredMessage.platform_message_id` has `unique=True`; catch `sqlalchemy.exc.IntegrityError` on insert, skip silently |
| GW-03 | Gateway fetches the last N conversation messages (N configurable via env var) and attaches them as history | SQLAlchemy query with `order_by(StoredMessage.sent_at.desc()).limit(N)` then reverse; `SessionLocal` from `robotina.db` |
| GW-04 | Gateway enqueues a `handle-incoming-message` task at the front of the queue (urgent priority) | `Queue.enqueue(func, input, at_front=True, result_ttl=-1, failure_ttl=-1)` confirmed via `Queue.enqueue_call` signature |
| GW-05 | Gateway sends outgoing Telegram messages and persists them to Postgres | `Bot.send_message()` is async (confirmed); returns `Message` object; `message.message_id` is `int`, cast to `str` for `platform_message_id` |
| GW-06 | A `Conversation` record groups all messages for a `(platform, chat_id)` pair with a `@@unique` constraint | `Conversation` model already has `UniqueConstraint("platform", "chat_id")`; use get-or-create with IntegrityError catch |

</phase_requirements>

---

## Summary

Phase 3 implements the Telegram bot gateway that sits between Telegram users and the RQ task queue. The installed version is **python-telegram-bot 22.7** (above the `>=21` minimum), confirmed in the project venv. All key API surfaces — `ApplicationBuilder`, `Application.run_polling()`, `MessageHandler`, `Bot.send_message()` — are present and behave as expected.

The core flow is well-understood: PTB's `run_polling()` is a synchronous blocking call that manages its own event loop internally (it is NOT a coroutine). Message handler callbacks ARE async coroutines. The handler receives `Update` and `ContextTypes.DEFAULT_TYPE`; from the update, `update.message.message_id` (int), `update.message.chat_id` (int), `update.effective_user.id` (int), and `update.message.date` (datetime) are all directly accessible.

Database operations use the existing `SessionLocal` sessionmaker from `robotina.db`. Deduplication is handled by catching `sqlalchemy.exc.IntegrityError` on `StoredMessage` insert (unique constraint on `platform_message_id`). For `Conversation` upsert, the same IntegrityError catch pattern works for get-or-create. The `send_message()` function must be a standalone async function (not bound to the PTB handler context) so it can be called from Phase 6's send-notification tool.

The `uv run all` entrypoint uses `subprocess.Popen` to launch two child processes (`uv run agent` and `uv run gateway`), waits for a `KeyboardInterrupt`, then terminates both cleanly.

**Primary recommendation:** Build the gateway as `src/robotina/gateway/handler.py` (incoming message logic) + `src/robotina/gateway/send.py` (outgoing `send_message` function) + `src/robotina/gateway/__init__.py` (exports `main()`). The `uv run all` entrypoint lives in `src/robotina/all.py`.

---

## Standard Stack

### Core (all already in pyproject.toml)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-telegram-bot | 22.7 (installed); `>=21` required | Telegram Bot API wrapper; polling, handlers, bot.send_message | CLAUDE.md mandate; v21+ is async-native with ApplicationBuilder pattern |
| SQLAlchemy | `>=2.0` | ORM sessions for Conversation + StoredMessage; SessionLocal | Already in project; 2.x Mapped syntax matches existing models |
| redis-py | `>=4.0` | Redis connection for RQ | Already in project |
| rq | `>=2.5` | Queue.enqueue with at_front=True | Already in project; at_front confirmed via enqueue_call signature |
| python-dotenv | installed | Load env vars (TELEGRAM_BOT_TOKEN, HOUSEHOLD_ID, etc.) | Already in dependencies |

### No New Dependencies Needed
All dependencies for this phase are already declared in `pyproject.toml`. No `uv add` required.

---

## Architecture Patterns

### Recommended Project Structure
```
src/robotina/
├── gateway/
│   ├── __init__.py        # exports main() — entry point for uv run gateway
│   ├── handler.py         # handle_message() async PTB handler; contains full incoming flow
│   └── send.py            # send_message(chat_id, text, user_id) -> str; used by Phase 6
├── all.py                 # main() for uv run all — launches agent + gateway subprocesses
└── db.py                  # existing; SessionLocal and engine already here
```

### Pattern 1: PTB Application Setup (run_polling mode)

**What:** Build the Application with token, register async handler, call `run_polling()`. `run_polling` is synchronous (manages its own asyncio event loop). Handlers must be `async def`.

**Example:**
```python
# Source: verified against python-telegram-bot 22.7 in project venv
import logging
import os
from telegram.ext import Application, ApplicationBuilder, MessageHandler, filters, ContextTypes
from telegram import Update

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # update.message.message_id  -> int
    # update.message.chat_id     -> int
    # update.effective_user.id   -> int
    # update.message.date        -> datetime (UTC)
    # update.message.text        -> str | None
    ...

def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()  # blocking; manages its own event loop
```

**Key fact:** `run_polling()` is NOT a coroutine — call it directly, not with `asyncio.run()`. Confirmed: `inspect.iscoroutinefunction(Application.run_polling)` returns `False`.

### Pattern 2: Conversation Upsert (get-or-create)

**What:** Attempt to find existing `Conversation` for `(platform, chat_id)`. If not found, insert. Catch `IntegrityError` on insert race to handle concurrent duplicate (unlikely in single-worker but correct).

```python
# Source: verified against SQLAlchemy 2.0 in project venv + existing models.py
from sqlalchemy.exc import IntegrityError
from robotina.db import SessionLocal
from robotina.gateway.models import Conversation, Platform

def get_or_create_conversation(chat_id: str, household_id: str) -> Conversation:
    with SessionLocal() as session:
        conv = session.query(Conversation).filter_by(
            platform=Platform.TELEGRAM,
            chat_id=chat_id
        ).first()
        if conv is None:
            conv = Conversation(
                platform=Platform.TELEGRAM,
                chat_id=chat_id,
                household_id=household_id,
            )
            try:
                session.add(conv)
                session.commit()
                session.refresh(conv)
            except IntegrityError:
                session.rollback()
                conv = session.query(Conversation).filter_by(
                    platform=Platform.TELEGRAM,
                    chat_id=chat_id
                ).first()
        return conv
```

**Note:** `SessionLocal` is a `sessionmaker` instance (confirmed). Use as context manager: `with SessionLocal() as session:` — this is the pattern consistent with `robotina.db`.

### Pattern 3: StoredMessage Insert with Deduplication

**What:** Insert `StoredMessage`. If `platform_message_id` already exists (unique constraint), catch `IntegrityError` and skip silently (D-05, GW-02).

```python
from sqlalchemy.exc import IntegrityError
from robotina.gateway.models import StoredMessage, MessageRole
from datetime import datetime

def persist_incoming_message(
    session,
    conversation_id: str,
    platform_message_id: str,
    text: str,
    sent_at: datetime,
) -> StoredMessage | None:
    """Returns persisted StoredMessage or None on duplicate."""
    msg = StoredMessage(
        conversation_id=conversation_id,
        platform_message_id=platform_message_id,
        role=MessageRole.USER,
        text=text,
        sent_at=sent_at,
    )
    try:
        session.add(msg)
        session.flush()  # raises IntegrityError before commit if duplicate
        return msg
    except IntegrityError:
        session.rollback()
        return None
```

**Key point:** `platform_message_id` for incoming Telegram messages is `str(update.message.message_id)`. The `message_id` field on `Message` is an `int` — cast to str for storage.

### Pattern 4: Fetch Conversation History

**What:** Fetch last N messages for the conversation, ordered oldest→newest for `IncomingMessageInput.history`.

```python
from robotina.gateway.models import StoredMessage
from robotina.queue.task_types import Message as HistoryMessage

def fetch_history(session, conversation_id: str, limit: int) -> list[HistoryMessage]:
    rows = (
        session.query(StoredMessage)
        .filter_by(conversation_id=conversation_id)
        .order_by(StoredMessage.sent_at.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()  # oldest → newest
    return [
        HistoryMessage(
            message_id=row.platform_message_id,
            role=row.role.value,      # "user" or "assistant"
            text=row.text,
            sent_at=row.sent_at,
        )
        for row in rows
    ]
```

### Pattern 5: RQ Enqueue at Front

**What:** Enqueue `handle-incoming-message` at the front of `agent-tasks` queue with `at_front=True` and infinite TTLs (locked requirement).

```python
# Source: verified Queue.enqueue_call signature includes at_front param
from rq import Queue
from redis import Redis

def enqueue_incoming(redis_conn: Redis, input_model) -> str:
    """Returns job ID."""
    from robotina.queue.jobs import handle_incoming_message  # Phase 4 target
    q = Queue("agent-tasks", connection=redis_conn)
    job = q.enqueue(
        handle_incoming_message,
        input_model,
        at_front=True,
        result_ttl=-1,
        failure_ttl=-1,
        meta={"task_type": "handle-incoming-message"},
    )
    return job.id
```

**Note:** `at_front=True` is passed as a kwarg to `Queue.enqueue()` which delegates to `enqueue_call()` — confirmed that `enqueue_call` has `at_front` parameter.

### Pattern 6: send_message Standalone Async Function

**What:** `send_message()` must be a standalone async function (not a handler method) so Phase 6's `send-notification` tool can call it directly by importing from `robotina.gateway.send`.

```python
# Source: verified Bot.send_message is a coroutine function in PTB 22.7
import os
from telegram import Bot
from robotina.db import SessionLocal
from robotina.gateway.models import StoredMessage, MessageRole, Platform, Conversation
from datetime import datetime, timezone

async def send_message(chat_id: str, text: str, user_id: str) -> str:
    """Send a Telegram message and persist it as ASSISTANT StoredMessage.

    Returns the platform-assigned message_id (str).
    Called by Phase 6's send-notification tool.
    """
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    bot = Bot(token=token)
    async with bot:
        sent = await bot.send_message(chat_id=int(chat_id), text=text)
    platform_message_id = str(sent.message_id)

    household_id = os.environ.get("HOUSEHOLD_ID", "")
    with SessionLocal() as session:
        conv = session.query(Conversation).filter_by(
            platform=Platform.TELEGRAM, chat_id=chat_id
        ).first()
        if conv:
            msg = StoredMessage(
                conversation_id=conv.id,
                platform_message_id=platform_message_id,
                role=MessageRole.ASSISTANT,
                text=text,
                sent_at=datetime.now(timezone.utc),
            )
            session.add(msg)
            session.commit()
    return platform_message_id
```

**Important:** `bot.send_message(chat_id=...)` takes `chat_id` as int or str — Telegram accepts both, but `update.message.chat_id` is int so cast accordingly. `Bot` used as async context manager (`async with bot:`) ensures HTTP client lifecycle is correct for standalone (non-Application) usage.

### Pattern 7: uv run all Subprocess Launcher

**What:** `src/robotina/all.py` launches `uv run agent` and `uv run gateway` as concurrent subprocesses via `subprocess.Popen`. Handles `KeyboardInterrupt` to terminate both cleanly.

```python
import subprocess
import sys
import time

def main() -> None:
    """Entry point for `uv run all`. Starts agent worker + gateway bot."""
    procs = [
        subprocess.Popen(["uv", "run", "agent"]),
        subprocess.Popen(["uv", "run", "gateway"]),
    ]
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait()
        sys.exit(0)
```

**Note:** `p.wait()` on the first process means if `agent` exits unexpectedly, `all` won't wait for `gateway`. A more robust approach iterates with polling, but for Phase 1 dev simplicity, this is sufficient.

### Anti-Patterns to Avoid

- **Using `asyncio.run(app.run_polling())`:** `run_polling` is NOT a coroutine. Call it directly. Wrapping in `asyncio.run()` will fail.
- **Creating Bot instance at module level:** PTB Bot objects hold HTTP client state. Instantiate per-call for standalone `send_message` usage, or use the Application's `.bot` attribute inside handlers.
- **Using `session.query()` from outside the `with` block:** SQLAlchemy sessions are not thread-safe and expire after `session.close()`. Always use within the `with SessionLocal() as session:` context.
- **Passing `at_front` inside `meta` dict:** `at_front` is a direct kwarg to `Queue.enqueue()`, not inside a `meta` dict.
- **Using `update.message.from_user.id` without null check:** If a message comes from a channel post, `from_user` may be None. Filter handlers to `filters.TEXT` and expect text messages only.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Telegram polling + retry | Custom HTTP polling loop | `Application.run_polling()` | PTB handles backoff, reconnection, update offsets, error logging |
| Message deduplication logic | Custom seen-message tracking | `StoredMessage.platform_message_id` unique constraint + `IntegrityError` catch | DB constraint is the correct dedup mechanism; already in place |
| Async event loop for gateway | `asyncio.run()` + manual loop | `Application.run_polling()` | Manages its own event loop; running two loops causes conflict |
| Subprocess lifecycle | Custom daemon/signal management | `subprocess.Popen` + `KeyboardInterrupt` catch | Standard Python; sufficient for dev mode |

---

## Common Pitfalls

### Pitfall 1: Async Handler in Sync Context

**What goes wrong:** Developer tries to call `async def handle_message` directly from sync code, or uses `asyncio.get_event_loop().run_until_complete()` inside the handler.

**Why it happens:** Confusion about which parts of PTB are async vs sync.

**How to avoid:** PTB's internals call handler coroutines via `await`. Write handlers as `async def` and let PTB manage execution. Never call `asyncio.run()` inside a handler.

**Warning signs:** `RuntimeError: This event loop is already running` at startup.

### Pitfall 2: Session Used Outside Context Manager

**What goes wrong:** Passing a `Session` object out of the `with SessionLocal() as session:` block and accessing attributes — triggers `DetachedInstanceError` or lazy-load after session close.

**Why it happens:** SQLAlchemy sessions expire object state on close by default (`expire_on_commit=True`).

**How to avoid:** Do all DB work (query, insert, commit, refresh, map to Pydantic/dataclass) inside a single `with SessionLocal() as session:` block. Return plain values or Pydantic models, not ORM objects.

**Warning signs:** `DetachedInstanceError: Instance <Conversation> is not bound to a Session`.

### Pitfall 3: Missing `TELEGRAM_BOT_TOKEN` or `HOUSEHOLD_ID` at Runtime

**What goes wrong:** `KeyError` on `os.environ["TELEGRAM_BOT_TOKEN"]` when starting the gateway.

**Why it happens:** These env vars are not set in `.env` or not injected by Docker Compose.

**How to avoid:** `main()` should validate env vars at startup (before entering polling loop) and exit with a clear error message. Add `TELEGRAM_BOT_TOKEN`, `HOUSEHOLD_ID`, `REDIS_URL`, `DATABASE_URL` to `.env.example`.

**Warning signs:** Stack trace immediately on `uv run gateway` rather than after first message.

### Pitfall 4: IntegrityError Leaves Session in Bad State

**What goes wrong:** After catching `IntegrityError`, further operations on the same session fail with `InvalidRequestError: This Session's transaction has been rolled back`.

**Why it happens:** An `IntegrityError` automatically rolls back the transaction; subsequent operations on the same session fail.

**How to avoid:** After catching `IntegrityError`, explicitly call `session.rollback()` before any further session operations (as shown in Pattern 2 and 3 above).

**Warning signs:** `sqlalchemy.exc.InvalidRequestError: This Session's transaction has been rolled back due to a previous exception during flush`.

### Pitfall 5: bot.send_message chat_id Type Mismatch

**What goes wrong:** Passing `chat_id` as string to `bot.send_message()` when Telegram requires int for user chats.

**Why it happens:** `Conversation.chat_id` is stored as `String` in DB but Telegram's `message.chat_id` is `int`.

**How to avoid:** Cast to int when calling `bot.send_message(chat_id=int(chat_id), ...)`. Store as str in DB for forward-compatibility with channel IDs (which can include `-100` prefix, e.g. `-1001234567890`).

### Pitfall 6: send_message Bot Context

**What goes wrong:** `Bot.send_message()` called outside `async with bot:` context raises `RuntimeError` about closed HTTP client.

**Why it happens:** PTB 22+ requires the Bot to be initialized (HTTP client started) before making API calls. For standalone usage (outside Application), use `async with bot:`.

**How to avoid:** Always wrap standalone Bot usage in `async with bot:` as shown in Pattern 6.

---

## Code Examples

### Full Incoming Message Handler Flow

```python
# Source: patterns verified against PTB 22.7 + SQLAlchemy 2.0 in project venv
import os
from datetime import datetime, timezone
from telegram.ext import ContextTypes
from telegram import Update
from sqlalchemy.exc import IntegrityError
from robotina.db import SessionLocal
from robotina.gateway.models import Conversation, StoredMessage, Platform, MessageRole
from robotina.queue.task_types import IncomingMessageInput, Message as HistoryMessage

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text:
        return

    platform_message_id = str(msg.message_id)
    chat_id = str(msg.chat_id)
    user_id = str(update.effective_user.id)
    household_id = os.environ.get("HOUSEHOLD_ID", "")
    history_limit = int(os.environ.get("CONVERSATION_HISTORY_WINDOW", "10"))

    with SessionLocal() as session:
        # 1. Upsert Conversation
        conv = session.query(Conversation).filter_by(
            platform=Platform.TELEGRAM, chat_id=chat_id
        ).first()
        if conv is None:
            conv = Conversation(
                platform=Platform.TELEGRAM,
                chat_id=chat_id,
                household_id=household_id,
            )
            try:
                session.add(conv)
                session.flush()
            except IntegrityError:
                session.rollback()
                conv = session.query(Conversation).filter_by(
                    platform=Platform.TELEGRAM, chat_id=chat_id
                ).first()

        # 2. Persist StoredMessage (dedup via unique constraint)
        stored = StoredMessage(
            conversation_id=conv.id,
            platform_message_id=platform_message_id,
            role=MessageRole.USER,
            text=msg.text,
            sent_at=msg.date.replace(tzinfo=timezone.utc) if msg.date.tzinfo is None else msg.date,
        )
        try:
            session.add(stored)
            session.flush()
        except IntegrityError:
            session.rollback()
            return  # duplicate — skip silently

        # 3. Fetch history
        rows = (
            session.query(StoredMessage)
            .filter_by(conversation_id=conv.id)
            .order_by(StoredMessage.sent_at.desc())
            .limit(history_limit)
            .all()
        )
        rows.reverse()
        history = [
            HistoryMessage(
                message_id=r.platform_message_id,
                role=r.role.value,
                text=r.text,
                sent_at=r.sent_at,
            )
            for r in rows
        ]

        session.commit()

    # 4. Enqueue at front
    from redis import Redis
    from rq import Queue
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    redis_conn = Redis.from_url(redis_url)
    q = Queue("agent-tasks", connection=redis_conn)

    task_input = IncomingMessageInput(
        message_id=platform_message_id,
        platform="telegram",
        received_at=datetime.now(timezone.utc),
        chat_id=chat_id,
        user_id=user_id,
        household_id=household_id,
        text=msg.text,
        history=history,
    )
    q.enqueue(
        "robotina.queue.jobs.handle_incoming_message",  # string ref until Phase 4 exists
        task_input,
        at_front=True,
        result_ttl=-1,
        failure_ttl=-1,
        meta={"task_type": "handle-incoming-message"},
    )
```

### Gateway main() Entry Point

```python
# Source: PTB ApplicationBuilder pattern verified in project venv
import logging
import os
from telegram.ext import ApplicationBuilder, MessageHandler, filters

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Updater` + `Dispatcher` (PTB v13) | `Application` + `ApplicationBuilder` (PTB v20+) | PTB v20 (2022) | Fully async-native; `Updater` class removed |
| `updater.start_polling()` + `updater.idle()` | `app.run_polling()` (single call) | PTB v20 | Simpler lifecycle management |
| `MessageHandler(Filters.text, ...)` | `MessageHandler(filters.TEXT, ...)` (lowercase module) | PTB v20 | Module renamed `filters` (lowercase) |

**Deprecated/outdated:**
- `Updater` class: removed in PTB v20. Do not use.
- `Dispatcher`: replaced by `Application`. Do not use.
- `Filters` (uppercase): renamed to `filters` (lowercase module). `filters.TEXT`, `filters.COMMAND` are the current names.

---

## Open Questions

1. **Job function reference in Phase 3**
   - What we know: `handle-incoming-message` job function will live in Phase 4's `robotina.queue.jobs` (or similar)
   - What's unclear: The function does not exist yet. Gateway must enqueue a reference to it.
   - Recommendation: Use string function reference in `Queue.enqueue()` (e.g. `"robotina.queue.jobs.handle_incoming_message"`) — RQ supports string references and will resolve at execution time. Alternatively, define a placeholder `handle_incoming_message` stub in Phase 3 and replace in Phase 4.

2. **Redis connection lifecycle in async handler**
   - What we know: PTB handler is async; `redis.Redis` is sync by default; creating a new Redis connection per message is valid but suboptimal
   - What's unclear: Whether to use a module-level Redis connection (created at `main()` time) or per-message
   - Recommendation: Create `redis_conn` once in `main()` and pass via closure or store in `Application.bot_data`. This avoids repeated connection overhead.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python-telegram-bot | GW-01, GW-05 | ✓ | 22.7 | — |
| SQLAlchemy | GW-01, GW-02, GW-03, GW-06 | ✓ | in venv | — |
| redis-py | GW-04 | ✓ | in venv | — |
| rq | GW-04 | ✓ | >=2.5 in venv | — |
| Postgres (live) | Integration tests | ✓ | 15 (Docker) | — |
| Redis (live) | Integration tests | ✓ | 7 (Docker) | — |
| TELEGRAM_BOT_TOKEN | GW-01 (runtime) | Not checked | — | Cannot test live polling without it; unit tests mock PTB |

**Missing dependencies with no fallback:**
- `TELEGRAM_BOT_TOKEN` env var — required at runtime; unit tests that mock PTB do not need it; integration smoke test needs a real token or a test bot.

**Missing dependencies with fallback:**
- None.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio 0.x |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `asyncio_mode = "auto"`) |
| Quick run command | `uv run pytest tests/test_gateway.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GW-01 | Message persisted as `StoredMessage(role=USER)` | integration | `uv run pytest tests/test_gateway.py::test_incoming_message_persisted -x` | ❌ Wave 0 |
| GW-02 | Duplicate `platform_message_id` skips silently; no second StoredMessage row | integration | `uv run pytest tests/test_gateway.py::test_deduplication -x` | ❌ Wave 0 |
| GW-03 | History list contains last N messages ordered oldest→newest | integration | `uv run pytest tests/test_gateway.py::test_history_window -x` | ❌ Wave 0 |
| GW-04 | `handle-incoming-message` job enqueued at front of `agent-tasks` queue | integration | `uv run pytest tests/test_gateway.py::test_enqueue_at_front -x` | ❌ Wave 0 |
| GW-05 | `send_message()` returns platform_message_id str; persists ASSISTANT StoredMessage | unit (mock Bot) | `uv run pytest tests/test_gateway.py::test_send_message -x` | ❌ Wave 0 |
| GW-06 | Second message from same chat reuses existing Conversation row | integration | `uv run pytest tests/test_gateway.py::test_conversation_upsert -x` | ❌ Wave 0 |

**Note on GW-01:** Full end-to-end polling test requires `TELEGRAM_BOT_TOKEN`. The integration tests should test the handler function directly (by calling `handle_message(update, context)` with a mock `Update`) rather than spinning up the polling loop.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_gateway.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_gateway.py` — covers GW-01 through GW-06; requires live Postgres + Redis; mark with `@pytest.mark.integration`
- [ ] `tests/conftest.py` — shared fixtures: clean-state Postgres session per test, mock `Update` factory

*(No new framework install needed — pytest + pytest-asyncio already in `[project.optional-dependencies] dev`.)*

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 3 |
|-----------|-------------------|
| **Tech Stack: Python, LangChain, Postgres (SQLAlchemy + Alembic), Redis + RQ, uv — no deviations** | No new libraries; all stack choices are already in pyproject.toml |
| **Concurrency: task runner processes jobs sequentially (concurrency = 1)** | Gateway enqueues but does NOT run jobs; worker is separate process |
| **Redis persistence: AOF with appendfsync always** | No change needed; Redis config set in Phase 1 |
| **result_ttl=-1 and failure_ttl=-1 on all RQ jobs** | Must be set on every `Queue.enqueue()` call in gateway |
| **python-telegram-bot>=21** | Installed version is 22.7; confirmed compatible |
| **LLM: Full connection details required per task type** | Not applicable to gateway phase |
| **LangWatch instrumentation active** | Not applicable to gateway phase; Phase 4 concern |
| **`uv run` shortcuts defined in pyproject.toml scripts** | `gateway` and `all` entries must be added to `[project.scripts]` |

---

## Sources

### Primary (HIGH confidence)
- python-telegram-bot 22.7 — installed in project venv; `ApplicationBuilder`, `Application.run_polling`, `MessageHandler`, `Bot.send_message`, `filters.TEXT`, `ContextTypes.DEFAULT_TYPE`, `Update.message.*` all verified via `uv run python -c "..."` inspection
- SQLAlchemy 2.x — installed in project venv; `SessionLocal` (sessionmaker), `IntegrityError` from `sqlalchemy.exc`, session context manager pattern verified
- RQ — `Queue.enqueue_call` signature including `at_front` parameter verified via `inspect.signature`
- `src/robotina/gateway/models.py` — `Conversation`, `StoredMessage`, `Platform`, `MessageRole` — confirmed field names, types, constraints
- `src/robotina/queue/task_types.py` — `IncomingMessageInput`, `Message` — confirmed field names and types
- `src/robotina/db.py` — `SessionLocal`, `engine` — confirmed pattern for session usage
- `src/robotina/queue/runner.py` — `main()` entry point pattern for `uv run` scripts

### Secondary (MEDIUM confidence)
- `plans/01-kickoff/spec.md` §Gateway, §Queue — authoritative specification for gateway message flow, deduplication behavior, `IncomingMessageInput` shape

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages in installed venv, API verified
- Architecture: HIGH — PTB handler pattern, SQLAlchemy session lifecycle, RQ enqueue all verified directly
- Pitfalls: HIGH — IntegrityError/session rollback, Bot context manager, run_polling sync behavior all verified

**Research date:** 2026-03-25
**Valid until:** 2026-06-25 (stable libraries; PTB minor version bumps unlikely to break patterns within 90 days)
