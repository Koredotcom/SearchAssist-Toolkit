#!/usr/bin/env python3
"""Drive one CrawlJob end to end without the HTTP layer.

    python -m tools.mock_findly_callbacks &
    python -m tools.dry_run_job --url https://example.com --limit 3
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from custom_crawler import settings as _settings  # noqa: E402


async def run(args: argparse.Namespace) -> int:
    # Set after settings import so these win over .env for this run only.
    os.environ["CRAWLER_PROFILE_ROOT"] = args.profile_root
    os.environ["CRAWLER_SPOOL_DIR"] = args.spool_dir
    os.environ["CRAWLER_XVFB_MODE"] = args.xvfb
    os.environ["CRAWLER_CHALLENGE_WAIT_SECONDS"] = str(int(args.cf_wait))

    from playwright.async_api import async_playwright

    from custom_crawler.engine.xvfb import XvfbDisplay
    from custom_crawler.job import CrawlJob

    cfg = _settings.ServiceConfig()
    _settings.ensure_data_dirs(cfg)
    xvfb = XvfbDisplay(mode=cfg.xvfb_mode)
    xvfb.start()
    print(f"DISPLAY={os.environ.get('DISPLAY')} xvfbOwned={xvfb.owned}", flush=True)

    try:
        async with async_playwright() as pw:
            job = CrawlJob(
                submit={
                    "jobId": args.job_id,
                    "baseUrl": args.url,
                    "callbackUrl": f"{args.callback_base}/callback",
                    "completeUrl": f"{args.callback_base}/complete",
                    "callbackBatchSize": 2,
                    "advanceSettings": {
                        "maxUrlLimit": args.limit,
                        "crawlDepth": args.depth,
                        "crawlDelay": args.delay,
                        "crawlBeyondSitemaps": True,
                    },
                },
                service_cfg=cfg,
                playwright=pw,
            )
            await job.run()
            print(json.dumps(job.status_doc(), indent=2), flush=True)
            return 0 if job.counters.success else 1
    finally:
        xvfb.stop()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run one crawl job in-process")
    p.add_argument("--url", required=True)
    p.add_argument("--job-id", default="dry-run-1")
    p.add_argument("--limit", type=int, default=3)
    p.add_argument("--depth", type=int, default=1)
    p.add_argument("--delay", type=float, default=1.0)
    p.add_argument("--cf-wait", type=float, default=25.0)
    p.add_argument("--callback-base", default="http://127.0.0.1:9999")
    p.add_argument("--profile-root", default="/tmp/cc_dryrun/profiles")
    p.add_argument("--spool-dir", default="/tmp/cc_dryrun/spool")
    p.add_argument("--xvfb", choices=("auto", "always", "never"), default="always")
    return p.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
