from __future__ import annotations

import json
import logging
from typing import Any

from db.database import get_active_prompt
from agents.llm_client import call_llm_json
from agents.prompts import FILTER_GENERATOR_PROMPT

logger = logging.getLogger(__name__)


def _load_mapper(app_id: str) -> tuple[str, str] | None:
    """Read the response mapper script from DB (agent_name='filter_mapper').

    Stored as JSON: {"lang": "python"|"js", "code": "..."}
    Returns (lang, code) or None if not configured.
    """
    row = get_active_prompt(app_id, "filter_mapper")
    if not row or not row.get("prompt_text", "").strip():
        return None
    try:
        data = json.loads(row["prompt_text"])
        if isinstance(data, dict) and data.get("lang") and data.get("code", "").strip():
            return data["lang"], data["code"]
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def generate_meta_filters(
    question: str,
    app_id: str,
    user_prompt_override: str | None = None,
) -> list[dict[str, Any]]:
    """Generate Kore.ai metaFilters for a single RAG query.

    The prompt used is:
      - the saved active prompt for the 'filter_generator' agent, OR
      - the built-in FILTER_GENERATOR_PROMPT default.

    If a response mapper script is saved in DB (agent_name='filter_mapper'), the raw
    LLM response is passed through map_response(response) before being returned.
    This handles cases where the LLM doesn't follow the strict metaFilters JSON format.

    Returns a list of metaFilter groups. Empty list on parse failure or no filters.
    """
    if user_prompt_override:
        system_prompt = user_prompt_override
    else:
        row = get_active_prompt(app_id, "filter_generator")
        system_prompt = row["prompt_text"] if row else FILTER_GENERATOR_PROMPT

    mapper = _load_mapper(app_id)

    if mapper:
        # Mapper is configured — let LLM respond freely; script normalises
        system_full = system_prompt
    else:
        # No mapper — require strict JSON so default parsing succeeds
        system_full = (
            f"{system_prompt}\n\n"
            "STRICT OUTPUT FORMAT (return JSON ONLY, no prose):\n"
            '{"metaFilters": [{"condition": "AND" | "OR", "rules": ['
            '{"fieldName": "...", "fieldValue": ["..."], "operator": "..."}'
            "]}]}\n"
            "If no filters apply for this question, return: {\"metaFilters\": []}"
        )

    try:
        raw = call_llm_json(app_id, "filter_generator", system_full, f"Question: {question}")

        if mapper:
            lang, code = mapper
            from pipeline.evaluate import exec_filter_script  # local import avoids circular
            filters = exec_filter_script(
                code, lang, input_text=raw,
                py_func_names=("map_response", "get_filters"),
                js_func_names=("mapResponse", "getFilters"),
            )
            logger.debug(
                "FilterGen | Mapper produced %d filter group(s) for question='%s...'",
                len(filters), question[:60],
            )
            return filters

        parsed = json.loads(raw)
        filters = parsed.get("metaFilters", [])
        if not isinstance(filters, list):
            logger.warning("FilterGen | metaFilters is not a list, ignoring | got=%s", type(filters).__name__)
            return []
        logger.debug("FilterGen | Generated %d filter group(s) for question='%s...'", len(filters), question[:60])
        return filters

    except json.JSONDecodeError as exc:
        logger.warning("FilterGen | JSON parse failed | error=%s", exc)
        return []
    except Exception as exc:
        logger.error("FilterGen | Unexpected error | %s", exc, exc_info=True)
        return []


def build_source_filter(sys_content_type: str) -> list[dict[str, Any]]:
    """Build a single AND filter group restricting results to a Kore.ai source type."""
    return [{
        "condition": "AND",
        "rules": [{
            "fieldName": "sys_content_type",
            "fieldValue": [sys_content_type],
            "operator": "equals",
        }],
    }]


def build_field_filters(tc: dict, field_names: list[str]) -> list[dict[str, Any]]:
    """Build a combined AND metaFilter from user-selected fields on a test case.

    For each field name:
      - "sys_content_type" is read from generation_metadata
      - anything else is read from custom_fields
    Only fields that have a non-empty value for this specific test case are included,
    so test cases missing a value for a field are not filtered incorrectly.
    """
    meta = tc.get("generation_metadata") or {}
    custom = tc.get("custom_fields") or {}
    rules: list[dict] = []
    for field in field_names:
        val = meta.get(field) if field == "sys_content_type" else custom.get(field)
        if val and str(val).strip():
            rules.append({
                "fieldName": field,
                "fieldValue": [str(val).strip()],
                "operator": "equals",
            })
    if not rules:
        return []
    return [{"condition": "AND", "rules": rules}]
