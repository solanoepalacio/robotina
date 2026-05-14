# Phase 13: Queue Visibility Dashboard - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-14
**Phase:** 13-queue-visibility-dashboard
**Areas discussed:** (none discussed individually — user delegated full discretion)

---

## Gray Areas Presented

| Option | Description | Selected |
|--------|-------------|----------|
| Template layout + CSS/HTMX assets | How are Jinja templates organized? Where do status-badge macros live? How is CSS delivered (static file, inline, Pico/Tailwind CDN)? Vendored vs CDN HTMX? | (delegated) |
| Status badge styling | Visual treatment for PENDING/RUNNING/DONE/FAILED/CANCELLED. FAILED vs CANCELLED must be clearly distinct. Pills, color-only, emoji+text? | (delegated) |
| HTMX polling-halt mechanic | How does the page stop polling once the workflow hits a terminal status? Server returns no hx-trigger, swap polling element out, or conditional trigger via response headers? | (delegated) |
| Migration + wiring + test strategy | Commit order for migration vs workflow_runner.py wiring change. Test approach (real Postgres TestClient, SQLite swap, or manual smoke). | (delegated) |

**User's choice:** "This one is completely yours. Make every decision yourself. My only ask is that it should be completely independent of the other robotina modules."

**Notes:** User issued a single hard constraint — module independence — and granted Claude full discretion on every other implementation detail. The independence rule is captured as the only non-discretionary decision in CONTEXT.md `D-01`. All other decisions (`D-02` through `D-23`) are Claude-chosen with rationale documented so downstream agents do not re-ask.

---

## Claude's Discretion

Claude exercised discretion on, with defaults recorded in CONTEXT.md:

- **Template layout** (D-02 through D-06) — single `base.html`, two page templates, two HTMX fragment partials, one `_status_badge.html` macro.
- **Status badge styling** (D-07, D-08) — semantic pill chips, diagonal-stripe outlined amber for `CANCELLED` vs solid red for `FAILED` to satisfy SPEC req 8's visual-distinction acceptance.
- **HTMX polling-halt mechanic** (D-09, D-10, D-11) — fragment-wrapper-attached `hx-trigger`, server omits the attribute on terminal-status responses, polling halts naturally. List view polls unconditionally; detail view halts on `DONE`/`FAILED`.
- **CSS / asset delivery** (D-12, D-13, D-14) — hand-written `dashboard.css`, vendored `htmx.min.js`, no CDN, FastAPI `StaticFiles`.
- **Migration + wiring + dashboard order** (D-15, D-16, D-17) — three commits in one PR: migration → wiring → dashboard module.
- **Test strategy** (D-18, D-19, D-20, D-21) — pytest + httpx `AsyncClient` via `ASGITransport`; DB-touching tests marked `@pytest.mark.integration`; happy-path failed-step+cancelled-cascade test plus empty-state and polling-halt tests; manual smoke at the end.
- **pyproject + docker-compose** (D-22, D-23) — `dashboard = "robotina.dashboard:main"`; `DASHBOARD_PORT` env var (default 8001); compose service mirrors gateway/agent env wiring and depends_on postgres, but is NOT a dependency of agent/gateway.

## Deferred Ideas

(See CONTEXT.md `<deferred>` section. All deferrals are SPEC-driven and explicitly out-of-scope: filtering/search/pagination, worker-crash reconciliation, Spanish UI, per-step duration_ms, WebSockets/SSE, auth, retry/cancel/requeue.)
