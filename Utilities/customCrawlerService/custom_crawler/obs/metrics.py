"""Simple in-process counters/gauges surfaced through /health and completion stats."""
from __future__ import annotations

import threading
from typing import Dict

_FIELDS = (
    "discovered",
    "fetched",
    "success",
    "failed",
    "skipped",
    "non_html",
    "retried",
    "challenged",
    "context_recycles",
    "callback_failures",
    "spool_depth",
    "batches_sent",
)


class Counters:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        for name in _FIELDS:
            setattr(self, name, 0)

    def inc(self, name: str, by: int = 1) -> None:
        with self._lock:
            setattr(self, name, getattr(self, name) + by)

    def set(self, name: str, value: int) -> None:
        with self._lock:
            setattr(self, name, value)

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return {name: getattr(self, name) for name in _FIELDS}
