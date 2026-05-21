from __future__ import annotations

from typing import Any

from config import get_config
from koreai.client import get_client


def query_rag(question: str) -> dict[str, Any]:
    """Query Advance Search V2 and return structured result."""
    cfg = get_config()
    url = (
        f"{cfg.koreai_host_url}/api/public/bot/{cfg.koreai_bot_id}"
        f"/search/v2/advanced-search"
    )

    payload: dict[str, Any] = {
        "query": question,
        "answerSearch": True,
        "searchResults": True,
        "includeChunksInResponse": True,
    }

    if cfg.koreai_racl_entity_ids:
        payload["raclEntityIds"] = cfg.koreai_racl_entity_ids

    with get_client(timeout=60.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        raw = resp.json()

    return _parse_response(raw)


def _parse_response(raw: dict[str, Any]) -> dict[str, Any]:
    template = raw.get("template", {})
    answer_details = template.get("answer_details", {})
    response_block = answer_details.get("response", {})

    answer_text = response_block.get("answer", "")
    is_valid = response_block.get("isValidAnswer", False)
    search_request_id = answer_details.get("searchRequestId", "")

    # Extract cited docIds from sources
    cited_doc_ids: list[str] = []
    sources = []
    center = response_block.get("answer_payload", {}).get("center_panel", {})
    for item in center.get("data", []):
        for snippet in item.get("snippet_content", []):
            for src in snippet.get("sources", []):
                doc_id = src.get("doc_id") or src.get("docId")
                if doc_id and doc_id not in cited_doc_ids:
                    cited_doc_ids.append(doc_id)
                sources.append(src)

    # Also collect docIds from search results
    result_doc_ids: list[str] = []
    for source_type, source_data in template.get("results", {}).items():
        for doc in source_data.get("data", []):
            if doc.get("docId") and doc["docId"] not in result_doc_ids:
                result_doc_ids.append(doc["docId"])

    # Chunk-level signals
    chunk_signals: list[dict[str, Any]] = []
    for chunk in template.get("chunk_result", []):
        src = chunk.get("_source", {})
        chunk_signals.append(
            {
                "chunkId": src.get("chunkId"),
                "docId": src.get("docId"),
                "score": chunk.get("_score"),
                "chunkQualified": src.get("chunkQualified"),
                "sentToLLM": src.get("sentToLLM"),
                "usedInAnswer": src.get("usedInAnswer"),
            }
        )

    return {
        "answer": answer_text,
        "is_valid_answer": is_valid,
        "search_request_id": search_request_id,
        "cited_doc_ids": cited_doc_ids,
        "result_doc_ids": result_doc_ids,
        "chunk_signals": chunk_signals,
        "latency_llm_ms": raw.get("llmResponseTime"),
        "latency_retrieval_ms": raw.get("retrievalResponseTime"),
        "sources": sources,
    }
