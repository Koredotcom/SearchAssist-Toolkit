"""Single-page fetch for the crawl job. Returns Findly callback field names via PageResult."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urldefrag, urljoin

from .challenge import (
    extract_title,
    looks_blocked,
    looks_challenged,
    turnstile_present,
    wait_out_challenge,
)
from .log import log

_HTML_CT = ("text/html", "application/xhtml+xml")
MAX_HTML_BYTES = 5 * 1024 * 1024


def is_html(content_type: Optional[str]) -> bool:
    if not content_type:
        return True  # assume HTML when the server omits it
    ct = content_type.split(";", 1)[0].strip().lower()
    return ct in _HTML_CT


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class PageResult:
    """Same field names and ``to_page()`` payload the Findly callback already expects."""

    page_url: str
    redirected_url: Optional[str] = None
    status: str = "failed"  # "success" | "failed"
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    page_html: Optional[str] = None
    http_last_modified: str = ""
    http_etag: str = ""
    http_x_last_modified: str = ""
    error: Optional[str] = None
    crawled_at: str = ""
    links: List[str] = field(default_factory=list)
    challenged: bool = False
    blocked: bool = False
    title: str = ""

    def to_page(self) -> Dict[str, Any]:
        return {
            "page_url": self.page_url,
            "redirected_url": self.redirected_url,
            "status": self.status,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "page_html": self.page_html,
            "http_last_modified": self.http_last_modified,
            "http_etag": self.http_etag,
            "http_x_last_modified": self.http_x_last_modified,
            "error": self.error,
            "crawled_at": self.crawled_at,
        }


async def _extract_links(page: Any, base_url: str) -> List[str]:
    try:
        hrefs = await page.evaluate(
            """() => Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href)
                .filter(Boolean)"""
        )
    except Exception as exc:
        log(f"link extract warning: {type(exc).__name__}: {exc}")
        return []
    if not isinstance(hrefs, list):
        return []
    out: List[str] = []
    seen = set()
    for raw in hrefs:
        if not isinstance(raw, str):
            continue
        url, _frag = urldefrag(urljoin(base_url, raw))
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


async def fetch_page(
    page: Any,
    url: str,
    *,
    wait_after_load: float = 1.0,
    cf_wait: float = 45.0,
    page_timeout_ms: int = 90_000,
    extract_links: bool = False,
) -> PageResult:
    """Load one URL in the shared headed tab."""
    result = PageResult(page_url=url, crawled_at=_now_iso())

    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=page_timeout_ms)
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        log(f"goto failed {url}: {result.error}")
        return result

    if resp is None:
        result.error = "no_response"
        return result

    result.status_code = resp.status
    try:
        headers = await resp.all_headers()
    except Exception:
        headers = {}
    result.content_type = headers.get("content-type")
    result.http_last_modified = headers.get("last-modified", "") or ""
    result.http_etag = headers.get("etag", "") or ""
    result.http_x_last_modified = headers.get("x-last-modified", "") or ""
    result.redirected_url = resp.url if resp.url and resp.url != url else None

    if wait_after_load > 0:
        await asyncio.sleep(wait_after_load)

    if not is_html(result.content_type):
        result.status = "success"
        log(f"non-HTML content_type={result.content_type} {url}")
        return result

    title, html, still_cf = await wait_out_challenge(page, cf_wait=cf_wait)
    result.title = title or extract_title(html)
    result.challenged = still_cf

    if still_cf:
        result.blocked = looks_blocked(title, html)
        result.error = "cloudflare_blocked" if result.blocked else "challenge_not_cleared"
        result.status_code = result.status_code or 403
        if result.blocked:
            log(f"Cloudflare blocked this URL {url} title={result.title!r}")
        else:
            log(
                f"still Cloudflare after {cf_wait:.0f}s {url} "
                f"turnstile={await turnstile_present(page)} title={result.title!r}"
            )
        return result

    result.page_html = (html or "")[:MAX_HTML_BYTES]
    result.status = "success"
    # Cloudflare's JS often answers 403 first and then navigates to the real page.
    if result.status_code is None or int(result.status_code) >= 400:
        result.status_code = 200
    if extract_links:
        result.links = await _extract_links(page, page.url or url)
    return result


async def looks_blocked_now(page: Any) -> bool:
    """Challenge state of the current page, used for consecutive-block aborts."""
    try:
        return looks_challenged(await page.title(), await page.content())
    except Exception:
        return False
