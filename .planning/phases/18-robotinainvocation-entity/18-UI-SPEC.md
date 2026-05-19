---
phase: 18
slug: robotinainvocation-entity
status: approved
shadcn_initialized: false
preset: none
created: 2026-05-19
reviewed_at: 2026-05-19
inherits_from: ../13-queue-visibility-dashboard/13-UI-SPEC.md
---

# Phase 18 — UI Design Contract

> Visual and interaction contract for the **single** dashboard change shipped by Phase 18. Phase 18 is primarily a backend/persistence phase (new `RobotinaInvocation` SQLAlchemy entity + nullable `WorkflowRun.triggered_by_invocation_id` FK). The ONLY UI deliverable is surfacing the new FK on the existing WorkflowRun **detail** view per DASH-13 (`triggered_by_invocation_id` appears on the detail page) and DASH-14 (module-isolation grep gate still passes).
>
> **Scope discipline:** No new screens. No new components. No new tokens. No JS, no HTMX trigger changes, no CSS additions. One new `<dt>/<dd>` pair inside the existing `kv-grid` in `src/robotina/dashboard/templates/workflow.html`. Everything else is inherited verbatim from Phase 13.

---

## Inheritance

This phase inherits Phase 13's UI-SPEC unchanged. Phase 18 adds NO new tokens or components. The references below are pointers, not duplicates.

| Concern | Source of Truth | Phase 18 Change |
|---------|-----------------|-----------------|
| Design System (tool, preset, fonts, JS runtime) | `13-UI-SPEC.md` §Design System | none |
| Layout & Responsive Breakpoints | `13-UI-SPEC.md` §Layout & Responsive Breakpoints | none |
| Spacing Scale (6 tokens, multiples of 4) | `13-UI-SPEC.md` §Spacing Scale | none |
| Typography (3 sizes, 2 weights) | `13-UI-SPEC.md` §Typography | none |
| Color (60/30/10 + status badge tokens) | `13-UI-SPEC.md` §Color | none |
| Components 1–8 (page header, list row, status badge, workflow header card, step row, JSON block, polling wrapper, empty state) | `13-UI-SPEC.md` §Component Contracts | none |
| Interaction Contracts (polling cadence, hover, focus) | `13-UI-SPEC.md` §Interaction Contracts | none |
| State Definitions (list view, detail view, server error) | `13-UI-SPEC.md` §State Definitions | one new state added below for the new FK row |
| Accessibility (WCAG AA, semantic HTML, focus rings) | `13-UI-SPEC.md` §Accessibility | none |
| Module Independence (D-01 at the UI layer) | `13-UI-SPEC.md` §Independence from Other Robotina Modules | preserved (see DASH-14 note below) |
| Registry Safety (no shadcn, no third-party) | `13-UI-SPEC.md` §Registry Safety | none |

---

## The Single UI Change (DASH-13)

### What gets rendered

A new key/value pair inside the existing `<dl class="kv-grid">` block in the workflow header card (`src/robotina/dashboard/templates/workflow.html`).

**Insertion point:** after the existing `ID` row (line 16–17 of `workflow.html` as of 2026-05-19), before the closing `</dl>`.

**Markup contract (exact):**

```jinja
<dt>Triggered by invocation</dt>
<dd class="mono">{{ run.triggered_by_invocation_id or "—" }}</dd>
```

### Why this exact markup

- `<dt>` and `<dd>` reuse the existing `.workflow-header .kv-grid dt` / `.workflow-header .kv-grid dd` CSS rules (no new CSS).
- The `<dt>` text inherits the existing uppercase / 12px / 600-weight label typography automatically (see `dashboard.css` lines 143–149).
- The `<dd>` uses `class="mono"` to match the `ID` row above it — invocation IDs are UUIDs and must be visually grep-able / copy-paste-friendly in the same monospace style as the workflow ID.
- The `or "—"` fallback handles the nullable case (per ARCH-03 / D-02: column lands nullable in v1.1; legacy WorkflowRuns predate the FK).

### Visual placement (textual mockup)

