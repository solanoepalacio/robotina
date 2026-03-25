---
phase: 03-gateway
plan: "03"
subsystem: gateway
tags: [python-telegram-bot, sqlalchemy, asyncio, telegram, outgoing-messages]

# Dependency graph
requires:
  - phase: 03-01
    provides: test scaffold with db_session fixture and test_send_message_persists stub
  - phase: 02-01
    provides: Conversation and StoredMessage SQLAlchemy models, SessionLocal
provides:
  - send_message(chat_id, text, user_id) async function at robotina.gateway.send
  - Outgoing Telegram message persistence as ASSISTANT StoredMessage
  - Stable import path for Phase 6 send-notification tool
affects: [phase-06-notification-agent, any code importing from robotina.gateway.send]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PTB Bot as async context manager: `async with Bot(token=token):` for standalone (non-Application) Telegram calls"
    - "Enum values_callable=lambda for SQLAlchemy native PostgreSQL enum value mapping (use .value not .name)"

key-files:
  created:
    - src/robotina/gateway/send.py
  modified:
    - src/robotina/gateway/models.py
    - tests/test_gateway.py

key-decisions:
  - "Bot used as async context manager (`async with bot:`) per PTB 22.7 standalone pattern — ensures HTTP client lifecycle is correct without PTB Application"
  - "send_message silently skips DB persistence when no Conversation found (defensive; Phase 6 always has prior conversation from incoming message)"
  - "SQLAlchemy Enum requires values_callable=_enum_values to send PostgreSQL enum values (lowercase) instead of Python enum names (uppercase) — fixes silent DB mismatch"

patterns-established:
  - "Standalone async Telegram Bot usage: instantiate Bot, use async with, call methods inside context"
  - "SQLAlchemy Enum(MyEnum, values_callable=lambda e: [x.value for x in e]) for PostgreSQL native enum columns"

requirements-completed:
  - GW-05

# Metrics
duration: 2min
completed: 2026-03-25
---

# Phase 03 Plan 03: send_message Outgoing Function Summary

**Standalone async send_message() using Bot async context manager, persisting ASSISTANT StoredMessage to Postgres via SessionLocal**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-25T21:56:09Z
- **Completed:** 2026-03-25T21:58:06Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments
- Implemented `send_message(chat_id, text, user_id) -> str` in `src/robotina/gateway/send.py`
- Bot used as async context manager ensuring HTTP client lifecycle is properly managed per PTB 22.7 standalone pattern
- ASSISTANT StoredMessage persisted to Postgres on successful send; graceful skip when no prior Conversation found
- Stable import path `from robotina.gateway.send import send_message` ready for Phase 6
- Fixed pre-existing SQLAlchemy Enum serialization bug (name vs value) blocking DB persistence

## Task Commits

Each task was committed atomically:

1. **TDD RED: test_send_message_persists real assertions** - `59bd06d` (test)
2. **TDD GREEN: send_message + models enum fix** - `fd73922` (feat)

_Note: TDD tasks have multiple commits (test RED → feat GREEN)_

## Files Created/Modified
- `src/robotina/gateway/send.py` - Standalone async send_message() function; Phase 6 import target
- `src/robotina/gateway/models.py` - Added values_callable to Enum columns for correct PostgreSQL value mapping
- `tests/test_gateway.py` - Replaced pytest.skip stub with full GW-05 assertions using mocked Bot

## Decisions Made
- Bot used as async context manager (`async with bot:`) — matches PTB 22.7 standalone pattern; avoids PTB Application entanglement
- Skip DB persistence when no Conversation found — defensive; Phase 6 always has a prior conversation
- SQLAlchemy `Enum(Platform, values_callable=_enum_values)` applied to both Platform and MessageRole columns — needed for PostgreSQL enum compatibility

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed SQLAlchemy Enum sending Python name instead of PostgreSQL value**
- **Found during:** Task 1 (TDD GREEN — first test run)
- **Issue:** `Enum(Platform)` by default sends Python enum *name* (`"TELEGRAM"`) to PostgreSQL, but the database enum type stores lowercase values (`"telegram"`). Caused `invalid input value for enum platform: "TELEGRAM"` DataError.
- **Fix:** Added `values_callable=_enum_values` helper to `Enum(Platform, ...)` and `Enum(MessageRole, ...)` columns in `models.py`, mapping each enum to its `.value` (lowercase string) rather than `.name`.
- **Files modified:** `src/robotina/gateway/models.py`
- **Verification:** All 42 tests pass including `test_send_message_persists` and all integration gateway tests
- **Committed in:** `fd73922` (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Pre-existing bug that would have also affected all other gateway integration tests using `Platform.TELEGRAM`. Fix is minimal and correct.

## Issues Encountered
- SQLAlchemy Enum serialization mismatch discovered on first GREEN test run. Root cause: SQLAlchemy `Enum(SomeEnum)` uses enum *names* for native PostgreSQL enum columns by default; requires `values_callable` to use values. Fixed immediately via Rule 1.

## Known Stubs
None - `send_message` is fully wired; no placeholders or hardcoded empty data.

## User Setup Required
None - no external service configuration required. TELEGRAM_BOT_TOKEN is read from env at call time.

## Next Phase Readiness
- Gateway phase complete: incoming handler (Plan 02) and outgoing send_message (Plan 03) both implemented
- Phase 6 can import `from robotina.gateway.send import send_message` directly
- All 42 tests green

## Self-Check: PASSED
- `src/robotina/gateway/send.py` exists
- `.planning/phases/03-gateway/03-03-SUMMARY.md` exists
- Commit `59bd06d` (test RED) found
- Commit `fd73922` (feat GREEN) found

---
*Phase: 03-gateway*
*Completed: 2026-03-25*
