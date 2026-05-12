---
quick_id: 260330-mgk
description: Fix recipe-research-gather prompt step 6 to explicitly specify recipes output format instead of ambiguous JSON array
date: 2026-03-30
status: ready
---

# Quick Plan 260330-mgk

## Task

Fix step 6 in the gather agent prompt so the LLM outputs `{"recipes": [...]}` instead of a plain JSON array.

**Root cause:** Step 6 says "Responde con un JSON que contenga la lista de recetas encontradas." — ambiguous phrasing leads the LLM to output `[{...}]` instead of `{"recipes": [...]}`.

**Fix:** Replace step 6 with an explicit instruction specifying the exact output structure, consistent with the skill file at `src/robotina/agent/skills/recipe-research/gather.md`.

## Tasks

### T1: Update step 6 in V001.md prompt

**File:** `src/robotina/agent/prompts/recipe-research-gather/V001.md`

**Action:** Replace line 16 (step 6) from the ambiguous phrasing to an explicit JSON structure example.

**Current:**
```
6. Responde con un JSON que contenga la lista de recetas encontradas.
```

**New:**
```
6. Responde con un JSON con la siguiente estructura: {"recipes": [...]} donde cada elemento sigue el formato del skill.
```

**Verify:** Line 16 in V001.md contains the explicit `{"recipes": [...]}` format.

**Done:** File saved, step 6 unambiguously specifies the output key.

**Commit message:** `fix(prompt): clarify gather agent step 6 output format to {"recipes": [...]}`
