from __future__ import annotations

import json
import uuid
from typing import Any

import anthropic

from config import get_config

QUESTION_TYPES = [
    "factual",
    "multi_hop",
    "comparative",
    "negation_unanswerable",
    "ambiguous",
    "boundary",
    "refusal_required",
]

# Target distribution for ~80 cases (generate 1.4x = ~112)
TYPE_QUOTAS = {
    "factual": 28,
    "multi_hop": 21,
    "comparative": 14,
    "negation_unanswerable": 21,
    "ambiguous": 7,
    "boundary": 14,
    "refusal_required": 14,
}

TYPE_INSTRUCTIONS = {
    "factual": (
        "Generate questions whose answer is a single specific fact from the document. "
        "The answer must be extractive or one-step paraphrase. "
        "Example: 'What deployment date is recorded for v3.2?' → '14 March 2024'"
    ),
    "multi_hop": (
        "Generate questions requiring synthesis of 2+ distinct facts from the document. "
        "Verify the answer is NOT derivable from any single sentence alone. "
        "Use the relations list to find bridges between entities."
    ),
    "comparative": (
        "Generate questions comparing two entities, time periods, or numeric facts. "
        "Both sides must be grounded in the document."
    ),
    "negation_unanswerable": (
        "Generate plausible-looking questions NOT answerable from the document. "
        "Use out_of_scope_markers, entity-swap (real entity but details absent), or adjacent topics. "
        "expected_answer = 'Insufficient information in source documents'. "
        "expected_behavior = 'REFUSE'."
    ),
    "ambiguous": (
        "Generate questions with 2+ plausible answers in the document where a RAG should ask for "
        "clarification rather than guess. expected_behavior = 'CLARIFY'."
    ),
    "boundary": (
        "Generate questions about edge values: thresholds, exact numeric limits, "
        "inclusive/exclusive ranges, before/after specific dates."
    ),
    "refusal_required": (
        "Generate questions fully out-of-scope for the document domain: "
        "personal information, opinions, advice. expected_behavior = 'REFUSE'. "
        "expected_answer = 'This question is outside the scope of available content'."
    ),
}

SYSTEM_PROMPT = """You are a test case generator for a RAG evaluation framework. Generate high-quality evaluation Q&A pairs grounded ONLY in the provided document content.

UNIVERSAL RULES
1. Every test case must be answerable (or correctly unanswerable) using ONLY the provided content. No world-knowledge questions.
2. expected_answer must be derivable from the document, or be the canonical refusal string for negative cases.
3. Cite reference_doc_ids from the input.
4. rationale explains grounding and what the case tests.
5. Output a JSON array ONLY. No prose.

FORBIDDEN
- Questions answerable from general knowledge alone
- Meta-questions ("What does the document say about X?")
- Questions referencing the document directly ("the doc", "the article")
- Yes/no questions without justification follow-up

OUTPUT SCHEMA (JSON array):
[
  {
    "question": "...",
    "expected_answer": "...",
    "expected_behavior": "ANSWER"|"REFUSE"|"CLARIFY",
    "reference_doc_ids": ["..."],
    "question_type": "...",
    "difficulty": 1|2|3,
    "answer_type": "EXTRACTIVE"|"ABSTRACTIVE"|"NUMERIC"|"BOOLEAN"|"LIST",
    "rationale": "..."
  }
]"""


def generate_test_cases(
    extraction: dict[str, Any],
    doc: dict[str, Any],
    batch_size: int = 5,
) -> list[dict[str, Any]]:
    """Run Agent 2 on one document extraction. Returns raw test cases (pre-ranking)."""
    cfg = get_config()
    client = anthropic.Anthropic()

    all_cases: list[dict[str, Any]] = []

    extraction_summary = json.dumps(
        {
            "doc_id": extraction["doc_id"],
            "doc_title": extraction["doc_title"],
            "atomic_claims": extraction.get("atomic_claims", []),
            "key_concepts": extraction.get("key_concepts", []),
            "entities": extraction.get("entities", []),
            "relations": extraction.get("relations", []),
            "numeric_facts": extraction.get("numeric_facts", []),
            "out_of_scope_markers": extraction.get("out_of_scope_markers", []),
        },
        indent=2,
    )

    for q_type, target in TYPE_QUOTAS.items():
        calls_needed = max(1, -(-target // batch_size))  # ceiling division

        for _ in range(calls_needed):
            user_msg = (
                f"QUESTION TYPE: {q_type}\n\n"
                f"TYPE INSTRUCTION: {TYPE_INSTRUCTIONS[q_type]}\n\n"
                f"Generate exactly {batch_size} test cases of this type.\n\n"
                f"DOCUMENT EXTRACTION:\n{extraction_summary}"
            )

            message = client.messages.create(
                model=cfg.agent_model,
                max_tokens=3000,
                temperature=0.7,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )

            raw = message.content[0].text.strip()
            try:
                cases = json.loads(raw)
            except json.JSONDecodeError:
                start = raw.find("[")
                end = raw.rfind("]") + 1
                cases = json.loads(raw[start:end])

            for case in cases:
                case["tc_id"] = f"tc-{uuid.uuid4()}"
                case.setdefault("reference_doc_ids", [doc["doc_id"]])
                all_cases.append(case)

    return all_cases
