"""Non-LLM metrics + per-row case detection for the 4-case evaluation design.

Cases:
  1: question only                                  → observation; optional LLM self-eval
  2: question + expected_answer                     → answer correctness
  3: question + reference_doc(s)                    → retrieval eval
  4: question + expected_answer + reference_doc(s)  → full eval
"""
from __future__ import annotations

from typing import Any

from agents.llm_client import _infer_provider
from db.database import get_api_key, get_llm_config
from judge.embeddings import semantic_similarity

# Default semantic similarity thresholds (overridden per-app from app_config)
DEFAULT_CASE1_THRESHOLD = 0.5
DEFAULT_CASE2_THRESHOLD = 0.5

# Recall@K levels reported on every Case-3 / Case-4 row
RECALL_K_LEVELS = (1, 3, 5, 10)

# Pass criterion for Cases 3 & 4: expected doc chunk must be in top-K chunks
TOP_K_PASS = 5


def detect_case(tc: dict) -> int:
    """Detect which evaluation case a test case falls into based on its columns."""
    has_answer = bool((tc.get("expected_answer") or "").strip())
    has_ref    = bool(tc.get("reference_match_spec")) or bool(tc.get("reference_doc_ids"))
    if has_answer and has_ref:
        return 4
    if has_ref:
        return 3
    if has_answer:
        return 2
    return 1


def chunks_matched_by_spec(
    chunk_signals: list[dict],
    match_spec: list[dict],
) -> list[str]:
    """Return ordered list of doc_ids whose chunk satisfies any spec rule.

    A spec is [{"field": "recordUrl", "value": "..."}]. Priority-OR semantics:
    a chunk matches if any (field, value) pair equals chunk[field].
    """
    if not chunk_signals or not match_spec:
        return []
    matched: list[str] = []
    seen: set[str] = set()
    for chunk in chunk_signals:
        for rule in match_spec:
            field = rule.get("field")
            value = rule.get("value")
            if not field or value is None:
                continue
            cv = chunk.get(field)
            if cv is None:
                continue
            if str(cv).strip() == str(value).strip():
                doc_id = chunk.get("docId") or chunk.get("doc_id") or ""
                if doc_id and doc_id not in seen:
                    matched.append(doc_id)
                    seen.add(doc_id)
                break  # this chunk matched; move to next chunk
    return matched


def first_matched_chunk_rank(
    chunk_signals: list[dict],
    match_spec: list[dict],
) -> int | None:
    """1-indexed rank of the first chunk that satisfies the match spec, else None."""
    if not chunk_signals or not match_spec:
        return None
    for i, chunk in enumerate(chunk_signals):
        for rule in match_spec:
            field = rule.get("field")
            value = rule.get("value")
            if not field or value is None:
                continue
            cv = chunk.get(field)
            if cv is None:
                continue
            if str(cv).strip() == str(value).strip():
                return i + 1
    return None


def first_matched_chunk(
    chunk_signals: list[dict],
    match_spec: list[dict],
) -> dict | None:
    """Return the full chunk dict that first satisfies the match spec, else None."""
    if not chunk_signals or not match_spec:
        return None
    for chunk in chunk_signals:
        for rule in match_spec:
            field = rule.get("field")
            value = rule.get("value")
            if not field or value is None:
                continue
            cv = chunk.get(field)
            if cv is None:
                continue
            if str(cv).strip() == str(value).strip():
                return chunk
    return None


def qualified_chunks_count(chunk_signals: list[dict]) -> int:
    """Number of chunks Kore.ai marked as chunkQualified=True (search retrieval set)."""
    if not chunk_signals:
        return 0
    return sum(1 for c in chunk_signals if c.get("chunkQualified") is True)


def judge_configured(app: dict) -> bool:
    """A judge is 'configured' when the API key for its provider is present.

    Provider is inferred from the judge agent's model name (anthropic / openai /
    gemini), matching the same logic the LLM client itself uses — that way a
    Gemini-based judge is correctly detected, not silently rejected.
    """
    cfg = get_llm_config(app["app_id"], "judge")
    provider = _infer_provider(cfg.get("model") or "")
    key = get_api_key(app["app_id"], provider) or ""
    return bool(key.strip())


def expected_doc_rank(retrieved_doc_ids: list[str], reference_doc_ids: list[str]) -> int | None:
    """1-indexed position of the first expected doc in retrieved list, or None."""
    if not reference_doc_ids or not retrieved_doc_ids:
        return None
    ref = set(reference_doc_ids)
    for i, d in enumerate(retrieved_doc_ids):
        if d in ref:
            return i + 1
    return None


def recall_at_k(
    retrieved_doc_ids: list[str],
    reference_doc_ids: list[str],
    levels: tuple[int, ...] = RECALL_K_LEVELS,
) -> dict[str, int]:
    """For each K in levels, return 1 if any expected doc is in top K, else 0."""
    if not reference_doc_ids:
        return {}
    ref = set(reference_doc_ids)
    out: dict[str, int] = {}
    for k in levels:
        top_k = set(retrieved_doc_ids[:k])
        out[str(k)] = 1 if (top_k & ref) else 0
    return out


def answer_similarity(rag_answer: str | None, expected: str | None) -> float | None:
    """Semantic similarity in [0, 1] between RAG answer and expected answer.

    Uses sentence-transformers embeddings (all-MiniLM-L6-v2). Falls back to
    None on missing inputs or model load failure.
    """
    return semantic_similarity(rag_answer, expected)


