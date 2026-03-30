"""household-manager-api tool for the Robotina routing agent.

HouseholdManagerApiTool is a generic HTTP client for the household-manager REST API.
Auth is injected invisibly at construction — the agent never sees tokens or household IDs.

Per-job injection pattern (locked Phase 4 constraint):
    tools.append(HouseholdManagerApiTool(household_id=task_input.household_id))

401/403 → raise RuntimeError (hard stop — agent loop terminates, step marked FAILED).
Other non-2xx → return structured error dict (agent can recover and report).

NOTE — household_id injection into request paths/params is deferred (Phase 7 scope
decision). self.household_id is stored for future use when endpoint-specific injection
patterns are determined from skill files (recipes_get.md, meal_plan.md, etc.).
The agent is expected to include household_id in the path or query args it passes.
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class HouseholdManagerApiTool(BaseTool):
    """LangChain tool for calling the household-manager REST API.

    Generic HTTP client: agent passes method, path, optional body, optional query.
    The tool injects the Authorization header automatically.

    household_id is stored at construction and available as self.household_id for
    future endpoint-specific injection. In Phase 7 it is NOT automatically appended
    to URLs — the caller includes it in path or query where required by the API.

    Args (via _run):
        method: HTTP method — "GET", "POST", "PATCH", "DELETE"
        path: API path relative to base URL, e.g. "/api/recipes"
        body: Optional JSON request body dict
        query: Optional URL query parameters dict

    Returns:
        Parsed JSON dict on success (2xx).
        {"error": status_code, "message": response_text} on recoverable non-2xx.

    Raises:
        RuntimeError: On 401 or 403 (unrecoverable auth error — stops agent loop).
    """

    name: str = "household-manager-api"
    description: str = (
        "Call the household-manager REST API. "
        "Read the household-manager skill before calling this tool to understand "
        "available endpoints, pagination, and error codes. "
        "Args: method (str) — HTTP method (GET/POST/PATCH/DELETE). "
        "path (str) — API path relative to base URL (e.g. /api/recipes). "
        "body (dict | None) — JSON request body for POST/PATCH. "
        "query (dict | None) — URL query parameters for filtering/pagination."
    )

    # Injected at construction — agent never sees or reasons about household_id.
    # Phase 7 scope: stored for future endpoint-specific injection; NOT auto-appended
    # to every request. See module docstring for rationale.
    household_id: str

    def _run(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        query: dict | None = None,
    ) -> dict | str:
        """Call household-manager API. Returns parsed JSON or raises on auth errors.

        Note: self.household_id is available but NOT automatically injected into
        the request URL in Phase 7. The agent includes household_id in path/query
        where required by the API (per household-manager skill files).
        """
        api_key = os.environ["HOUSEHOLD_MANAGER_API_KEY"]
        base_url = os.environ.get("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")

        async def _call() -> dict | str:
            async with httpx.AsyncClient() as client:
                resp = await client.request(
                    method=method.upper(),
                    url=f"{base_url}{path}",
                    headers={"Authorization": f"Bearer {api_key}"},
                    params=query,
                    json=body,
                )
                if resp.status_code in (401, 403):
                    raise RuntimeError(
                        f"household-manager-api: unrecoverable auth error "
                        f"(status={resp.status_code}). Check HOUSEHOLD_MANAGER_API_KEY env var."
                    )
                if not resp.is_success:
                    return {"error": resp.status_code, "message": resp.text}
                return resp.json()

        try:
            result = asyncio.run(_call())
        except RuntimeError:
            raise  # 401/403 must propagate (hard stop)
        except Exception as exc:
            logger.error(
                "household-manager-api | method=%s path=%s error=%s",
                method.upper(), path, exc,
            )
            return {"error": "request_failed", "message": str(exc)}
        logger.info(
            "household-manager-api | method=%s path=%s",
            method.upper(),
            path,
        )
        return result

    async def _arun(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        query: dict | None = None,
    ) -> dict | str:
        return self._run(method, path, body, query)
