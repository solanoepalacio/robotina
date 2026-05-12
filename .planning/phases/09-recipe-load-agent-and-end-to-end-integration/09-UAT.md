---
status: testing
phase: 09-recipe-load-agent-and-end-to-end-integration
source: [09-01-SUMMARY.md, 09-02-SUMMARY.md]
started: 2026-03-31T02:00:00Z
updated: 2026-03-31T02:00:00Z
---

## Current Test

number: 1
name: Unit Tests Pass
expected: |
  Run `uv run pytest tests/unit/ -q`. All 77 tests pass, including:
  - test_recipe_load_registered
  - test_recipe_load_uses_household_manager_skill
  - test_prompt_file_exists_for_recipe_load
awaiting: user response

## Tests

### 1. Unit Tests Pass
expected: Run `uv run pytest tests/unit/ -q`. All 77 tests pass including 3 new recipe-load tests (RLOAD-01, RLOAD-02, RLOAD-05).
result: [pending]

### 2. Recipe-Load Prompt Exists and Contains Key Sections
expected: File `src/robotina/agent/prompts/recipe-load/V001.md` exists and contains: name resolution rules (exact-first matching), field mapping table (snake_case to camelCase), compound create sequence, and JSON output format.
result: [pending]

### 3. Recipe-Load Experiment Runs Successfully
expected: Run `uv run experiments.recipe_load`. The experiment executes 4 edge cases (happy path, missing food, ambiguous name, null unit). Each case produces output with recipe_slug and relevant fields. LangWatch traces appear in your LangWatch project.
result: [pending]

### 4. Notification Text in Spanish
expected: When the add-recipe workflow completes, the notification sent to Telegram is in Spanish, includes the recipe description, and contains an app link using HOUSEHOLD_MANAGER_BASE_URL.
result: [pending]

### 5. Full Add-Recipe Workflow End-to-End
expected: Send a message to Robotina via Telegram asking to research and save a recipe (e.g., "busca una receta de paella"). The full workflow executes: gather -> instructions -> ingredients -> metadata -> load -> notify. You receive a Telegram notification with the saved recipe details.
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps

