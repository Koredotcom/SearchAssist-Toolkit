from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from koreai.client import get_client


class RagApiTimeoutError(Exception):
    """Raised when the Kore.ai Agent Platform API does not respond within the timeout."""

logger = logging.getLogger(__name__)


def query_rag(
    app: dict,
    question: str,
    meta_filters: list[dict[str, Any]] | None = None,
    user_email: str | None = None,
) -> dict[str, Any]:
    """Query Kore.ai Agent Platform API and return structured result.

    New endpoint: POST /api/v1/process/{processId}/version/{versionId}
    Auth: x-api-key header (set in get_client via app["x_api_key"])

    Args:
        meta_filters: Ignored — Agent Platform API does not support meta-filters.
        user_email:   Optional RACL identity override; falls back to app["identity"].
    """
    app_id = app.get("app_id", "?")
    process_id = app.get("process_id", "")
    cf_version_id = app.get("cf_version_id", "")

    if not process_id or not cf_version_id:
        raise ValueError(
            f"app {app_id} is missing process_id or cf_version_id — "
            "update the app config with the new Kore.ai Agent Platform credentials"
        )

    base_url = (app.get("host_url") or "https://agent-platform.kore.ai").rstrip("/")
    url = f"{base_url}/api/v1/process/{process_id}/version/{cf_version_id}"

    identity = user_email or app.get("identity", "")
    racl_entity_ids = app.get("racl_entity_ids") or []
    # API expects a single string value — join multiple IDs with comma, fall back to "*"
    racl_value: str = ",".join(racl_entity_ids) if racl_entity_ids else "*"

    logger.info(
        "Kore.ai | RAG query | app=%s question='%s...' identity=%s racl=%s",
        app_id, question[:80], identity or "none", racl_value,
    )

    if meta_filters:
        logger.warning(
            "Kore.ai | meta_filters provided but are NOT sent — Agent Platform API does not support them | app=%s filters_ignored=%s",
            app_id, meta_filters,
        )

    payload: dict[str, Any] = {
        "input": {
            "query": question,
            "raclEntityIds": racl_value,
            "identity": identity,
        }
    }

    logger.debug("Kore.ai | payload: %s", payload)

    try:
        with get_client(app, timeout=10.0) as client:
            resp = client.post(url, json=payload)

            if not resp.is_success:
                logger.error(
                    "Kore.ai | RAG API error | status=%d | app=%s | body=%s",
                    resp.status_code, app_id, resp.text[:300],
                )
            resp.raise_for_status()
            raw = resp.json()

    except httpx.TimeoutException as exc:
        logger.error(
            "Kore.ai | RAG query TIMEOUT (>10s) | app=%s question='%s...' | error: %s",
            app_id, question[:80], exc,
        )
        raise RagApiTimeoutError(f"Kore.ai API did not respond within 10 seconds") from exc
    except Exception as exc:
        logger.error(
            "Kore.ai | RAG query FAILED | app=%s question='%s...' | error: %s",
            app_id, question[:80], exc, exc_info=True,
        )
        raise

    logger.debug("Kore.ai | Raw response keys: %s", list(raw.keys()) if isinstance(raw, dict) else type(raw).__name__)

    result = _parse_response(raw)
    result["search_payload"] = payload

    logger.info(
        "Kore.ai | RAG response | app=%s cited_docs=%d result_docs=%d chunks=%d elapsed=%s",
        app_id,
        len(result["cited_doc_ids"]),
        len(result["result_doc_ids"]),
        len(result["chunk_signals"]),
        result.get("elapsed_time"),
    )

    if not result["answer"]:
        logger.warning("Kore.ai | RAG returned empty answer | app=%s question='%s...'", app_id, question[:80])

    logger.debug("Kore.ai | Cited doc IDs: %s", result["cited_doc_ids"])
    logger.debug("Kore.ai | Answer preview: '%s...'", result["answer"][:120])

    return result


def _parse_elapsed_ms(elapsed_time: str | None) -> float | None:
    """Parse '2.88 seconds' → 2880.0 ms."""
    if not elapsed_time:
        return None
    m = re.search(r"([\d.]+)", str(elapsed_time))
    if m:
        return round(float(m.group(1)) * 1000)
    return None


