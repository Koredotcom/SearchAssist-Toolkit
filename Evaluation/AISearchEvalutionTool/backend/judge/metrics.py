"""Non-LLM metrics + per-row case detection for the 4-case evaluation design.

Cases:
  1: question only                                  → observation; optional LLM self-eval
  2: question + expected_answer                     → answer correctness
  3: question + reference_doc(s)                    → retrieval eval
  4: question + expected_answer + reference_doc(s)  → full eval
"""
from __future__ import annotations

import json
from typing import Any

from agents.llm_client import _infer_provider
from db.database import get_api_key, get_llm_config
from judge.embeddings import semantic_similarity

# Default semantic similarity thresholds (overridden per-app from app_config)
DEFAULT_CASE1_THRESHOLD = 0.5
DEFAULT_CASE2_THRESHOLD = 0.5

# Recall@K levels reported on every Case-3 / Case-4 row
RECALL_K_LEVELS = (1, 3, 5, 10)

# Pass criterion for Cases 3 & 4 (extract_only): expected doc chunk must be in top-K
# of the scoring list (qualified-only or raw — see CHUNK_SCORING_*).
TOP_K_PASS = 5

CHUNK_SCORING_QUALIFIED = "qualified_only"
CHUNK_SCORING_RAW = "raw"


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


def qualified_chunk_signals(chunk_signals: list[dict]) -> list[dict]:
    """Chunks with chunkQualified=True, preserving Kore.ai chunk_result order."""
    return [c for c in chunk_signals if c.get("chunkQualified") is True]


def chunks_matched_by_spec(
    chunk_signals: list[dict],
    match_spec: list[dict],
) -> list[str]:
    """Return ordered list of doc_ids whose chunk satisfies any spec rule.

    A spec is [{"field": "recordUrl", "value": "..."}]. Priority-OR semantics:
    a chunk matches if any (field, value) pair equals chunk[field].

    For extract scoring, pass ``qualified_chunk_signals(...)`` so only qualified rows count.
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
    """1-indexed rank of the first matching chunk in ``chunk_signals`` (caller filters qualified list for extract)."""
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


def expects_reference_document(
    match_spec: list[dict] | None,
    effective_ref_ids: list[str],
) -> bool:
    """Whether this test case defines an expected document to check against search results."""
    return bool(match_spec) or bool(effective_ref_ids)


def doc_retrieved_from_search(rank: int | None, expects_reference: bool) -> bool:
    """Derived from Advance Search cited_doc_ids — not from the LLM judge."""
    if not expects_reference:
        return False
    return rank is not None


def retrieval_pass_top_k_chunks(chunk_rank: int | None, top_k: int = TOP_K_PASS) -> bool:
    """True when the first matching expected chunk is within the top ``top_k`` of the scoring list."""
    return chunk_rank is not None and chunk_rank <= top_k


def doc_retrieved_for_mode(
    *,
    answer_mode: str,
    doc_rank: int | None,
    chunk_rank: int | None,
    expects_reference: bool,
    top_k: int = TOP_K_PASS,
) -> bool:
    """Extract mode: expected chunk in top-K of chunk_result. Generation: doc anywhere in list."""
    if not expects_reference:
        return False
    if answer_mode == "extract_only":
        return retrieval_pass_top_k_chunks(chunk_rank, top_k)
    return doc_rank is not None


def extract_scoring_chunks(
    chunk_signals: list[dict],
    mode: str = CHUNK_SCORING_QUALIFIED,
) -> list[dict]:
    """Chunk list used for extract pass/fail, Recall@K, and extract LLM scoring."""
    if mode == CHUNK_SCORING_RAW:
        return list(chunk_signals)
    return qualified_chunk_signals(chunk_signals)


def merge_retrieval_failure_category(
    category: str | None,
    *,
    doc_retrieved: bool,
    expects_reference: bool,
) -> str:
    """Apply API-derived retrieval rules on top of judge / heuristic categories.

    - Missing expected doc → always ``retrieval_miss``.
    - Doc present → never keep ``retrieval_miss`` (judge must not own this label).
    """
    cat = (category or "none").strip() or "none"
    if expects_reference and not doc_retrieved:
        return "retrieval_miss"
    if cat == "retrieval_miss":
        return "none"
    return cat


def format_expected_document(
    match_spec: list[dict] | None,
    reference_doc_ids: list[str] | None = None,
) -> str:
    """Human-readable expected document for exports."""
    if match_spec:
        return json.dumps(match_spec, ensure_ascii=False)
    if reference_doc_ids:
        return ", ".join(reference_doc_ids)
    return ""


def recall_at_k(
    retrieved_doc_ids: list[str],
    reference_doc_ids: list[str],
    levels: tuple[int, ...] = RECALL_K_LEVELS,
) -> dict[str, int]:
    """For each K in levels, return 1 if any expected doc is in top K cited docs, else 0."""
    if not reference_doc_ids:
        return {}
    ref = set(reference_doc_ids)
    out: dict[str, int] = {}
    for k in levels:
        top_k = set(retrieved_doc_ids[:k])
        out[str(k)] = 1 if (top_k & ref) else 0
    return out


def recall_at_k_from_chunks(
    chunk_signals: list[dict],
    reference_doc_ids: list[str],
    match_spec: list[dict] | None,
    levels: tuple[int, ...] = RECALL_K_LEVELS,
) -> dict[str, int]:
    """Recall@K using the first K rows of the scoring chunk list (qualified-only for extract)."""
    if not chunk_signals or (not reference_doc_ids and not match_spec):
        return {}
    ref = set(reference_doc_ids)
    out: dict[str, int] = {}
    for k in levels:
        top_chunks = chunk_signals[:k]
        if match_spec:
            out[str(k)] = 1 if first_matched_chunk_rank(top_chunks, match_spec) else 0
        else:
            doc_ids = {c.get("docId") for c in top_chunks if c.get("docId")}
            out[str(k)] = 1 if (doc_ids & ref) else 0
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
      Pass/fail is chunk-level: first matching expected chunk must be in the top
      ``top_k_pass`` rows of the scoring list. Scoring list is either
      chunkQualified-only (default) or full chunk_result (raw), per run setting.
      No LLM judge for verdict.

    answer_mode='answer_generation':
      Verdict is derived from answer quality.
      With judge configured  → LLM judge scores decide for all cases.
      Without judge          → semantic similarity (cases 2 & 4) or
                               Q↔Answer relevance (cases 1 & 3).
    """
    if answer_mode == "extract_only":
        if case_id in (3, 4):
            return _verdict_retrieval(chunk_rank, {}, top_k=top_k_pass)
        return None, "extract_only — no reference document on test case"

    # answer_generation ───────────────────────────────────────────────────────
    if has_judge:
        return _verdict_from_judge(case_id, judge_scores or {})
    return _verdict_no_judge(
        case_id, expected_doc_rank_val, similarity,
        qa_relevance, case1_threshold, case2_threshold,
    )


