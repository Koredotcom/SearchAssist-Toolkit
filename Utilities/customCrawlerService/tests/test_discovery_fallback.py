from __future__ import annotations

import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from custom_crawler.job import CrawlJob
from custom_crawler.settings import ServiceConfig


class DiscoveryFallbackTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def make_job(
        self,
        *,
        beyond: bool = False,
        max_urls: int = 20,
        depth: int = 5,
    ) -> CrawlJob:
        cfg = ServiceConfig(
            profile_root=self.tmp.name,
            spool_dir=self.tmp.name,
            use_profile=False,
        )
        job = CrawlJob(
            submit={
                "jobId": "test-job",
                "baseUrl": "https://example.com",
                "advanceSettings": {
                    "crawlBeyondSitemaps": beyond,
                    "maxUrlLimit": max_urls,
                    "crawlDepth": depth,
                },
            },
            service_cfg=cfg,
            playwright=None,
        )
        job.robots.allowed = AsyncMock(return_value=True)
        return job

    async def test_uses_sitemap_urls_without_bfs(self) -> None:
        job = self.make_job()
        discovered = (
            ["https://example.com/sitemap.xml"],
            ["https://example.com/a", "https://example.com/b"],
        )
        with patch(
            "custom_crawler.job.discover_urls_via_sitemaps",
            new=AsyncMock(return_value=discovered),
        ):
            await job._collect_start_urls(None, seed_home=False)

        self.assertEqual(job.discovery_mode, "sitemap")
        self.assertIsNone(job.discovery_fallback_reason)
        self.assertFalse(job._bfs_active)
        self.assertEqual([url for url, _depth in job._urls], discovered[1])

    async def test_missing_sitemap_activates_bfs_fallback(self) -> None:
        job = self.make_job()
        with patch(
            "custom_crawler.job.discover_urls_via_sitemaps",
            new=AsyncMock(return_value=([], ["https://example.com"])),
        ):
            await job._collect_start_urls(None, seed_home=False)

        self.assertEqual(job.discovery_mode, "bfs_fallback")
        self.assertEqual(job.discovery_fallback_reason, "sitemap_not_found")
        self.assertTrue(job._bfs_active)
        added = await job._expand_links(["https://example.com/next"], 0)
        self.assertEqual(added, 1)

    async def test_crawl_beyond_sitemaps_skips_sitemap_discovery(self) -> None:
        job = self.make_job(beyond=True)
        discover = AsyncMock(return_value=([], []))
        with patch("custom_crawler.job.discover_urls_via_sitemaps", new=discover):
            await job._collect_start_urls(None, seed_home=False)

        discover.assert_not_awaited()
        self.assertEqual(job.discovery_mode, "bfs")
        self.assertIsNone(job.discovery_fallback_reason)
        self.assertTrue(job._bfs_active)
        self.assertEqual([url for url, _depth in job._urls], ["https://example.com/"])
        self.assertEqual(await job._expand_links(["https://example.com/next"], 0), 1)

    async def test_depth_filtered_sitemap_activates_fallback(self) -> None:
        job = self.make_job(depth=1)
        with patch(
            "custom_crawler.job.discover_urls_via_sitemaps",
            new=AsyncMock(
                return_value=(
                    ["https://example.com/sitemap.xml"],
                    ["https://example.com/a/b/c"],
                )
            ),
        ):
            await job._collect_start_urls(None, seed_home=False)

        self.assertEqual(job.discovery_mode, "bfs_fallback")
        self.assertEqual(job.discovery_fallback_reason, "sitemap_empty_or_filtered")

    async def test_bfs_fallback_honors_url_limit(self) -> None:
        job = self.make_job(max_urls=2)
        with patch(
            "custom_crawler.job.discover_urls_via_sitemaps",
            new=AsyncMock(return_value=([], [])),
        ):
            await job._collect_start_urls(None, seed_home=False)

        added = await job._expand_links(
            [
                "https://example.com/one",
                "https://example.com/two",
                "https://example.com/three",
            ],
            0,
        )
        self.assertEqual(added, 1)
        self.assertEqual(len(job._urls), 2)


if __name__ == "__main__":
    unittest.main()
