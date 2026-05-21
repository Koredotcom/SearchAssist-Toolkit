from __future__ import annotations

import logging
from typing import Any

from koreai.client import get_client

logger = logging.getLogger(__name__)


def query_rag(
    app: dict,
    question: str,
    meta_filters: list[dict[str, Any]] | None = None,
    user_email: str | None = None,
) -> dict[str, Any]:
    """Query Advance Search V2 and return structured result.

    Args:
        meta_filters: Optional list of filter groups to attach as ``metaFilters``.
        user_email:   Optional RACL user identifier; sent as ``customData.userContext.userId``.
    """
    app_id = app.get("app_id", "?")
    bot_id = app.get("bot_id", "?")
    url = f"{app['host_url']}/api/public/bot/{bot_id}/search/v2/advanced-search"

    logger.info(
        "Kore.ai | RAG query | app=%s question='%s...' filters=%d racl_user=%s",
        app_id, question[:80], len(meta_filters or []), "yes" if user_email else "no",
    )

    answer_mode = app.get("answer_mode", "answer_generation")

    logger.debug("Kore.ai | answer_mode=%s", answer_mode)

    payload: dict[str, Any] = {
        "query": question,
        "answerSearch": True,
        "searchResults": True,
        "includeChunksInResponse": True,
        "maxNumOfChunks": 100,
    }

    if meta_filters:
        payload["metaFilters"] = meta_filters
        logger.debug("Kore.ai | metaFilters: %s", meta_filters)

    if user_email:
        payload.setdefault("customData", {}).setdefault("userContext", {})["userId"] = user_email
        logger.debug("Kore.ai | userContext.userId=%s", user_email)

    if app.get("racl_entity_ids"):
        payload["raclEntityIds"] = app["racl_entity_ids"]
        logger.debug("Kore.ai | Using RACL entity IDs: %s", app["racl_entity_ids"])

    try:
        with get_client(app, timeout=60.0) as client:
            resp = client.post(url, json=payload)

            if not resp.is_success:
                logger.error(
                    "Kore.ai | RAG API error | status=%d | app=%s | body=%s",
                    resp.status_code, app_id, resp.text[:300],
                )
            resp.raise_for_status()
            raw = resp.json()

    except Exception as exc:
        logger.error("Kore.ai | RAG query FAILED | app=%s question='%s...' | error: %s",
                     app_id, question[:80], exc, exc_info=True)
        raise

    logger.debug("Kore.ai | Raw response keys: %s", list(raw.keys()) if isinstance(raw, dict) else type(raw).__name__)

    # Structural debug — logs once per query so we can discover actual field names
    _log_response_structure(raw)

    result = _parse_response(raw, answer_mode=answer_mode)
    # Expose the exact payload that was sent so callers can store/show it for debugging
    result["search_payload"] = payload
    # Expose the full raw response so the UI / persistence layer can show it
    # exactly as Kore.ai returned it. Useful for debugging chunk scoring,
    # answer payload structure, and parameters the parser ignored.
    result["search_response"] = raw

    logger.info(
        "Kore.ai | RAG response | app=%s valid=%s cited_docs=%d result_docs=%d "
        "chunks=%d latency_llm=%sms latency_retrieval=%sms",
        app_id,
        result["is_valid_answer"],
        len(result["cited_doc_ids"]),
        len(result["result_doc_ids"]),
        len(result["chunk_signals"]),
        result.get("latency_llm_ms"),
        result.get("latency_retrieval_ms"),
    )

    if not result["answer"]:
        logger.warning("Kore.ai | RAG returned empty answer | app=%s question='%s...'", app_id, question[:80])

    logger.debug("Kore.ai | Cited doc IDs: %s", result["cited_doc_ids"])
    logger.debug("Kore.ai | Answer preview: '%s...'", result["answer"][:120])

    return result


