"""Findly public API client for ``get-content-by-status``.

Used by ``crawl_retry`` jobs to pull the failed URLs of a source:

``POST {host}/api/public/bot/{streamId}/search/get-content-by-status``
with an ``auth`` JWT header and body ``{"sourceId": ..., "status": "failed"}``.

The request is scoped by **sourceId only**. FindlyErrors rows stay keyed by the
crawl job that produced them, so filtering by the new retry ``jobId`` would
always return an empty page.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from ..obs.logging import log

DEFAULT_CONTENT_STATUS_PATH = "/api/public/bot/{streamId}/search/get-content-by-status"
# Guard against a server that keeps returning a cursor.
MAX_PAGES = 500


class ContentStatusError(RuntimeError):
    """Failed URL lookup could not complete. ``code`` is reported as the job error."""

    def __init__(self, code: str, message: Optional[str] = None) -> None:
        super().__init__(message or code)
        self.code = code


def build_content_status_url(host: str, stream_id: str, path_template: str = "") -> str:
    template = (path_template or DEFAULT_CONTENT_STATUS_PATH).strip() or DEFAULT_CONTENT_STATUS_PATH
    if not template.startswith("/"):
        template = "/" + template
    path = template.replace("{streamId}", stream_id)
    return f"{(host or '').rstrip('/')}{path}"


async def fetch_urls_by_status(
    *,
    host: str,
    stream_id: str,
    source_id: str,
    headers: Dict[str, str],
    status: str = "failed",
    page_limit: int = 200,
    max_urls: int = 5000,
    path_template: str = "",
    timeout: float = 30.0,
    logger: Optional[logging.Logger] = None,
) -> List[str]:
    """Page through ``get-content-by-status`` and return unique URLs."""
    if not (host or "").strip():
        raise ContentStatusError(
            "content_status_host_not_configured",
            "CRAWLER_CONTENT_STATUS_HOST / CRAWLER_CALLBACK_PUBLIC_HOST is not set.",
        )
    if not stream_id or not source_id:
        raise ContentStatusError(
            "content_status_identifiers_missing",
            "streamId and sourceId (extractionSourceId) are required for crawl_retry.",
        )

    url = build_content_status_url(host, stream_id, path_template)
    request_headers = dict(headers or {})
    request_headers.setdefault("Content-Type", "application/json")

    urls: List[str] = []
    seen = set()
    next_cursor: Optional[str] = None
    pages = 0

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        while pages < MAX_PAGES and len(urls) < max_urls:
            body: Dict[str, Any] = {
                "sourceId": source_id,
                "status": status,
                "limit": max(1, min(page_limit, max_urls - len(urls))),
            }
            if next_cursor:
                body["nextCursor"] = next_cursor
            try:
                resp = await client.post(url, headers=request_headers, json=body)
            except Exception as exc:
                raise ContentStatusError(
                    "content_status_unreachable",
                    f"{url} unreachable: {type(exc).__name__}: {exc}",
                ) from exc
            if resp.status_code >= 300:
                raise ContentStatusError(
                    "content_status_request_failed",
                    f"{url} returned HTTP {resp.status_code}: {(resp.text or '')[:200]}",
                )
            try:
                payload = resp.json()
            except ValueError as exc:
                raise ContentStatusError(
                    "content_status_bad_response", f"{url} returned a non-JSON body."
                ) from exc

            pages += 1
            rows = payload.get("data") or []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                row_url = str(row.get("url") or "").strip()
                if not row_url or row_url in seen:
                    continue
                seen.add(row_url)
                urls.append(row_url)
                if len(urls) >= max_urls:
                    break

            if logger is not None:
                log(
                    logger,
                    logging.INFO,
                    "content-by-status page fetched",
                    url=url,
                    status=status,
                    page=pages,
                    rows=len(rows),
                    urls=len(urls),
                    hasMore=bool(payload.get("hasMore")),
                )

            cursor = payload.get("nextCursor")
            if not payload.get("hasMore") or not cursor or cursor == next_cursor:
                break
            next_cursor = str(cursor)

    return urls