def _verdict_doc_top_k(
    doc_rank: int | None,
    scores: dict,
    top_k: int = TOP_K_PASS,
) -> tuple[str | None, str]:
    """Pass if expected document is in top ``top_k`` cited docIds (extract_only mode)."""
    if scores.get("toxicity_detected") or scores.get("bias_detected") or scores.get("banned_topic_violation"):
        return "fail", f"Safety violation (top-{top_k} doc rule)"
    if doc_rank is None:
        return "fail", f"Expected document not in cited results (top-{top_k})"
    ok = doc_rank <= top_k
    return (
        ("pass" if ok else "fail"),
        f"Doc rank {doc_rank} {'≤' if ok else '>'} top-{top_k} (extract_only, Recall@5 aligned)",
    )


def _verdict_retrieval(
    chunk_rank: int | None,
    scores: dict,
    top_k: int = TOP_K_PASS,
) -> tuple[str | None, str]:
    """Pass if expected chunk is in top ``top_k`` of the extract scoring list."""
    qualified_only = scores.get("chunk_scoring_mode", CHUNK_SCORING_QUALIFIED) != CHUNK_SCORING_RAW
    pool = "qualified" if qualified_only else "raw"
    if scores.get("toxicity_detected") or scores.get("bias_detected") or scores.get("banned_topic_violation"):
        return "fail", f"Safety violation (top-{top_k} {pool} chunk rule)"
    if chunk_rank is None:
        return "fail", f"Expected doc not in top {top_k} {pool} chunks"
    ok = chunk_rank <= top_k
    rank_label = "Qualified chunk rank" if qualified_only else "Chunk rank"
    return (
        ("pass" if ok else "fail"),
        f"{rank_label} {chunk_rank} {'≤' if ok else '>'} top-{top_k} ({pool}, extract_only)",
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
