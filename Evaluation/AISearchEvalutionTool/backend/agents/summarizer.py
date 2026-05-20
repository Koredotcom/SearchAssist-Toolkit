from __future__ import annotations

import json
import logging
from typing import Any

from db.database import get_active_prompt
from agents.llm_client import call_llm
from agents.prompts import AGENT1_PROMPT

logger = logging.getLogger(__name__)


def summarize_document(doc: dict[str, Any], app_id: str) -> dict[str, Any]:
    doc_id = doc.get("doc_id", "?")
    title = doc.get("title", "Untitled")
    content_len = len(doc.get("content") or "")

    logger.info("Agent1 | Summarising doc '%s' (id=%s, content_chars=%d)", title, doc_id, content_len)

    prompt_row = get_active_prompt(app_id, "agent1")
    system_prompt = prompt_row["prompt_text"] if prompt_row else AGENT1_PROMPT

    content = (doc.get("content") or "")[:12000]
    user_msg = f"Document title: {title}\n\nDocument content:\n{content}"

    raw = call_llm(app_id, "agent1", system_prompt, user_msg)

    try:
        extraction = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Agent1 | JSON parse failed for doc %s — attempting bracket extraction", doc_id)
        s, e = raw.find("{"), raw.rfind("}") + 1
        if s == -1 or e == 0:
            logger.error("Agent1 | Could not extract JSON from response for doc %s | raw[:200]=%s", doc_id, raw[:200])
            raise ValueError(f"Agent1 returned non-JSON for doc {doc_id}")
        extraction = json.loads(raw[s:e])

    extraction["doc_id"] = doc_id
    extraction["doc_title"] = title

    claims = len(extraction.get("atomic_claims", []))
    concepts = len(extraction.get("key_concepts", []))
    logger.info("Agent1 | Done doc '%s' | claims=%d key_concepts=%d", title, claims, concepts)

    return extraction
