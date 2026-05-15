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
from typing import Literal

import httpx
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, model_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Typed body schemas (per endpoint)
#
# Why typed instead of `dict`: when `body` is a free-form `dict`, the OpenAI
# constrained-decoder accepts `{}` and `null` as legal completions of
# `"body": ` — both pass the schema, both produce 400 from the backend, and
# the agent loops resending the same empty body forever (canelones-class bug).
#
# Enumerating every field as required-nullable forces the decoder to emit each
# key explicitly: for unknown values it picks `null`, but it cannot collapse
# the body to `{}`. The model_validator on HouseholdManagerApiArgs additionally
# forbids `null` body for POST /api/recipes, removing the last escape hatch.
#
# Today only POST /api/recipes is typed because it is the only non-GET
# endpoint actually called by an agent. When future endpoints need typed
# request bodies, expand `body` into a discriminated union or split the tool.
# ---------------------------------------------------------------------------


class CreateRecipeIngredient(BaseModel):
    """One ingredient in a POST /api/recipes body."""

    model_config = ConfigDict(extra="forbid")

    foodId: str = Field(
        description="Food UUID resolved upstream by validate-foods. Required."
    )
    unitId: str | None = Field(
        description="Unit UUID resolved upstream by validate-units; null if the ingredient has no unit."
    )
    quantity: float | None = Field(
        description="Numeric amount; may be decimal. Null if unspecified."
    )
    note: str | None = Field(
        description="Per-ingredient note (e.g. 'finely chopped'); null if none."
    )


class CreateRecipeStep(BaseModel):
    """One instruction step in a POST /api/recipes body."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(description="Instruction text for this step. Required.")
    title: str | None = Field(description="Optional step heading; null if none.")


class CreateRecipeBody(BaseModel):
    """Strict body for POST /api/recipes.

    Keys are camelCase to match the household-manager API contract. Every key
    is required at the schema level — fields the recipe might not have are
    typed as nullable so the LLM emits `null` rather than omitting them. This
    prevents the constrained decoder from satisfying the body argument with
    `{}`.

    The recipe-load agent constructs this from the snake_case `RecipeData`
    artifact by applying the rename map in its prompt.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Recipe name. Required and non-null.")
    description: str | None = Field(
        description="Plain-text description; null if none."
    )
    servingsQty: int | None = Field(
        description="Number of servings (integer); null if unknown."
    )
    servingsUnit: str | None = Field(
        description="Servings label (e.g. 'porciones'); null if unknown."
    )
    prepTime: int | None = Field(description="Prep time in minutes; null if unknown.")
    cookTime: int | None = Field(description="Cook time in minutes; null if unknown.")
    totalTime: int | None = Field(
        description="Total time in minutes; null if unknown."
    )
    sourceUrl: str | None = Field(
        description="Recipe source URL; null if not from a single source."
    )
    ingredients: list[CreateRecipeIngredient] = Field(
        description="All ingredients in display order. Use [] only if the recipe truly has none."
    )
    steps: list[CreateRecipeStep] = Field(
        description="Instruction steps in execution order. Use [] only if the recipe truly has none."
    )


