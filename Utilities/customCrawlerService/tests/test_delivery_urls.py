from __future__ import annotations

import unittest

from custom_crawler.delivery.urls import merge_callback_headers, resolve_delivery_urls


class DeliveryUrlResolutionTests(unittest.TestCase):
    def test_payload_urls_win_over_sdk_config(self) -> None:
        callback, complete = resolve_delivery_urls(
            {
                "jobId": "crawl-1",
                "streamId": "stream-1",
                "callbackUrl": "https://payload.example/callback",
                "completeUrl": "https://payload.example/complete",
            },
            callback_public_host="http://localhost:3000",
            callback_url_default="http://cfg/callback",
            complete_url_default="http://cfg/complete",
        )
        self.assertEqual(callback, "https://payload.example/callback")
        self.assertEqual(complete, "https://payload.example/complete")

    def test_sdk_absolute_defaults_when_payload_empty(self) -> None:
        callback, complete = resolve_delivery_urls(
            {"jobId": "crawl-1", "streamId": "stream-1", "callbackUrl": "", "completeUrl": ""},
            callback_public_host="http://localhost:3000",
            callback_url_default="http://cfg/callback",
            complete_url_default="http://cfg/complete",
        )
        self.assertEqual(callback, "http://cfg/callback")
        self.assertEqual(complete, "http://cfg/complete")

    def test_builds_from_public_host_when_no_urls(self) -> None:
        callback, complete = resolve_delivery_urls(
            {"jobId": "crawl-1", "streamId": "stream-1"},
            callback_public_host="http://localhost:3000/",
        )
        self.assertEqual(
            callback,
            "http://localhost:3000/api/customCrawler/callback/stream-1/crawl-1",
        )
        self.assertEqual(
            complete,
            "http://localhost:3000/api/customCrawler/complete/stream-1/crawl-1",
        )

    def test_missing_payload_keys_use_public_host(self) -> None:
        callback, complete = resolve_delivery_urls(
            {"jobId": "crawl-1", "streamId": "stream-1"},
            callback_public_host="http://localhost",
        )
        self.assertEqual(
            callback,
            "http://localhost/api/customCrawler/callback/stream-1/crawl-1",
        )
        self.assertEqual(
            complete,
            "http://localhost/api/customCrawler/complete/stream-1/crawl-1",
        )

    def test_missing_stream_id_does_not_invent_host_urls(self) -> None:
        callback, complete = resolve_delivery_urls(
            {"jobId": "crawl-1"},
            callback_public_host="http://localhost:3000",
        )
        self.assertEqual(callback, "")
        self.assertEqual(complete, "")

    def test_payload_auth_header_overrides_sdk_auth(self) -> None:
        headers = merge_callback_headers(
            [{"key": "auth", "value": "payload-jwt", "encodingFormat": "none"}],
            callback_auth_header="sdk-jwt",
        )
        by_key = {h["key"].lower(): h["value"] for h in headers}
        self.assertEqual(by_key["auth"], "payload-jwt")

    def test_sdk_auth_used_when_payload_omits_it(self) -> None:
        headers = merge_callback_headers([], callback_auth_header="sdk-jwt")
        by_key = {h["key"].lower(): h["value"] for h in headers}
        self.assertEqual(by_key["auth"], "sdk-jwt")


if __name__ == "__main__":
    unittest.main()
