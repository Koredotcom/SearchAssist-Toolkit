"""Headed Chrome session: ephemeral or per-host persistent profile."""
from __future__ import annotations

import json
import platform
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from .log import log

STATE_FILE_NAME = "storage_state.json"
SESSION_META_NAME = "session_meta.json"

_SAFE_HOST_RE = re.compile(r"[^a-z0-9._-]+")

LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
]

VIEWPORT = {"width": 1280, "height": 900}


def profile_key_for_host(host: str) -> str:
    host = (host or "").lower().removeprefix("www.")
    return _SAFE_HOST_RE.sub("_", host) or "default"


def profile_key_for_url(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or parsed.path.split("/")[0] or "").lower()
    return profile_key_for_host(host)


# Cookies that actually carry Cloudflare clearance, as opposed to analytics noise.
CF_AUTH_COOKIES = ("cf_clearance",)


def looks_like_chrome_profile(path: Path) -> bool:
    if not path.is_dir():
        return False
    return (path / "Default").is_dir() or (path / "Local State").is_file()


def load_cookies(state_file: Path) -> List[Dict[str, Any]]:
    if not state_file.is_file():
        return []
    try:
        raw = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return []
    cookies = raw.get("cookies") if isinstance(raw, dict) else raw
    if not isinstance(cookies, list):
        return []
    out: List[Dict[str, Any]] = []
    for c in cookies:
        if not isinstance(c, dict) or not c.get("name") or c.get("value") is None:
            continue
        item = {
            k: c[k]
            for k in (
                "name",
                "value",
                "domain",
                "path",
                "expires",
                "httpOnly",
                "secure",
                "sameSite",
                "partitionKey",
            )
            if k in c
        }
        out.append(item)

        # Cloudflare may store cf_clearance partitioned (CHIPS). A partition-scoped
        # cookie does not authorise a plain top-level load, and warming on a deep page
        # can leave *only* the partitioned copy — which is how a profile ends up
        # clearing /firearms but re-challenging the homepage. Chrome keeps partitioned
        # and unpartitioned cookies separate, so inject both and let the browser pick.
        if item.get("partitionKey") and item["name"] in CF_AUTH_COOKIES:
            plain = {k: v for k, v in item.items() if k != "partitionKey"}
            out.append(plain)
    return out


def cookie_health(cookies: List[Dict[str, Any]]) -> Tuple[bool, str]:
    names = {str(c.get("name") or "") for c in cookies}
    has_cf = "cf_clearance" in names
    n = len(cookies)
    if n < 10 and not has_cf:
        return (
            False,
            f"weak cookie jar: count={n} cf_clearance=missing "
            "(profile was likely saved during CF, or cookies expired — re-run warmup_profile)",
        )
    if not has_cf:
        return (
            False,
            f"cookie jar count={n} but cf_clearance=missing "
            "(Cloudflare will usually re-challenge — re-run warmup_profile)",
        )
    return True, f"cookie jar count={n} cf_clearance=present"


async def apply_stealth(context: Any, page: Any) -> None:
    try:
        from playwright_stealth import Stealth

        plat = "MacIntel" if platform.system() == "Darwin" else "Linux x86_64"
        stealth = Stealth(
            navigator_platform_override=plat,
            navigator_languages_override=("en-US", "en"),
        )
        if hasattr(stealth, "apply_stealth_async"):
            await stealth.apply_stealth_async(page)
        else:
            await stealth.hook_playwright_context(context)
        log("playwright-stealth applied")
    except Exception as exc:
        log(f"stealth skipped: {type(exc).__name__}: {exc}")


