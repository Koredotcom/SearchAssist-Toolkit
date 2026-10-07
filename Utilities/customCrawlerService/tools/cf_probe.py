"""Diagnose whether a host needs a warmed profile, and why.

Opens the URL in the same headed Chrome the crawler uses, watches the response, and
reports whether the Cloudflare gate clears:

  * clear       -> crawlable with this browser setup
  * challenged  -> still gated when the watch window ran out

A Turnstile iframe is reported but never ends the wait: the same widget backs both the
self-clearing managed challenge and the click-required checkbox.

    python -m tools.cf_probe --url https://www.guns.com/robots.txt --xvfb never

Use the launch flags to compare setups against the same URL, which is how you tell a
site-side rule apart from a fingerprint problem:

    python -m tools.cf_probe --url <url> --xvfb never                    # ephemeral, no stealth
    python -m tools.cf_probe --url <url> --xvfb never --stealth          # ephemeral + stealth
    python -m tools.cf_probe --url <url> --xvfb never --use-profile      # warmed profile
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from custom_crawler.browser.challenge import (  # noqa: E402
    looks_challenged as _page_blocked,
)
from custom_crawler.browser.challenge import turnstile_present as interactive_challenge  # noqa: E402
from custom_crawler.browser.session import (  # noqa: E402
    BrowserSession,
    apply_stealth,
    profile_key_for_url,
)
from custom_crawler.engine.xvfb import XvfbDisplay  # noqa: E402
from custom_crawler.settings import ServiceConfig, load_env  # noqa: E402


def log(msg: str) -> None:
    print(f"[cf_probe] {msg}", flush=True)


async def probe(page, url: str, watch_seconds: float, shot_dir: Path) -> str:
    log(f"--- goto {url}")
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        log(f"status={resp.status if resp else None}")
    except Exception as exc:
        log(f"goto failed: {type(exc).__name__}: {exc}")
        return "error"

    verdict = "challenged"
    deadline = time.perf_counter() + watch_seconds
    last = ""
    while time.perf_counter() < deadline:
        try:
            title = await page.title()
            html = await page.content()
        except Exception:
            await asyncio.sleep(2)
            continue

        if not _page_blocked(title, html):
            log(f"CLEAR - title={title!r}")
            log(f"body starts: {html[:200]!r}")
            verdict = "clear"
            break

        turnstile = await interactive_challenge(page)
        state = f"challenged turnstile={turnstile} title={title!r} len={len(html)}"
        if state != last:
            log(f"{state} ({int(deadline - time.perf_counter())}s left)")
            last = state
        await asyncio.sleep(2)

    shot_dir.mkdir(parents=True, exist_ok=True)
    shot = shot_dir / "cf_probe.png"
    try:
        await page.screenshot(path=str(shot))
        log(f"screenshot -> {shot}")
    except Exception:
        pass
    return verdict


async def run(args: argparse.Namespace) -> int:
    from playwright.async_api import async_playwright

    load_env()
    cfg = ServiceConfig()
    xvfb = XvfbDisplay(mode=args.xvfb)
    xvfb.start()
    log(f"DISPLAY={os.environ.get('DISPLAY')} xvfb_owned={xvfb.owned}")

    try:
        async with async_playwright() as pw:
            worker = BrowserSession(
                pw,
                profile_root=args.profile_root or cfg.profile_root,
                profile_key=profile_key_for_url(args.url),
                channel=cfg.chrome_channel,
                use_profile=args.use_profile,
            )
            log(f"profile={worker.profile_dir} warmed={worker.warmed()}")
            await worker.start()
            log(f"launched ephemeral={worker.ephemeral} stealth_requested={args.stealth}")
            try:
                if args.stealth and worker.ephemeral:
                    await apply_stealth(worker.context, worker.page)
                verdict = await probe(
                    worker.page,
                    args.url,
                    args.watch_seconds,
                    Path(args.shot_dir),
                )
            finally:
                await worker.close()

        log(f"VERDICT: {verdict}")
        if verdict != "clear":
            log(f"Run: python -m tools.warmup_profile --url {args.url}")
        return 0 if verdict == "clear" else 1
    finally:
        xvfb.stop()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Check what Cloudflare gate a URL is behind")
    p.add_argument("--url", required=True)
    p.add_argument("--watch-seconds", type=float, default=45.0)
    p.add_argument("--profile-root", default="")
    p.add_argument("--shot-dir", default="/tmp/cf_probe")
    p.add_argument(
        "--use-profile",
        action="store_true",
        help="Launch the warmed per-host profile instead of ephemeral Chrome",
    )
    p.add_argument(
        "--stealth",
        action="store_true",
        help="Apply playwright-stealth to ephemeral Chrome (profile mode always applies it)",
    )
    p.add_argument("--xvfb", choices=("auto", "always", "never"), default="always")
    return p.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