def _log_response_structure(raw: dict[str, Any]) -> None:
    """Log the skeleton of the Kore.ai response so we can discover field names."""
    try:
        template = raw.get("template", {}) if isinstance(raw, dict) else {}
        if not isinstance(template, dict):
            logger.debug("STRUCT | template is not a dict: %s", type(template))
            return

        logger.debug("STRUCT | template keys: %s", list(template.keys()))

        # answer_details path
        ad = template.get("answer_details")
        logger.debug("STRUCT | answer_details type=%s keys=%s",
                     type(ad).__name__,
                     list(ad.keys()) if isinstance(ad, dict) else "N/A")
        if isinstance(ad, dict):
            resp = ad.get("response")
            logger.debug("STRUCT | answer_details.response type=%s keys=%s",
                         type(resp).__name__,
                         list(resp.keys()) if isinstance(resp, dict) else "N/A")

        # First chunk
        chunks = template.get("chunk_result", [])
        if chunks and isinstance(chunks, list) and isinstance(chunks[0], dict):
            c0 = chunks[0]
            logger.debug("STRUCT | chunk_result[0] keys: %s", list(c0.keys()))
            src0 = c0.get("_source")
            if isinstance(src0, dict):
                logger.debug("STRUCT | chunk_result[0]._source keys: %s", list(src0.keys()))
                # Log first 200 chars of any text-like field
                for k, v in src0.items():
                    if isinstance(v, str) and len(v) > 20:
                        logger.debug("STRUCT |   _source.%s = '%s...'", k, v[:120])

        # First result doc
        results = template.get("results")
        if isinstance(results, dict):
            for src_key, src_val in results.items():
                if isinstance(src_val, dict):
                    docs = src_val.get("data", [])
                    if docs and isinstance(docs[0], dict):
                        logger.debug("STRUCT | results[%s].data[0] keys: %s", src_key, list(docs[0].keys()))
                        for k, v in docs[0].items():
                            if isinstance(v, str) and len(v) > 20:
                                logger.debug("STRUCT |   doc.%s = '%s...'", k, v[:120])
                    break  # only first source group
    except Exception as exc:
        logger.debug("STRUCT | dump failed: %s", exc)


def _safe_dict(obj: Any) -> dict[str, Any]:
    """Return obj if it is a dict, otherwise an empty dict."""
    return obj if isinstance(obj, dict) else {}


def _build_extract_answer(template: dict[str, Any]) -> str:
    """Build a synthetic answer for extract_only mode from chunk/result content."""
    parts: list[str] = []

    # Primary: chunk_result._source.chunkText (confirmed field name from Kore.ai)
    for chunk in template.get("chunk_result", []):
        if not isinstance(chunk, dict):
            continue
        src = _safe_dict(chunk.get("_source"))
        # Only use qualified chunks that were sent to LLM (highest quality signal)
        text = (
            src.get("chunkText")        # confirmed Kore.ai field name
            or src.get("chunkContent")  # alternate spelling
            or src.get("chunk_content")
            or src.get("content")
            or src.get("text")
            or ""
        )
        if text and text not in parts:
            parts.append(text.strip())
        if len(parts) >= 5:
            break

    return "\n\n".join(parts) if parts else ""


def _extract_doc_ids_from_chunks(template: dict[str, Any]) -> list[str]:
    """Extract unique docIds from chunk_result._source when answer_payload is unavailable."""
    doc_ids: list[str] = []
    for chunk in template.get("chunk_result", []):
        if not isinstance(chunk, dict):
            continue
        src = _safe_dict(chunk.get("_source"))
        # Kore.ai uses both camelCase docId and snake_case doc_id
        doc_id = src.get("docId") or src.get("doc_id")
        if doc_id and doc_id not in doc_ids:
            doc_ids.append(doc_id)
    return doc_ids


