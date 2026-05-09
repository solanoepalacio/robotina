# Gather: Recipe web search

## Goal
Search recipes across multiple websites and extract structured data from each result.

## Process

### 1. Build search queries
Build 3 search queries, in Spanish, around the recipe name. Use natural phrases that an Argentine home cook would actually type. The query strings themselves stay in Spanish; only this instructional text is in English.
- Examples for "Pasta Bolognesa": `"Pasta Bolognesa facil de preparar"`, `"pasta bolognesa deliciosa"`, `"receta casera de salsa bolognesa"`
- Prioritize Argentine and Latin American recipe sites.

### 2. Search with web-search
Call the `web-search` tool once per query. Each call returns up to 3 results, each with these fields:
- `title`: page title
- `url`: result URL
- `content`: short text summary of the page
- `raw_content`: full HTML page content (may be `null`)
- `score`: relevance score for the result

### 3. Extract data from each result
For each result that has `raw_content` available, try to extract structured recipe data:
- Title, ingredients, instructions, times, servings.
- If you cannot extract structured data from the HTML, fall back to the `content` summary as the source.

### 4. Error handling
- If a single result has no usable data, skip it and move on to the next.
- Only fail if **every** result is unusable.
- One usable source is enough to continue the pipeline.

## Output format
Your final response must be a JSON object with the list of recipes you found. Each recipe is an object with the fields you were able to extract:
```json
{
  "recipes": [
    {
      "title": "nombre de la receta",
      "url": "URL fuente",
      "ingredients": ["ingrediente 1", "ingrediente 2"],
      "instructions": ["paso 1", "paso 2"],
      "prep_time": 15,
      "cook_time": 30,
      "total_time": 45,
      "servings": "4 porciones"
    }
  ]
}
```

**JSON output rules.** Use the JSON literal `null` for missing optional fields — never the Python value `None`, never the bare word `none`, never an empty string in place of `null`. Booleans are `true` and `false`, lowercase. Numeric fields are bare numbers, never quoted. Do not omit optional fields when you have decided their value is "missing" — emit them with `null`.
