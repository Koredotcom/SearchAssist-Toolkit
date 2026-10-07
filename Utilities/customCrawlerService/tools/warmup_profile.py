#!/usr/bin/env python3
"""Warm a per-host Chrome profile so Cloudflare-protected sites become crawlable.

Opens headed Chrome with the same profile directory the crawler uses, holds the page
open while you solve the challenge (VNC on a headless host), and saves only once the
page is no longer challenged.

    # server without a display
    python -m tools.warmup_profile --url https://example.com --xvfb always --vnc

    # desktop
    python -m tools.warmup_profile --url https://example.com --xvfb never --no-vnc

    # optionally verify other URLs in the same session before saving
    python -m tools.warmup_profile --xvfb never --no-vnc \
        --url 'https://example.com/hard-page' \
        --verify-url 'https://example.com/another-page'

Warm with the *hardest* URL as ``--url``. Sites commonly gate detail pages
(``/firearms/p/*``) behind an interactive Turnstile while the homepage clears on its
own, and clearance earned on the homepage does not always cover those paths. Verify
URLs get the same treatment: passive wait, auto-click, then a human window.

Then crawl with advanceSettings.useProfile=true (or CRAWLER_USE_PROFILE=true).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from custom_crawler.engine.vnc import ViewAttach  # noqa: E402
from custom_crawler.engine.xvfb import XvfbDisplay  # noqa: E402
from custom_crawler.browser.challenge import (  # noqa: E402
    click_turnstile,
    looks_challenged,
    turnstile_present,
    wait_out_challenge,
)
from custom_crawler.browser.session import (  # noqa: E402
    LAUNCH_ARGS,
    VIEWPORT,
    cookie_health,
    load_cookies,
    profile_key_for_url,
)
from custom_crawler.capture.persist import (  # noqa: E402
    on_target_site,
    persist_profile,
    snapshot,
)
from custom_crawler.settings import ServiceConfig, ensure_writable_dir, load_env  # noqa: E402


def log(msg: str) -> None:
    print(f"[warmup] {msg}", flush=True)


async def capture_until_ready(
    page: Any,
    seed_url: str,
    *,
    wait_seconds: float,
    wait_after_load: float,
) -> tuple[str, str, bool]:
    """Exactly the ``fetch_page.py`` sequence: settle, then poll title/content only.

    Nothing else touches the page while the challenge is up. Screenshots and ``page.url``
    reads during the challenge (what the old capture loop did every 3s) put Turnstile into a
    reload loop, which is why ``fetch_page.py`` cleared and the warmup never did.
    """
    if wait_after_load > 0:
        await asyncio.sleep(wait_after_load)

    title, html, still_cf = await wait_out_challenge(page, cf_wait=wait_seconds)
    if still_cf:
        return "timeout", title, False
    if not on_target_site(page.url, seed_url):
        log(f"CF cleared but not on the target host yet (url={page.url})")
        return "off_target", title, False
    return "cleared", title, True


async def verify_urls(
    page: Any, urls: list[str], *, cf_wait: float, human_wait: float
) -> list[dict]:
    """Load extra URLs in the same session, solving any challenge they raise.

    Detail pages often sit behind a stricter rule than the homepage and raise an
    *interactive* Turnstile that no wait will clear. So each URL gets three chances:
    a passive wait, a best-effort checkbox click, then a long window for the operator
    to click it in the Chrome/VNC window. Clearance earned here lands in the profile,
    which is the whole point — the crawler has no human to fall back on.
    """
    out: list[dict] = []
    for url in urls:
        log(f"verify GET {url}")
        status: Optional[int] = None
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            status = resp.status if resp else None
        except Exception as exc:
            log(f"  verify goto failed: {type(exc).__name__}: {exc}")
            out.append({"url": url, "ok": False, "status": status, "title": "", "error": "goto_failed"})
            continue

        title, _html, still_cf = await wait_out_challenge(page, cf_wait=cf_wait)
        solved_by = "auto" if not still_cf else ""

        if still_cf and await turnstile_present(page):
            log("  interactive Turnstile — trying the checkbox automatically")
            if await click_turnstile(page):
                title, _html, still_cf = await wait_out_challenge(page, cf_wait=cf_wait)
                if not still_cf:
                    solved_by = "click"

        if still_cf and human_wait > 0:
            log(f"  >>> CLICK THE CHECKBOX for {url} in the Chrome window <<<")
            log(f"  waiting up to {human_wait:.0f}s for you")
            title, _html, still_cf = await wait_out_challenge(page, cf_wait=human_wait)
            if not still_cf:
                solved_by = "human"

        out.append(
            {
                "url": url,
                "ok": not still_cf,
                "status": 403 if still_cf else (status or 200),
                "title": title,
                "solvedBy": solved_by,
                "error": "challenge_not_cleared" if still_cf else "",
            }
        )
        log(f"  verify {'OK' if not still_cf else 'CHALLENGED'} title={title!r} solvedBy={solved_by or 'n/a'}")

    ok_n = sum(1 for r in out if r["ok"])
    log(f"verification: {ok_n}/{len(out)} URLs reachable with this session")
    if ok_n < len(out):
        log("unreachable URLs will also fail at crawl time — re-warm with one as --url")
    return out


async def shutdown(context: Any) -> None:
    """Never let a driver teardown error mask a profile that was already saved."""
    if context is None:
        return
    try:
        await context.close()
    except Exception as exc:
        log(f"close warning (ignored): {type(exc).__name__}: {exc}")


async def run(args: argparse.Namespace) -> int:
    from playwright.async_api import async_playwright

    load_env()
    cfg = ServiceConfig()

    profile_key = profile_key_for_url(args.url)
    if args.profile_dir:
        # Point warmup at an existing profile directory instead of the per-host layout.
        profile_dir = Path(args.profile_dir).expanduser().resolve()
        profile_dir.mkdir(parents=True, exist_ok=True)
    else:
        # Same ownership check the service uses — refuse to warm into a root-owned tree.
        profile_root = ensure_writable_dir(
            args.profile_root or cfg.profile_root, label="CRAWLER_PROFILE_ROOT"
        )
        profile_dir = profile_root / profile_key
        profile_dir.mkdir(parents=True, exist_ok=True)
    state_file = (
        Path(args.state_file).expanduser().resolve()
        if args.state_file
        else profile_dir / "storage_state.json"
    )
    preview_png = profile_dir / "preview.png"

    xvfb = XvfbDisplay(mode=args.xvfb)
    xvfb.start()
    display = os.environ.get("DISPLAY")

    view = ViewAttach()
    if args.vnc and xvfb.owned and display:
        view.start(display, listen=args.vnc_listen)
    elif args.vnc and not xvfb.owned:
        # Never mirror the operator's own desktop; there is nothing to attach to.
        log(f"VNC skipped — using existing display {display}, watch the Chrome window directly")

    log(f"url         = {args.url}")
    log(f"profile_key = {profile_key}")
    log(f"profile_dir = {profile_dir}")
    log(f"state_file  = {state_file} exists={state_file.is_file()}")
    log(f"DISPLAY     = {display} (xvfb mode={args.xvfb}, owned={xvfb.owned})")
    log(f"channel     = {args.channel}")
    log(f"chrome_args = {list(LAUNCH_ARGS)}")
    log(f"CF wait     = {args.wait_seconds:.0f}s, same poll loop as fetch_page.py")
    log(f"screenshot  = {preview_png} (taken after CF clears, not during)")
    if xvfb.owned and not args.vnc:
        log("WARNING: virtual display without VNC — you cannot click the challenge.")
        log("          Use --xvfb always --vnc on a server, or --xvfb never on a desktop.")

    cookies_n = 0
    context = None
    try:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                channel=args.channel,
                viewport=VIEWPORT,
                args=list(LAUNCH_ARGS),
                ignore_default_args=["--enable-automation"],
            )
            page = context.pages[0] if context.pages else await context.new_page()

            # fetch_page.py injects the saved jar before navigating, so a re-warm starts from
            # whatever clearance is left instead of provoking a fresh challenge.
            cookies = load_cookies(state_file)
            if cookies:
                ok_jar, jar_msg = cookie_health(cookies)
                log(jar_msg)
                try:
                    await context.add_cookies(cookies)
                    log(f"injected {len(cookies)} cookies")
                except Exception as exc:
                    log(f"cookie inject warning: {type(exc).__name__}: {exc}")

            log("solve the challenge in the Chrome window; nothing else touches the page")
            try:
                await page.goto(args.url, wait_until="domcontentloaded", timeout=90_000)
            except Exception as exc:
                log(f"goto warning: {type(exc).__name__}: {exc}")

            reason, title, cleared = await capture_until_ready(
                page,
                args.url,
                wait_seconds=args.wait_seconds,
                wait_after_load=args.wait_after_load,
            )

            try:
                html = await page.content()
                title = title or (await page.title())
                if not cleared:
                    cleared = (not looks_challenged(title, html)) and on_target_site(
                        page.url, args.url
                    )
            except Exception:
                pass

            log(f"save trigger = {reason} cleared={cleared} title={title!r}")
            if not cleared:
                log("NOT SAVING (still Cloudflare / not on target). Re-run and solve it.")
                await shutdown(context)
                return 2

            await snapshot(page, preview_png)

            verified: list[dict] = []
            if args.verify_url:
                verified = await verify_urls(
                    page,
                    list(args.verify_url),
                    cf_wait=args.verify_cf_wait,
                    human_wait=args.verify_human_wait,
                )

            cookies_n = await persist_profile(
                context,
                profile_dir,
                url=args.url,
                title=title,
                profile_key=profile_key,
                extra={
                    "save_trigger": reason,
                    "display": display,
                    "xvfb_mode": args.xvfb,
                    "verified": verified,
                },
            )
            log("PERSISTED — profile ready for crawl")
            await shutdown(context)

        log(f"  cookies = {cookies_n}")
        log(f"  state   = {state_file}")
        log(f"  crawl now with baseUrl on host: {profile_key}")
        return 0
    finally:
        view.stop()
        xvfb.stop()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Warm a per-host Chrome profile (solve Cloudflare once)")
    p.add_argument("--url", required=True, help="Site URL to warm up, e.g. https://example.com")
    p.add_argument("--profile-root", default="", help="Override CRAWLER_PROFILE_ROOT")
    p.add_argument("--profile-dir", default="", help="Use this exact profile dir (skips per-host layout)")
    p.add_argument("--state-file", default="", help="Override storage_state.json path")
    p.add_argument(
        "--cf-wait",
        "--wait-seconds",
        dest="wait_seconds",
        type=float,
        default=900.0,
        help="Seconds to wait for Cloudflare to clear while you solve it (default 900)",
    )
    p.add_argument(
        "--wait-after-load",
        type=float,
        default=2.0,
        help="Settle time after goto before polling, as fetch_page.py does",
    )
    p.add_argument(
        "--verify-url",
        action="append",
        default=[],
        metavar="URL",
        help="After the challenge clears, load this URL in the same session and report "
        "whether it is reachable. Repeatable; use real crawl targets (e.g. a product page)",
    )
    p.add_argument(
        "--verify-cf-wait",
        type=float,
        default=90.0,
        help="Passive wait per verify URL before trying to click, matching the crawler's "
        "default (90s). Detail pages sit behind a slower check than the homepage",
    )
    p.add_argument(
        "--verify-human-wait",
        type=float,
        default=300.0,
        help="After the passive wait and auto-click fail, seconds to hold the page open "
        "so you can click the checkbox yourself. 0 disables the human step",
    )
    p.add_argument("--channel", default="")
    p.add_argument(
        "--xvfb",
        choices=("auto", "always", "never"),
        default="auto",
        help="auto = use DISPLAY if set, else own Xvfb (fetch_page.py default). "
        "always = own Xvfb, pair with --vnc on a server. never = the real desktop display",
    )
    p.add_argument(
        "--vnc",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Start x11vnc on the Xvfb display so you can click the challenge",
    )
    p.add_argument("--vnc-listen", default="0.0.0.0")
    args = p.parse_args()
    if not args.channel:
        load_env()
        args.channel = ServiceConfig().chrome_channel
    return args


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr, flush=True)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
