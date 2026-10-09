from __future__ import annotations

import hashlib
import logging
from typing import Any, Generator

from koreai.client import get_client

logger = logging.getLogger(__name__)


def fetch_documents(
    app: dict,
    filters: dict[str, Any] | None = None,
    extraction_type: str | None = None,
    source_id: str | None = None,
    max_docs: int = 10,
) -> Generator[dict[str, Any], None, None]:
    """Yield documents from Content by Condition API with cursor pagination."""
    app_id = app.get("app_id", "?")
    bot_id = app.get("bot_id", "?")
    url = f"{app['host_url']}/api/public/bot/{bot_id}/content-by-cond"

    unlimited = max_docs == 0
    logger.info(
        "Kore.ai | Fetching documents | app=%s extraction_type=%s source_id=%s max_docs=%s filters=%s",
        app_id, extraction_type, source_id, "unlimited" if unlimited else max_docs, filters,
    )

    query: dict[str, Any] = dict(filters or {})
    if extraction_type:
        query["extractionType"] = extraction_type

    next_cursor: str | None = None
    fetched = 0
    page = 0

    with get_client(app) as client:
        while unlimited or fetched < max_docs:
            page += 1
            payload: dict[str, Any] = {"query": query}
            if next_cursor:
                payload["nextCursor"] = next_cursor

            logger.debug("Kore.ai | Content page %d | fetched_so_far=%d cursor=%s", page, fetched, next_cursor)
            resp = client.post(url, json=payload)

            if not resp.is_success:
                logger.error(
                    "Kore.ai | Content API error | status=%d | body=%s",
                    resp.status_code, resp.text[:300],
                )
            resp.raise_for_status()

            data = resp.json()
            items = data.get("data", [])
            logger.debug("Kore.ai | Content page %d returned %d items", page, len(items))

            if not items:
                logger.warning("Kore.ai | Empty page returned on page %d — stopping", page)
                break

            for item in data.get("data", []):
                if not unlimited and fetched >= max_docs:
                    logger.debug("Kore.ai | Reached max_docs=%d — stopping", max_docs)
                    return
                item_source_id = item.get("connectorId") or item.get("extractionSourceId")
                if source_id and item_source_id != source_id:
                    continue
                source = item.get("_source", {})
                content = (
                    source.get("content")
                    or source.get("page_body")
                    or source.get("text")
                    or source.get("page_preview")
                    or source.get("page_html")
                    or ""
                )
                title = (
                    source.get("title")
                    or source.get("file_title")
                    or source.get("page_title")
                    or source.get("recordTitle")
                    or item.get("_id", "Untitled")
                )

                logger.debug(
                    "Kore.ai | Doc #%d: id=%s title='%s' connector=%s content_chars=%d",
                    fetched + 1, item["_id"], title, item_source_id, len(content),
                )

                yield {
                    "doc_id": item["_id"],
                    "app_id": app_id,
                    "title": title,
                    "content_hash": hashlib.sha256(content.encode()).hexdigest(),
                    "content": content,
                    "metadata": source,
                    "sys_content_type": source.get("sys_content_type"),
                    "source_url": (
                        source.get("url")
                        or source.get("page_url")
                        or source.get("base_url")
                        or source.get("sys_source_url")
                    ),
                    "connector_id": item_source_id,
                }
                fetched += 1

            next_cursor = data.get("nextCursor")
            if not next_cursor:
                logger.debug("Kore.ai | No nextCursor — all pages exhausted after %d docs", fetched)
                break

    logger.info("Kore.ai | Document fetch complete | total_fetched=%d", fetched)
