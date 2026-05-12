# Phase 9: recipe-load Agent and End-to-End Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 09-recipe-load-agent-and-end-to-end-integration
**Areas discussed:** Name resolution, Missing ingredients, Notification content, Experiment design, Skill design, Unit edge cases, Notify message format

---

## Name Resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Exact-first | If any result's name matches exactly (case-insensitive), pick it. Otherwise pick the shortest name. | ~partial |
| Always pick first | Trust API ordering, always pick first result. | |
| Fail on ambiguity | If more than one result, skip ingredient. | |

**User's choice:** Exact-first, but when no exact match the agent uses its common sense to pick the most reasonable result (not shortest name mechanically).
**Notes:** User wants the LLM's judgment involved, not a mechanical fallback.

---

## Missing Ingredients

| Option | Description | Selected |
|--------|-------------|----------|
| Skip ingredient | Drop unresolvable ingredient, continue creating recipe. | |
| Fail the task | Any unresolvable ingredient fails the whole step. | |
| Create with partial + warn | Skip + include warning in output for notification. | |

**User's choice:** Skip the ingredient. Add `missing_ingredients` property to the step artifact with the food names for troubleshooting/analytics. Will deal with these cases in a future iteration.
**Notes:** User explicitly wants tracking but not blocking.

---

## Notification Content

| Option | Description | Selected |
|--------|-------------|----------|
| Keep simple | Just "Recipe added: {name}". | |
| Add summary | Include ingredient count, cook time, skipped ingredients. | |
| Add summary + link | Summary plus link to recipe in household-manager. | ~partial |

**User's choice:** Notification should contain the recipe description and a link to the recipe on the app. Not ingredient counts or cook times.
**Notes:** User narrowed down from "summary + link" to specifically description + link only.

---

## Experiment Design

| Option | Description | Selected |
|--------|-------------|----------|
| Live API | Hit real household-manager API. | ✓ |
| Mocked API responses | Mock tool to return canned IDs. | |

**User's choice:** Live API (same pattern as recipe-research experiment).

### Edge Cases

| Option | Description | Selected |
|--------|-------------|----------|
| Happy path | Full RecipeData with resolvable ingredients. | ✓ |
| Missing foods | Ingredients that return zero matches. | ✓ |
| Ambiguous names | Names returning multiple matches. | ✓ |
| No units | Ingredients with null unit_name. | ✓ |

**User's choice:** All four edge cases selected.

---

## Skill Design

| Option | Description | Selected |
|--------|-------------|----------|
| Use household-manager | Reuse existing skill with recipes_create.md. | ✓ |
| Dedicated recipe-load skill | New skill directory, self-contained. | |
| Both skills | Thin recipe-load + household-manager for API details. | |

**User's choice:** Reuse household-manager skill. No new skill directory needed.

---

## Unit Edge Cases

| Option | Description | Selected |
|--------|-------------|----------|
| Skip unitId | Omit unitId if null or unresolvable; move text to note. | |
| Always resolve or skip ingredient | Missing unit = skip entire ingredient. | |
| You decide | Claude's discretion, principle: don't lose ingredients. | ✓ |

**User's choice:** Claude's discretion. General principle: don't lose ingredients over a missing unit.

---

## Notify Message Format

| Option | Description | Selected |
|--------|-------------|----------|
| Summary block | Name, ingredient count, cook time, missing count. | |
| Summary + app link | Summary block plus link to recipe. | ~partial |
| You decide | Claude designs the format. | |

**User's choice:** Notification should only contain the recipe description and a link to the recipe on the app. No ingredient counts or timing info.
**Notes:** Simpler than the full summary option.

---

## Claude's Discretion

- Unit handling details (null unit_name, unresolvable units, note field usage)
- Compound create payload construction from RecipeData
- recipe-load/V001.md prompt wording
- Experiment evaluation criteria and output formatting
- Error handling for API failures during name resolution

## Deferred Ideas

None — discussion stayed within phase scope.