```
┌─ Workflow header card ─────────────────────────────────────┐
│  Workflow a1b2c3d4                                          │
│  add-recipe · household hh-xyz                              │
│  [DONE]                                                     │
│                                                             │
│  CREATED                  2026-05-19 14:32:01               │
│  UPDATED                  2026-05-19 14:32:47               │
│  ID                       a1b2c3d4-...-fffe                 │
│  TRIGGERED BY INVOCATION  inv-7f8a9b0c-...-1234   ← NEW    │
│                                                             │
│  ▸ Shared context                                           │
└─────────────────────────────────────────────────────────────┘
```

### What is explicitly NOT done in Phase 18

Per CONTEXT.md D-19 / D-20 (scope discipline):

- **No JOIN to `RobotinaInvocation`** — the cell renders the FK value directly; no eager-load, no extra query in `get_workflow_with_steps`.
- **No hyperlink to a future invocation detail view** — that view doesn't exist; making the value a link would deceive the developer.
- **No short-id helper / formatting** — render the raw UUID string. The existing `ID` row also renders the full UUID, so visual symmetry is preserved.
- **No list-view column** for `triggered_by_invocation_id`.
- **No `conversation_id` rendering** (DASH-10) — deferred to Phase 20.
- **No `outcome` summary cell** (DASH-12) — deferred to Phase 20.
- **No dedicated `RobotinaInvocation` list/detail view** — DASH-13 explicitly marks this "nice-to-have"; not in Phase 18 scope.

---

## State Definitions (delta only)

Adds one row state to Phase 13's §State Definitions. All other states inherit verbatim.

### Detail view — "Triggered by invocation" cell

| State | Condition | Rendered Text |
|-------|-----------|---------------|
| Populated | `run.triggered_by_invocation_id is not None` | The UUID string in monospace, e.g. `inv-7f8a9b0c-...` |
| Null / legacy row | `run.triggered_by_invocation_id is None` (any WorkflowRun created before Phase 18 deploy, or any row whose dispatcher did not stamp the FK) | The em-dash placeholder `—` in monospace, muted-text-color-equivalent (the placeholder is the same character pattern already used by the `Created` / `Updated` rows when those columns are null) |

The em-dash matches the existing convention in `workflow.html` lines 13–15 (`run.created_at.strftime(...) if run.created_at else "—"`). No new placeholder vocabulary introduced.

---

## Copywriting Contract (delta only)

Adds two strings to Phase 13's §Copywriting Contract. All other copy inherits verbatim.

| Element | Copy | Style |
|---------|------|-------|
| Detail view, kv-grid label for the new FK row | `Triggered by invocation` | Inherits `.workflow-header .kv-grid dt` (uppercase via CSS `text-transform`, 12px, weight 600, letter-spacing 0.04em). Author the literal string in title case in the template; CSS uppercases at render time, matching the existing `Created` / `Updated` / `ID` labels. |
| Detail view, value when FK is null | `—` (U+2014 em dash) | Inherits `.mono` class. No "(none)" string; no "n/a". The em-dash is the established null-cell convention for this card (see `Created` / `Updated` rows). |

**Destructive copy:** Not applicable — read-only render, no actions.
**Confirmation copy:** Not applicable — no mutations.
**Empty state copy:** Not applicable — the cell is always present on the detail view; the cell itself has a null variant (em-dash), not the page.
**Error state copy:** Not applicable — null FK is the documented expected state, not an error.

---

## Module Independence (DASH-14 enforcement)

The dashboard's existing module-isolation rule (Phase 13 D-01) is unaffected because:

- `RobotinaInvocation` lives in `src/robotina/queue/models.py` (per CONTEXT.md D-04), which the dashboard is already allowed to import from (per Phase 13 D-01 allow-list: `robotina.queue.models`, `robotina.db`, `robotina.queue.task_types`).
- The template reads `run.triggered_by_invocation_id` directly off the existing `WorkflowRun` instance produced by `get_workflow_with_steps`. No new import in the template, no new import in `queries.py`, no new cross-module edge.
- The existing `tests/dashboard/test_independence.py` grep + AST + inward-only audit must continue to pass after Phase 18 lands. **This is the load-bearing acceptance test for DASH-14.**

