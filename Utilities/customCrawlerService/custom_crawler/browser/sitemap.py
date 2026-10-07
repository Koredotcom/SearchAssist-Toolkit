"""Sitemap discovery via robots.txt + common paths + nested indexes.

Uses the same headed Playwright tab as page crawl so Cloudflare cookies apply.
Stops once ``max_url_limit`` unique HTML page URLs are collected.
"""
from __future__ import annotations

import asyncio
import gzip
import re
import xml.etree.ElementTree as ET
from html import unescape
from typing import Any, List, Optional, Sequence, Set, Tuple
from urllib.parse import urljoin, urlparse

from .log import log

SITEMAP_PATTERNS = (
    "sitemap.xml",
    "sitemap_index.xml",
    "sitemap-index.xml",
    "sitemaps.xml",
    "sitemap/sitemap.xml",
    "wp-sitemap.xml",
    ".sitemap.xml",
    "sitemap",
    "admin/config/search/xmlsitemap",
    "sitemap/sitemap-index.xml",
    "sitemap_news.xml",
    "sitemap-news.xml",
    "sitemap1.xml",
    "sitemap_1.xml",
    "post-sitemap.xml",
    "page-sitemap.xml",
    "category-sitemap.xml",
    "sitemap.php",
    "sitemap.html",
)

NON_HTML_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".bmp",
    ".ico",
    ".tif",
    ".tiff",
    ".heic",
    ".avif",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".gz",
    ".rar",
    ".7z",
    ".tar",
    ".mp3",
    ".mp4",
    ".mov",
    ".avi",
    ".webm",
    ".mkv",
    ".wav",
    ".css",
    ".js",
    ".map",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".json",
    ".xml",
    ".rss",
    ".atom",
)

CHALLENGE_MARKERS = (
    "just a moment",
    "sorry, you have been blocked",
    "attention required",
    "cf-browser-verification",
    "challenge-platform",
    "verify you are not a bot",
    "checking your browser",
)


def origin_of(url: str) -> str:
    p = urlparse(url if "://" in url else f"https://{url}")
    host = p.netloc or p.path.split("/")[0]
    return f"{(p.scheme or 'https')}://{host}".rstrip("/")


def looks_like_sitemap_url(url: str) -> bool:
    lower = (url or "").lower().split("?", 1)[0]
    return lower.endswith((".xml", ".xml.gz", ".rss"))


def is_html_page_url(url: str) -> bool:
    path = urlparse(url).path.lower().rstrip("/")
    if not path or path.endswith("/"):
        return True
    return not any(path.endswith(ext) for ext in NON_HTML_EXTENSIONS)


def _page_blocked(title: str, html: str) -> bool:
    blob = f"{title}\n{(html or '')[:20000]}".lower()
    return any(m in blob for m in CHALLENGE_MARKERS)


def _clean_url(url_text: Optional[str]) -> Optional[str]:
    if not url_text:
        return None
    cleaned = unescape(url_text).strip().strip("<>")
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned or None


def _resolve_url(cleaned_url: str, sitemap_base: str) -> str:
    if not sitemap_base:
        return cleaned_url
    lower_url = cleaned_url.lower()
    lower_base = sitemap_base.lower()
    if lower_url == lower_base or lower_url.startswith(lower_base + "/"):
        return cleaned_url
    return urljoin(sitemap_base + "/", cleaned_url)


def _is_valid_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    # CF HTML often leaks into robots as ``…/sitemap.xml</pre></body></html>``.
    if any(ch in url for ch in "<>\"' \t\r\n"):
        return False
    return True


