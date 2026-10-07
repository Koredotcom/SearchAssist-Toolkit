"""Short ``log(msg)`` helper for the browser engine (structured job logger underneath)."""
from __future__ import annotations

import logging

from ..obs.logging import log as _structured_log
from ..obs.logging import setup_logger

_logger = setup_logger("custom_crawler.browser")


def log(msg: str) -> None:
    _structured_log(_logger, logging.INFO, msg)
