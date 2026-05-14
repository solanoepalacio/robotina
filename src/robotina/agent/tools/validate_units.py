"""validate-units tool: resolve Spanish unit names to household-manager unit ids.

Constructed once per job inside ``robotina.queue.jobs.run_task`` (per-job tool
injection pattern). Takes no constructor args (per D-10 — the unit catalog is
shared across households in the v1 setup).

Returns ``{"matched": [{name, id}], "unmatched": [{name, id: None}]}``.

401/403 from household-manager → ``raise RuntimeError`` (unrecoverable). Other
non-2xx return a structured error dict.
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


class ValidateUnitsArgs(BaseModel):
    """Strict argument schema for ValidateUnitsTool.

    ``extra='forbid'`` turns LLM-hallucinated extra fields into a recoverable
    ``ToolMessage(status='error')`` on the agent's next turn — see
    ``ValidateFoodsArgs`` rationale.
    """

    model_config = ConfigDict(extra="forbid")

    names: list[str] = Field(
        description="Spanish unit names to resolve against the household-manager unit catalog.",
    )


class ValidateUnitsTool(BaseTool):
    """Resolve Spanish unit names to household-manager unit catalog ids.

    Args (via _run):
        names: list of Spanish unit names.

    Returns:
        ``{"matched": [{"name": str, "id": str}], "unmatched": [{"name": str, "id": None}]}``

    Raises:
        RuntimeError: On 401 or 403 from household-manager (unrecoverable).
    """

    name: str = "validate-units"
    description: str = (
        "Resolve a list of Spanish unit names against the household catalog. "
        "Returns matched entries with catalog ids and unmatched names with id=null. "
        "Use this once you have collected the ingredient unit names; "
        "unmatched units indicate the ingredient should be dropped from the recipe. "
        "Do NOT pass the catalog as input — the tool fetches it internally."
    )
    args_schema: type[BaseModel] = ValidateUnitsArgs

    def _run(self, names: list[str]) -> dict:
        api_key = os.environ["HOUSEHOLD_MANAGER_API_KEY"]
        base_url = os.environ.get("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")

        async def _fetch() -> dict | list:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{base_url}/api/units",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code in (401, 403):
                    raise RuntimeError(
                        f"validate-units: unrecoverable auth error "
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
            logger.error("validate-units | error=%s", exc)
            return {"error": "request_failed", "message": str(exc)}

        if isinstance(catalog, dict) and "error" in catalog:
            return catalog

        if not isinstance(catalog, list):
            return {"error": "invalid_catalog", "message": f"expected list, got {type(catalog).__name__}"}

        result = resolve_catalog(category="unit", catalog=catalog, names=names)
        logger.info(
            "validate-units | input=%d matched=%d unmatched=%d",
            len(names), len(result["matched"]), len(result["unmatched"]),
        )
        return result

    async def _arun(self, names: list[str]) -> dict:
        return self._run(names)