### Grep-able acceptance evidence

After Phase 18 lands, the following must all hold:

1. `grep -n 'triggered_by_invocation_id' src/robotina/dashboard/templates/workflow.html` returns exactly one match (the new `<dd>` line).
2. `grep -rE 'from robotina\.dashboard|import robotina\.dashboard' src/robotina/ --exclude-dir=dashboard` returns zero matches (Phase 13 SPEC AC, unchanged).
3. `grep -n 'RobotinaInvocation' src/robotina/dashboard/` returns zero matches — the dashboard reads the FK STRING off `WorkflowRun`; it does NOT import the `RobotinaInvocation` model class. (The dashboard never needs to resolve the FK to a full row in Phase 18.)
4. `uv run pytest tests/dashboard/test_independence.py -x` passes.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (inherited from Phase 13 — Python repo, no JS toolchain) |
| Preset | not applicable |
| Component library | none — hand-written Jinja2 templates |
| Icon library | none — Unicode glyphs (the em-dash `—` is the only Unicode character introduced by this phase) |
| Font | inherited from Phase 13 (system font stack for body, system mono stack for `.mono`) |

---

## Spacing Scale

Inherited verbatim from Phase 13. The new `<dt>/<dd>` pair sits inside the existing `.workflow-header .kv-grid` which already uses `gap: var(--space-xs) var(--space-md)` — no spacing token introduced or modified.

Exceptions: none.

---

## Typography

Inherited verbatim from Phase 13. The new label uses the existing `dt` styling (12px, weight 600, uppercase, 0.04em tracking). The new value uses the existing `.mono` class (13px, weight 400, 1.5 line-height, monospace stack). No new typography role introduced.

---

## Color

Inherited verbatim from Phase 13. The new row uses:
- Label foreground: `var(--color-text-muted)` (#71717A) — from the existing `dt` rule.
- Value foreground: `var(--color-text)` (#18181B) — default body color, inherited because `.mono` sets only `font:`, not `color:`.
- Background: `var(--color-surface)` (#FFFFFF) — inherited from `.workflow-header`.

Contrast ratios (re-verified for the new row):
- `#71717A` on `#FFFFFF` (label on card surface) = 4.5:1 — WCAG AA body ✓
- `#18181B` on `#FFFFFF` (value on card surface) = 17.4:1 — WCAG AAA ✓
- `#18181B` on `#FFFFFF` for the em-dash placeholder — same ratio, AAA ✓ (decision: keep value at full text color, not muted, so the em-dash is visible at a glance rather than fading into the card)

Accent color (`#2563EB`) is NOT used by the new row — consistent with Phase 13's accent-reserved-for list.

---

## Copywriting Contract

Defined in §"Copywriting Contract (delta only)" above. The two strings are:

| Element | Copy |
|---------|------|
| Label | `Triggered by invocation` |
| Null value | `—` (em-dash) |

All other dashboard copy inherits verbatim from `13-UI-SPEC.md` §Copywriting Contract.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none — not applicable (Python repo, no JS toolchain) | not required |
| Third-party registries | none | not required |
| Vendored runtime | HTMX (already vendored in Phase 13; unchanged this phase) | inherited — `htmx.version.txt` unchanged |

No new third-party assets. No new HTMX behavior. No new CSS. No new JS. No new fonts. No new images.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS — 2 new strings defined (`Triggered by invocation`, `—`); both consistent with Phase 13 tone (English, terse, em-dash for null cells)
- [ ] Dimension 2 Visuals: PASS — 0 new components; 1 new row inside existing `kv-grid`; markup contract specified verbatim
- [ ] Dimension 3 Color: PASS — 0 new tokens; new row contrast verified at 4.5:1 (label) and 17.4:1 (value)
- [ ] Dimension 4 Typography: PASS — 0 new roles; new row reuses existing `dt` + `.mono` styles
- [ ] Dimension 5 Spacing: PASS — 0 new tokens; new row uses inherited `kv-grid` gap rules
- [ ] Dimension 6 Registry Safety: PASS — 0 new assets; HTMX vendor file unchanged

**Approval:** pending
