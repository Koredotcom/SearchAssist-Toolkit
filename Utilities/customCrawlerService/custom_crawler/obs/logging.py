"""Structured JSON logging with jobId binding and secret redaction."""
from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar
from typing import Any, Dict

job_id_var: ContextVar[str] = ContextVar("job_id", default="-")
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")

# Header/field names whose values must never appear in logs.
_SECRET_KEYS = re.compile(
    r"(authorization|api[-_]?key|token|secret|password|passwd|cookie|set-cookie|x-api-key)",
    re.IGNORECASE,
)


def redact(value: Any) -> Any:
    """Recursively redact secret-looking values in dicts/lists."""
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and _SECRET_KEYS.search(k):
                out[k] = "***"
            else:
                out[k] = redact(v)
        return out
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "jobId": job_id_var.get(),
            "traceId": trace_id_var.get(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(redact(extra))
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logger(name: str = "custom_crawler", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if getattr(logger, "_configured", False):
        return logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
    logger._configured = True  # type: ignore[attr-defined]
    return logger


def log(logger: logging.Logger, level: int, msg: str, **fields: Any) -> None:
    logger.log(level, msg, extra={"extra_fields": fields})
