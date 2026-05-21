from __future__ import annotations

import logging
import time
from typing import Any

from db.database import get_llm_config, get_active_prompt
from agents.llm_client import _infer_provider, call_llm_json, parse_json_loose
from agents.prompts import JUDGE_PROMPT

# Backoff delays (seconds) between judge retries on rate-limit errors.
# 3 attempts total: immediate → 15 s → 45 s
_RATE_LIMIT_DELAYS = [15, 45]

logger = logging.getLogger(__name__)

NUMERIC_METRICS = (
    "groundedness", "query_relevance", "ground_truth_relevance",
    "coherence", "fluency", "gpt_similarity",
    "paraphrasing", "completeness",
)
BOOLEAN_METRICS = ("bias_detected", "banned_topic_violation", "toxicity_detected")


def judge_result(
    question: str,
    expected_answer: str,
    expected_behavior: str,
    rag_response: str,
    retrieved_doc_ids: list[str],
    reference_doc_ids: list[str],
    app_id: str,
    banned_topics: list[str] | None = None,
) -> dict[str, Any]:
    cfg = get_llm_config(app_id, "judge")
    prompt_row = get_active_prompt(app_id, "judge")
    system_prompt = prompt_row["prompt_text"] if prompt_row else JUDGE_PROMPT

    banned_topics = banned_topics or []
    doc_match = any(d in retrieved_doc_ids for d in reference_doc_ids)

    logger.debug(
        "Judge | question='%s...' doc_match=%s banned_topics=%d",
        question[:80], doc_match, len(banned_topics),
    )

    context = (
        f"QUESTION: {question}\n\n"
        f"RAG_ANSWER: {rag_response}\n\n"
        f"EXPECTED_ANSWER: {expected_answer}\n\n"
        f"RETRIEVED_DOC_IDS: {retrieved_doc_ids}\n"
        f"EXPECTED_DOC_IDS: {reference_doc_ids}\n"
        f"DOCUMENT_RETRIEVED: {doc_match}\n\n"
        f"BANNED_TOPICS: {banned_topics if banned_topics else '(none configured)'}\n"
    )

    verdict = _call_judge(app_id, cfg, system_prompt, context)

    if not verdict:
        logger.warning(
            "Judge | Empty verdict returned for question='%s...' — "
            "check that the judge LLM (%s) is configured and the API key is valid.",
            question[:80], cfg.get("model", "?"),
        )

    scores: dict[str, Any] = {"doc_retrieved": doc_match}
    for k in NUMERIC_METRICS:
        v = verdict.get(k)
        if isinstance(v, (int, float)):
            scores[k] = v
    for k in BOOLEAN_METRICS:
        scores[k] = bool(verdict.get(k, False))

    failure_category = verdict.get("failure_category", "none")
    if scores.get("toxicity_detected"):
        failure_category = "toxic"
    elif scores.get("bias_detected"):
        failure_category = "biased"
    elif scores.get("banned_topic_violation"):
        failure_category = "banned_topic"
    elif not doc_match and failure_category == "none":
        failure_category = "retrieval_miss"

    logger.info(
        "Judge | scores: ground=%s qrel=%s gtrel=%s coh=%s flu=%s sim=%s comp=%s | "
        "bias=%s banned=%s tox=%s | doc_retrieved=%s failure=%s",
        scores.get("groundedness"), scores.get("query_relevance"),
        scores.get("ground_truth_relevance"), scores.get("coherence"),
        scores.get("fluency"), scores.get("gpt_similarity"),
        scores.get("completeness"),
        scores.get("bias_detected"), scores.get("banned_topic_violation"),
        scores.get("toxicity_detected"), doc_match, failure_category,
    )

    rationale = verdict.get("rationale", "")
    if not rationale and not verdict:
        rationale = (
            f"Judge scoring unavailable — the model '{cfg.get('model', '?')}' did not return a valid response. "
            "Verify your LLM configuration and API key under LLM Config."
        )

    return {
        "scores": scores,
        "failure_category": failure_category,
        "judge_rationale": rationale,
    }


def _call_judge(
    app_id: str,
    cfg: dict,
    system: str,
    user: str,
    max_tokens_override: int | None = None,
) -> dict:
    """Call the judge LLM and parse its JSON output.

    Delegates to :func:`agents.llm_client.call_llm_json`, which supports
    Anthropic, OpenAI and Gemini uniformly — historically this helper only
    handled Anthropic and OpenAI which silently broke Gemini-based judges.
    Rate-limit / 429 retries are kept here on top of the underlying call.
    """
    model: str = cfg["model"]
    max_tokens = max_tokens_override if max_tokens_override is not None else cfg["max_tokens"]
    provider = _infer_provider(model)

    # Total attempts = 1 initial + len(_RATE_LIMIT_DELAYS) retries
    delays = [None] + list(_RATE_LIMIT_DELAYS)  # None = first attempt (no sleep)
    for attempt, sleep_secs in enumerate(delays, 1):
        if sleep_secs is not None:
            logger.warning(
                "Judge | Rate limit — sleeping %ds before retry %d/%d | model=%s",
                sleep_secs, attempt, len(delays), model,
            )
            time.sleep(sleep_secs)

        logger.debug(
            "Judge | Calling %s via %s | max_tokens=%d attempt=%d",
            model, provider, max_tokens, attempt,
        )
        try:
            raw = call_llm_json(
                app_id, "judge", system, user,
                max_tokens_override=max_tokens,
            )
        except Exception as exc:
            # Detect rate-limit errors from any provider so we can sleep+retry.
            exc_str = str(exc).lower()
            is_rate_limit = (
                "rate limit" in exc_str
                or "429" in exc_str
                or "too many requests" in exc_str
                or getattr(exc, "status_code", None) == 429
                or type(exc).__name__ in ("RateLimitError",)
            )
            if is_rate_limit and attempt < len(delays):
                logger.warning(
                    "Judge | Rate limit detected (attempt %d/%d) | will retry | model=%s | error: %s",
                    attempt, len(delays), model, exc,
                )
                continue  # sleep handled at top of next iteration
            logger.error(
                "Judge | API call FAILED | model=%s provider=%s attempt=%d | error: %s",
                model, provider, attempt, exc, exc_info=True,
            )
            return {}

        parsed = parse_json_loose(raw, expect="object", agent_name="judge")
        if isinstance(parsed, dict):
            return parsed
        logger.error(
            "Judge | JSON parse failed | model=%s | raw[:200]=%s",
            model, (raw or "")[:200],
        )
        return {}

    return {}