class BrowserSession:
    """Headed Chrome for one crawl job (shared tab for discovery + page fetch)."""

    def __init__(
        self,
        playwright: Any,
        *,
        profile_root: str,
        profile_key: str,
        channel: str = "chrome",
        js_enabled: bool = True,
        use_profile: bool = False,
    ) -> None:
        self.playwright = playwright
        self.profile_key = profile_key
        self.profile_dir = Path(profile_root) / profile_key
        self.channel = channel
        self.js_enabled = js_enabled
        self.use_profile = use_profile
        self.launched_with_profile = False
        self.context: Any = None
        self.page: Any = None
        self.browser: Any = None
        self.cookie_count = 0
        self.has_cf_clearance = False
        self.jar_ok = False
        self.jar_message = ""

    @property
    def ephemeral(self) -> bool:
        return not self.launched_with_profile

    @property
    def state_file(self) -> Path:
        return self.profile_dir / STATE_FILE_NAME

    def warmed(self) -> bool:
        meta = self.profile_dir / SESSION_META_NAME
        if not meta.is_file():
            return False
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            return False
        return bool(data.get("cloudflare_cleared"))

    def _clear_singleton_lock(self) -> None:
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            p = self.profile_dir / name
            try:
                if p.is_symlink() or p.exists():
                    p.unlink()
            except OSError:
                pass

    async def start(self) -> None:
        # Persistent only when explicitly requested AND warmup left a cleared session.
        # A half-baked profile folder without cloudflare_cleared is worse than ephemeral.
        use_profile = bool(
            self.use_profile and self.warmed() and looks_like_chrome_profile(self.profile_dir)
        )
        if self.use_profile and not use_profile:
            log(
                "profile requested but not warmed (no cloudflare_cleared) — "
                "falling back to ephemeral Chrome; run warmup_profile first"
            )
        self.launched_with_profile = use_profile

        if use_profile:
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            self._clear_singleton_lock()
            log(f"launch = persistent Chrome profile {self.profile_dir}")
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=False,
                channel=self.channel,
                viewport=VIEWPORT,
                accept_downloads=True,
                args=list(LAUNCH_ARGS),
                ignore_default_args=["--enable-automation"],
                java_script_enabled=self.js_enabled,
            )
        else:
            log("launch = ephemeral headed Chrome (no persistent profile)")
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                channel=self.channel,
                args=list(LAUNCH_ARGS),
                ignore_default_args=["--enable-automation"],
            )
            self.context = await self.browser.new_context(
                viewport=VIEWPORT,
                java_script_enabled=self.js_enabled,
            )

        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        # Stealth + cookie jar only for warmed persistent profiles.
        if use_profile:
            await apply_stealth(self.context, self.page)
            cookies = load_cookies(self.state_file)
            self.jar_ok, self.jar_message = cookie_health(cookies)
            log(self.jar_message)
            if cookies:
                try:
                    await self.context.add_cookies(cookies)
                    self.cookie_count = len(cookies)
                    self.has_cf_clearance = any(
                        c.get("name") == "cf_clearance" for c in cookies
                    )
                    log(f"injected {len(cookies)} cookies")
                except Exception as exc:
                    log(f"cookie inject warning: {type(exc).__name__}: {exc}")

    async def refresh_state(self) -> None:
        """Persist cookies when using a durable profile, but never downgrade it.

        Overwriting the saved jar with a session that has lost its clearance turns one
        challenged crawl into a permanently broken profile, so a live cf_clearance is
        the precondition for writing. Warmup remains the only way to (re)create one.
        """
        if self.context is None or not self.launched_with_profile:
            return
        try:
            live = await self.context.cookies()
        except Exception:
            return
        if not any(c.get("name") in CF_AUTH_COOKIES for c in live):
            log("skipping state save — session has no cf_clearance, keeping warmed profile")
            return
        try:
            await self.context.storage_state(path=str(self.state_file))
        except Exception:
            pass

    async def close(self) -> None:
        for closeable in (self.context, self.browser):
            if closeable is None:
                continue
            try:
                await closeable.close()
            except Exception as exc:
                log(f"close warning (ignored): {type(exc).__name__}: {exc}")
        self.context = None
        self.browser = None
        self.page = None
