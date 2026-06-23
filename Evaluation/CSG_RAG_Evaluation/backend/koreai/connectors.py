from __future__ import annotations

import logging
from typing import Any

from koreai.client import get_client

logger = logging.getLogger(__name__)

# Cap on pagination when aggregating content-derived sources (web / file).
# Kore.ai's content-by-cond returns ~20 records per page by default — capping
# at 100 pages gives us ~2000 records of enumeration before we give up and
# return what we have. For Viasat-style apps where Websites/Documents are
# small slices of the index (most volume lives in connectors) this is plenty.
_MAX_AGGREGATION_PAGES = 100


def list_connectors(app: dict) -> list[dict[str, Any]]:
    """Fetch all connectors (sources) for an app."""
    app_id = app.get("app_id", "?")
    bot_id = app.get("bot_id", "?")
    url = f"{app['host_url']}/api/public/bot/{bot_id}/connectors"
    logger.info("Kore.ai | Fetching connectors for app=%s bot=%s", app_id, bot_id)

    connectors = []
    skip = 0
    limit = 20

    with get_client(app) as client:
        while True:
            logger.debug("Kore.ai | GET connectors | skip=%d limit=%d", skip, limit)
            resp = client.get(url, params={"skip": skip, "limit": limit})

            if not resp.is_success:
                logger.error(
                    "Kore.ai | Connectors API error | status=%d | body=%s",
                    resp.status_code, resp.text[:300],
                )
            resp.raise_for_status()

            data = resp.json()
            items = data.get("connectors", [])
            logger.debug("Kore.ai | Connectors page: got %d items", len(items))

            for item in items:
                connectors.append({
                    "connector_id": item.get("_id"),
                    "name": item.get("name"),
                    "type": item.get("type"),
                    "is_active": item.get("isActive", False),
                    "records_count": item.get("recordsCount", 0),
                    "size": item.get("size", 0),
                })
            if not data.get("hasMore"):
                break
            skip += limit

    logger.info("Kore.ai | Found %d connectors for app=%s", len(connectors), app_id)
    for c in connectors:
        logger.debug("  connector: id=%s name='%s' type=%s active=%s records=%d",
                     c["connector_id"], c["name"], c["type"], c["is_active"], c["records_count"])
    return connectors


def list_content_sources(app: dict, sys_content_type: str) -> list[dict[str, Any]]:
    """List the source containers behind a given ``sys_content_type``.

    Kore.ai's public API only documents one source-listing endpoint
    (``GET /connectors``) which doesn't include web crawls or uploaded files —
    those live under "Websites" and "Documents" in the admin UI and are
    indistinguishable from connector content except by ``sys_content_type``.

    To surface them we paginate the documented ``POST /content-by-cond`` API
    filtered by ``sys_content_type`` (``"web"`` for websites, ``"file"`` for
    uploads) and aggregate by ``extractionSourceId``.

    Returns one entry per parent source ("fs-..." for crawls/uploads) with:
      - ``source_id``       : the extractionSourceId (parent container)
      - ``name``            : human label (sys_source_name → first url → source_id)
      - ``sys_content_type``: echoed back for the UI badge
      - ``records_count``   : number of documents observed in this source
      - ``sample_url``      : first non-empty url we saw (handy for click-through)
      - ``base_url``        : first non-empty base_url we saw
    """
    app_id = app.get("app_id", "?")
    bot_id = app.get("bot_id", "?")
    url = f"{app['host_url']}/api/public/bot/{bot_id}/content-by-cond"

    logger.info(
        "Kore.ai | Aggregating content sources | app=%s sys_content_type=%s",
        app_id, sys_content_type,
    )

    aggregated: dict[str, dict[str, Any]] = {}
    next_cursor: str | None = None
    pages = 0

    with get_client(app) as client:
        while pages < _MAX_AGGREGATION_PAGES:
            pages += 1
            payload: dict[str, Any] = {"query": {"sys_content_type": sys_content_type}}
            if next_cursor:
                payload["nextCursor"] = next_cursor

            resp = client.post(url, json=payload)
            if not resp.is_success:
                logger.error(
                    "Kore.ai | content-by-cond error | sys_content_type=%s status=%d body=%s",
                    sys_content_type, resp.status_code, resp.text[:300],
                )
                resp.raise_for_status()

            data = resp.json()
            items = data.get("data", []) or []
            logger.debug(
                "Kore.ai | content-by-cond page %d (%s) → %d items",
                pages, sys_content_type, len(items),
            )
            if not items:
                break

            for item in items:
                src_id = item.get("extractionSourceId") or "unknown"
                source = item.get("_source", {}) or {}
                bucket = aggregated.setdefault(src_id, {
                    "source_id":        src_id,
                    "name":             source.get("sys_source_name") or "",
                    "sys_content_type": sys_content_type,
                    "records_count":    0,
                    "sample_url":       source.get("url") or "",
                    "base_url":         source.get("base_url") or "",
                })
                bucket["records_count"] += 1
                if not bucket["name"]:
                    bucket["name"] = source.get("sys_source_name") or ""
                if not bucket["sample_url"]:
                    bucket["sample_url"] = source.get("url") or ""
                if not bucket["base_url"]:
                    bucket["base_url"] = source.get("base_url") or ""

            next_cursor = data.get("nextCursor")
            if not next_cursor:
                break
        else:
            logger.warning(
                "Kore.ai | Hit aggregation cap (%d pages) for sys_content_type=%s — "
                "result counts may be partial",
                _MAX_AGGREGATION_PAGES, sys_content_type,
            )

    # Post-process: fall back name to base_url / sample_url / source_id
    out = []
    for bucket in aggregated.values():
        if not bucket["name"]:
            bucket["name"] = bucket["base_url"] or bucket["sample_url"] or bucket["source_id"]
        out.append(bucket)

    # Largest sources first — matches user intuition
    out.sort(key=lambda b: -b["records_count"])

    logger.info(
        "Kore.ai | Aggregated %d %s source(s) across %d page(s) for app=%s",
        len(out), sys_content_type, pages, app_id,
    )
    return out
