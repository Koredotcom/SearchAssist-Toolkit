"""In-process capture sessions: one headed Chrome + VNC stack per host."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from ..browser.session import (
    LAUNCH_ARGS,
    VIEWPORT,
    cookie_health,
    load_cookies,
    looks_like_chrome_profile,
    profile_key_for_url,
)
from ..obs.logging import log, setup_logger
from ..settings import ServiceConfig, ensure_writable_dir
from .persist import page_is_cleared, persist_profile, read_session_meta, snapshot
from .vnc import CaptureVncStack

logger = setup_logger("custom_crawler.capture")


@dataclass
class CaptureSession:
    host: str
    base_url: str
    vnc: Optional[CaptureVncStack]
    context: Any
    page: Any
    started_at: float = field(default_factory=time.time)


class CaptureManager:
    def __init__(self, cfg: ServiceConfig) -> None:
        self.cfg = cfg
        self.playwright: Any = None
        self._active: Dict[str, CaptureSession] = {}
        self._lock = asyncio.Lock()

    def vnc_allowed(self, token: str, ws_port: int) -> bool:
        for session in self._active.values():
            if (
                session.vnc is not None
                and session.vnc.session_token == token
                and session.vnc.ws_port == ws_port
            ):
                return True
        return False

    def status(self, host: str) -> Dict[str, Any]:
        profile_dir = Path(self.cfg.profile_root) / host
        meta = read_session_meta(profile_dir)
        session = self._active.get(host)
        return {
            "host": host,
            "warmed": bool(meta.get("cloudflare_cleared")),
            "savedAt": meta.get("saved_at"),
            "captureInProgress": session is not None,
            "vncUrl": session.vnc.vnc_url if session and session.vnc else None,
            "baseUrl": session.base_url if session else meta.get("url"),
        }

    async def start(self, base_url: str) -> Dict[str, Any]:
        host = profile_key_for_url(base_url)
        async with self._lock:
            existing = self._active.get(host)
            if existing is not None:
                log(
                    logger,
                    logging.INFO,
                    "resuming in-progress capture",
                    host=host,
                )
                return {
                    "host": host,
                    "vncUrl": existing.vnc.vnc_url if existing.vnc else None,
                    "viewer": "vnc" if existing.vnc else "chrome",
                    "resumed": True,
                    "status": "capturing",
                }
            session = await self._launch(host, base_url)
            self._active[host] = session
            return {
                "host": host,
                "vncUrl": session.vnc.vnc_url if session.vnc else None,
                "viewer": "vnc" if session.vnc else "chrome",
                "resumed": False,
                "status": "capturing",
            }

    async def complete(self, base_url: str) -> Dict[str, Any]:
        host = profile_key_for_url(base_url)
        async with self._lock:
            session = self._active.get(host)
            if session is None:
                return {"ok": False, "error": "no_capture", "host": host}

            cleared, title, reason = await page_is_cleared(session.page, session.base_url)
            if not cleared:
                log(
                    logger,
                    logging.INFO,
                    "capture complete refused",
                    host=host,
                    reason=reason,
                    title=title,
                )
                return {
                    "ok": False,
                    "error": reason,
                    "host": host,
                    "title": title,
                    "stillChallenged": reason == "still_challenged",
                }

            profile_dir = Path(self.cfg.profile_root) / host
            await snapshot(session.page, profile_dir / "preview.png")
            cookies_n = await persist_profile(
                session.context,
                profile_dir,
                url=session.base_url,
                title=title,
                profile_key=host,
                extra={"save_trigger": "ui_continue", "display": session.vnc.display},
            )
            await self._teardown(host)
            log(
                logger,
                logging.INFO,
                "capture persisted",
                host=host,
                cookies=cookies_n,
            )
            return {
                "ok": True,
                "host": host,
                "warmed": True,
                "title": title,
                "cookies": cookies_n,
            }

    async def cancel(self, base_url: str) -> Dict[str, Any]:
        host = profile_key_for_url(base_url)
        async with self._lock:
            if host not in self._active:
                return {"ok": True, "host": host, "cancelled": False}
            await self._teardown(host)
            log(logger, logging.INFO, "capture cancelled", host=host)
            return {"ok": True, "host": host, "cancelled": True}

    async def stop_all(self) -> None:
        async with self._lock:
            for host in list(self._active):
                await self._teardown(host)

    async def _launch(self, host: str, base_url: str) -> CaptureSession:
        if self.playwright is None:
            raise RuntimeError("playwright not ready")
        profile_root = ensure_writable_dir(self.cfg.profile_root, label="CRAWLER_PROFILE_ROOT")
        profile_dir = profile_root / host
        profile_dir.mkdir(parents=True, exist_ok=True)
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            p = profile_dir / name
            try:
                if p.is_symlink() or p.exists():
                    p.unlink()
            except OSError:
                pass

        vnc = CaptureVncStack(novnc_web_dir=self.cfg.novnc_web_dir)
        try:
            vnc.start()
        except Exception:
            vnc.stop()
            raise

        context = None
        try:
            context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                channel=self.cfg.chrome_channel,
                viewport=VIEWPORT,
                args=list(LAUNCH_ARGS),
                ignore_default_args=["--enable-automation"],
                env=vnc.chrome_env(),
            )
            page = context.pages[0] if context.pages else await context.new_page()
            state_file = profile_dir / "storage_state.json"
            cookies = load_cookies(state_file)
            if cookies:
                ok_jar, jar_msg = cookie_health(cookies)
                log(logger, logging.INFO, jar_msg, host=host)
                try:
                    await context.add_cookies(cookies)
                except Exception as exc:
                    log(
                        logger,
                        logging.WARNING,
                        "cookie inject warning",
                        host=host,
                        err=str(exc),
                    )
            try:
                await page.goto(base_url, wait_until="domcontentloaded", timeout=90_000)
            except Exception as exc:
                log(
                    logger,
                    logging.WARNING,
                    "capture goto warning",
                    host=host,
                    err=f"{type(exc).__name__}: {exc}",
                )
            log(
                logger,
                logging.INFO,
                "capture chrome launched",
                host=host,
                display=vnc.display,
                profileDir=str(profile_dir),
                existingProfile=looks_like_chrome_profile(profile_dir),
            )
            return CaptureSession(
                host=host,
                base_url=base_url,
                vnc=vnc,
                context=context,
                page=page,
            )
        except Exception:
            if context is not None:
                try:
                    await context.close()
                except Exception:
                    pass
            vnc.stop()
            raise

    async def _teardown(self, host: str) -> None:
        session = self._active.pop(host, None)
        if session is None:
            return
        try:
            await session.context.close()
        except Exception as exc:
            log(
                logger,
                logging.WARNING,
                "capture close warning",
                host=host,
                err=str(exc),
            )
        session.vnc.stop()
