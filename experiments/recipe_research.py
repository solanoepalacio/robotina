"""Recipe Research experiment script.

Runs the full 4-step recipe research pipeline (gather -> instructions ->
ingredients -> metadata) against a hardcoded test recipe. Each step is
traced to LangWatch with prompt version and model config metadata (OBS-04).

Usage:
    uv run experiments.recipe_research

Prerequisites:
    LANGWATCH_API_KEY env var set
    TAVILY_API_KEY env var set
    RECIPE_RESEARCH_GATHER_API_TOKEN env var set
    RECIPE_RESEARCH_INSTRUCTIONS_API_TOKEN env var set
    RECIPE_RESEARCH_INGREDIENTS_API_TOKEN env var set
    RECIPE_RESEARCH_METADATA_API_TOKEN env var set
    HOUSEHOLD_MANAGER_API_KEY env var set (for ingredients step)
    HOUSEHOLD_MANAGER_BASE_URL env var set (for ingredients step)
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

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Test recipe -- a representative Argentine/Latin dish per CONTEXT.md specifics
TEST_RECIPE = "Empanadas de carne"
TEST_HOUSEHOLD_ID = "experiment-household"

STEPS = [
    {
        "task_type": "recipe-research-gather",
        "label": "Step 1: Gather",
        "extra_tools_fn": "_make_gather_tools",
    },
    {
        "task_type": "recipe-research-instructions",
        "label": "Step 2: Instructions",
        "extra_tools_fn": None,
    },
    {
        "task_type": "recipe-research-ingredients",
        "label": "Step 3: Ingredients",
        "extra_tools_fn": "_make_ingredients_tools",
    },
    {
        "task_type": "recipe-research-metadata",
        "label": "Step 4: Metadata",
        "extra_tools_fn": None,
    },
]


def _make_gather_tools():
    from robotina.agent.tools.web_search import WebSearchTool
    return [WebSearchTool()]


def _make_ingredients_tools():
    from robotina.agent.tools.household_manager_api import HouseholdManagerApiTool
    return [HouseholdManagerApiTool(household_id=TEST_HOUSEHOLD_ID)]


def build_agent(task_type: str, extra_tools_fn: str | None):
    """Build agent for a given task_type, same as run_task() but without RQ."""
    from robotina.agent.agents import get_agent_config
    from robotina.agent.tools.read_skill import SkillSet, build_read_skill_tool
    from robotina.llm import make_backend

    config = get_agent_config(task_type)
    backend = make_backend(config.model_config)

    skill_sets = [SkillSet(s) for s in config.skills]
    skill_index = "\n\n".join(ss.index_content for ss in skill_sets)
    tools = list(config.tools)
    if skill_sets:
        tools.append(build_read_skill_tool(skill_sets))

    # Inject step-specific tools
    if extra_tools_fn:
        fn = globals()[extra_tools_fn]
        tools.extend(fn())

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
        # Only inspect AI messages — skip tool responses which also contain JSON
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


def _gathered_recipes(artifacts: dict) -> list:
    """Extract recipe list from gather artifact (list or {"recipes": [...]})."""
    gather = artifacts.get("gather", [])
    if isinstance(gather, list):
        return gather
    return gather.get("recipes", [])


def _as_dict(artifact) -> dict:
    """Return artifact as dict, wrapping a bare list as an empty dict fallback."""
    return artifact if isinstance(artifact, dict) else {}


def build_user_message(step_index: int, artifacts: dict) -> str:
    """Build the user message for each step based on accumulated artifacts."""
    if step_index == 0:
        # Gather: just the recipe query
        return TEST_RECIPE
    elif step_index == 1:
        # Instructions: query + gathered recipes
        gathered = _gathered_recipes(artifacts)
        return (
            f"Create baseline instructions for: {TEST_RECIPE}\n\n"
            f"Gathered recipes:\n{json.dumps(gathered, ensure_ascii=False, indent=2)}"
        )
    elif step_index == 2:
        # Ingredients: query + draft instructions + gathered recipes
        instructions = artifacts.get("instructions", {}).get("draft_instructions", [])
        gathered = _gathered_recipes(artifacts)
        instructions_text = "\n".join(
            f"- {s.get('body', s) if isinstance(s, dict) else s}" for s in instructions
        )
        return (
            f"Extract and verify ingredients for: {TEST_RECIPE}\n\n"
            f"Draft instructions:\n{instructions_text}\n\n"
            f"Gathered recipes:\n{json.dumps(gathered, ensure_ascii=False, indent=2)}"
        )
    elif step_index == 3:
        # Metadata: query + all prior artifacts
        instr = _as_dict(artifacts.get("instructions", {}))
        ingr = _as_dict(artifacts.get("ingredients", {}))
        gathered = _gathered_recipes(artifacts)
        instructions_text = "\n".join(
            f"- {s.get('body', s) if isinstance(s, dict) else s}"
            for s in instr.get("draft_instructions", [])
        )
        ingredients_text = "\n".join(
            f"- {i.get('food_name', '')}: {i.get('quantity', '')} {i.get('unit_name', '')}"
            for i in ingr.get("ingredients", [])
        )
        return (
            f"Estimate metadata for: {TEST_RECIPE}\n\n"
            f"Name: {instr.get('draft_name', TEST_RECIPE)}\n"
            f"Description: {instr.get('draft_description', '')}\n\n"
            f"Instructions:\n{instructions_text}\n\n"
            f"Ingredients:\n{ingredients_text}\n\n"
            f"Gathered recipes:\n{json.dumps(gathered, ensure_ascii=False, indent=2)}"
        )
    return TEST_RECIPE


def main() -> None:
    """Run the full 4-step recipe research pipeline."""
    print("\n" + "=" * 60)
    print(f"recipe-research experiment -- {TEST_RECIPE}")
    print("=" * 60)

    accumulated_artifacts: dict[str, dict] = {}
    step_keys = ["gather", "instructions", "ingredients", "metadata"]
    results_summary = []

    for i, (step_def, step_key) in enumerate(zip(STEPS, step_keys)):
        task_type = step_def["task_type"]
        label = step_def["label"]
        extra_tools_fn = step_def["extra_tools_fn"]

        print(f"\n--- {label} ({task_type}) ---")

        agent, config = build_agent(task_type, extra_tools_fn)
        run_name = f"prompt-V001 model={config.model_config.get('model')}"
        user_message = build_user_message(i, accumulated_artifacts)

        print(f"Model: {config.model_config.get('model')} ({config.model_config.get('provider')})")
        print(f"Input length: {len(user_message)} chars")

        tracer = langwatch.langchain.LangChainTracer(
            metadata={
                "experiment": "recipe-research",
                "prompt_version": "V001",
                "run_name": run_name,
                "step": step_key,
                "step_index": i,
                "task_type": task_type,
                "model": config.model_config.get("model"),
                "provider": config.model_config.get("provider"),
                "test_recipe": TEST_RECIPE,
            }
        )

        with tracer:
            try:
                result = agent.invoke(
                    {"messages": [{"role": "user", "content": user_message}]},
                    config=RunnableConfig(callbacks=[tracer]),
                )

                output = extract_json_output(result)
                accumulated_artifacts[step_key] = output

                output_keys = list(output.keys()) if isinstance(output, dict) else f"<list len={len(output)}>"
                print(f"Output: {output_keys}")
                print(f"Output preview: {json.dumps(output, ensure_ascii=False)[:500]}")

                with tracer.trace.span(type="evaluation", name=label) as eval_span:
                    eval_span.update(
                        passed=bool(output and (not isinstance(output, dict) or "raw_messages" not in output)),
                        details=f"Output: {output_keys}",
                    )

                results_summary.append({
                    "step": label,
                    "status": "OK" if not isinstance(output, dict) or "raw_messages" not in output else "WARN: no JSON extracted",
                    "output_keys": output_keys,
                })

            except Exception as e:
                logger.exception("%s failed: %s", label, e)
                with tracer.trace.span(type="evaluation", name=label) as eval_span:
                    eval_span.update(passed=False, details=str(e))
                results_summary.append({
                    "step": label,
                    "status": f"ERROR: {e}",
                    "output_keys": [],
                })
                print(f"FAILED: {e}")
                # Do not continue to next step if current step failed
                break

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results_summary:
        print(f"  {r['step']}: {r['status']} (keys: {r['output_keys']})")

    # Print final recipe if metadata step completed
    if "metadata" in accumulated_artifacts:
        recipe = accumulated_artifacts["metadata"].get("recipe", {})
        print(f"\nFinal recipe: {recipe.get('name', 'N/A')}")
        print(f"  Servings: {recipe.get('servings_qty', 'N/A')} {recipe.get('servings_unit', '')}")
        print(f"  Prep: {recipe.get('prep_time', 'N/A')} min, Cook: {recipe.get('cook_time', 'N/A')} min")
        print(f"  Ingredients: {len(recipe.get('ingredients', []))}")
        print(f"  Steps: {len(recipe.get('steps', []))}")

    # Flush traces
    if LangWatchClient._tracer_provider is not None:
        LangWatchClient._tracer_provider.force_flush()

    errors = [r for r in results_summary if r["status"].startswith("ERROR")]
    if errors:
        print(f"\n{len(errors)} step(s) failed.")
        raise SystemExit(1)

    print("\nAll steps completed. Check LangWatch for traces.")


if __name__ == "__main__":
    main()
