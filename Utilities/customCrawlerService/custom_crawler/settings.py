"""Service environment config and per-job EngineConfig.

`advanceSettings` keys are camelCase and shared verbatim with Findly — no snake_case rename and no
wire-level translation table. `EngineConfig` reads those same keys.

Loads ``.env`` from the service root (next to ``requirements.txt``) once at import time so you do
not need to ``export CRAWLER_*`` manually. The file is authoritative (``override=True``): a stale
``export CRAWLER_XVFB_MODE=auto`` left in your shell must not silently defeat ``.env``. Docker images
ship without a ``.env``, so container ``ENV`` values still apply there.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_SERVICE_ROOT = Path(__file__).resolve().parent.parent
_ENV_LOADED = False


def load_env(env_file: Optional[str] = None) -> Path:
    """Load ``.env`` into ``os.environ`` (idempotent). Returns the file path used, if any."""
    global _ENV_LOADED
    path = Path(env_file) if env_file else (_SERVICE_ROOT / ".env")
    if not _ENV_LOADED:
        try:
            from dotenv import load_dotenv

            if path.is_file():
                load_dotenv(path, override=True)
            _ENV_LOADED = True
        except ImportError:
            # python-dotenv optional until installed; env vars still work.
            _ENV_LOADED = True
    return path


# Load before ServiceConfig defaults read os.environ.
load_env()


def ensure_writable_dir(path: str, *, label: str) -> Path:
    """Create ``path`` and prove the current user can write into it.

    Catches the common AWS/local mismatch where Chrome was previously started as root and left
    ``CRAWLER_PROFILE_ROOT/<host>/`` owned by root, so a later non-root warmup/crawl silently fails
    to persist ``cf_clearance``.
    """
    p = Path(path).expanduser().resolve()
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"{label} {p} is not creatable by uid={os.getuid()}: {exc}. "
            f"Fix ownership (chown -R $(whoami) {p}) or point CRAWLER_* at a writable volume."
        ) from exc
    if not os.access(p, os.W_OK | os.X_OK):
        raise RuntimeError(
            f"{label} {p} is not writable by uid={os.getuid()} (mode={oct(p.stat().st_mode)}). "
            f"Fix: sudo chown -R $(whoami) {p}"
        )
    # Prove create+unlink works (sticky bits / NFS quirks can pass access() but fail open()).
    try:
        fd, probe = tempfile.mkstemp(prefix=".crawler_write_probe_", dir=str(p))
        os.close(fd)
        os.unlink(probe)
    except OSError as exc:
        raise RuntimeError(
            f"{label} {p} rejected a write probe by uid={os.getuid()}: {exc}. "
            f"Fix: sudo chown -R $(whoami) {p}"
        ) from exc
    return p


def ensure_data_dirs(cfg: "ServiceConfig") -> Tuple[Path, Path]:
    """Validate profile + spool roots at service / warmup startup."""
    profiles = ensure_writable_dir(cfg.profile_root, label="CRAWLER_PROFILE_ROOT")
    spool = ensure_writable_dir(cfg.spool_dir, label="CRAWLER_SPOOL_DIR")
    return profiles, spool


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _opt_int(name: str) -> Optional[int]:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


@dataclass
class ServiceConfig:
    port: int = field(default_factory=lambda: _int("CRAWLER_PORT", 8080))
    profile_root: str = field(
        default_factory=lambda: os.environ.get("CRAWLER_PROFILE_ROOT", "/data/profiles")
    )
    spool_dir: str = field(
        default_factory=lambda: os.environ.get("CRAWLER_SPOOL_DIR", "/data/spool")
    )
    chrome_channel: str = field(
        default_factory=lambda: os.environ.get("CRAWLER_CHROME_CHANNEL", "chrome")
    )
    xvfb_mode: str = field(
        default_factory=lambda: os.environ.get("CRAWLER_XVFB_MODE", "auto")
    )
    page_timeout_ms: int = field(
        default_factory=lambda: _int("CRAWLER_PAGE_TIMEOUT_MS", 60000)
    )
    challenge_wait_seconds: int = field(
        default_factory=lambda: _int("CRAWLER_CHALLENGE_WAIT_SECONDS", 90)
    )
    # Extra wait when an operator is expected to click Turnstile during warmup/local debug.
    human_cf_wait_seconds: int = field(
        default_factory=lambda: _int("CRAWLER_HUMAN_CF_WAIT_SECONDS", 90)
    )
    job_budget_seconds: int = field(
        default_factory=lambda: _int("CRAWLER_JOB_BUDGET_SECONDS", 7200)
    )
    context_recycle_every: int = field(
        default_factory=lambda: _int("CRAWLER_CONTEXT_RECYCLE_EVERY", 50)
    )
    rss_limit_mb: Optional[int] = field(default_factory=lambda: _opt_int("CRAWLER_RSS_LIMIT_MB"))
    callback_retry_max: int = field(
        default_factory=lambda: _int("CRAWLER_CALLBACK_RETRY_MAX", 5)
    )
    # KoreServer public API base used when submit omits callbackUrl/completeUrl.
    # Example: http://localhost:3000  →  …/api/customCrawler/callback/{streamId}/{jobId}
    callback_public_host: str = field(
        default_factory=lambda: os.environ.get("CRAWLER_CALLBACK_PUBLIC_HOST", "").rstrip("/")
    )
    # Optional absolute overrides (rarely needed; payload still wins when present).
    callback_url: str = field(
        default_factory=lambda: os.environ.get("CRAWLER_CALLBACK_URL", "").strip()
    )
    complete_url: str = field(
        default_factory=lambda: os.environ.get("CRAWLER_COMPLETE_URL", "").strip()
    )
    # KoreServer PublicAPI JWT for the ``auth`` header (SDK does not mint JWTs).
    # Payload reqHeaders with the same key override this.
    callback_auth_header: str = field(
        default_factory=lambda: os.environ.get("CRAWLER_CALLBACK_AUTH_HEADER", "").strip()
    )
    # crawl_retry reads failed URLs from the Findly public API. Host and JWT fall
    # back to the callback values, which already point at the same KoreServer.
    content_status_host: str = field(
        default_factory=lambda: os.environ.get("CRAWLER_CONTENT_STATUS_HOST", "").rstrip("/")
    )
    content_status_auth_header: str = field(
        default_factory=lambda: os.environ.get("CRAWLER_CONTENT_STATUS_AUTH_HEADER", "").strip()
    )
    content_status_path: str = field(
        default_factory=lambda: os.environ.get("CRAWLER_CONTENT_STATUS_PATH", "").strip()
    )
    content_status_page_limit: int = field(
        default_factory=lambda: _int("CRAWLER_CONTENT_STATUS_LIMIT", 200)
    )
    # Default off — ephemeral Chrome. Enable after warmup for CF-protected hosts.
    use_profile: bool = field(
        default_factory=lambda: os.environ.get("CRAWLER_USE_PROFILE", "false").lower()
        in ("1", "true", "yes", "on")
    )
    vnc_enabled: bool = field(
        default_factory=lambda: os.environ.get("CRAWLER_VNC_ENABLED", "true").lower()
        in ("1", "true", "yes", "on")
    )
    vnc_host: str = field(
        default_factory=lambda: os.environ.get("CRAWLER_VNC_HOST", "localhost")
    )
    novnc_web_dir: str = field(
        default_factory=lambda: os.environ.get("CRAWLER_NOVNC_WEB_DIR", "/opt/noVNC")
    )


# Hard default ceiling so a missing/oversized maxUrlLimit cannot blow up memory.
DEFAULT_MAX_URL_LIMIT = 5000


@dataclass
class EngineConfig:
    """Per-job crawl configuration. Field names mirror Findly advanceSettings (camelCase)."""

    crawlBeyondSitemaps: bool = True
    allowSubdomains: bool = False
    maxUrlLimit: int = DEFAULT_MAX_URL_LIMIT
    crawlDepth: int = 5
    respectRobotTxtDirectives: bool = True
    isJavaScriptRendered: bool = True
    crawlDelay: float = 0.1
    useCookies: bool = True
    # None = use service CRAWLER_USE_PROFILE; True/False = per-job override.
    useProfile: Optional[bool] = None
    crawlEverything: bool = False
    allowedOpt: bool = False
    allowedURLs: List[Dict[str, Any]] = field(default_factory=list)
    blockedOpt: bool = False
    blockedURLs: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_advance_settings(cls, adv: Optional[Dict[str, Any]]) -> "EngineConfig":
        adv = adv or {}
        cfg = cls()
        if "crawlBeyondSitemaps" in adv:
            cfg.crawlBeyondSitemaps = bool(adv["crawlBeyondSitemaps"])
        if "allowSubdomains" in adv:
            cfg.allowSubdomains = bool(adv["allowSubdomains"])
        if adv.get("maxUrlLimit"):
            try:
                cfg.maxUrlLimit = max(1, int(adv["maxUrlLimit"]))
            except (TypeError, ValueError):
                pass
        if adv.get("crawlDepth") is not None:
            try:
                cfg.crawlDepth = max(0, int(adv["crawlDepth"]))
            except (TypeError, ValueError):
                pass
        if "respectRobotTxtDirectives" in adv:
            cfg.respectRobotTxtDirectives = bool(adv["respectRobotTxtDirectives"])
        if "isJavaScriptRendered" in adv:
            cfg.isJavaScriptRendered = bool(adv["isJavaScriptRendered"])
        if adv.get("crawlDelay") is not None:
            try:
                cfg.crawlDelay = max(0.0, float(adv["crawlDelay"]))
            except (TypeError, ValueError):
                pass
        if "useCookies" in adv:
            cfg.useCookies = bool(adv["useCookies"])
        if "useProfile" in adv:
            cfg.useProfile = bool(adv["useProfile"])
        if "crawlEverything" in adv:
            cfg.crawlEverything = bool(adv["crawlEverything"])
        if "allowedOpt" in adv:
            cfg.allowedOpt = bool(adv["allowedOpt"])
        if isinstance(adv.get("allowedURLs"), list):
            cfg.allowedURLs = adv["allowedURLs"]
        if "blockedOpt" in adv:
            cfg.blockedOpt = bool(adv["blockedOpt"])
        if isinstance(adv.get("blockedURLs"), list):
            cfg.blockedURLs = adv["blockedURLs"]
        return cfg
