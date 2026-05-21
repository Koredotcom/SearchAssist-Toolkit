from __future__ import annotations

import logging
import uuid
from typing import Any
import json

from db.database import get_active_prompt
from agents.llm_client import call_llm_json, parse_json_loose
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
    target_language: str = "English",
) -> list[dict[str, Any]]:
    """Generate up to max_questions diverse, content-specific test cases for a document."""
    max_questions = max(1, min(max_questions, 5))
    doc_id = extraction["doc_id"]
    doc_title = extraction.get("doc_title", "?")

    logger.info(
        "Agent2 | Generating up to %d %s test case(s) for doc '%s' (id=%s)",
        max_questions, target_language, doc_title, doc_id,
    )

    prompt_row = get_active_prompt(app_id, "agent2")
    system_prompt = prompt_row["prompt_text"] if prompt_row else AGENT2_PROMPT

    extraction_summary = json.dumps({
        "doc_id": doc_id,
        "doc_title": doc_title,
        "atomic_claims": extraction.get("atomic_claims", []),
        "key_concepts": extraction.get("key_concepts", []),
        "entities": extraction.get("entities", []),
        "relations": extraction.get("relations", []),
        "numeric_facts": extraction.get("numeric_facts", []),
    }, indent=2)

    # Give Agent 2 enough source text to choose distinctive details, not just
    # generic questions from the extraction summary.
    full_content = (doc.get("content") or "")[:30000]

    user_msg = (
        f"Generate up to {max_questions} HIGH-QUALITY test cases for the document below.\n\n"
        "PICK QUALITY OVER QUANTITY:\n"
        f"- If the document is thin on distinctive detail, generate FEWER than {max_questions} cases.\n"
        "- Never invent a question just to hit a quota; every case must target a real, distinctive detail.\n\n"
        f"QUESTION-TYPE GUIDANCE (use as a menu, not a checklist):\n{TYPE_DESCRIPTIONS}\n"
        "Aim for variety across types. Lean toward factual and multi_hop when the document supports them.\n\n"
        "CONTENT-SPECIFICITY CHECK:\n"
        "Before writing each question, ask: 'Could this be answered by someone who never read THIS document?'\n"
        "If yes, discard it and pick a more specific detail: a named entity, number, date, step, product, role, or exact condition.\n\n"
        "HUMAN-LIKE PHRASING:\n"
        "- lowercase, short, casual\n"
        "- sound like a real user typing into a search box or support chat\n"
        "- never reference the document, policy, article, guide, source title, or internal fields\n\n"
        "EXPECTED ANSWERS:\n"
        "- 2-4 sentences, drawn directly from the document content\n"
        "- include the specific values that make the question unique\n"
        "- never punt to 'see the document' or 'refer to section X'\n\n"
        f"TARGET LANGUAGE:\n"
        f"- Write every `question`, `expected_answer`, and `rationale` in {target_language}.\n"
        f"- Keep schema keys and enum values in English exactly as specified.\n"
        f"- If the source document is in another language, translate faithfully into {target_language}; do not change facts.\n"
        f"- Preserve product names, system names, URLs, IDs, and brand terms exactly when they should not be translated.\n\n"
        f"reference_doc_ids must be exactly: [\"{doc_id}\"]\n\n"
        f"DOCUMENT TITLE: {doc_title}\n\n"
        f"DOC ID: {doc_id}\n\n"
        f"DOCUMENT CONTENT (source of truth):\n{full_content}\n\n"
        f"DOCUMENT EXTRACTION (structured facts):\n{extraction_summary}"
    )

    logger.debug("Agent2 | doc=%s content_chars=%d max_questions=%d", doc_id, len(full_content), max_questions)

    raw = call_llm_json(app_id, "agent2", system_prompt, user_msg)

    cases = parse_json_loose(raw, expect="array", agent_name=f"Agent2:{doc_id}")
    if isinstance(cases, dict):
        for key in ("test_cases", "cases", "questions", "data", "results"):
            if isinstance(cases.get(key), list):
                cases = cases[key]
                break
    if not isinstance(cases, list):
        logger.error("Agent2 | Expected array, got %s for doc=%s", type(cases).__name__, doc_id)
        return []

    result: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            logger.warning("Agent2 | Skipping non-dict entry in doc=%s: %r", doc_id, case)
            continue
        # Enforce ANSWER behavior — never let model produce REFUSE/CLARIFY
        case["expected_behavior"] = "ANSWER"
        case["tc_id"] = f"tc-{uuid.uuid4()}"
        case["app_id"] = app_id
        case["reference_doc_ids"] = [doc["doc_id"]]
        metadata = case.get("generation_metadata") if isinstance(case.get("generation_metadata"), dict) else {}
        metadata["target_language"] = target_language
        case["generation_metadata"] = metadata
        result.append(case)

    logger.info("Agent2 | Done doc '%s' | generated=%d", doc_title, len(result))
    return result
