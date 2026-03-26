"""start-workflow tool for the handle-incoming-message agent.

StartWorkflowTool creates a WorkflowRun record and all WorkflowRunStep records,
enqueues the first step, and returns the workflow_run_id string.

Used by the Robotina routing agent (Phase 7) when it identifies a multi-step
workflow intent. For Phase 5 this tool exists but is not yet registered in any
production agent's tools list — it is tested in isolation via test_start_workflow_tool.py.

Pattern: BaseTool subclass (same pattern as ReadSkillTool from Phase 4).
Session management: creates and closes its own session via SessionLocal() (D-10).
"""
from __future__ import annotations

import logging
import os

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class StartWorkflowTool(BaseTool):
    """LangChain tool that initiates a multi-step workflow.

    Creates a WorkflowRun + all WorkflowRunStep records with PENDING status,
    enqueues the first step to the agent-tasks queue, and returns the
    workflow_run_id string.

    Args (via _run):
        workflow_type: Workflow identifier (e.g. "add-recipe"). Must exist in WORKFLOW_REGISTRY.
        shared_context: Dict containing everything steps need but shouldn't own:
                        reply_context, household_id, recipe_query, etc.
                        Stored immutably on WorkflowRun — never modified by steps.

    Returns:
        workflow_run_id: UUID string identifying the created WorkflowRun.
    """

    name: str = "start-workflow"
    description: str = (
        "Initiate a multi-step workflow. Creates a WorkflowRun and enqueues the first step. "
        "Returns the workflow_run_id. Use this for complex multi-step tasks like adding a recipe."
        "\n\nArgs:\n"
        "  workflow_type (str): Workflow name, e.g. 'add-recipe'.\n"
        "  shared_context (dict): Context dict with reply_context, household_id, and task-specific fields."
    )

    def _run(self, workflow_type: str, shared_context: dict) -> str:
        """Create and enqueue a workflow. Returns workflow_run_id.

        Session lifecycle: creates a new session, closes it in a finally block (D-10).
        Queue: connects to agent-tasks via REDIS_URL env var.
        """
        from redis import Redis
        from rq import Queue

        from robotina.db import SessionLocal
        from robotina.queue import workflow_runner

        household_id = shared_context.get("household_id", "")
        session = SessionLocal()
        try:
            queue = Queue(
                "agent-tasks",
                connection=Redis.from_url(
                    os.environ.get("REDIS_URL", "redis://localhost:6379")
                ),
            )
            workflow_run_id = workflow_runner.start_workflow(
                workflow_type=workflow_type,
                shared_context=shared_context,
                household_id=household_id,
                queue=queue,
                session=session,
            )
            logger.info(
                "start-workflow tool | workflow_type=%s run_id=%s",
                workflow_type,
                workflow_run_id,
            )
            return workflow_run_id
        finally:
            session.close()

    async def _arun(self, workflow_type: str, shared_context: dict) -> str:
        return self._run(workflow_type, shared_context)