def question_answer_relevance(question: str | None, rag_answer: str | None) -> float | None:
    """Semantic similarity between the question and the RAG-generated answer.

    Used as a Case-1 pass/fail proxy when no ground truth is available — a
    relevant answer should be topically close to its question.
    """
    return semantic_similarity(question, rag_answer)


# ── Verdict derivation ──────────────────────────────────────────────────────

def derive_verdict(
    case_id: int,
    has_judge: bool,
    judge_scores: dict[str, Any] | None,
    expected_doc_rank_val: int | None,
    similarity: float | None,
    qa_relevance: float | None = None,
    case1_threshold: float = DEFAULT_CASE1_THRESHOLD,
    case2_threshold: float = DEFAULT_CASE2_THRESHOLD,
    chunk_rank: int | None = None,
    answer_mode: str = "answer_generation",
    top_k_pass: int = TOP_K_PASS,
) -> tuple[str | None, str]:
    """Return (verdict, verdict_source).

    verdict ∈ {'pass', 'fail', None}
    verdict_source describes how the verdict was derived.

    answer_mode='extract_only':
      Pass/fail is purely retrieval-based for all cases that have a reference doc
      (cases 3 & 4): expected doc chunk must be in top ``top_k_pass`` chunks.
      Cases 1 & 2 without a reference doc fall back to semantic similarity.

    answer_mode='answer_generation':
      Verdict is derived from answer quality.
      With judge configured  → LLM judge scores decide for all cases.
      Without judge          → semantic similarity (cases 2 & 4) or
                               Q↔Answer relevance (cases 1 & 3).
    """
    if answer_mode == "extract_only":
        if case_id in (3, 4):
            return _verdict_retrieval(chunk_rank, judge_scores or {}, top_k=top_k_pass)
        # Cases 1 & 2 in extract mode: no generated answer, use semantic if available
        return _verdict_no_judge(
            case_id, expected_doc_rank_val, similarity,
            qa_relevance, case1_threshold, case2_threshold,
        )

    # answer_generation ───────────────────────────────────────────────────────
    if has_judge:
        return _verdict_from_judge(case_id, judge_scores or {})
    return _verdict_no_judge(
        case_id, expected_doc_rank_val, similarity,
        qa_relevance, case1_threshold, case2_threshold,
    )


def _verdict_retrieval(
    chunk_rank: int | None,
    scores: dict,
    top_k: int = TOP_K_PASS,
) -> tuple[str | None, str]:
    """Pass if expected document chunk is in top ``top_k`` (extract_only mode)."""
    if scores.get("toxicity_detected") or scores.get("bias_detected") or scores.get("banned_topic_violation"):
        return "fail", f"Safety violation (top-{top_k} chunk rule)"
    if chunk_rank is None:
        return "fail", f"Expected doc not found in top {top_k} chunks"
    ok = chunk_rank <= top_k
    return (
        ("pass" if ok else "fail"),
        f"Chunk rank {chunk_rank} {'≤' if ok else '>'} top-{top_k} (extract_only)",
    )


def _verdict_from_judge(case_id: int, scores: dict) -> tuple[str | None, str]:
    """Judge-based verdict for answer_generation mode, all 4 cases."""
    if scores.get("toxicity_detected") or scores.get("bias_detected") or scores.get("banned_topic_violation"):
        return "fail", "Safety violation (LLM judge)"

    if case_id == 1:
        ok = (scores.get("coherence") or 0) >= 3 and (scores.get("fluency") or 0) >= 3
        return ("pass" if ok else "fail"), "LLM judge (coherence + fluency)"

    if case_id == 2:
        ok = (scores.get("ground_truth_relevance") or 0) >= 3 and (scores.get("completeness") or 0) >= 3
        return ("pass" if ok else "fail"), "LLM judge (answer correctness)"

    if case_id == 3:
        ok = (scores.get("groundedness") or 0) >= 3 and (scores.get("query_relevance") or 0) >= 3
        return ("pass" if ok else "fail"), "LLM judge (groundedness + relevance)"

    # case_id == 4
    ok = (
        (scores.get("groundedness") or 0) >= 3
        and (scores.get("query_relevance") or 0) >= 3
        and (scores.get("ground_truth_relevance") or 0) >= 3
        and (scores.get("completeness") or 0) >= 3
    )
    return ("pass" if ok else "fail"), "LLM judge (full eval)"


def _verdict_no_judge(
    case_id: int,
    rank: int | None,
    similarity: float | None,
    qa_relevance: float | None,
    case1_threshold: float,
    case2_threshold: float,
) -> tuple[str | None, str]:
    """Semantic-similarity fallback for answer_generation mode without a judge.

    Cases 1 & 3 → Q↔Answer relevance (no ground-truth answer available).
    Cases 2 & 4 → Answer↔Expected similarity.
    """
    if case_id in (1, 3):
        if qa_relevance is None:
            return None, "Observation only — embedding model unavailable"
        ok = qa_relevance >= case1_threshold
        return (
            ("pass" if ok else "fail"),
            f"Semantic Q↔Answer relevance ≥ {case1_threshold:.2f}",
        )
    # case_id in (2, 4)
    if similarity is None:
        return "fail", f"Semantic Answer↔Expected similarity ≥ {case2_threshold:.2f} (no answer)"
    ok = similarity >= case2_threshold
    return (
        ("pass" if ok else "fail"),
        f"Semantic Answer↔Expected similarity ≥ {case2_threshold:.2f}",
    )
