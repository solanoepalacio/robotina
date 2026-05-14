"""validate-foods tool: resolve Spanish food names to household-manager food ids.

Constructed once per job inside ``robotina.queue.jobs.run_task`` (per-job tool
injection pattern). Takes no constructor args (per D-10 — the food catalog is
shared across households in the v1 setup).

Returns ``{"matched": [{name, id}], "unmatched": [{name, id: None}]}``. The
agent's prompt explains: keep matched items as resolved ingredients, drop
unmatched names from ``ingredients[]`` and append them to
``missing_ingredients``.

401/403 from household-manager → ``raise RuntimeError`` (unrecoverable; the
agent loop terminates and the workflow step is marked FAILED). Other non-2xx
return a structured error dict the agent can read and react to.
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from robotina.agent.tools._catalog_match import resolve_catalog

logger = logging.getLogger(__name__)


class ValidateFoodsArgs(BaseModel):
    """Strict argument schema for ValidateFoodsTool.

    ``extra='forbid'`` makes any unknown LLM-emitted field raise ``ValidationError``
    at ``tool.invoke()`` time. The langgraph ``ToolNode`` wraps that error in a
    ``ToolMessage(status='error')`` the agent sees on its next turn, so a single
    LLM hallucination (e.g. an extra ``catalog`` field) becomes a recoverable
    error instead of a ``TypeError`` that kills the workflow.
    """

    model_config = ConfigDict(extra="forbid")

    names: list[str] = Field(
        description="Spanish food names to resolve against the household-manager food catalog.",
    )


class ValidateFoodsTool(BaseTool):
    """Resolve Spanish food names to household-manager food catalog ids.

    Args (via _run):
        names: list of Spanish food names.

    Returns:
        ``{"matched": [{"name": str, "id": str}], "unmatched": [{"name": str, "id": None}]}``

    Raises:
        RuntimeError: On 401 or 403 from household-manager (unrecoverable).
    """

    name: str = "validate-foods"
    description: str = (
        "Resolve a list of Spanish food names against the household catalog. "
        "Returns matched entries with catalog ids and unmatched names with id=null. "
        "Use this once you have collected the ingredient food names; "
        "items in `unmatched` should be dropped from the recipe and recorded in `missing_ingredients`. "
        "Do NOT pass the catalog as input — the tool fetches it internally."
    )
    args_schema: type[BaseModel] = ValidateFoodsArgs

    def _run(self, names: list[str]) -> dict:
        api_key = os.environ["HOUSEHOLD_MANAGER_API_KEY"]
        base_url = os.environ.get("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")

        async def _fetch() -> dict | list:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{base_url}/api/foods",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code in (401, 403):
                    raise RuntimeError(
                        f"validate-foods: unrecoverable auth error "
                        f"(status={resp.status_code}). Check HOUSEHOLD_MANAGER_API_KEY env var."
                    )
                if not resp.is_success:
                    return {"error": resp.status_code, "message": resp.text}
                return resp.json()

        try:
            catalog = asyncio.run(_fetch())
        except RuntimeError:
            raise
        except Exception as exc:
            logger.error("validate-foods | error=%s", exc)
            return {"error": "request_failed", "message": str(exc)}

        if isinstance(catalog, dict) and "error" in catalog:
            return catalog

        if not isinstance(catalog, list):
            return {"error": "invalid_catalog", "message": f"expected list, got {type(catalog).__name__}"}

        result = resolve_catalog(category="food", catalog=catalog, names=names)
        logger.info(
            "validate-foods | input=%d matched=%d unmatched=%d",
            len(names), len(result["matched"]), len(result["unmatched"]),
        )
        return result

    async def _arun(self, names: list[str]) -> dict:
        return self._run(names)
