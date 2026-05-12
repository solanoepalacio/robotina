---
quick_id: 260330-mgk
status: complete
commit: 0b0ed36
---

# Summary: Fix recipe-research-gather prompt step 6

## What was done

Updated step 6 in `src/robotina/agent/prompts/recipe-research-gather/V001.md` to explicitly specify the `{"recipes": [...]}` output structure instead of the ambiguous "Responde con un JSON que contenga la lista de recetas encontradas."

## Change

**File:** `src/robotina/agent/prompts/recipe-research-gather/V001.md`, line 16

**Before:**
```
6. Responde con un JSON que contenga la lista de recetas encontradas.
```

**After:**
```
6. Responde con un JSON con la siguiente estructura: {"recipes": [...]} donde cada elemento sigue el formato del skill.
```

## Why this fixes the bug

The original phrasing was ambiguous about the top-level JSON key. The LLM was outputting a plain array `[{...}]`, but the experiment code and downstream steps call `result["recipes"]` expecting an object wrapper. The new phrasing explicitly names the required key, consistent with the canonical format defined in `src/robotina/agent/skills/recipe-research/gather.md`.

## Commit

`0b0ed36` — fix(prompt): clarify gather agent step 6 output format to {"recipes": [...]}
