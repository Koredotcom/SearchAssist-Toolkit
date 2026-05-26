"""Score extract-only runs from top-K chunk text (no generated answer)."""
from __future__ import annotations

import json
import logging
from typing import Any

from agents.llm_client import call_llm_json, parse_json_loose
from agents.prompts import EXTRACT_SCORER_PROMPT
from db.database import get_llm_config

logger = logging.getLogger(__name__)

EXTRACT_SCORE_KEYS = (
    "query_relevance",
    "groundedness",
    "completeness",
    "ground_truth_relevance",
    "gpt_similarity",
)


def top_k_chunks_payload(chunk_signals: list[dict], k: int = 5) -> list[dict[str, Any]]:
    """Build top-K qualified chunks for the extract scorer (JSON-friendly).

    ``chunk_signals`` should already be the scoring list from evaluate (qualified or raw).
    """
    out: list[dict[str, Any]] = []
    for i, ch in enumerate(chunk_signals[:k]):
        text = (ch.get("chunkText") or "").strip()
        out.append({
            "rank": i + 1,
            "docId": ch.get("docId"),
            "chunkId": ch.get("chunkId"),
            "chunkQualified": ch.get("chunkQualified"),
            "score": ch.get("score"),
            "chunkText": text[:4000] if text else "",
        })
    return out


def score_extract_chunks(
    question: str,
    expected_answer: str,
    chunk_signals: list[dict],
    app_id: str,
    *,
    top_k: int = 5,
) -> dict[str, Any]:
    """LLM rubric over top-K chunk texts. Does not affect extract pass/fail."""
    cfg = get_llm_config(app_id, "judge")
    system_prompt = EXTRACT_SCORER_PROMPT

    top_chunks = top_k_chunks_payload(chunk_signals, k=top_k)
    user = json.dumps(
        {
            "question": question,
            "expected_answer": expected_answer or "",
            "top_chunks": top_chunks,
        },
        ensure_ascii=False,
        indent=2,
    )

    try:
        raw = call_llm_json(app_id, "judge", system_prompt, user)
        parsed = parse_json_loose(raw, expect="object", agent_name="extract_scorer")
    except Exception as exc:
        logger.error("ExtractScorer | API failed | %s", exc, exc_info=True)
        parsed = {}

    scores: dict[str, Any] = {}
    for k in EXTRACT_SCORE_KEYS:
        v = (parsed or {}).get(k)
        if isinstance(v, (int, float)):
            scores[k] = int(v) if k == "gpt_similarity" else v

    rationale = (parsed or {}).get("rationale", "")
    if not rationale and not parsed:
        rationale = (
            f"Extract scoring unavailable — judge model '{cfg.get('model', '?')}' "
            "did not return valid JSON."
        )

    logger.info(
        "ExtractScorer | qrel=%s ground=%s comp=%s gtrel=%s sim=%s",
        scores.get("query_relevance"), scores.get("groundedness"),
        scores.get("completeness"), scores.get("ground_truth_relevance"),
        scores.get("gpt_similarity"),
    )

    return {"scores": scores, "rationale": rationale, "top_chunks": top_chunks}
