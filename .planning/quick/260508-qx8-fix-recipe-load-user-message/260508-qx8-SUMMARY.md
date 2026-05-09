---
quick_id: 260508-qx8
status: complete
date: 2026-05-08
description: Fix RecipeLoadInput.to_user_message — give the load agent the full structured recipe
---

# Quick Task 260508-qx8 — Summary

## What broke

`RecipeLoadInput.to_user_message()` rendered only the recipe **name**:

```python
def to_user_message(self) -> str:
    return f"Load recipe: {self.recipe.name}"
```

The `RecipeData` (ingredients, steps, times, source_url) carried in `self.recipe`
was silently dropped. The recipe-load agent therefore received a user message
of literally:

> Load recipe: Tomates rellenos al horno

…with nothing else. Its thinking trace concluded — correctly, given the input —
*"the user just gave a recipe name. We need more recipe details: ingredients
list, steps, etc... So we cannot proceed."* The agent made **zero tool calls**
(no `read-skill`, no `GET /api/foods`, no `POST /api/recipes`), exited with
prose, and `_extract_task_output` somehow accepted whatever the agent emitted
(no parse-failure log fired).

The workflow's `notify` step then ran `_build_notify_text(artifacts["load"])`,
which calls `load_artifact.get("recipe_name", "Unknown recipe")` —
the user received a Telegram message reading **"Receta agregada: unknown
recipe"** even though no recipe had been created.

Sibling research-step inputs (`RecipeResearchInstructionsInput`,
`RecipeResearchIngredientsInput`, `RecipeResearchMetadataInput` at
`task_types.py:130-185`) all dump their structured fields via `json.dumps`.
`RecipeLoadInput` was the odd one out.

## What was changed

**`src/robotina/queue/task_types.py`** — `RecipeLoadInput.to_user_message()`

Now dumps the full `RecipeData` as JSON, mirroring the sibling inputs' pattern:

```python
def to_user_message(self) -> str:
    import json
    return (
        "Load this recipe into the household-manager system:\n\n"
        + json.dumps(self.recipe.model_dump(mode="json"), ensure_ascii=False, indent=2)
    )
```

`model_dump(mode="json")` future-proofs against any non-trivially-serializable
field types being added later. `ensure_ascii=False` keeps Spanish accents and
other Unicode readable in the prompt instead of `\\uXXXX` escapes.

**`tests/test_task_types.py`** — new regression test
`test_recipe_load_input_user_message_contains_full_recipe`

Uses the existing `_make_recipe_data()` helper (Carbonara with 2 ingredients
and 2 steps), builds a `RecipeLoadInput`, and asserts the rendered message:
- starts with the "Load this recipe into the household-manager system:" prefix,
- contains the recipe name, description, and source_url,
- contains every ingredient's `food_name` and (when non-null) `unit_name`,
- contains every step's `body`.

This pins the contract so future refactors of `to_user_message` can't silently
drop a field again.

## What was *not* changed

- `RecipeLoadInput` model fields — unchanged.
- `RecipeData` model — unchanged.
- `workflows.py` `build_input` callables — unchanged.
- `recipe-load` agent prompt — unchanged. The prompt was correct all along; it
  just had nothing to work with.
- `_build_notify_text`'s `"unknown recipe"` fallback — left as a separate
  follow-up. With the load step now actually creating recipes, the fallback
  should rarely trigger; tightening it (detect missing `recipe_id` and emit a
  failure-style message) is a future improvement.

## Verification

```
$ uv run pytest tests/test_task_types.py -q
..................                                                       [100%]
18 passed in 0.02s
```

```
$ uv run pytest tests/test_workflow_runner.py tests/test_workflows.py \
                tests/unit/test_queue_tool.py tests/unit/test_start_workflow_tool.py -q
37 passed, 2 warnings in 0.18s
```

(Warnings are pre-existing `LangGraphDeprecatedSinceV10` notices from
`create_react_agent` import paths, unrelated to this fix.)
