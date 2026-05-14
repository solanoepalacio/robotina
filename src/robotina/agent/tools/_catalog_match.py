"""Catalog-matching infrastructure for validate-foods / validate-units tools.

Provides:
- ``_normalize``: NFKD-strip + casefold normalizer for Spanish names.
- ``SemanticMatchEntry`` / ``SemanticMatchResult``: Pydantic schema bound as
  the matcher LLM's structured-output target.
- ``resolve_catalog``: hybrid resolver. Direct NFKD match first; for the
  unmatched remainder, a single batched LLM call against the full catalog.

Architecture:
- The matcher LLM is registered as the ``validate-catalog`` AgentConfig in
  ``robotina.agent.agents``. It picks up overrides from
  ``AGENT_OVERRIDES_FILEPATH`` like every other agent. The backend is
  constructed per call (never cached at module scope) so env-var and override
  hot-reload behave consistently.
- The matcher LLM call must show up in LangWatch traces — we thread
  ``LangChainTracer`` through ``RunnableConfig(callbacks=...)`` when the
  langwatch package is available (Pitfall 2 in 15-RESEARCH.md). The matcher
  uses ``with_structured_output`` (not ``create_agent``), so the Phase 12
  ``create_agent`` middleware does NOT cover it — the tracer callback is the
  only path that emits a span.
- For Ollama backends we pass ``method='function_calling'`` because Ollama's
  default ``method='json_schema'`` returns malformed output on gpt-oss for
  complex schemas (Pitfall 3).
"""
from __future__ import annotations

import logging
import unicodedata
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _normalize(s: str) -> str:
    """NFKD-strip, ASCII-lowercase, casefold, strip a Spanish name.

    ``_normalize('CEBOLLÁ')`` → ``'cebolla'``
    ``_normalize('ñoqui')``  → ``'noqui'``
    """
    return (
        unicodedata.normalize("NFKD", s)
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold()
        .strip()
    )


class SemanticMatchEntry(BaseModel):
    name: str
    catalog_id: str | None  # null => unmatched


class SemanticMatchResult(BaseModel):
    matches: list[SemanticMatchEntry]


def resolve_catalog(
    category: str,
    catalog: list[dict],
    names: list[str],
) -> dict:
    """Resolve a list of Spanish names against a household-manager catalog.

    Pipeline:
    1. Direct match using NFKD-normalized casefold equality (no LLM call).
    2. Single batched LLM call for the remainder (catalog + unmatched names in
       one shot, structured output enforced via ``with_structured_output``).
    3. Defensive filter on the LLM response — drop hallucinated names not in
       the input and hallucinated catalog ids not in the catalog.

    Args:
        category: ``"food"`` or ``"unit"`` (passed into the matcher prompt for
            tone; the matcher prompt loaded from ``validate-catalog/V001.md``
            already covers both cases).
        catalog: List of ``{"id": str, "name": str, ...}`` dicts as returned by
            ``GET /api/foods`` / ``GET /api/units``.
        names: Input Spanish names from the agent.

    Returns:
        ``{"matched": [{"name": str, "id": str}], "unmatched": [{"name": str, "id": None}]}``
    """
    if not names:
        return {"matched": [], "unmatched": []}

    # Build NFKD index. Last write wins on collisions; log a warning if we
    # collapse two catalog entries to the same key — caller can decide.
    index: dict[str, dict] = {}
    for entry in catalog:
        key = _normalize(entry.get("name", ""))
        if not key:
            continue
        if key in index and index[key].get("id") != entry.get("id"):
            logger.warning(
                "catalog-match: duplicate normalized name %r — keeping last (%s)",
                key, entry.get("id"),
            )
        index[key] = entry

    matched: list[dict] = []
    remaining: list[str] = []
    for n in names:
        hit = index.get(_normalize(n))
        if hit is not None:
            matched.append({"name": n, "id": hit["id"]})
        else:
            remaining.append(n)

    if not remaining:
        return {"matched": matched, "unmatched": []}

    # ----- Semantic fallback (single batched LLM call) -----
    # Deferred imports: per src/robotina/llm/__init__.py the LLM adapter must
    # never be constructed at module import time. The AGENT_OVERRIDES_FILEPATH
    # hot-reload contract relies on get_agent_config() being called per
    # invocation.
    from robotina.agent.agents import get_agent_config
    from robotina.llm import make_backend
    from langchain_ollama import ChatOllama
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_core.runnables import RunnableConfig

    try:
        from langwatch.langchain import LangChainTracer  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover — langwatch optional
        LangChainTracer = None  # type: ignore[assignment]

    config = get_agent_config("validate-catalog")
    backend = make_backend(config.model_config)

    kwargs: dict = {}
    if isinstance(backend.model, ChatOllama):
        # Pitfall 3: Ollama's default method='json_schema' returns malformed
        # output on gpt-oss; the tool-calling path has been load-tested.
        kwargs["method"] = "function_calling"

    runnable = (
        backend.model.with_structured_output(SemanticMatchResult, **kwargs)
        .with_retry(stop_after_attempt=2)
    )

    prompt = Path(config.prompt_path).read_text(encoding="utf-8")

    catalog_text = "\n".join(
        f"- {c.get('id')}: {c.get('name')}" for c in catalog
    ) or "(empty catalog)"
    names_text = "\n".join(f"- {n}" for n in remaining)
    user_msg = (
        f"category: {category}\n\n"
        f"Catalog:\n{catalog_text}\n\n"
        f"Names to resolve:\n{names_text}"
    )

    callbacks = [LangChainTracer()] if LangChainTracer is not None else []
    result: SemanticMatchResult = runnable.invoke(
        [SystemMessage(content=prompt), HumanMessage(content=user_msg)],
        config=RunnableConfig(callbacks=callbacks),
    )

    # Defensive hallucination filter (Pitfall 1 / D-09 posture).
    remaining_set = set(remaining)
    valid_ids = {c.get("id") for c in catalog}
    seen_names: set[str] = set()
    unmatched: list[dict] = []

    for entry in result.matches:
        if entry.name not in remaining_set:
            logger.warning(
                "catalog-match: matcher returned name %r not in input — dropping",
                entry.name,
            )
            continue
        if entry.name in seen_names:
            continue  # ignore duplicates from the LLM
        seen_names.add(entry.name)
        if entry.catalog_id is None:
            unmatched.append({"name": entry.name, "id": None})
        elif entry.catalog_id in valid_ids:
            matched.append({"name": entry.name, "id": entry.catalog_id})
        else:
            logger.warning(
                "catalog-match: matcher returned catalog_id %r not in catalog — treating as unmatched",
                entry.catalog_id,
            )
            unmatched.append({"name": entry.name, "id": None})

    # Anything in remaining that the LLM never addressed → unmatched.
    for n in remaining:
        if n not in seen_names:
            unmatched.append({"name": n, "id": None})

    return {"matched": matched, "unmatched": unmatched}
