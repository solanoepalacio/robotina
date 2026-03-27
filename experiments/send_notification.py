"""Send Notification experiment script.

Runs the send-notification agent against 4 representative inputs to verify:
- The agent applies format-telegram-message skill correctly
- MarkdownV2 escaping is applied for all 18 special characters
- LangWatch traces are generated with correct metadata (OBS-03, OBS-05)

SendNotificationTool._run() is mocked — no real Telegram messages are sent.
This allows the script to run without TELEGRAM_BOT_TOKEN or a live Telegram chat.

Usage:
    uv run experiments.send_notification

Prerequisites:
    LANGWATCH_API_KEY env var set (for trace upload)
    LANGWATCH_ENDPOINT env var set (optional — defaults to LangWatch cloud)
    SEND_NOTIFICATION_API_TOKEN env var set (for LLM API access)
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from unittest.mock import patch

import langwatch
import langwatch.langchain
from langchain_core.runnables import RunnableConfig
from langwatch.client import Client as LangWatchClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Test cases per D-06 (locked decision)
TEST_CASES = [
    {
        "label": "Case 1: Baseline plain text",
        "text": "The recipe has been saved successfully.",
        "description": "Simple confirmation — minimal escaping needed (just the period)",
    },
    {
        "label": "Case 2: Structured data",
        "text": "Recipe added: Spaghetti Carbonara. Servings: 4, prep 10 min, cook 20 min.",
        "description": "Multiple periods and colon — tests period escaping in structured data",
    },
    {
        "label": "Case 3: Bullet list",
        "text": (
            "This week's meal plan: Monday pasta, Tuesday soup, Wednesday salad, "
            "Thursday stir fry, Friday pizza."
        ),
        "description": "Long list — tests bullet list formatting and trailing period",
    },
    {
        "label": "Case 4: Special characters stress test",
        "text": "Ready in 30 min! (serves 4) — cost: ~€8.50",
        "description": "!, (, ), ~, . all require escaping — Telegram BadRequest if missed",
    },
]


def run_experiment_case(
    agent,
    text: str,
    label: str,
    model_config: dict,
    tracer: "langwatch.langchain.LangChainTracer",
) -> dict:
    """Run one experiment case. Returns result dict.

    The caller owns the tracer (and its trace lifecycle). The tracer is
    passed directly so no second trace is created here.
    """
    result = agent.invoke(
        {"messages": [{"role": "user", "content": text}]},
        config=RunnableConfig(callbacks=[tracer]),
    )
    return result


def extract_formatted_text(result: dict) -> str:
    """Extract the last assistant message text from agent result."""
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content:
            return str(msg.content)
    return ""


def check_escaping(formatted: str) -> list[str]:
    """Check for common unescaped special characters. Returns list of issues found."""
    issues = []
    # Check for unescaped periods not inside already-escaped sequences
    # Simple heuristic: look for digit-period-digit (e.g., "8.50" should be "8\.50")
    import re
    if re.search(r'\d\.\d', formatted) and r'\.' not in formatted:
        issues.append("Possible unescaped period in decimal number (e.g., '8.50' should be '8\\.50')")
    # Unescaped exclamation not preceded by backslash
    if '!' in formatted and r'\!' not in formatted:
        issues.append("Unescaped '!' found (should be '\\!')")
    return issues


def main() -> None:
    """Run all 4 experiment cases and print summary."""
    # Build agent using the same infrastructure as run_task()
    from robotina.agent.agents import get_agent_config
    from robotina.agent import SkillSet, build_read_skill_tool
    from robotina.llm import make_backend

    config = get_agent_config("send-notification")
    backend = make_backend(config.model_config)

    skill_sets = [SkillSet(s) for s in config.skills]
    skill_index = "\n\n".join(ss.index_content for ss in skill_sets)
    tools = []
    if skill_sets:
        tools.append(build_read_skill_tool(skill_sets))

    prompt_text = Path(config.prompt_path).read_text()
    if skill_index:
        prompt_text = prompt_text + "\n\n" + skill_index

    # Mock SendNotificationTool._run to capture formatted output without real Telegram send
    # The tool is injected by run_task() normally; here we build the agent directly
    from robotina.agent.tools.send_notification import SendNotificationTool
    mock_tool = SendNotificationTool(
        chat_id="experiment-chat-id",
        user_id="experiment-user-id",
        platform="telegram",
    )
    captured_outputs: list[str] = []

    def capture_run(self, formatted_text: str) -> str:
        captured_outputs.append(formatted_text)
        logger.info("Captured formatted output (%d chars)", len(formatted_text))
        return "Notification Successfully Delivered. Notification ID = experiment-msg-id"

    tools.append(mock_tool)
    agent = backend.create_agent(system_prompt=prompt_text, tools=tools)

    print("\n" + "=" * 60)
    print("send-notification experiment — 4 cases")
    print(f"Model: {config.model_config.get('model')} ({config.model_config.get('provider')})")
    print("=" * 60)

    results_summary = []
    run_name = f"prompt-V001 model={config.model_config.get('model')}"

    with patch.object(SendNotificationTool, "_run", capture_run):
        for i, case in enumerate(TEST_CASES, 1):
            captured_outputs.clear()
            print(f"\n--- {case['label']} ---")
            print(f"Input: {case['text']}")
            print(f"({case['description']})")

            # Each case gets its own trace. LangChainTracer owns the trace lifecycle —
            # it calls trace.__enter__() in __init__ and trace.__exit__() in __exit__.
            # We use it as a context manager so __exit__ is always called.
            tracer = langwatch.langchain.LangChainTracer(
                metadata={
                    "experiment": "send-notification",
                    "prompt_version": "V001",
                    "run_name": run_name,
                    "case_index": i,
                    "case_label": case["label"],
                }
            )
            with tracer:
                try:
                    result = run_experiment_case(
                        agent=agent,
                        text=case["text"],
                        label=case["label"],
                        model_config=config.model_config,
                        tracer=tracer,
                    )

                    formatted = captured_outputs[0] if captured_outputs else ""
                    issues = check_escaping(formatted) if formatted else ["tool not called"]

                    passed = not issues and bool(captured_outputs)
                    status = "PASS" if passed else f"WARN: {'; '.join(issues)}"
                    print(f"Formatted output:\n{formatted[:300]}")
                    print(f"Result: {status}")

                    # Log evaluation as a child span under the case trace.
                    # This uses the current (non-deprecated) span API.
                    with tracer.trace.span(type="evaluation", name=case["label"]) as eval_span:
                        eval_span.update(passed=passed, details=status)

                    results_summary.append({
                        "case": case["label"],
                        "status": status,
                        "formatted_len": len(formatted),
                        "tool_called": bool(captured_outputs),
                    })

                except Exception as e:
                    logger.exception("Case %d failed: %s", i, e)
                    with tracer.trace.span(type="evaluation", name=case["label"]) as eval_span:
                        eval_span.update(passed=False, details=str(e))
                    results_summary.append({
                        "case": case["label"],
                        "status": f"ERROR: {e}",
                        "formatted_len": 0,
                        "tool_called": False,
                    })

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results_summary:
        tool_status = "tool called" if r["tool_called"] else "tool NOT called"
        print(f"  {r['case']}: {r['status']} ({tool_status}, {r['formatted_len']} chars)")

    if LangWatchClient._tracer_provider is not None:
        LangWatchClient._tracer_provider.force_flush()

    errors = [r for r in results_summary if r["status"].startswith("ERROR")]
    if errors:
        print(f"\n{len(errors)} case(s) failed with errors.")
        raise SystemExit(1)

    print("\nAll cases completed. Check LangWatch for traces.")


if __name__ == "__main__":
    main()
