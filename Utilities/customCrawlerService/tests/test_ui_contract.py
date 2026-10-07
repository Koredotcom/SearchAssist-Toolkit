from __future__ import annotations

import unittest
from pathlib import Path


UI_FILE = Path(__file__).resolve().parents[1] / "ui" / "index.html"


class ProductionUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = UI_FILE.read_text(encoding="utf-8")

    def test_supports_direct_and_prefixed_proxy_paths(self) -> None:
        self.assertIn('const BASE = window.location.pathname.replace(/\\/ui\\/?$/, "");', self.html)
        self.assertIn("const api = (path) => BASE + path;", self.html)
        self.assertIn('params.set("path", BASE + wsPath)', self.html)
        self.assertNotIn('fetch("/', self.html)

    def test_exposes_client_crawl_settings(self) -> None:
        for element_id in (
            "maxUrls",
            "maxDepth",
            "crawlDelay",
            "javascriptRendered",
            "respectRobots",
            "allowSubdomains",
            "callbackUrl",
            "completeUrl",
            "authHeader",
        ):
            self.assertIn(f'id="{element_id}"', self.html)

    def test_requests_sitemap_first_discovery_without_a_toggle(self) -> None:
        self.assertIn("crawlBeyondSitemaps: false", self.html)
        self.assertNotIn('id="fallbackBfs"', self.html)

    def test_restores_button_labels_after_busy_state(self) -> None:
        self.assertIn("delete button.dataset.previousLabel;", self.html)

    def test_reports_validation_outcome_inline(self) -> None:
        self.assertIn('id="urlStatus"', self.html)
        self.assertIn('setValidation("success", "Validation successful"', self.html)
        self.assertIn('setValidation("error", "Validation failed"', self.html)

    def test_uses_client_facing_profile_actions(self) -> None:
        self.assertIn("Warm Profile", self.html)
        self.assertIn("Save Profile &amp; Start Crawl", self.html)
        self.assertNotIn("Profile required", self.html)


if __name__ == "__main__":
    unittest.main()
