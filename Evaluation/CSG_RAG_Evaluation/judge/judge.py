from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from config import get_config

_openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

FAITHFULNESS_PROMPT = """You are evaluating whether a RAG system's answer is grounded in its retrieved content.

Given:
- QUESTION: the user's query
- RAG_ANSWER: the system's response
- RETRIEVED_DOCS: document IDs that were cited

Score FAITHFULNESS (1-5):
1 = answer makes claims not supported by any retrieved source
3 = answer is mostly grounded but contains 1-2 unsupported claims
5 = every claim in the answer is directly supported by the retrieved content

Also determine the FAILURE_CATEGORY (pick one):
- "none" — answer is correct and grounded
- "hallucination" — answer contains fabricated facts not in retrieved content
- "retrieval_miss" — expected document was not retrieved
- "wrong_refusal" — refused an answerable question
- "missed_refusal" — answered an out-of-scope question
- "off_topic" — answer doesn't address the question
- "incomplete" — answer is grounded but misses key information

Respond with JSON only:
{"faithfulness": int, "failure_category": str, "rationale": str}"""

RELEVANCE_PROMPT = """You are evaluating whether a RAG system's answer addresses the user's question.

Score RELEVANCE (1-5):
1 = answer is completely unrelated to the question
3 = answer partially addresses the question but misses the main point
5 = answer directly and fully addresses what was asked

Respond with JSON only:
{"relevance": int, "rationale": str}"""

COMPLETENESS_PROMPT = """You are evaluating whether a RAG system's answer covers all key information from the expected answer.

Score COMPLETENESS (1-5):
1 = answer is missing most key information from the expected answer
3 = answer covers the main point but misses supporting details
5 = answer covers all key information present in the expected answer

Respond with JSON only:
{"completeness": int, "rationale": str}"""

REFUSAL_PROMPT = """You are evaluating whether a RAG system correctly handled a question that should be refused or clarified.

EXPECTED_BEHAVIOR: {expected_behavior}
RAG_ANSWER: {rag_answer}

For REFUSE cases: did the system decline to answer without hallucinating a response?
For CLARIFY cases: did the system ask for clarification rather than guessing?

Respond with JSON only:
{"refusal_correct": true|false, "rationale": str}"""


def judge_result(
    question: str,
    expected_answer: str,
    expected_behavior: str,
    rag_response: str,
    retrieved_doc_ids: list[str],
    reference_doc_ids: list[str],
    reference_title: str | None = None,
    retrieved_titles: list[str] | None = None,
) -> dict[str, Any]:
    """Run all judge metrics. Returns scores dict + failure_category."""
    cfg = get_config()

    retrieved_titles = retrieved_titles or []
    if reference_doc_ids:
        doc_match = any(d in retrieved_doc_ids for d in reference_doc_ids)
    elif reference_title:
        norm = reference_title.lower()
        doc_match = any(norm in t.lower() for t in retrieved_titles)
    else:
        doc_match = False

    context = (
        f"QUESTION: {question}\n\n"
        f"RAG_ANSWER: {rag_response}\n\n"
        f"EXPECTED_ANSWER: {expected_answer}\n\n"
        f"RETRIEVED_DOC_IDS: {retrieved_doc_ids}\n"
        f"EXPECTED_DOC_IDS: {reference_doc_ids}\n"
        f"DOCUMENT_RETRIEVED: {doc_match}"
    )

    faithfulness = _call_judge(_openai_client, cfg.judge_model, FAITHFULNESS_PROMPT, context)
    relevance = _call_judge(_openai_client, cfg.judge_model, RELEVANCE_PROMPT, context)
    completeness = _call_judge(_openai_client, cfg.judge_model, COMPLETENESS_PROMPT, context)

    refusal_correct: bool | None = None
    if expected_behavior in ("REFUSE", "CLARIFY"):
        refusal_context = (
            REFUSAL_PROMPT.format(
                expected_behavior=expected_behavior,
                rag_answer=rag_response,
            )
            + f"\n\nQUESTION: {question}"
        )
        refusal_result = _call_judge(_openai_client, cfg.judge_model, "", refusal_context)
        refusal_correct = refusal_result.get("refusal_correct")

    scores = {
        "faithfulness": faithfulness.get("faithfulness"),
        "relevance": relevance.get("relevance"),
        "completeness": completeness.get("completeness"),
        "refusal_correct": refusal_correct,
        "doc_retrieved": doc_match,
    }

    failure_category = faithfulness.get("failure_category", "none")
    if not doc_match and failure_category == "none":
        failure_category = "retrieval_miss"

    rationale = (
        f"Faithfulness: {faithfulness.get('rationale', '')} | "
        f"Relevance: {relevance.get('rationale', '')} | "
        f"Completeness: {completeness.get('rationale', '')}"
    )

    return {
        "scores": scores,
        "failure_category": failure_category,
        "judge_rationale": rationale,
    }


def _call_judge(client: OpenAI, model: str, system: str, user: str) -> dict[str, Any]:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        response_format={"type": "json_object"},
        max_tokens=500,
    )

    try:
        return json.loads(resp.choices[0].message.content)
    except (json.JSONDecodeError, AttributeError):
        return {}