def _parse_response(raw: dict[str, Any], answer_mode: str = "answer_generation") -> dict[str, Any]:
    template = _safe_dict(raw.get("template"))
    answer_details = _safe_dict(template.get("answer_details"))
    response_block = _safe_dict(answer_details.get("response"))

    if answer_mode == "extract_only":
        answer_text = _build_extract_answer(template)
        is_valid = bool(answer_text)
    else:
        answer_text = response_block.get("answer", "")
        is_valid = response_block.get("isValidAnswer", False)
        # If Kore.ai didn't generate an LLM answer (e.g. app is extract-only at Kore.ai level),
        # fall back to extracting from chunks so results are not always empty
        if not answer_text:
            answer_text = _build_extract_answer(template)
            if answer_text:
                logger.debug("Kore.ai | answer_generation mode but no LLM answer — using extract fallback")
                is_valid = True

    search_request_id = answer_details.get("searchRequestId", "")

    cited_doc_ids: list[str] = []
    center = _safe_dict(_safe_dict(response_block.get("answer_payload")).get("center_panel"))
    for item in center.get("data", []):
        if not isinstance(item, dict):
            continue
        for snippet in item.get("snippet_content", []):
            if not isinstance(snippet, dict):
                continue
            for src in snippet.get("sources", []):
                if not isinstance(src, dict):
                    continue
                doc_id = src.get("doc_id") or src.get("docId")
                if doc_id and doc_id not in cited_doc_ids:
                    cited_doc_ids.append(doc_id)

    # Fallback: when Kore.ai didn't generate an LLM answer the answer_payload is empty.
    # Use chunk_result._source docIds so doc_retrieved can still be evaluated.
    if not cited_doc_ids:
        cited_doc_ids = _extract_doc_ids_from_chunks(template)

    result_doc_ids: list[str] = []
    results = template.get("results")
    if isinstance(results, dict):
        for _, source_data in results.items():
            if not isinstance(source_data, dict):
                continue
            for doc in source_data.get("data", []):
                if not isinstance(doc, dict):
                    continue
                if doc.get("docId") and doc["docId"] not in result_doc_ids:
                    result_doc_ids.append(doc["docId"])

    chunk_signals: list[dict[str, Any]] = []
    for chunk in template.get("chunk_result", []):
        if not isinstance(chunk, dict):
            continue
        src = _safe_dict(chunk.get("_source"))
        chunk_signals.append({
            "chunkId": src.get("chunkId"),
            "docId": src.get("docId") or src.get("doc_id"),
            "score": chunk.get("_score"),
            "vector_score": chunk.get("vector_search_score"),
            "keyword_score": chunk.get("keyword_search_score"),
            "positional_score": chunk.get("positional_score"),
            "chunkQualified": src.get("chunkQualified"),
            "sentToLLM": src.get("sentToLLM"),
            "usedInAnswer": src.get("usedInAnswer"),
            "recordUrl": src.get("recordUrl"),
            "recordTitle": src.get("recordTitle"),
        })

    return {
        "answer": answer_text,
        "is_valid_answer": is_valid,
        "search_request_id": search_request_id,
        "cited_doc_ids": cited_doc_ids,
        "result_doc_ids": result_doc_ids,
        "chunk_signals": chunk_signals,
        "answer_mode": answer_mode,
        "latency_llm_ms": raw.get("llmResponseTime"),
        "latency_retrieval_ms": raw.get("retrievalResponseTime"),
    }


def verify_doc_in_chunks(app: dict[str, Any], doc_id: str, doc_title: str = "") -> bool:
    """Return True if the document has at least one indexed chunk in Kore.ai.

    Uses the dedicated Chunk List API (POST /chunk/list) with a docId filter —
    this is the correct API per Kore.ai documentation:
      https://docs.kore.ai/ai-for-service/apis/searchai/chunk-apis

    Equivalent curl:
      curl -X POST "{host_url}/api/public/bot/{botId}/chunk/list"
           -H "auth: <jwt_token>"
           -H "Content-Type: application/json"
           -d '{
                 "filters": {
                   "conditions": [{"key": "docId", "op": "equals", "value": "<doc_id>"}],
                   "operand": "and"
                 },
                 "enableFilters": true,
                 "nextCursor": null
               }'

    Returns True on network/API error to avoid false-positive skips.
    """
    app_id = app.get("app_id", "?")
    bot_id = app.get("bot_id", "?")
    url = f"{app['host_url']}/api/public/bot/{bot_id}/chunk/list"

    payload: dict[str, Any] = {
        "filters": {
            "conditions": [
                {"key": "docId", "op": "equals", "value": doc_id},
            ],
            "operand": "and",
        },
        "enableFilters": True,
    }

    logger.debug(
        "Kore.ai | Chunk verify | app=%s doc='%s' (id=%s) | POST %s",
        app_id, doc_title or "?", doc_id, url,
    )

    try:
        with get_client(app, timeout=30.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            raw = resp.json()
    except Exception as exc:
        logger.warning(
            "Kore.ai | Chunk verify FAILED for doc=%s app=%s | error: %s — assuming present",
            doc_id, app_id, exc,
        )
        return True  # fail-open: never falsely skip a doc due to a network error

    # Response has a "count" field and a "chunks" array
    count = raw.get("count", 0)
    chunks = raw.get("chunks", [])
    has_chunks = (isinstance(count, int) and count > 0) or (isinstance(chunks, list) and len(chunks) > 0)

    logger.info(
        "Kore.ai | Chunk verify | app=%s doc=%s title='%s' has_chunks=%s count=%s",
        app_id, doc_id, doc_title or "?", has_chunks, count,
    )
    return has_chunks
