"""Cloudflare challenge detection and waiting."""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Tuple

from .log import log

CHALLENGE_MARKERS = (
    "just a moment",
    "sorry, you have been blocked",
    "attention required",
    "cf-browser-verification",
    "challenge-platform",
    "verify you are not a bot",
    "checking your browser",
    "performing security verification",
)

# Terminal WAF verdicts: unlike "Just a moment...", these never clear by waiting.
BLOCK_MARKERS = (
    "sorry, you have been blocked",
    "attention required",
    "access denied",
    "error 1015",
    "error 1020",
)

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def extract_title(html: str) -> str:
    m = _TITLE_RE.search(html or "")
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def looks_challenged(title: str, html: str = "") -> bool:
    blob = f"{title}\n{(html or '')[:12000]}".lower()
    return any(m in blob for m in CHALLENGE_MARKERS)


def looks_blocked(title: str, html: str = "") -> bool:
    blob = f"{title}\n{(html or '')[:12000]}".lower()
    return any(m in blob for m in BLOCK_MARKERS)


async def wait_out_challenge(page: Any, *, cf_wait: float) -> Tuple[str, str, bool]:
    """Poll until CF challenge clears or timeout. Returns (title, html, still_challenged)."""
    title = await page.title()
    html = await page.content()
    if not looks_challenged(title, html) or cf_wait <= 0:
        return title, html, looks_challenged(title, html)

    if looks_blocked(title, html):
        log(f"CF hard block (title={title!r}) — terminal verdict, not waiting {cf_wait:.0f}s")
        return title, html, True

    log(f"CF challenge detected (title={title!r}); waiting up to {cf_wait:.0f}s for auto-clear…")
    deadline = time.perf_counter() + cf_wait
    while time.perf_counter() < deadline:
        await asyncio.sleep(1.0)
        try:
            title = await page.title()
            html = await page.content()
        except Exception:
            continue
        if not looks_challenged(title, html):
            log(f"CF cleared → title={title!r}")
            return title, html, False
        remaining = deadline - time.perf_counter()
        if int(remaining) % 5 == 0:
            log(f"still challenged… {remaining:.0f}s left title={title!r}")

    return title, html, True


async def turnstile_present(page: Any) -> bool:
    """True when a Cloudflare Turnstile widget iframe is on the page (diagnostics only)."""
    try:
        for frame in page.frames:
            if "challenges.cloudflare.com" in (frame.url or ""):
                return True
    except Exception:
        pass
    return False


TURNSTILE_IFRAME = 'iframe[src*="challenges.cloudflare.com"]'


async def click_turnstile(page: Any) -> bool:
    """Best-effort click of the Turnstile checkbox. True when a click landed.

    Only call this after a passive wait has already failed: touching the page while a
    managed challenge is self-clearing can restart it (see ``capture_until_ready``).
    The widget markup is not stable, so treat failure as normal and fall back to a human.
    """
    try:
        checkbox = page.frame_locator(TURNSTILE_IFRAME).locator("input[type=checkbox]")
        await checkbox.click(timeout=5_000)
        log("clicked Turnstile checkbox")
        return True
    except Exception:
        pass

    # Markup changed or the checkbox is shadow-hidden: click the widget centre instead.
    try:
        box = await page.locator(TURNSTILE_IFRAME).first.bounding_box(timeout=5_000)
    except Exception:
        box = None
    if not box:
        return False
    try:
        # The checkbox sits at the left edge of the widget, not its centre.
        await page.mouse.click(box["x"] + 30, box["y"] + box["height"] / 2)
        log("clicked Turnstile widget area (checkbox selector unavailable)")
        return True
    except Exception as exc:
        log(f"Turnstile click failed: {type(exc).__name__}: {exc}")
        return False
