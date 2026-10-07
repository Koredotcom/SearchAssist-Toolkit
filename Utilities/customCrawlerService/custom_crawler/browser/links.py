"""Same-host link extraction helpers (used when expanding beyond sitemaps)."""
from __future__ import annotations

import asyncio
import time
from typing import Any, List, Optional, Set, Tuple
from urllib.parse import urldefrag, urljoin, urlparse

from .log import log
from .sitemap import is_html_page_url, origin_of

CHALLENGE_MARKERS = (
    "just a moment",
    "sorry, you have been blocked",
    "attention required",
    "cf-browser-verification",
    "challenge-platform",
    "verify you are not a bot",
    "checking your browser",
    "performing security verification",
)


def _challenged(title: str, html: str = "") -> bool:
    blob = f"{title}\n{(html or '')[:12000]}".lower()
    return any(m in blob for m in CHALLENGE_MARKERS)


def _same_host(url: str, seed_host: str) -> bool:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    want = seed_host.lower().removeprefix("www.")
    return bool(host and want and (host == want or host.endswith("." + want)))


def _normalize(url: str) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    if url.startswith(("mailto:", "tel:", "javascript:", "data:", "#")):
        return None
    url, _frag = urldefrag(url)
    if not url.startswith(("http://", "https://")):
        return None
    return url.rstrip() or None


async def _wait_cf(page: Any, *, cf_wait: float) -> bool:
    """Return True if still challenged after wait."""
    try:
        title = await page.title()
        html = await page.content()
    except Exception:
        return True
    if not _challenged(title, html) or cf_wait <= 0:
        return _challenged(title, html)
    log(f"CF on link discovery; waiting up to {cf_wait:.0f}s…")
    deadline = time.perf_counter() + cf_wait
    while time.perf_counter() < deadline:
        await asyncio.sleep(1.0)
        try:
            title = await page.title()
            html = await page.content()
        except Exception:
            continue
        if not _challenged(title, html):
            log(f"CF cleared for discovery → title={title!r}")
            return False
    return True


async def _extract_links(page: Any, base_url: str) -> List[str]:
    hrefs = await page.evaluate(
        """() => Array.from(document.querySelectorAll('a[href]'))
            .map(a => a.href)
            .filter(Boolean)"""
    )
    if not isinstance(hrefs, list):
        return []
    out: List[str] = []
    seen: Set[str] = set()
    for raw in hrefs:
        if not isinstance(raw, str):
            continue
        abs_url = urljoin(base_url, raw)
        norm = _normalize(abs_url)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out


async def discover_urls_via_links(
    page: Any,
    seed_url: str,
    *,
    max_url_limit: int,
    cf_wait: float = 45.0,
    link_depth: int = 1,
) -> Tuple[List[str], List[str]]:
    """
    Load seed page, extract same-host HTML links, optionally BFS to link_depth.

    Returns (visited_pages, urls_to_crawl) — crawl list includes seed and
    discovered links, capped at max_url_limit.
    """
    if not seed_url.startswith(("http://", "https://")):
        seed_url = "https://" + seed_url
    seed_url = seed_url.strip()
    origin = origin_of(seed_url)
    seed_host = urlparse(origin).hostname or ""
    limit = max_url_limit if max_url_limit > 0 else 100_000
    depth = max(0, int(link_depth))

    visited: Set[str] = set()
    collected: List[str] = []
    collected_set: Set[str] = set()

    def add_url(u: str) -> None:
        if u in collected_set:
            return
        if not is_html_page_url(u):
            return
        if not _same_host(u, seed_host):
            return
        collected_set.add(u)
        collected.append(u)

    add_url(seed_url)

    # BFS: frontier is pages we still want to extract links from
    frontier: List[str] = [seed_url]
    for level in range(depth + 1):
        if len(collected) >= limit and level > 0:
            break
        next_frontier: List[str] = []
        log(f"link discovery depth={level} frontier={len(frontier)} collected={len(collected)}")
        for url in frontier:
            if url in visited:
                continue
            visited.add(url)
            log(f"link page GET {url}")
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
                status = resp.status if resp else None
            except Exception as exc:
                log(f"link page goto warning: {type(exc).__name__}: {exc}")
                continue
            await asyncio.sleep(0.75)
            if await _wait_cf(page, cf_wait=cf_wait):
                log(f"still CF on {url} status={status} — skip link extract")
                continue
            hrefs = await _extract_links(page, page.url or url)
            same_host = [h for h in hrefs if _same_host(h, seed_host) and is_html_page_url(h)]
            log(f"extracted {len(same_host)} same-host HTML links from {url}")
            for h in same_host:
                before = len(collected)
                add_url(h)
                if len(collected) > before and level < depth and h not in visited:
                    next_frontier.append(h)
                if len(collected) >= limit:
                    break
            if len(collected) >= limit:
                break
        frontier = next_frontier
        if not frontier:
            break

    out = collected[:limit]
    log(f"link discovery done visited={len(visited)} html_pages={len(out)}")
    return sorted(visited), out
