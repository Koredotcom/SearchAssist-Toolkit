from __future__ import annotations

import unittest
from typing import Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from custom_crawler.browser import sitemap as sitemap_mod

CHALLENGE_HTML = b"<html><head><title>Just a moment...</title></head><body></body></html>"
HTML_404 = b"<html><body><h1>404 Not Found</h1></body></html>"
URLSET_XML = (
    b'<?xml version="1.0"?>'
    b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    b"<url><loc>https://example.com/a</loc></url>"
    b"</urlset>"
)


class SitemapProbeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.requested: List[str] = []
        patcher = patch(
            "custom_crawler.browser.challenge.wait_out_challenge",
            new=AsyncMock(return_value=("Example", "<html></html>", False)),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def fetcher(self, responses: Dict[str, Tuple[Optional[int], bytes]], default):
        async def fetch_bytes(_page, url, **_kwargs):
            self.requested.append(url)
            return responses.get(url, default)

        return fetch_bytes

    async def discover(self, responses, default):
        with patch.object(
            sitemap_mod, "fetch_bytes", new=self.fetcher(responses, default)
        ):
            return await sitemap_mod.discover_urls_via_sitemaps(
                AsyncMock(), "https://example.com", max_url_limit=10, cf_wait=0.0
            )

    async def test_challenge_stops_common_path_probing(self) -> None:
        visited, pages = await self.discover({}, (403, CHALLENGE_HTML))

        probes = [u for u in self.requested if not u.endswith("robots.txt")]
        self.assertEqual(len(probes), 1, f"probed {probes} after a challenge response")
        self.assertEqual(visited, [])
        self.assertEqual(pages, ["https://example.com"])

    async def test_html_404_keeps_probing_next_pattern(self) -> None:
        index = "https://example.com/sitemap_index.xml"
        visited, pages = await self.discover(
            {
                "https://example.com/robots.txt": (200, b"User-agent: *"),
                index: (200, URLSET_XML),
            },
            (404, HTML_404),
        )

        self.assertIn(index, self.requested)
        self.assertEqual(visited, [index])
        self.assertEqual(pages, ["https://example.com/a"])


if __name__ == "__main__":
    unittest.main()