class HouseholdManagerApiArgs(BaseModel):
    """Strict argument schema for HouseholdManagerApiTool.

    ``extra='forbid'`` makes any unknown LLM-emitted field raise ``ValidationError``
    at ``tool.invoke()`` time. The langgraph ``ToolNode`` wraps that error in a
    ``ToolMessage(status='error')`` the agent sees on its next turn, so a single
    LLM hallucination (e.g. extra ``response`` field) becomes a recoverable error
    instead of a ``TypeError`` that kills the workflow.

    ``body`` is typed as ``CreateRecipeBody | None`` rather than ``dict``: when
    the LLM emits a body object, it must match CreateRecipeBody field-by-field
    (required keys, nullable optionals). The ``_enforce_body_for_known_endpoints``
    model_validator additionally rejects ``null`` body for POST /api/recipes.
    """

    model_config = ConfigDict(extra="forbid")

    method: Literal["GET", "POST", "PATCH", "DELETE"] = Field(
        description="HTTP method."
    )
    path: str = Field(
        description="API path relative to base URL, e.g. /api/recipes."
    )
    body: CreateRecipeBody | None = Field(
        default=None,
        description=(
            "Request body. For POST /api/recipes this MUST be a fully-populated "
            "CreateRecipeBody (every key present; nullable fields use null when "
            "unknown). Use null only for GET / DELETE. Empty objects ({}) and "
            "null body for POST /api/recipes are rejected at validation time."
        ),
    )
    query: dict | None = Field(
        default=None,
        description="URL query parameters; null if none.",
    )

    @model_validator(mode="after")
    def _enforce_body_for_known_endpoints(self) -> HouseholdManagerApiArgs:
        if self.method == "POST" and self.path == "/api/recipes":
            if self.body is None:
                raise ValueError(
                    "POST /api/recipes requires a non-null body matching "
                    "CreateRecipeBody (keys: name, description, servingsQty, "
                    "servingsUnit, prepTime, cookTime, totalTime, sourceUrl, "
                    "ingredients, steps). Construct the body from the RecipeData "
                    "in the user message and pass it as the `body` argument — "
                    "never null, never {}."
                )
        return self


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
        "Args: method (GET/POST/PATCH/DELETE), path (e.g. /api/recipes), "
        "body (object | null), query (object | null). "
        "For POST /api/recipes the body MUST be a complete object matching "
        "CreateRecipeBody (every key present; null for unknown nullable fields) — "
        "the tool's strict schema rejects {} or null body for that endpoint at "
        "validation time, before any HTTP call. "
        "Arguments are JSON. Use JSON literals: null, true, false (not None / "
        "True / False). Strings use double quotes."
    )

    # Strict input schema: rejects unknown LLM-emitted fields with ValidationError
    # rather than letting them flow into _run() as kwargs (where they would raise
    # TypeError and crash the workflow). See HouseholdManagerApiArgs docstring.
    args_schema: type[BaseModel] = HouseholdManagerApiArgs

    # Injected at construction — agent never sees or reasons about household_id.
    # Phase 7 scope: stored for future endpoint-specific injection; NOT auto-appended
    # to every request. See module docstring for rationale.
    household_id: str

    def _run(
        self,
        method: str,
        path: str,
        body: CreateRecipeBody | dict | None = None,
        query: dict | None = None,
    ) -> dict | str:
        """Call household-manager API. Returns parsed JSON or raises on auth errors.

        Note: self.household_id is available but NOT automatically injected into
        the request URL in Phase 7. The agent includes household_id in path/query
        where required by the API (per household-manager skill files).

        ``body`` is typed loosely here (`CreateRecipeBody | dict | None`) because
        Pydantic validates the LLM-emitted args via ``args_schema`` BEFORE
        ``_run`` is called — so by the time we get here, ``body`` is either a
        ``CreateRecipeBody`` instance, a plain dict (test paths that bypass the
        args_schema), or ``None``. We dump model instances to JSON-safe dicts
        before handing to httpx.
        """
        api_key = os.environ["HOUSEHOLD_MANAGER_API_KEY"]
        base_url = os.environ.get("HOUSEHOLD_MANAGER_BASE_URL", "http://localhost:3001")

        body_payload: dict | None
        if isinstance(body, BaseModel):
            body_payload = body.model_dump(mode="json")
        else:
            body_payload = body

        async def _call() -> dict | str:
            async with httpx.AsyncClient() as client:
                resp = await client.request(
                    method=method.upper(),
                    url=f"{base_url}{path}",
                    headers={"Authorization": f"Bearer {api_key}"},
                    params=query,
                    json=body_payload,
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
        body: CreateRecipeBody | dict | None = None,
        query: dict | None = None,
    ) -> dict | str:
        return self._run(method, path, body, query)
