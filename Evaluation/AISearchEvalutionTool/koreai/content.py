from __future__ import annotations

import hashlib
import json
from typing import Any, Generator

from config import get_config
from koreai.client import get_client


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def fetch_documents(
    filters: dict[str, Any] | None = None,
    max_docs: int | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Yield documents from Content by Condition API with cursor pagination."""
    cfg = get_config()
    limit = max_docs or cfg.max_docs
    url = f"{cfg.koreai_host_url}/api/public/bot/{cfg.koreai_bot_id}/content-by-cond"

    next_cursor: str | None = None
    fetched = 0

    with get_client() as client:
        while fetched < limit:
            payload: dict[str, Any] = {"query": filters or {}}
            if next_cursor:
                payload["nextCursor"] = next_cursor

            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("data", []):
                if fetched >= limit:
                    return

                source = item.get("_source", {})
                content = source.get("content", "") or ""
                title = (
                    source.get("title")
                    or source.get("file_title")
                    or item.get("_id", "")
                )

                yield {
                    "doc_id": item["_id"],
                    "title": title,
                    "content_hash": _hash(content),
                    "content": content,
                    "metadata": source,
                    "sys_content_type": source.get("sys_content_type"),
                    "source_url": source.get("url") or source.get("base_url"),
                }
                fetched += 1

            next_cursor = data.get("nextCursor")
            if not next_cursor:
                break
