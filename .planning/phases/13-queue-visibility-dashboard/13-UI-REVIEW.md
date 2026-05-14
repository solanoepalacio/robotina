---
phase: 13
slug: queue-visibility-dashboard
status: complete
overall_score: 23
max_score: 24
created: 2026-05-14
baseline: 13-UI-SPEC.md
visual_evidence:
  - source: 13-03-SUMMARY.md
    type: chrome_inspection
    gates_verified: [B1, B2, B3]
---

# Phase 13 — UI Review

> Retroactive 6-pillar audit of the Queue Visibility Dashboard against the approved UI-SPEC.md design contract. Visual gates B1 (FAILED vs CANCELLED), B2 (3s polling cadence), and B3 (polling halt at terminal status) were verified in a live Chrome session and recorded in `13-03-SUMMARY.md`.

## Overall Score: **23/24**

| Pillar | Score | Notes |
|--------|------:|-------|
| 1. Copywriting | 4/4 | All ~17 spec-declared strings render verbatim. English-only, terse, no emoji, no generic CTAs. Empty-state, 404, and 500 copy paths all match the spec. |
| 2. Visuals | 4/4 | All 8 component contracts rendered with correct semantic markup (`<header>`, `<main>`, `<section>`, `<article>`, `<dl>`). `data-status` attr present on step rows for grep-able assertions. Failure block styled with the spec's red left border + visible failure-reason. |
| 3. Color | 4/4 | 60/30/10 split holds. Accent `#2563EB` reserved to header brand link, `<a>` elements, `:focus-visible` outline, and the RUNNING badge — no accent leakage to non-link elements. FAILED solid red `rgb(220,38,38)` vs CANCELLED `repeating-linear-gradient(45deg, #FEF3C7 0-6px, #FDE68A 6-12px)` confirmed via Chrome `getComputedStyle()` (B1 PASS). |
| 4. Typography | 4/4 | 4 roles (Body 14 / Mono 13 / Heading 18 / Label 12), 2 weights (400/600), system font stacks. One minor token-discipline lapse noted (Fix 2 below). |
| 5. Spacing | 4/4 | All padding/margin/gap declarations reference one of the 6 declared tokens; zero arbitrary `[Npx]` values. Breakpoints intentionally at `max - 1` (1023, 639) for `max-width` media-query semantics. |
| 6. Experience Design | 3/4 | Polling cadence (3s detail / 10s list) and halt-on-terminal both Chrome-verified (B2 + B3 PASS). `prefers-reduced-motion` guard live on the RUNNING pulse. One workflow-header drift from the spec contract (Fix 1 below). |

## Top Fixes (all WARNING; zero BLOCKERs)

### Fix 1 — Workflow header renders `Updated` instead of spec's `Started`/`Completed`

**File:** `src/robotina/dashboard/templates/workflow.html:14-15`
**Pillar:** Experience Design (cost 1 point)
**Severity:** WARNING

UI-SPEC §Component Contract 4 declares the workflow-header kv-grid as `Created` + `Started (if any)` + `Completed (if any)` + full UUID. The implementation substitutes `Updated` (mapped to the `WorkflowRun.updated_at` column). Pragmatic but off-contract — a developer scanning the workflow status loses the "when did this start running" datapoint at the header level (it remains on individual step rows via `_workflow_body.html`, but the contract specified it at the header card too).

**Recommended fix:** Replace the `Updated` `<dt>/<dd>` pair with conditional `started_at` / `completed_at` rows, mirroring the per-step pattern. If `WorkflowRun` doesn't carry those columns today, either (a) add them in a follow-up phase (would touch the queue layer, so likely deferred), or (b) amend UI-SPEC §Component Contract 4 to declare `Updated` as the canonical replacement at the workflow level.

### Fix 2 — `.step-key` uses raw `font-weight: 600` instead of the declared token

