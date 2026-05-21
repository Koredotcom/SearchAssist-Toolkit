from __future__ import annotations

import logging
from typing import Any

from db.database import get_active_prompt
from agents.llm_client import call_llm_json, parse_json_loose
from agents.prompts import AGENT1_PROMPT

logger = logging.getLogger(__name__)


def summarize_document(doc: dict[str, Any], app_id: str) -> dict[str, Any]:
    doc_id = doc.get("doc_id", "?")
    title = doc.get("title", "Untitled")
    content_len = len(doc.get("content") or "")

    logger.info("Agent1 | Summarising doc '%s' (id=%s, content_chars=%d)", title, doc_id, content_len)

    prompt_row = get_active_prompt(app_id, "agent1")
    system_prompt = prompt_row["prompt_text"] if prompt_row else AGENT1_PROMPT

    content = (doc.get("content") or "")[:60000]
    user_msg = f"Document title: {title}\n\nDocument content:\n{content}"

    raw = call_llm_json(app_id, "agent1", system_prompt, user_msg, max_tokens_override=12000)

    extraction = parse_json_loose(raw, expect="object", agent_name=f"Agent1:{doc_id}")
    if not isinstance(extraction, dict):
        raise ValueError(f"Agent1 returned non-JSON for doc {doc_id} (got {type(extraction).__name__})")

    extraction["doc_id"] = doc_id
    extraction["doc_title"] = title

    claims = len(extraction.get("atomic_claims", []))
    concepts = len(extraction.get("key_concepts", []))
    logger.info("Agent1 | Done doc '%s' | claims=%d key_concepts=%d", title, claims, concepts)

    return extraction
