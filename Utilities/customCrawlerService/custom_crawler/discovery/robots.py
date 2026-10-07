"""robots.txt fetch, parse, cache, and allow-check (per-host).

Sitemap: line parsing matches Findly ``components.py`` (BOM strip, comments,
http/https validation). Full sitemap discovery (common patterns + recursion)
lives in ``sitemap.py``; this module only supplies robots Sitemap: seeds and
``can_fetch`` checks.
"""
from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _decode_robots_txt(resp: httpx.Response) -> str:
    """Same strategy as Findly ``UrlFetcher._decode_robots_txt``."""
    raw = resp.content or b""
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    encoding = None
    declared = (resp.charset_encoding or "").lower()
    if declared and declared not in {"iso-8859-1", "latin-1", "latin1"}:
        encoding = declared
    if not encoding:
        encoding = "utf-8"
    try:
        return raw.decode(encoding, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")


def _is_valid_sitemap_url(url: str) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _extract_sitemaps_from_robots(robots_txt: str) -> List[str]:
    out: List[str] = []
    if not robots_txt:
        return out
    for line in robots_txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.lower().startswith("sitemap:"):
            continue
        value = line.split(":", 1)[1]
        sitemap_url = value.split("#", 1)[0].strip()
        if _is_valid_sitemap_url(sitemap_url):
            out.append(sitemap_url)
    return out


class RobotsCache:
    def __init__(self, respect: bool = True, timeout: float = 15.0) -> None:
        self.respect = respect
        self.timeout = timeout
        self._parsers: Dict[str, Optional[RobotFileParser]] = {}
        self._sitemaps: Dict[str, List[str]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _host_key(self, url: str) -> Tuple[str, str]:
        parts = urlsplit(url)
        return parts.scheme or "https", parts.netloc

    async def _load(self, scheme: str, netloc: str) -> None:
        key = f"{scheme}://{netloc}"
        robots_url = f"{key}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        sitemaps: List[str] = []
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT}
            ) as client:
                resp = await client.get(robots_url)
            if resp.status_code >= 400:
                parser.parse([])
            else:
                text = _decode_robots_txt(resp)
                parser.parse(text.splitlines())
                sitemaps = _extract_sitemaps_from_robots(text)
        except Exception:
            parser = None  # fetch failed → treat as allow-all
        self._parsers[netloc] = parser
        self._sitemaps[netloc] = sitemaps

    async def _ensure(self, url: str) -> None:
        scheme, netloc = self._host_key(url)
        if netloc in self._parsers:
            return
        lock = self._locks.setdefault(netloc, asyncio.Lock())
        async with lock:
            if netloc not in self._parsers:
                await self._load(scheme, netloc)

    async def allowed(self, url: str, user_agent: str = "*") -> bool:
        if not self.respect:
            return True
        await self._ensure(url)
        _, netloc = self._host_key(url)
        parser = self._parsers.get(netloc)
        if parser is None:
            return True
        try:
            return parser.can_fetch(user_agent, url)
        except Exception:
            return True

    async def sitemaps_for(self, url: str) -> List[str]:
        await self._ensure(url)
        _, netloc = self._host_key(url)
        return list(self._sitemaps.get(netloc, []))
