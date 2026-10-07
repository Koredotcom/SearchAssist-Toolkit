"""Shared persist gate for CLI warmup and HTTP capture.

Never write storage_state / session_meta while the page is still a Cloudflare
interstitial or has redirected off the target host.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional, Tuple
from urllib.parse import urlparse

from ..browser.challenge import looks_challenged
from ..browser.session import SESSION_META_NAME, STATE_FILE_NAME


def host_of(url: str) -> str:
    return (urlparse(url if "://" in url else f"https://{url}").hostname or "").lower()


def on_target_site(page_url: str, seed_url: str) -> bool:
    want = host_of(seed_url).removeprefix("www.")
    got = host_of(page_url).removeprefix("www.")
    return bool(want and got and (got == want or got.endswith("." + want)))


async def snapshot(page: Any, preview_png: Path) -> None:
    try:
        await page.screenshot(path=str(preview_png), full_page=False)
    except Exception:
        pass


async def page_is_cleared(page: Any, seed_url: str) -> Tuple[bool, str, str]:
    """Return (cleared, title, reason). Does not wait — caller must have already solved CF."""
    try:
        title = await page.title()
        html = await page.content()
        url = page.url or ""
    except Exception as exc:
        return False, "", f"read_failed:{type(exc).__name__}"
    if looks_challenged(title, html):
        return False, title, "still_challenged"
    if not on_target_site(url, seed_url):
        return False, title, "off_target"
    return True, title, "cleared"


async def persist_profile(
    context: Any,
    profile_dir: Path,
    *,
    url: str,
    title: str,
    profile_key: str,
    extra: Optional[dict] = None,
) -> int:
    profile_dir.mkdir(parents=True, exist_ok=True)
    state_file = profile_dir / STATE_FILE_NAME
    await context.storage_state(path=str(state_file))
    cookies = await context.cookies()
    meta = {
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "url": url,
        "title": title,
        "cloudflare_cleared": True,
        "profile_key": profile_key,
        "cookie_count": len(cookies),
        "cf_clearance": any(c.get("name") == "cf_clearance" for c in cookies),
    }
    if extra:
        meta.update(extra)
    (profile_dir / SESSION_META_NAME).write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    return len(cookies)


def read_session_meta(profile_dir: Path) -> dict:
    meta = profile_dir / SESSION_META_NAME
    if not meta.is_file():
        return {}
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def profile_is_warmed(profile_root: str, profile_key: str) -> bool:
    data = read_session_meta(Path(profile_root) / profile_key)
    return bool(data.get("cloudflare_cleared"))