def _decode_robots_txt(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8", errors="replace")


def _maybe_gunzip(url: str, body: bytes) -> bytes:
    if url.lower().endswith(".gz") or body[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(body)
        except Exception:
            return body
    return body


def _extract_sitemaps_from_robots(robots_txt: str) -> List[str]:
    found: List[str] = []
    for line in (robots_txt or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.lower().startswith("sitemap:"):
            continue
        value = line.split(":", 1)[1]
        raw = value.split("#", 1)[0].strip()
        sitemap_url = raw.split()[0] if raw else ""
        sitemap_url = re.sub(r"<.*$", "", sitemap_url).rstrip(".,;)")
        if _is_valid_http_url(sitemap_url):
            found.append(sitemap_url)
    return found


def parse_sitemap_xml(content: bytes, sitemap_url: str) -> Tuple[List[str], List[str]]:
    """Return (child_sitemaps, page_urls) from sitemap / sitemapindex / rss XML."""
    child_sitemaps: List[str] = []
    page_urls: List[str] = []
    parsed = urlparse(sitemap_url)
    sitemap_base = f"{parsed.scheme}://{parsed.netloc}".rstrip("/") if parsed.scheme and parsed.netloc else sitemap_url.rstrip("/")

    try:
        root = ET.fromstring(content)
    except Exception as exc:
        log(f"sitemap XML parse failed {sitemap_url}: {type(exc).__name__}: {exc}")
        return child_sitemaps, page_urls

    ns_match = re.match(r"\{(.*)\}", root.tag)
    ns = ns_match.group(1) if ns_match else None

    if root.tag.endswith("sitemapindex"):
        path = f".//{{{ns}}}sitemap/{{{ns}}}loc" if ns else ".//sitemap/loc"
        for loc in root.findall(path):
            cleaned = _clean_url(loc.text)
            if cleaned:
                child_sitemaps.append(_resolve_url(cleaned, sitemap_base))
        return child_sitemaps, page_urls

    if root.tag.endswith("rss"):
        for item in root.findall(".//item"):
            link = item.find("link")
            if link is not None:
                cleaned = _clean_url(link.text)
                if cleaned:
                    page_urls.append(_resolve_url(cleaned, sitemap_base))
        return child_sitemaps, page_urls

    loc_path = f".//{{{ns}}}url/{{{ns}}}loc" if ns else ".//url/loc"
    child_like: List[str] = []
    pages_like: List[str] = []
    for loc in root.findall(loc_path):
        cleaned = _clean_url(getattr(loc, "text", None))
        if not cleaned:
            continue
        resolved = _resolve_url(cleaned, sitemap_base)
        if re.search(r"sitemap[^/]*\.xml(\.gz)?$", cleaned, re.IGNORECASE):
            child_like.append(resolved)
        else:
            pages_like.append(resolved)

    if child_like and not pages_like:
        child_sitemaps.extend(child_like)
    else:
        page_urls.extend(pages_like)
    return child_sitemaps, page_urls


def _body_looks_like_challenge(body: bytes) -> bool:
    head = body[:8000].decode("utf-8", errors="ignore").lower()
    if any(m in head for m in CHALLENGE_MARKERS):
        return True
    # Cloudflare/HTML error pages mistaken for sitemap XML
    if b"<html" in body[:500].lower() or b"<!doctype html" in body[:500].lower():
        return True
    return False


def _body_is_challenge(body: bytes) -> bool:
    """Anti-bot interstitial specifically, unlike the HTML-or-challenge check above.

    A plain HTML 404 for ``/sitemap.xml`` is normal and says nothing about the next
    candidate path, so only marker hits may abort probing.
    """
    head = body[:8000].decode("utf-8", errors="ignore").lower()
    return any(m in head for m in CHALLENGE_MARKERS)


def _looks_like_gzip(body: bytes) -> bool:
    return len(body) >= 2 and body[:2] == b"\x1f\x8b"


def _looks_like_xml(body: bytes) -> bool:
    head = body.lstrip()[:200].lower()
    return head.startswith(b"<?xml") or head.startswith(b"<urlset") or head.startswith(
        b"<sitemapindex"
    ) or head.startswith(b"<rss")


async def _fetch_via_page_js(page: Any, url: str, *, timeout_ms: int) -> Tuple[Optional[int], bytes]:
    """In-page fetch() — same cookies/TLS as the headed tab (better vs CF than request.get)."""
    import base64

    page.set_default_timeout(timeout_ms)
    result = await page.evaluate(
        """async (url) => {
            const resp = await fetch(url, { credentials: 'include', redirect: 'follow' });
            const buf = await resp.arrayBuffer();
            const bytes = new Uint8Array(buf);
            const chunk = 0x8000;
            let binary = '';
            for (let i = 0; i < bytes.length; i += chunk) {
                binary += String.fromCharCode.apply(null, bytes.subarray(i, Math.min(i + chunk, bytes.length)));
            }
            return {
                status: resp.status,
                b64: btoa(binary),
                contentType: resp.headers.get('content-type') || '',
            };
        }""",
        url,
    )
    if not isinstance(result, dict):
        return None, b""
    status = int(result.get("status") or 0) or None
    b64 = result.get("b64") or ""
    body = base64.b64decode(b64) if b64 else b""
    return status, body


async def _fetch_gz_via_download(page: Any, url: str, *, timeout_ms: int) -> Tuple[Optional[int], bytes]:
    """Capture Chrome file-download for .xml.gz (page.goto starts a Download)."""
    from pathlib import Path

    try:
        async with page.expect_download(timeout=timeout_ms) as download_info:
            try:
                await page.goto(url, wait_until="commit", timeout=timeout_ms)
            except Exception as exc:
                # Expected when Chrome starts a download instead of navigation
                if "Download is starting" not in str(exc) and "download" not in str(exc).lower():
                    log(f"goto during download: {type(exc).__name__}: {exc}")
        download = await download_info.value
        path = await download.path()
        if not path:
            # force save if path not ready
            path = str(Path("/tmp") / (download.suggested_filename or "sitemap.xml.gz"))
            await download.save_as(path)
        raw = Path(path).read_bytes()
        log(f"download captured {url} ({len(raw)} bytes, file={download.suggested_filename!r})")
        return 200, raw
    except Exception as exc:
        log(f"download capture failed {url}: {type(exc).__name__}: {exc}")
        return None, b""


async def fetch_bytes(page: Any, url: str, *, timeout_ms: int = 90_000, cf_wait: float = 25.0) -> Tuple[Optional[int], bytes]:
    """
    GET url via headed Playwright Chrome only (no context.request.get).

    Cloudflare often blocks APIRequestContext; the real tab is required.

    Order:
      1) .gz — page.goto + expect_download (Chrome download capture)
      2) in-page fetch() (same cookies/TLS as the visible tab)
      3) page.goto for robots.txt / plain .xml
    """
    import time

    status: Optional[int] = None
    body = b""
    is_gz = url.lower().rstrip("/").endswith(".gz")

    # 1) .gz → Playwright download (page.goto starts a file Download)
    if is_gz:
        log(f"playwright download GET {url}")
        dl_status, dl_body = await _fetch_gz_via_download(page, url, timeout_ms=timeout_ms)
        if dl_body and not _body_looks_like_challenge(dl_body) and (
            _looks_like_gzip(dl_body) or _looks_like_xml(dl_body)
        ):
            return dl_status, dl_body
        status, body = dl_status or status, dl_body or body
        # Fall through to in-page fetch if download returned CF HTML / empty

    # 2) In-page fetch() — real Chrome tab network stack
    try:
        log(f"playwright in-page fetch {url}")
        js_status, js_body = await _fetch_via_page_js(page, url, timeout_ms=timeout_ms)
        if js_body and not _body_looks_like_challenge(js_body):
            if is_gz and not (_looks_like_gzip(js_body) or _looks_like_xml(js_body)):
                log(f"in-page fetch non-gzip/xml for .gz url; continuing ({len(js_body)} bytes)")
            else:
                log(f"in-page fetch OK {url} status={js_status} bytes={len(js_body)}")
                return js_status, js_body
        if js_body and _body_looks_like_challenge(js_body):
            log(f"in-page fetch still CF/HTML for {url} status={js_status}")
            status, body = js_status, js_body
        elif js_body:
            status, body = js_status, js_body
    except Exception as exc:
        log(f"in-page fetch warning {url}: {type(exc).__name__}: {exc}")

    if is_gz:
        return status, body or b""

    # 3) Normal Playwright navigation (robots.txt / .xml)
    log(f"playwright goto {url}")
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    except Exception as exc:
        log(f"goto warning {url}: {type(exc).__name__}: {exc}")
        return status, body or b""

    status = resp.status if resp else status
    try:
        if resp is not None:
            got = await resp.body()
            if got:
                body = got
    except Exception:
        pass

    try:
        title = await page.title()
        html = await page.content()
    except Exception:
        title, html = "", ""

    if _page_blocked(title, html) and cf_wait > 0:
        log(f"CF on sitemap/robots fetch; waiting up to {cf_wait:.0f}s… {url}")
        deadline = time.perf_counter() + cf_wait
        while time.perf_counter() < deadline:
            await asyncio.sleep(0.75)
            try:
                html = await page.content()
                title = await page.title() or ""
            except Exception:
                continue
            if not _page_blocked(title, html):
                try:
                    body = html.encode("utf-8", errors="replace")
                except Exception:
                    pass
                break

    return status, body or b""


async def discover_urls_via_sitemaps(
    page: Any,
    seed_url: str,
    *,
    max_url_limit: int,
    cf_wait: float = 25.0,
    extra_sitemaps: Sequence[str] = (),
) -> Tuple[List[str], List[str]]:
    """
    Same control flow as UrlFetcher._discover_sitemaps_and_extract_urls:
      direct sitemap URL → robots.txt → common paths → recurse indexes
      until max_url_limit HTML page URLs.
    """
    if not seed_url.startswith(("http://", "https://")):
        seed_url = "https://" + seed_url
    seed_url = seed_url.strip()
    origin = origin_of(seed_url)
    limit = max_url_limit if max_url_limit > 0 else 100_000

    sitemap_urls_found: Set[str] = set()
    all_visited: Set[str] = set()
    urls_to_crawl: Set[str] = set()

    def add_pages(pages: Sequence[str]) -> None:
        for u in pages:
            if not u or not _is_valid_http_url(u):
                continue
            if not is_html_page_url(u):
                continue
            urls_to_crawl.add(u)

    async def extract_from_sitemap(sitemap_url: str) -> Tuple[List[str], List[str]]:
        log(f"sitemap GET {sitemap_url}")
        status, body = await fetch_bytes(page, sitemap_url, cf_wait=cf_wait)
        if not body:
            log(f"sitemap empty status={status} {sitemap_url}")
            return [], []
        if _body_looks_like_challenge(body) or (status is not None and int(status) >= 400):
            log(
                f"sitemap blocked/CF HTML status={status} bytes={len(body)} {sitemap_url} "
                "(re-run create_profile.py if cookies expired)"
            )
            return [], []
        body = _maybe_gunzip(sitemap_url, body)
        if _body_looks_like_challenge(body):
            log(f"sitemap still looks like HTML after gunzip {sitemap_url}")
            return [], []
        children, pages = parse_sitemap_xml(body, sitemap_url)
        log(f"sitemap parsed children={len(children)} pages={len(pages)} status={status}")
        return children, pages

    # Land on the site and wait until CF clears. Sitemap XML can succeed via
    # in-page fetch() even while the tab is still challenged; HTML product
    # pages need a real cleared session (cf_clearance) from this warmup.
    from .challenge import wait_out_challenge

    try:
        log(f"warmup GET {origin}/")
        await page.goto(origin + "/", wait_until="domcontentloaded", timeout=90_000)
        await asyncio.sleep(1.0)
        title, _html, still_cf = await wait_out_challenge(page, cf_wait=cf_wait)
        if still_cf:
            log(
                f"warmup still Cloudflare (title={title!r}) — "
                "sitemap XML may still fetch, but HTML pages will likely fail Turnstile"
            )
        else:
            log(f"warmup CF cleared → title={title!r}")
    except Exception as exc:
        log(f"warmup warning: {type(exc).__name__}: {exc}")

    is_direct = looks_like_sitemap_url(seed_url)
    if extra_sitemaps:
        for s in extra_sitemaps:
            if s:
                sitemap_urls_found.add(s.strip())

    if is_direct:
        sitemap_urls_found.add(seed_url)
        all_visited.add(seed_url)
        children, pages = await extract_from_sitemap(seed_url)
        sitemap_urls_found.update(children)
        add_pages(pages)
        if not children:
            out = sorted(urls_to_crawl)[:limit]
            log(f"direct sitemap (flat): returning {len(out)} URLs")
            return list(all_visited), out
        if len(urls_to_crawl) >= limit:
            out = sorted(urls_to_crawl)[:limit]
            log(f"reached limit {limit} from direct sitemap")
            return list(all_visited), out
    else:
        robots_url = f"{origin}/robots.txt"
        log(f"robots GET {robots_url}")
        _status, robots_body = await fetch_bytes(page, robots_url, cf_wait=cf_wait)
        if _body_looks_like_challenge(robots_body):
            log("robots.txt still looks like CF/HTML — ignoring Sitemap: lines, probing common paths")
        else:
            for sm in _extract_sitemaps_from_robots(_decode_robots_txt(robots_body)):
                sitemap_urls_found.add(sm)
                log(f"robots Sitemap: {sm}")

        # Same common-path list as CrawlerConstants.SITEMAP_PATTERNS.
        # If robots.txt already listed valid sitemaps, skip probing (avoids extra CF hits).
        if sitemap_urls_found:
            log(
                f"robots listed {len(sitemap_urls_found)} sitemap(s); "
                "skipping common-path probes"
            )
        else:
            for pattern in SITEMAP_PATTERNS:
                location = f"{origin}/{pattern}"
                if location in sitemap_urls_found:
                    continue
                status, body = await fetch_bytes(
                    page, location, cf_wait=min(cf_wait, 15.0)
                )
                if body and _body_is_challenge(body):
                    # Cloudflare is answering for this origin, so every remaining
                    # pattern costs another challenge wait and returns the same page.
                    log(
                        f"common-path probing stopped at {location} — anti-bot challenge "
                        "response, no sitemap is reachable in this session"
                    )
                    break
                if (
                    status == 200
                    and body
                    and not _body_looks_like_challenge(body)
                    and (_looks_like_xml(body) or _looks_like_gzip(body) or b"<" in body[:400])
                ):
                    sitemap_urls_found.add(location)
                    log(f"common sitemap hit {location}")
                    # Stop probing — further 404s only burn the CF session.
                    break

    if not sitemap_urls_found:
        log("no sitemaps found — falling back to seed URL")
        return [], [seed_url]

    processed: Set[str] = set()
    queue: List[str] = list(sitemap_urls_found)
    log(f"sitemaps_to_process = {len(queue)}")

    while queue and len(urls_to_crawl) < limit:
        sitemap_url = queue.pop(0)
        if sitemap_url in processed:
            continue
        processed.add(sitemap_url)
        all_visited.add(sitemap_url)
        log(f"processing sitemap {len(processed)}/{len(processed) + len(queue)} {sitemap_url}")
        children, pages = await extract_from_sitemap(sitemap_url)
        for child in children:
            if child not in processed and child not in queue:
                queue.append(child)
        before = len(urls_to_crawl)
        add_pages(pages)
        log(
            f"added {len(urls_to_crawl) - before} HTML URLs "
            f"(total {len(urls_to_crawl)}/{limit})"
        )

    out = sorted(urls_to_crawl)[:limit]
    log(
        f"discovery done sitemaps_visited={len(all_visited)} "
        f"html_pages={len(out)}"
    )
    return sorted(all_visited), out
