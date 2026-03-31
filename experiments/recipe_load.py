"""Recipe Load experiment script.

Runs the recipe-load agent against 4 edge cases: happy path, missing foods,
ambiguous names, and null units. Each case is traced to LangWatch with
prompt version and model config metadata (OBS-04).

Usage:
    uv run experiments.recipe_load

Prerequisites:
    LANGWATCH_API_KEY env var set
    RECIPE_LOAD_API_TOKEN env var set
    HOUSEHOLD_MANAGER_API_KEY env var set
    HOUSEHOLD_MANAGER_BASE_URL env var set
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import langwatch
import langwatch.langchain
from langchain_core.runnables import RunnableConfig
from langwatch.client import Client as LangWatchClient

from robotina.queue.task_types import RecipeData, RecipeIngredient, RecipeStep

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

TEST_HOUSEHOLD_ID = "experiment-household"

TEST_CASES = [
    {
        "label": "Case 1: Happy path",
        "recipe": RecipeData(
            name="Tortilla Espanola",
            description="Receta clasica espanola con huevos y patatas",
            servings_qty=4,
            servings_unit="porciones",
            prep_time=15,
            cook_time=20,
            total_time=35,
            source_url="https://example.com/tortilla",
            ingredients=[
                RecipeIngredient(food_name="Huevo", unit_name="unidad", quantity=6, note=None),
                RecipeIngredient(food_name="Patata", unit_name="kilogramo", quantity=0.5, note="cortadas finas"),
            ],
            steps=[
                RecipeStep(body="Batir los huevos con sal.", title=None),
                RecipeStep(body="Freir las patatas en aceite hasta dorar.", title=None),
                RecipeStep(body="Mezclar huevos y patatas, cocinar a fuego lento.", title=None),
            ],
        ),
    },
    {
        "label": "Case 2: Missing food (zero matches)",
        "recipe": RecipeData(
            name="Test Recipe Missing Food",
            description="Receta de prueba con ingrediente inexistente",
            servings_qty=2,
            servings_unit="porciones",
            prep_time=10,
            cook_time=15,
            total_time=25,
            source_url=None,
            ingredients=[
                RecipeIngredient(food_name="Huevo", unit_name="unidad", quantity=3, note=None),
                RecipeIngredient(food_name="Xylofrutonium", unit_name="gramo", quantity=100, note=None),
            ],
            steps=[
                RecipeStep(body="Preparar los ingredientes.", title=None),
            ],
        ),
    },
    {
        "label": "Case 3: Ambiguous food name",
        "recipe": RecipeData(
            name="Test Recipe Ambiguous",
            description="Receta de prueba con nombre ambiguo",
            servings_qty=2,
            servings_unit="porciones",
            prep_time=5,
            cook_time=10,
            total_time=15,
            source_url=None,
            ingredients=[
                RecipeIngredient(food_name="Aceite", unit_name="cucharada", quantity=2, note=None),
            ],
            steps=[
                RecipeStep(body="Calentar el aceite.", title=None),
            ],
        ),
    },
    {
        "label": "Case 4: Null unit_name",
        "recipe": RecipeData(
            name="Test Recipe No Unit",
            description="Receta de prueba sin unidad",
            servings_qty=1,
            servings_unit="porcion",
            prep_time=5,
            cook_time=0,
            total_time=5,
            source_url=None,
            ingredients=[
                RecipeIngredient(food_name="Sal", unit_name=None, quantity=None, note="al gusto"),
            ],
            steps=[
                RecipeStep(body="Anadir sal al gusto.", title=None),
            ],
        ),
    },
]


def build_agent():
    """Build recipe-load agent, same as run_task() but without RQ."""
    from robotina.agent.agents import get_agent_config
    from robotina.agent.tools.read_skill import SkillSet, build_read_skill_tool
    from robotina.llm import make_backend

    config = get_agent_config("recipe-load")
    backend = make_backend(config.model_config)

    skill_sets = [SkillSet(s) for s in config.skills]
    skill_index = "\n\n".join(ss.index_content for ss in skill_sets)
    tools = list(config.tools)
    if skill_sets:
        tools.append(build_read_skill_tool(skill_sets))

    # Inject HouseholdManagerApiTool -- same pattern as run_task() for recipe-load
    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    tools.append(HouseholdManagerApiTool(household_id=TEST_HOUSEHOLD_ID))

    prompt_text = Path(config.prompt_path).read_text()
    if skill_index:
        prompt_text = prompt_text + "\n\n" + skill_index

    agent = backend.create_agent(system_prompt=prompt_text, tools=tools)
    return agent, config


def extract_json_output(result: dict) -> dict:
    """Extract JSON from the last assistant message in agent result.

    Per Pitfall 4: create_react_agent returns {"messages": [...]}.
    The agent's prompt instructs it to respond with JSON.
    """
    messages = result.get("messages", [])
    for msg in reversed(messages):
        # Only inspect AI messages -- skip tool responses which also contain JSON
        if getattr(msg, "type", None) not in ("ai", "AIMessageChunk"):
            continue
        content = getattr(msg, "content", None) or ""
        # AIMessage.content can be a list of content blocks (Anthropic tool-use format)
        if isinstance(content, list):
            content = " ".join(
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        if not content:
            continue
        # Handle markdown code blocks: ```json ... ```
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json) and last line (```)
            json_lines = []
            for line in lines[1:]:
                if line.strip() == "```":
                    break
                json_lines.append(line)
            text = "\n".join(json_lines)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Scan for first JSON object or array in case of leading prose
        for start_char in ('{', '['):
            idx = text.find(start_char)
            if idx != -1:
                try:
                    return json.loads(text[idx:])
                except json.JSONDecodeError:
                    pass
        continue
    logger.warning("Could not extract JSON from agent output, returning raw messages")
    return {"raw_messages": [str(m) for m in messages[-3:]]}


def _build_user_message(recipe: RecipeData) -> str:
    """Build user message with full recipe data for the agent.

    The agent needs the complete recipe structure (ingredients with food_name,
    unit_name, quantities, steps, metadata) to resolve names and create the
    recipe via the household-manager API.
    """
    recipe_json = recipe.model_dump(mode="json")
    return (
        f"Load recipe: {recipe.name}\n\n"
        f"Recipe data:\n{json.dumps(recipe_json, ensure_ascii=False, indent=2)}"
    )


def main() -> None:
    """Run 4 recipe-load experiment cases and print summary."""
    agent, config = build_agent()

    print("\n" + "=" * 60)
    print("recipe-load experiment -- 4 edge cases")
    print(f"Model: {config.model_config.get('model')} ({config.model_config.get('provider')})")
    print("=" * 60)

    results_summary = []
    run_name = f"prompt-V001 model={config.model_config.get('model')}"

    for case in TEST_CASES:
        label = case["label"]
        recipe = case["recipe"]
        user_message = _build_user_message(recipe)

        print(f"\n--- {label} ---")
        print(f"Recipe: {recipe.name}")
        print(f"Ingredients: {len(recipe.ingredients)}")
        print(f"Input length: {len(user_message)} chars")

        tracer = langwatch.langchain.LangChainTracer(
            metadata={
                "experiment": "recipe-load",
                "prompt_version": "V001",
                "run_name": run_name,
                "case_label": label,
                "task_type": "recipe-load",
                "model": config.model_config.get("model"),
                "provider": config.model_config.get("provider"),
            }
        )

        with tracer:
            try:
                result = agent.invoke(
                    {"messages": [{"role": "user", "content": user_message}]},
                    config=RunnableConfig(callbacks=[tracer]),
                )

                output = extract_json_output(result)
                output_preview = json.dumps(output, ensure_ascii=False)[:500]
                print(f"Output preview: {output_preview}")

                # Validate expected fields
                has_recipe_id = "recipe_id" in output
                has_recipe_name = "recipe_name" in output
                has_recipe_slug = "recipe_slug" in output
                missing_list = output.get("missing_ingredients", [])

                # Case-specific validations
                status = "OK"
                details = []

                if not has_recipe_id:
                    details.append("missing recipe_id")
                if not has_recipe_name:
                    details.append("missing recipe_name")
                if not has_recipe_slug:
                    details.append("missing recipe_slug")

                # Case 2: verify missing_ingredients is non-empty
                if "Missing food" in label:
                    if missing_list:
                        details.append(f"missing_ingredients={missing_list}")
                    else:
                        details.append("WARN: expected non-empty missing_ingredients")

                # Case 4: verify recipe was created despite null unit_name
                if "Null unit" in label:
                    if has_recipe_id:
                        details.append("recipe created despite null unit_name")
                    else:
                        details.append("WARN: recipe not created with null unit_name")

                if any(d.startswith("missing ") for d in details):
                    status = "WARN"
                detail_str = "; ".join(details) if details else "all fields present"

                with tracer.trace.span(type="evaluation", name=label) as eval_span:
                    eval_span.update(
                        passed=has_recipe_id and status == "OK",
                        details=detail_str,
                    )

                results_summary.append({
                    "case": label,
                    "status": status,
                    "details": detail_str,
                    "recipe_id": output.get("recipe_id"),
                    "missing_ingredients": missing_list,
                })

            except Exception as e:
                logger.exception("%s failed: %s", label, e)
                with tracer.trace.span(type="evaluation", name=label) as eval_span:
                    eval_span.update(passed=False, details=str(e))
                results_summary.append({
                    "case": label,
                    "status": f"ERROR: {e}",
                    "details": str(e),
                    "recipe_id": None,
                    "missing_ingredients": [],
                })

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results_summary:
        print(f"  {r['case']}: {r['status']} ({r['details']})")
        if r["recipe_id"]:
            print(f"    recipe_id: {r['recipe_id']}")
        if r["missing_ingredients"]:
            print(f"    missing_ingredients: {r['missing_ingredients']}")

    # Flush traces
    if LangWatchClient._tracer_provider is not None:
        LangWatchClient._tracer_provider.force_flush()

    errors = [r for r in results_summary if r["status"].startswith("ERROR")]
    if errors:
        print(f"\n{len(errors)} case(s) failed with errors.")
        raise SystemExit(1)

    print("\nAll cases completed. Check LangWatch for traces.")


if __name__ == "__main__":
    main()
