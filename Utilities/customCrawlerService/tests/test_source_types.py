from __future__ import annotations

import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from custom_crawler.discovery.content_status import (
    build_content_status_url,
    fetch_urls_by_status,
)
from custom_crawler.discovery.seeds import (
    SeedExpansionError,
    normalize_source_type,
    parse_csv_column,
)
from custom_crawler.job import CrawlJob
from custom_crawler.settings import ServiceConfig


class CsvSeedParsingTests(unittest.TestCase):
    def test_reads_first_column_and_dedupes(self) -> None:
        csv_text = "url\nhttps://a.com/1\n https://a.com/2 \nhttps://a.com/1\n"
        self.assertEqual(
            parse_csv_column(csv_text, "url"),
            ["https://a.com/1", "https://a.com/2"],
        )

    def test_rejects_wrong_column_header(self) -> None:
        with self.assertRaises(SeedExpansionError) as ctx:
            parse_csv_column("sitemap\nhttps://a.com/sitemap.xml\n", "url")
        self.assertEqual(ctx.exception.code, "upload_file_invalid_column")

    def test_rejects_header_only_file(self) -> None:
        with self.assertRaises(SeedExpansionError) as ctx:
            parse_csv_column("url\n\n", "url")
        self.assertEqual(ctx.exception.code, "upload_file_empty")

    def test_unknown_source_type_falls_back_to_domain_crawl(self) -> None:
        self.assertEqual(normalize_source_type("connector"), "url")
        self.assertEqual(normalize_source_type(None), "url")
        self.assertEqual(normalize_source_type("uploadSitemap"), "uploadSitemap")


class ContentStatusUrlTests(unittest.TestCase):
    def test_builds_public_api_path(self) -> None:
        self.assertEqual(
            build_content_status_url("http://localhost/", "st-1"),
            "http://localhost/api/public/bot/st-1/search/get-content-by-status",
        )

    def test_honours_path_override(self) -> None:
        self.assertEqual(
            build_content_status_url("http://host", "st-1", "custom/{streamId}/failed"),
            "http://host/custom/st-1/failed",
        )


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.status_code = 200
        self.text = ""
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, pages: list) -> None:
        self.pages = pages
        self.bodies: list = []

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *exc_info) -> bool:
        return False

    async def post(self, url, headers=None, json=None):
        self.bodies.append(json)
        return _FakeResponse(self.pages.pop(0))


class ContentStatusPaginationTests(unittest.IsolatedAsyncioTestCase):
    async def test_follows_cursor_until_has_more_is_false(self) -> None:
        client = _FakeClient(
            [
                {
                    "data": [{"url": "https://a.com/1"}, {"url": "https://a.com/2"}],
                    "hasMore": True,
                    "nextCursor": "cursor-2",
                },
                {
                    "data": [{"url": "https://a.com/2"}, {"url": "https://a.com/3"}],
                    "hasMore": False,
                    "nextCursor": None,
                },
            ]
        )
        with patch(
            "custom_crawler.discovery.content_status.httpx.AsyncClient",
            lambda **kwargs: client,
        ):
            urls = await fetch_urls_by_status(
                host="http://localhost",
                stream_id="st-1",
                source_id="fs-1",
                headers={"auth": "jwt"},
                page_limit=2,
                max_urls=50,
            )

        self.assertEqual(
            urls, ["https://a.com/1", "https://a.com/2", "https://a.com/3"]
        )
        self.assertEqual([body.get("nextCursor") for body in client.bodies], [None, "cursor-2"])
        for body in client.bodies:
            self.assertEqual(body["sourceId"], "fs-1")
            self.assertEqual(body["status"], "failed")
            self.assertNotIn("jobId", body)


class SourceTypeDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def make_job(self, submit_extra: dict, **cfg_extra) -> CrawlJob:
        cfg = ServiceConfig(
            profile_root=self.tmp.name,
            spool_dir=self.tmp.name,
            use_profile=False,
            **cfg_extra,
        )
        submit = {
            "jobId": "test-job",
            "baseUrl": "https://example.com",
            "advanceSettings": {"maxUrlLimit": 20, "crawlDepth": 5},
        }
        submit.update(submit_extra)
        job = CrawlJob(submit=submit, service_cfg=cfg, playwright=None)
        job.robots.allowed = AsyncMock(return_value=True)
        return job

    async def test_upload_url_crawls_csv_pages_across_domains(self) -> None:
        job = self.make_job(
            {"sourceType": "uploadUrl", "fileUrl": "http://files/list.csv", "fileId": "f-1"}
        )
        csv_text = "url\nhttps://example.com/a\nhttps://other.com/b\n"
        discover = AsyncMock(return_value=([], []))
        with patch(
            "custom_crawler.discovery.seeds.fetch_csv_text",
            new=AsyncMock(return_value=csv_text),
        ), patch("custom_crawler.job.discover_urls_via_sitemaps", new=discover):
            await job._collect_start_urls(None, seed_home=False)

        discover.assert_not_awaited()
        self.assertEqual(job.discovery_mode, "seed_list")
        self.assertFalse(job._bfs_active)
        self.assertEqual(
            [url for url, _depth in job._urls],
            ["https://example.com/a", "https://other.com/b"],
        )
        self.assertEqual(await job._expand_links(["https://example.com/next"], 0), 0)

    async def test_upload_url_failure_does_not_fall_back_to_domain_crawl(self) -> None:
        job = self.make_job({"sourceType": "uploadUrl", "fileUrl": "http://files/bad.csv"})
        with patch(
            "custom_crawler.discovery.seeds.fetch_csv_text",
            new=AsyncMock(return_value="link\nhttps://example.com/a\n"),
        ):
            with self.assertRaises(SeedExpansionError) as ctx:
                await job._collect_start_urls(None, seed_home=False)
        self.assertEqual(ctx.exception.code, "upload_file_invalid_column")
        self.assertEqual(job._urls, [])

    async def test_upload_sitemap_expands_only_uploaded_sitemaps(self) -> None:
        job = self.make_job(
            {"sourceType": "uploadSitemap", "fileUrl": "http://files/sitemaps.csv"}
        )
        csv_text = "sitemap\nhttps://example.com/sitemap-a.xml\nhttps://example.com/sitemap-b.xml\n"
        discover = AsyncMock(
            side_effect=[
                (["https://example.com/sitemap-a.xml"], ["https://example.com/a"]),
                (["https://example.com/sitemap-b.xml"], ["https://example.com/b"]),
            ]
        )
        with patch(
            "custom_crawler.discovery.seeds.fetch_csv_text",
            new=AsyncMock(return_value=csv_text),
        ), patch("custom_crawler.job.discover_urls_via_sitemaps", new=discover):
            await job._collect_start_urls(None, seed_home=False)

        self.assertEqual(
            [call.args[1] for call in discover.await_args_list],
            ["https://example.com/sitemap-a.xml", "https://example.com/sitemap-b.xml"],
        )
        self.assertEqual(job.discovery_mode, "sitemap")
        self.assertEqual(
            [url for url, _depth in job._urls],
            ["https://example.com/a", "https://example.com/b"],
        )

    async def test_crawl_retry_queries_content_status_by_source_only(self) -> None:
        job = self.make_job(
            {
                "sourceType": "crawl_retry",
                "streamId": "st-1",
                "extractionSourceId": "fs-1",
                "reqHeaders": [{"key": "auth", "value": "jwt-123"}],
            },
            callback_public_host="http://localhost",
        )
        fetch = AsyncMock(
            return_value=["https://example.com/failed-1", "https://example.com/failed-2"]
        )
        with patch("custom_crawler.job.fetch_urls_by_status", new=fetch):
            await job._collect_start_urls(None, seed_home=False)

        kwargs = fetch.await_args.kwargs
        self.assertEqual(kwargs["host"], "http://localhost")
        self.assertEqual(kwargs["stream_id"], "st-1")
        self.assertEqual(kwargs["source_id"], "fs-1")
        self.assertEqual(kwargs["status"], "failed")
        self.assertEqual(kwargs["headers"]["auth"], "jwt-123")
        # FindlyErrors belong to the original crawl jobs, never the retry jobId.
        self.assertNotIn("job_id", kwargs)
        self.assertEqual(job.discovery_mode, "seed_list")
        self.assertEqual(len(job._urls), 2)

    async def test_crawl_retry_without_failed_urls_fails_the_job(self) -> None:
        job = self.make_job(
            {"sourceType": "crawl_retry", "streamId": "st-1", "extractionSourceId": "fs-1"},
            callback_public_host="http://localhost",
        )
        with patch("custom_crawler.job.fetch_urls_by_status", new=AsyncMock(return_value=[])):
            with self.assertRaises(SeedExpansionError) as ctx:
                await job._collect_start_urls(None, seed_home=False)
        self.assertEqual(ctx.exception.code, "no_failed_urls_to_retry")

    async def test_recrawl_page_crawls_submitted_urls_only(self) -> None:
        job = self.make_job(
            {
                "sourceType": "recrawl_page",
                "urls": ["https://example.com/only-page"],
            }
        )
        discover = AsyncMock(return_value=([], []))
        with patch("custom_crawler.job.discover_urls_via_sitemaps", new=discover):
            await job._collect_start_urls(None, seed_home=False)

        discover.assert_not_awaited()
        self.assertEqual(job.discovery_mode, "seed_list")
        self.assertFalse(job._bfs_active)
        self.assertEqual(
            [url for url, _depth in job._urls],
            ["https://example.com/only-page"],
        )
        self.assertEqual(await job._expand_links(["https://example.com/next"], 0), 0)

    async def test_recrawl_page_dedupes_submitted_urls(self) -> None:
        job = self.make_job(
            {
                "sourceType": "recrawl_page",
                "urls": [" https://example.com/a ", "https://example.com/a", ""],
            }
        )
        await job._collect_start_urls(None, seed_home=False)
        self.assertEqual(
            [url for url, _depth in job._urls],
            ["https://example.com/a"],
        )

    async def test_recrawl_page_without_urls_fails(self) -> None:
        job = self.make_job({"sourceType": "recrawl_page"})
        with self.assertRaises(SeedExpansionError) as ctx:
            await job._collect_start_urls(None, seed_home=False)
        self.assertEqual(ctx.exception.code, "recrawl_page_url_missing")


if __name__ == "__main__":
    unittest.main()