**File:** `src/robotina/dashboard/static/dashboard.css:172`
**Pillar:** Typography (sub-pillar token-discipline — did not cost a point but noted)
**Severity:** WARNING

UI-SPEC §Design System: "all tokens via CSS custom properties on `:root`". The declaration `font-weight: 600;` in `.step-key` is a valid weight but bypasses the `--font-label-weight: 600` token. A future weight refactor (e.g. 600 → 700) would silently miss this declaration.

**Recommended fix:** Change to `font-weight: var(--font-label-weight);` or, if `.step-key` is semantically distinct (mono identifier rather than label), introduce a `--font-body-strong-weight: 600` token and reference that.

### Fix 3 — `failure-block` adds undeclared background + symmetric padding

**File:** `src/robotina/dashboard/static/dashboard.css:183-189`
**Pillar:** Visuals (sub-pillar contract conformance — did not cost a point but noted)
**Severity:** WARNING

UI-SPEC §Component Contract 5 specifies the failure-block as `border-left: 4px solid #DC2626` plus `padding-left: var(--space-md)`. The implementation adds an additional `background: var(--color-surface-alt)` and symmetric vertical padding (`var(--space-sm) var(--space-md)`). Trivial visual divergence — reads slightly heavier than the spec's "border accent only" intent.

**Recommended fix:** Either tighten CSS to the literal contract (`border-left: 4px solid #DC2626; padding-left: var(--space-md);` — drop the bg + vertical padding), OR amend UI-SPEC §Component Contract 5 to declare the surface-alt background + symmetric padding as the agreed visual.

## Chrome-verified visual evidence

| Gate | Evidence | Result |
|------|----------|--------|
| B1 — FAILED vs CANCELLED distinction | `getComputedStyle(.badge--failed)` → solid `rgb(220,38,38)` filled; `getComputedStyle(.badge--cancelled)` → transparent + `repeating-linear-gradient(45deg, #FEF3C7 0-6px, #FDE68A 6-12px)` + amber border. Categorically different texture + hue. | PASS |
| B2 — Polling cadence | 5 `GET /fragments/workflows/<id>` requests in ~11 seconds on the RUNNING workflow, targeting the correct fragment endpoint. | PASS |
| B3 — Polling halt at terminal | After flipping workflow to DONE: `[...document.querySelectorAll('[hx-trigger]')].length === 0` and 0 fragment requests in a 12-second observation window. Server response also confirmed via curl to omit `hx-trigger` from the wrapper element. | PASS |

## Registry Safety

Not applicable. `components.json` absent; no shadcn registry; no third-party UI library registries. HTMX 2.0.10 is vendored locally with SHA-256 recorded per UI-SPEC §Registry Safety.

## Files Audited

- `src/robotina/dashboard/static/dashboard.css`
- `src/robotina/dashboard/templates/base.html`
- `src/robotina/dashboard/templates/index.html`
- `src/robotina/dashboard/templates/workflow.html`
- `src/robotina/dashboard/templates/_run_rows.html`
- `src/robotina/dashboard/templates/_workflow_body.html`
- `src/robotina/dashboard/templates/_status_badge.html`

## Recommendation Count

- **BLOCKERs:** 0
- **WARNINGs (priority fixes):** 3 (Fix 1, Fix 2, Fix 3 above)
- **INFO / Minor:** 0 additional

## Verdict

The dashboard implementation matches the approved UI-SPEC contract closely. Three minor warnings sit at the contract boundary — one (Fix 1) is a small experience-design drift, two (Fix 2, Fix 3) are token-discipline / visual-decoration nits. None block phase closure. The Chrome-verified visual evidence confirms the load-bearing visual contracts (FAILED vs CANCELLED differentiation, polling cadence, and polling halt) all hold in a real browser.

---

*Phase: 13-queue-visibility-dashboard*
*UI audit completed: 2026-05-14*
*Baseline: 13-UI-SPEC.md (approved 2026-05-14)*
