"""Per-worker login/session state — DEFERRED past v1.

Placeholder for the later auth phase: login runs once per worker (not per job), re-runs on context
recycle/relaunch, and re-logs on mid-crawl session loss (login-redirect pattern or sustained
401/403). Not used in v1.
"""
from __future__ import annotations

from typing import Any, Dict


class WorkerSession:  # pragma: no cover - deferred
    def __init__(self, auth: Dict[str, Any]) -> None:
        self.auth = auth
        self.logged_in = False
