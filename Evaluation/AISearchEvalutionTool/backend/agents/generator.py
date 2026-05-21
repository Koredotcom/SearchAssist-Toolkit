from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from db.database import get_active_prompt
from agents.llm_client import call_llm
from agents.prompts import AGENT2_PROMPT

logger = logging.getLogger(__name__)

# Only answerable, document-grounded question types — no refusal, no clarify
TYPE_PRIORITY = [
    "factual",
    "multi_hop",
    "comparative",
    "boundary",
    "follow_up",
]

TYPE_DESCRIPTIONS = (
    "- factual: a single specific fact directly extractable from the document\n"
    "- multi_hop: requires combining 2+ distinct facts from different parts of the document\n"
    "- comparative: compares two entities, time periods, or numeric values from the document\n"
    "- boundary: asks about exact numeric limits, thresholds, or date boundaries\n"
    "- follow_up: a natural follow-up question a reader might ask after understanding the entire document, answered by synthesising the document holistically"
)


def generate_test_cases(
    extraction: dict[str, Any],
    doc: dict[str, Any],
    app_id: str,
    max_questions: int = 5,
) -> list[dict[str, Any]]:
    """Generate up to max_questions diverse, answerable test cases for a document."""
    max_questions = max(1, min(max_questions, 5))
    doc_id = extraction["doc_id"]
    doc_title = extraction.get("doc_title", "?")

    logger.info(
        "Agent2 | Generating %d test case(s) for doc '%s' (id=%s)",
        max_questions, doc_title, doc_id,
    )

    prompt_row = get_active_prompt(app_id, "agent2")
    system_prompt = prompt_row["prompt_text"] if prompt_row else AGENT2_PROMPT

    selected_types = TYPE_PRIORITY[:max_questions]

    extraction_summary = json.dumps({
        "doc_id": doc_id,
        "doc_title": doc_title,
        "atomic_claims": extraction.get("atomic_claims", []),
        "key_concepts": extraction.get("key_concepts", []),
        "entities": extraction.get("entities", []),
        "relations": extraction.get("relations", []),
        "numeric_facts": extraction.get("numeric_facts", []),
    }, indent=2)

    full_content = (doc.get("content") or "")[:6000]

    user_msg = (
        f"Generate exactly {max_questions} answerable test case(s) for the document below.\n\n"
        f"PREFERRED QUESTION TYPES (one per type, in this order):\n"
        + "\n".join(f"  {i+1}. {t}" for i, t in enumerate(selected_types))
        + f"\n\nQUESTION TYPE DEFINITIONS:\n{TYPE_DESCRIPTIONS}\n\n"
        "RULES:\n"
        "- Every question MUST be fully answerable from the document content.\n"
        "- Every test case must use a DIFFERENT question type.\n"
        "- ALWAYS set expected_behavior to 'ANSWER'. Never generate refusal or clarification questions.\n"
        "- For follow_up questions, base them on the entire document and answer them by synthesising key information.\n"
        f"- CRITICAL: You MUST return exactly {max_questions} object(s). Never return fewer.\n"
        "- FALLBACK: If a preferred type is NOT applicable to this document (no numeric data for 'boundary',\n"
        "  no two comparable items for 'comparative', no multi-step path for 'multi_hop'), substitute it\n"
        "  with 'factual' or 'follow_up'. Mark the substituted question_type accordingly.\n\n"
        f"DOCUMENT TITLE: {doc_title}\n\n"
        f"DOCUMENT CONTENT:\n{full_content}\n\n"
        f"DOCUMENT EXTRACTION (structured facts):\n{extraction_summary}"
    )

    logger.debug("Agent2 | types=%s | doc=%s", selected_types, doc_id)

    raw = call_llm(app_id, "agent2", system_prompt, user_msg)

    try:
        cases = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Agent2 | JSON parse failed for doc=%s — attempting bracket extraction", doc_id)
        s, e = raw.find("["), raw.rfind("]") + 1
        if s == -1 or e == 0:
            logger.error("Agent2 | Could not extract JSON for doc=%s | raw[:200]=%s", doc_id, raw[:200])
            return []
        cases = json.loads(raw[s:e])

    result: list[dict[str, Any]] = []
    for case in cases:
        # Enforce ANSWER behavior — never let model produce REFUSE/CLARIFY
        case["expected_behavior"] = "ANSWER"
        case["tc_id"] = f"tc-{uuid.uuid4()}"
        case["app_id"] = app_id
        case.setdefault("reference_doc_ids", [doc["doc_id"]])
        result.append(case)

    logger.info("Agent2 | Done doc '%s' | generated=%d", doc_title, len(result))
    return result
