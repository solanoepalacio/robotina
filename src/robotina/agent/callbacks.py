"""LangChain callback handlers for Robotina agents."""
from __future__ import annotations

import logging

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)


class AgentLoggingHandler(BaseCallbackHandler):
    """LangChain callback handler for structured agent action logging.

    Logs four lifecycle events:
    - Chat model start (model name)
    - Thinking step (full content, only when reasoning_content is present)
    - Tool call (tool name + first 200 chars of input)
    - Tool result (first 200 chars of output)

    This is the single location for agent action logging. Individual agents do NOT
    need to emit their own tool-call log lines.
    """

    def on_chat_model_start(self, serialized: dict, messages: list, **kwargs) -> None:
        logger.info("LLM stream start | model=%s", serialized.get("name"))

    def on_llm_end(self, response, **kwargs) -> None:
        for gen_list in response.generations:
            for gen in gen_list:
                msg = getattr(gen, "message", None)
                thinking = msg and msg.additional_kwargs.get("reasoning_content")
                if thinking:
                    logger.info("Thinking | %s", thinking)

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
        logger.info(
            "Tool call | tool=%s input=%s",
            serialized.get("name"),
            str(input_str)[:200],
        )

    def on_tool_end(self, output: str, **kwargs) -> None:
        logger.info("Tool result | output=%s", str(output)[:200])
