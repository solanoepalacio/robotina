# Skill: recipe-research

A four-step recipe research pipeline. Each agent runs exactly one step.

## Steps

1. **gather** — Search the web for recipes using Spanish search queries. Read `recipe-research/gather.md` for the detailed instructions.
2. **instructions** — Build base instructions by consensus across the gathered recipes. Read `recipe-research/instructions.md`.
3. **ingredients** — Extract and verify ingredients against the household-manager API. Read `recipe-research/ingredients.md`.
4. **metadata** — Estimate prep time, cook time, and servings. Read `recipe-research/metadata.md`.

## Important

- All content the model produces — recipe names, ingredient names, step bodies, descriptions — must be written in Spanish, in the natural register an Argentine home cook would use.
- Search queries must read like natural phrases an Argentine home cook would type into a search engine.
- Use the `read-skill` tool with the path `recipe-research/<step>.md` to load the detailed instructions for your step.
