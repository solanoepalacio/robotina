---
phase: 24-recipe-images-topic-3
plan: 02
subsystem: queue/types + url/safe_fetch
tags: [schema, pydantic, regression-test, image-fetch]
requires:
  - 24-01 (Phase 24 ground prep)
provides:
  - RecipeData.image_url (str | None field, owned by recipe-image step)
  - RecipeImageInput Pydantic model (recipe + reply_context + household_id)
  - RecipeImageOutput sentinel alias (= RecipeData)
  - safe_fetch image/* wildcard regression-guard (7 parametrized cases)
affects:
  - src/robotina/queue/task_types.py (RecipeData shape + 2 new symbols)
  - tests/url/test_safe_fetch.py (+2 test functions, 7 parametrized cases)
tech-stack:
  added: []
  patterns:
    - "Sentinel-alias output: `RecipeImageOutput = RecipeData` (mirrors Phase 15 RecipeResearch*Output convention)"
    - "Pin-the-contract regression test (image/* wildcard) — guards Pitfall 4 from future refactor"
key-files:
  created: []
  modified:
    - src/robotina/queue/task_types.py
    - tests/url/test_safe_fetch.py
decisions:
  - "Picked sentinel-alias encoding for RecipeImageOutput (Option B per 24-PATTERNS.md): zero duplication, matches existing RecipeResearch*Output convention; the workflow_runner can pass dump unchanged."
  - "No code change to safe_fetch.py (D-13/D-17): wildcard sniff at safe_fetch.py:213-223 already accepts image/*. Plan adds the regression-guard test only."
  - "image_url slotted between source_url and ingredients in RecipeData — keeps the metadata-step adjacent fields together visually and preserves field-ownership-docstring grouping."
metrics:
  duration: ~10min
  completed: 2026-05-22
  tasks_completed: 2
  files_modified: 2
---

# Phase 24 Plan 02: Image schema + safe_fetch image/* regression-guard Summary

Phase 24 Plan 02 wires the Pydantic contracts the recipe-image step needs: a new
`RecipeData.image_url` accumulator field, a `RecipeImageInput` task model, a
`RecipeImageOutput` sentinel alias, and a pinned `safe_fetch image/*` content-type
sniff so a future refactor cannot silently break the recipe-image fetch path.

## Tasks Completed

| Task | Name                                                                    | Commit  | Files                                  |
| ---- | ----------------------------------------------------------------------- | ------- | -------------------------------------- |
| 1    | Add image_url field to RecipeData + RecipeImageInput + RecipeImageOutput alias | 87dbfed | src/robotina/queue/task_types.py       |
| 2    | Add safe_fetch image/* wildcard regression-guard test                   | 85799ae | tests/url/test_safe_fetch.py           |

## Implementation Notes

### Task 1 — `task_types.py` extensions (D-03 / D-04)

- `RecipeData.image_url: str | None = None` slotted between `source_url` and
  `ingredients`. Default `None` keeps all existing JSON artifacts (which lack
  the field) valid: Pydantic v2 treats missing optional fields with defaults
  as accepted. Backward-compat verified by full `tests/test_task_types.py`
  (24 passed) without touching any fixture.
- Field-ownership docstring updated with the new line
  `- recipe-image:  image_url (Phase 24 D-04)` next to the existing per-step
  ownership block so Phase 15's documented accumulator convention stays
  comprehensive.
- `RecipeImageInput` placed after `RecipeResearchMetadataInput`, mirroring
  field-by-field (`recipe`, `reply_context`, `household_id`) with
  `model_config = ConfigDict(extra="forbid")` matching the other Phase-15
  inputs and Phase-23 url-ingestion inputs. No `to_user_message` per D-02 —
  recipe-image is a deterministic, agent-less step.
- `RecipeImageOutput = RecipeData` placed alongside the existing
  `RecipeResearch*Output = RecipeData` sentinel-alias block. This is
  intentionally the lighter encoding (Option B in 24-PATTERNS.md) — it
  preserves the workflow_runner's existing build_input lambda assumption
  that the artifact dump round-trips through `RecipeData.model_validate`.

### Task 2 — `image/*` wildcard regression-guard (D-13 / D-17 / Pitfall 4)

- Two new test functions, 7 parametrized cases total:
  - `test_safe_fetch_image_wildcard_accepts_image_subtypes` over
    `image/jpeg`, `image/png`, `image/webp`, `image/gif`.
  - `test_safe_fetch_image_wildcard_rejects_non_image_types` over
    `text/html`, `application/pdf`, `application/json`.
- Reused the existing `respx.mock` + `monkeypatch socket.getaddrinfo` idiom
  via `_patch_dns(monkeypatch, PUBLIC_IP)` — same pattern as the
  text/html content-type tests directly above the new block. No new test
  fixtures or helpers.
- `safe_fetch.py` is unchanged. The wildcard sniff at lines 213-223 already
  routes `image/*` to the `("image/",)` prefix-match tuple. The tests pin
  the contract so the elif at line 216-217 cannot be "cleaned up" without
  surfacing the broken behavior immediately.
- Threat T-24-01 (Tampering at the safe_fetch image-content-type
  boundary) is now mitigated by an explicit test register; the threat
  register's `mitigate` disposition is honored.

## Verification

| Check                                                                          | Result |
| ------------------------------------------------------------------------------ | ------ |
| `uv run python -c "from robotina.queue.task_types import RecipeData, RecipeImageInput, RecipeImageOutput; ..."` (Task 1 verify command) | PASS   |
| `uv run pytest tests/url/test_safe_fetch.py -x -q -k "image_wildcard"`         | 7 passed |
| `uv run pytest tests/url/test_safe_fetch.py -q` (full file, no regression)     | 28 passed |
| `uv run pytest tests/test_task_types.py -q`                                    | 24 passed |
| `uv run pytest tests/queue/ tests/url/ tests/agents/ tests/test_task_types.py -q` (excluding DB-required wake/reconcile tests) | 120 passed |
| `grep -c "RecipeImageInput\|RecipeImageOutput\|image_url" src/robotina/queue/task_types.py` | 8 (≥4 required) |
| `grep -c "^def test_safe_fetch_image_wildcard" tests/url/test_safe_fetch.py`   | 2      |
| `grep -c "image_wildcard" tests/url/test_safe_fetch.py`                        | 2      |
| `git diff 924491d..HEAD -- src/robotina/url/safe_fetch.py` (must be empty)     | empty (no code change to safe_fetch.py — only test file changed) |

### Pre-existing test infra gaps (out of scope)

`tests/queue/test_wake_dispatch.py`, `tests/queue/test_wake_helper.py`,
`tests/queue/test_wake_helper_ordering.py`, and `tests/queue/test_reconcile.py`
ERROR (not FAIL) when run because the worktree environment lacks a live
Postgres instance — they require `psycopg2.connect()` to succeed against
`localhost:5432` as the `robotina` user. These errors reproduce on the
parent commit (`924491d`) and have nothing to do with this plan's changes.
Logged as a pre-existing environment limitation; out of scope per the
executor's SCOPE BOUNDARY rule. No `deferred-items.md` entry needed —
this is documented infrastructure rather than missed task work.

## Deviations from Plan

None — plan executed exactly as written. The two acceptance criteria
listed in the plan (image-subtype accept set + non-image reject set)
were satisfied verbatim; no extra tests added, no code change to
`safe_fetch.py`.

## Threat Flags

None. The plan's `<threat_model>` declared T-24-01 (`mitigate` for the
image/* wildcard sniff) and T-24-02 (`accept` for image_url
serialization PII concerns); both are addressed:
- T-24-01: Task 2's parametrized tests are the documented mitigation.
- T-24-02: `image_url: str | None` with no logging side-effects + the
  surrounding `RecipeData` model (Pydantic v2 default-strict, no extras
  on the input wrapper `RecipeImageInput`) match the accept disposition.

No new security-relevant surface introduced beyond what the threat
register already covers.

## Known Stubs

None. `image_url` defaults to `None` by design — it is an accumulator
field whose owner (the recipe-image step) lands in a later plan
(24-04 acquire_recipe_image, 24-05 workflow registration). The
`None` default is not a stub; it is the documented "no image yet" state
of the accumulator.

## Self-Check: PASSED

Files asserted present:
- `src/robotina/queue/task_types.py` — modified (8 occurrences of image_url/RecipeImage*)
- `tests/url/test_safe_fetch.py` — modified (+59 lines, 2 new test functions)
- `.planning/phases/24-recipe-images-topic-3/24-02-SUMMARY.md` — this file

Commits asserted present:
- `87dbfed` — Task 1 feat commit (verified via `git log --oneline 924491d..HEAD`)
- `85799ae` — Task 2 test commit (verified via `git log --oneline 924491d..HEAD`)

No deletions in either commit (`git diff --diff-filter=D --name-only HEAD~1 HEAD` empty for both).