def _parse_response(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse the new Agent Platform response structure.

    Response shape:
        {startTime, endTime, elapsedTime, output: {answerChunks: {<source>: {answer_chunks: [...]}}, ...}}
    """
    output = raw.get("output") or {}
    answer_chunks_map: dict[str, Any] = output.get("answerChunks") or {}
    elapsed_time: str | None = raw.get("elapsedTime")
    elapsed_ms = _parse_elapsed_ms(elapsed_time)

    # Collect all chunks across all sources, tag with source name
    all_chunks: list[dict[str, Any]] = []
    for source_name, source_data in answer_chunks_map.items():
        if not isinstance(source_data, dict):
            continue
        for chunk in source_data.get("answer_chunks", []):
            if not isinstance(chunk, dict):
                continue
            chunk["_source_name"] = source_name  # tag for logging
            all_chunks.append(chunk)

    # Sort by normalized_score desc (primary), vector_search_score desc (secondary)
    all_chunks.sort(
        key=lambda c: (
            c.get("normalized_score") or 0.0,
            c.get("vector_search_score") or 0.0,
            c.get("_score") or 0.0,
        ),
        reverse=True,
    )

    logger.debug("Kore.ai | Total chunks across all sources: %d", len(all_chunks))

    # Build chunk_signals
    chunk_signals: list[dict[str, Any]] = []
    cited_doc_ids: list[str] = []
    result_doc_ids: list[str] = []

    for chunk in all_chunks:
        src = chunk.get("_source") or {}
        if not isinstance(src, dict):
            continue

        doc_id = src.get("doc_id")
        chunk_id = src.get("chunkId")

        chunk_signals.append({
            "chunkId": chunk_id,
            "doc_id": doc_id,
            "score": chunk.get("_score"),
            "vector_score": chunk.get("vector_search_score"),
            "normalized_score": chunk.get("normalized_score"),
            # Fields absent in new API — kept as None for schema compatibility
            "keyword_score": None,
            "positional_score": None,
            "chunkQualified": None,
            "sentToLLM": None,
            "usedInAnswer": None,
            "recordUrl": src.get("recordUrl") or src.get("sourceUrl") or src.get("trackingUrl"),
            "recordTitle": src.get("recordTitle") or src.get("chunkTitle"),
            "chunkText": src.get("chunkText", ""),
            "sys_content_type": src.get("sys_content_type"),
            "sys_source_name": src.get("sys_source_name") or chunk.get("_source_name"),
        })

        if doc_id and doc_id not in cited_doc_ids:
            cited_doc_ids.append(doc_id)
        if doc_id and doc_id not in result_doc_ids:
            result_doc_ids.append(doc_id)

    # Build a synthetic answer from the top chunks (no LLM answer in new API)
    answer_text = _build_answer_from_chunks(chunk_signals)

    return {
        "answer": answer_text,
        "is_valid_answer": False,   # Agent Platform never generates an LLM answer
        "has_llm_answer": False,    # signals evaluate.py to skip all answer-quality metrics
        "search_request_id": output.get("traceId", ""),
        "cited_doc_ids": cited_doc_ids,
        "result_doc_ids": result_doc_ids,
        "chunk_signals": chunk_signals,
        "answer_mode": "extract_only",
        "elapsed_time": elapsed_time,
        "latency_llm_ms": None,
        "latency_retrieval_ms": elapsed_ms,
    }


_MAX_CHUNK_CHARS = 600  # keep each chunk short to avoid bloated synthetic answers


def _build_answer_from_chunks(chunk_signals: list[dict[str, Any]], max_chunks: int = 3) -> str:
    """Concatenate top chunk texts as a synthetic answer for retrieval evaluation.

    Truncates each chunk to _MAX_CHUNK_CHARS so judge scoring and semantic similarity
    are not diluted by raw dump of very long passages.
    """
    parts: list[str] = []
    for cs in chunk_signals[:max_chunks]:
        text = cs.get("chunkText", "").strip()
        if not text:
            continue
        if len(text) > _MAX_CHUNK_CHARS:
            text = text[:_MAX_CHUNK_CHARS].rsplit(" ", 1)[0] + "…"
        if text not in parts:
            parts.append(text)
    return "\n\n".join(parts)


def verify_doc_in_chunks(app: dict[str, Any], doc_id: str, doc_title: str = "") -> bool:
    """Return True if the document has at least one indexed chunk in Kore.ai.

    In the new Agent Platform API there is no standalone chunk-list endpoint,
    so we perform a quick search query using the doc_id as the search term and
    check whether the expected doc_id appears in any returned chunk.

    Returns True on network/API error to avoid false-positive skips.
    """
    app_id = app.get("app_id", "?")
    logger.debug(
        "Kore.ai | Chunk verify | app=%s doc='%s' (id=%s)",
        app_id, doc_title or "?", doc_id,
    )

    try:
        result = query_rag(app, question=doc_title or doc_id)
        chunk_doc_ids = {cs.get("doc_id") for cs in result.get("chunk_signals", [])}
        has_chunks = doc_id in chunk_doc_ids
    except Exception as exc:
        logger.warning(
            "Kore.ai | Chunk verify FAILED for doc=%s app=%s | error: %s — assuming present",
            doc_id, app_id, exc,
        )
        return True  # fail-open: never falsely skip a doc due to a network error

    logger.info(
        "Kore.ai | Chunk verify | app=%s doc=%s title='%s' has_chunks=%s",
        app_id, doc_id, doc_title or "?", has_chunks,
    )
    return has_chunks
