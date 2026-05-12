# Phase 3: Gateway - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the discussion.

**Date:** 2026-03-25
**Phase:** 03-gateway
**Mode:** discuss
**Areas discussed:** Bot server approach, Gateway entrypoint, Outgoing send_message scope, Error handling

---

## Gray Areas Presented

| Area | Options Offered | User Choice |
|------|-----------------|-------------|
| Bot server approach | PTB run_webhook() standalone / FastAPI + PTB / PTB run_polling() | `run_polling()` — simpler for Phase 1 dev |
| Gateway entrypoint | `uv run gateway` / Docker Compose service / manual invocation | `uv run gateway` + `uv run all` (starts both agent and gateway) |
| Outgoing send_message scope | Implement `send_message()` in gateway now / stub for Phase 6 | Implement now as async function |
| Error handling | Persist-first + log + 200 / PTB error handler / atomic rollback | Raise on DB failure, let PTB polling handle retries — HTTP 200 N/A since polling |

## Key User Notes

- "uv run all — runs both the agent and the gateway" — user explicitly requested this shortcut
- On error handling: "we changed webhooks for polling. returning 200 doesn't apply anymore. If DB fails, just throw the error. Leave retry to PTB.polling(), whatever it does is fine for phase 1"

## Scope Deferred

- Webhook mode for production (GW-01 explicitly says webhook — deferred to post-Phase-1)
- GW-03 (HTTP 200 always) — not applicable in polling mode, deferred with webhook

