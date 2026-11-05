"""Built-in knowledge-base search tool (Amazon Bedrock).

``make_kb`` builds a single Strands tool that searches one or more Bedrock
Knowledge Bases and returns merged, score-ranked passages. The KB ids and
retrieval settings are fixed at construction (closure config, invisible to the
model); the model only passes the query and may optionally target one KB.

Because it is a single tool with one name, there is no tool-name collision: the
multi-KB behaviour lives *inside* the tool (fan-out + merge), not in N separate
tools. Reuses the ``retrieve`` + score-threshold logic from the original
``KBTool`` draft, extended to multiple knowledge bases and a ``ToolResult``.

``kb_sources`` reads a result of that tool back — the knowledge base, score and
source document of each passage, without its text — for whoever stores what the
agent consulted (a turn transcript, an audit log). It lives here, next to the
encoding it parses.

Requires ``boto3`` (Loom's ``aws`` extra). It is imported lazily so that
importing :mod:`loom.builtins` does not require it.
"""

import json
import logging
from typing import Annotated, Any

from loom.adapters.strands import DecoratedFunctionTool, ToolResult, tool

logger = logging.getLogger(__name__)

_VALID_SEARCH_TYPES = ("HYBRID", "SEMANTIC")


def make_kb(
    *,
    kb_ids: list[str],
    region: str = "us-west-2",
    max_results: int = 10,
    score_threshold: float = 0.7,
    filters: dict[str, Any] | None = None,
    search_type: str = "HYBRID",
    top_k: int = 5,
    name: str = "kb_search",
    boto_session: Any | None = None,
) -> DecoratedFunctionTool:
    """Build a multi-KB Bedrock search tool.

    Args:
        kb_ids: Knowledge-base ids to search. One tool fans out across all of them.
        region: AWS region where the knowledge bases live.
        max_results: Results requested per KB before merging.
        score_threshold: Drop passages with a relevance score below this (0.0–1.0).
        filters: Optional Bedrock metadata filter applied to every KB.
        search_type: ``"HYBRID"`` or ``"SEMANTIC"``.
        top_k: Passages kept after the cross-KB merge and re-ranking.
        name: Strands tool name (unique within the agent).
        boto_session: Optional ``boto3.Session`` to build the client from — the
            per-run credentials overlay (see :func:`loom.core.loaders.tool.get_tools`).
            ``None`` falls back to boto3's default credential chain (the caller's
            ambient identity), same as before this parameter existed.

    Returns:
        A ``DecoratedFunctionTool`` named ``name``.

    Raises:
        ValueError: If ``kb_ids`` is empty or ``search_type`` is invalid.
    """
    if not kb_ids:
        raise ValueError("kb_ids must contain at least one knowledge-base id")
    if search_type not in _VALID_SEARCH_TYPES:
        raise ValueError(f"search_type must be one of {_VALID_SEARCH_TYPES}, got '{search_type}'")

    import boto3  # lazy: only required when this builtin is actually configured

    ids = list(kb_ids)
    valid = set(ids)
    client = (boto_session or boto3).client("bedrock-agent-runtime", region_name=region)

    retrieval_config: dict[str, Any] = {
        "vectorSearchConfiguration": {
            "numberOfResults": max_results,
            "overrideSearchType": search_type,
        }
    }
    if filters:
        retrieval_config["vectorSearchConfiguration"]["filter"] = filters

    desc = (
        f"Search the Bedrock knowledge base(s) [{', '.join(ids)}] for passages relevant to a "
        f"query. Returns up to {top_k} passages with their source location and relevance score."
    )

    @tool(name=name, description=desc)
    def search(
        query: Annotated[str, "Natural-language search query."],
        kb_id: Annotated[
            str | None,
            f"Optional: target a single KB. One of {ids}. Omit to search all.",
        ] = None,
    ) -> ToolResult:
        """Search the configured Bedrock knowledge base(s) and return ranked passages."""
        if kb_id is not None and kb_id not in valid:
            return {
                "status": "error",
                "content": [{"text": f"Unknown kb_id '{kb_id}'. Configured: {ids}"}],
            }
        targets = [kb_id] if kb_id else ids

        passages: list[dict[str, Any]] = []
        for kid in targets:
            logger.info("KB retrieve: kb_id=%s region=%s", kid, region)
            response = client.retrieve(
                knowledgeBaseId=kid,
                retrievalQuery={"text": query},
                retrievalConfiguration=retrieval_config,
            )
            for result in response.get("retrievalResults", []):
                score = result.get("score", 0.0)
                if score < score_threshold:
                    continue
                passages.append(
                    {
                        "kb_id": kid,
                        "score": score,
                        "text": result.get("content", {}).get("text", ""),
                        "location": result.get("location"),
                    }
                )

        # Merge across KBs: highest score first, keep the global top_k.
        passages.sort(key=lambda p: p["score"], reverse=True)
        passages = passages[:top_k]

        if not passages:
            return {"status": "success", "content": [{"text": "No relevant passages found."}]}

        return {"status": "success", "content": [{"text": _encode(passages, targets)}]}

    return search


def _encode(passages: list[dict[str, Any]], targets: list[str]) -> str:
    """The text block of a successful search: a summary line, then the passages as JSON.

    A native ``json`` content block hallucinates on Amazon Nova (Pro/Lite/Micro) — it
    produces an invalid tool-use sequence on the next turn. Every provider (Nova
    included) parses JSON embedded in ``text`` fine, so serializing here keeps the tool
    provider-agnostic. :func:`kb_sources` is the inverse; change both together.
    """
    summary = f"{len(passages)} passage(s) from {targets}."
    return f"{summary}\n{json.dumps({'passages': passages})}"


def kb_sources(content: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """The sources of a ``kb`` tool result: which documents the search returned.

    Reads the tool result's ``content`` (the list of blocks, as the tool returned it
    and as it stays in the conversation history) and gives one entry per passage, in
    the result's order (highest score first), without the passage text::

        {"kb_id": "docs", "score": 0.83, "type": "S3", "uri": "s3://bucket/guide.pdf"}

    ``type`` and ``uri`` come from the passage's Bedrock ``location``: ``uri`` is the
    ``uri``, ``url`` or ``id`` of its ``*Location`` object (S3, web, Confluence,
    SharePoint, Salesforce, Kendra, custom documents), ``None`` when it has none (SQL).

    A result with no passages, an error, ``None``, or content this tool did not
    produce gives ``[]``: it never raises, so a caller can apply it to any tool call.

    Args:
        content: The tool result's content blocks.

    Returns:
        A list of ``{"kb_id", "score", "type", "uri"}`` dicts.
    """
    if not content:
        return []
    for block in content:
        text = block.get("text") if isinstance(block, dict) else None
        if not isinstance(text, str) or "\n" not in text:
            continue
        try:
            payload = json.loads(text.split("\n", 1)[1])
        except ValueError:
            continue
        passages = payload.get("passages") if isinstance(payload, dict) else None
        if isinstance(passages, list):
            return [_source(p) for p in passages if isinstance(p, dict)]
    return []


def _source(passage: dict[str, Any]) -> dict[str, Any]:
    location = passage.get("location") if isinstance(passage.get("location"), dict) else {}
    return {
        "kb_id": passage.get("kb_id"),
        "score": passage.get("score"),
        "type": location.get("type"),
        "uri": _uri(location),
    }


def _uri(location: dict[str, Any]) -> str | None:
    for key, value in location.items():
        if key.endswith("Location") and isinstance(value, dict):
            for field in ("uri", "url", "id"):
                if isinstance(value.get(field), str):
                    return value[field]
    return None
