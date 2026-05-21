from __future__ import annotations

import json
from typing import Any

import anthropic

from config import get_config

SYSTEM_PROMPT = """You are a precise document analyst. Extract atomic, verbatim-grounded facts from the provided document content. These facts will seed evaluation questions for a retrieval-augmented system, so accuracy and citability matter more than coverage.

CRITICAL RULES
1. Extract ONLY facts present in the document. No inference, no world knowledge.
2. Each atomic_claim contains EXACTLY ONE assertion. Split compound facts.
3. confidence = "high" for verbatim/near-verbatim; "low" if substantial paraphrase.
4. out_of_scope_markers: topics the document EXPLICITLY says are not covered or excluded. These seed unanswerable test cases.
5. relations: subject-predicate-object triples connecting two entities. These seed multi-hop questions.
6. Output STRICT JSON matching the schema. No prose before or after.

FORBIDDEN
- Combining facts ("X is Y AND does Z" must be two claims)
- Interpretive commentary or implications
- Filling in details not explicitly stated

LIMITS
- atomic_claims: max 40 (prioritize specificity)
- key_concepts: max 15
- entities: max 30
- relations: max 20
- out_of_scope_markers: capture all

OUTPUT SCHEMA (respond with ONLY this JSON):
{
  "atomic_claims": [
    {"claim_id": "c1", "text": "...", "confidence": "high"|"low"}
  ],
  "key_concepts": ["..."],
  "entities": [{"name": "...", "type": "PERSON|ORG|DATE|NUMERIC|TERM|LOCATION"}],
  "relations": [{"subject": "...", "predicate": "...", "object": "..."}],
  "numeric_facts": [{"value": "...", "unit": "...", "context": "..."}],
  "out_of_scope_markers": ["topic not covered: ..."]
}"""


def summarize_document(doc: dict[str, Any]) -> dict[str, Any]:
    """Run Agent 1 on a document. Returns extraction dict."""
    cfg = get_config()
    client = anthropic.Anthropic()

    content = doc.get("content", "") or ""
    title = doc.get("title", "Untitled")

    user_message = f"Document title: {title}\n\nDocument content:\n{content[:12000]}"

    message = client.messages.create(
        model=cfg.agent_model,
        max_tokens=4000,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = message.content[0].text.strip()

    try:
        extraction = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        extraction = json.loads(raw[start:end])

    extraction["doc_id"] = doc["doc_id"]
    extraction["doc_title"] = title
    return extraction
