from __future__ import annotations

import json
import logging
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from db.database import get_active_prompt
from agents.llm_client import call_llm_json, parse_json_loose
from agents.prompts import AGENT3_PROMPT

logger = logging.getLogger(__name__)

MAX_WORKERS = 5


def _rank_batch(
    app_id: str,
    system_prompt: str,
    batch: list[dict[str, Any]],
    batch_idx: int,
) -> list[dict[str, Any]]:
    """Score a single batch of test cases (runs in a thread)."""
    logger.debug("Agent3 | Ranking batch #%d (%d cases)", batch_idx + 1, len(batch))

    payload = [
        {
            "tc_id": tc.get("tc_id"),
            "question": tc.get("question"),
            "expected_answer": tc.get("expected_answer"),
            "expected_behavior": tc.get("expected_behavior"),
            "question_type": tc.get("question_type"),
            "reference_doc_ids": tc.get("reference_doc_ids"),
            "rationale": tc.get("rationale"),
        }
        for tc in batch
    ]
    user_msg = f"Score these {len(batch)} test cases:\n\n{json.dumps(payload, indent=2)}"
    raw = call_llm_json(app_id, "agent3", system_prompt, user_msg)

    parsed = parse_json_loose(raw, expect="array", agent_name=f"Agent3:batch#{batch_idx + 1}")
    if isinstance(parsed, dict):
        for key in ("results", "scores", "data", "test_cases"):
            if isinstance(parsed.get(key), list):
                parsed = parsed[key]
                break
    results: list[dict[str, Any]] = parsed if isinstance(parsed, list) else []
    if not isinstance(parsed, (list, dict)):
        logger.error("Agent3 | No usable JSON for batch #%d", batch_idx + 1)

    decisions = {r.get("decision", "?") for r in results if isinstance(r, dict)}
    logger.debug("Agent3 | Batch #%d done | returned=%d decisions=%s", batch_idx + 1, len(results), decisions)
    return results


def rank_test_cases(
    test_cases: list[dict[str, Any]],
    app_id: str,
    batch_size: int = 10,
) -> list[dict[str, Any]]:
    total = len(test_cases)
    batches = [test_cases[i: i + batch_size] for i in range(0, total, batch_size)]
    logger.info("Agent3 | Ranking %d test cases in %d batches (%d parallel workers)",
                total, len(batches), MAX_WORKERS)

    prompt_row = get_active_prompt(app_id, "agent3")
    system_prompt = prompt_row["prompt_text"] if prompt_row else AGENT3_PROMPT

    scored: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_rank_batch, app_id, system_prompt, batch, idx): idx
            for idx, batch in enumerate(batches)
        }
        for future in as_completed(futures):
            batch_idx = futures[future]
            try:
                scored.extend(future.result())
            except Exception as exc:
                logger.error("Agent3 | FAILED for batch #%d | error: %s", batch_idx + 1, exc, exc_info=True)

    keep = sum(1 for r in scored if r.get("decision") == "KEEP")
    borderline = sum(1 for r in scored if r.get("decision") == "BORDERLINE")
    drop = sum(1 for r in scored if r.get("decision") == "DROP")
    logger.info("Agent3 | Done | total=%d KEEP=%d BORDERLINE=%d DROP=%d", len(scored), keep, borderline, drop)
    return scored
