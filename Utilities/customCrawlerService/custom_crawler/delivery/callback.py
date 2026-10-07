"""Batched delivery to the Findly callback URL.

Batches flush at whichever comes first: ``callbackBatchSize`` pages or ``callbackMaxBytes`` (1 MB so
broker messages stay bounded). Payloads are gzipped and base64-encoded into a JSON field (we do not
rely on HTTP Content-Encoding surviving the KoreServer proxy). Failed deliveries retry with backoff
and then spill to a disk spool that survives restarts and is replayed.
"""
from __future__ import annotations

import asyncio
import base64
import gzip
import json
import logging as _logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from custom_crawler.delivery.urls import headers_to_dict
from custom_crawler.obs.logging import log as slog

DEFAULT_MAX_BYTES = 1024 * 1024


class CallbackDelivery:
    def __init__(
        self,
        *,
        job_id: str,
        callback_url: str,
        complete_url: str,
        req_headers: Optional[List[Dict[str, Any]]],
        batch_size: int = 10,
        max_bytes: int = DEFAULT_MAX_BYTES,
        spool_dir: str = "/data/spool",
        retry_max: int = 5,
        timeout: float = 30.0,
        counters: Any = None,
        logger: Any = None,
    ) -> None:
        self.job_id = job_id
        self.callback_url = callback_url
        self.complete_url = complete_url
        self.headers = headers_to_dict(req_headers)
        self.headers.setdefault("Content-Type", "application/json")
        self.batch_size = max(1, batch_size)
        self.max_bytes = max(64 * 1024, max_bytes)
        self.spool_dir = Path(spool_dir) / job_id
        self.retry_max = max(1, retry_max)
        self.timeout = timeout
        self.counters = counters
        self.logger = logger

        self._buffer: List[Dict[str, Any]] = []
        self._buffer_bytes = 0
        self._batch_seq = 0
        self._lock = asyncio.Lock()
        self.spool_dir.mkdir(parents=True, exist_ok=True)

    @property
    def batches_sent(self) -> int:
        return self._batch_seq

    def _encode_body(self, obj: Dict[str, Any]) -> str:
        raw = json.dumps(obj, default=str).encode("utf-8")
        gz = gzip.compress(raw)
        return base64.b64encode(gz).decode("ascii")

    async def add_page(self, page: Dict[str, Any]) -> None:
        approx = len(json.dumps(page, default=str).encode("utf-8"))
        async with self._lock:
            # Flush first if this page would overflow the byte cap.
            if self._buffer and (self._buffer_bytes + approx) > self.max_bytes:
                await self._flush_locked(is_last=False)
            self._buffer.append(page)
            self._buffer_bytes += approx
            if len(self._buffer) >= self.batch_size or self._buffer_bytes >= self.max_bytes:
                await self._flush_locked(is_last=False)

    async def flush(self, is_last: bool = False) -> None:
        async with self._lock:
            if self._buffer or is_last:
                await self._flush_locked(is_last=is_last)

    def _log(self, level: int, msg: str, **fields: Any) -> None:
        if self.logger is not None:
            slog(self.logger, level, msg, **fields)

    async def _flush_locked(self, is_last: bool) -> None:
        if not self._buffer and not is_last:
            return
        self._batch_seq += 1
        pages = self._buffer
        self._buffer = []
        self._buffer_bytes = 0
        envelope = {
            "jobId": self.job_id,
            "batchSeq": self._batch_seq,
            "isLast": bool(is_last),
            "payloadGzipBase64": self._encode_body({"pages": pages}),
            "pageCount": len(pages),
        }
        self._log(
            _logging.INFO,
            "callback batch flush",
            batchSeq=self._batch_seq,
            pageCount=len(pages),
            isLast=bool(is_last),
            url=self.callback_url,
        )
        await self._deliver(self.callback_url, envelope, spool_name=f"batch-{self._batch_seq:06d}.json")

    async def _deliver(self, url: str, envelope: Dict[str, Any], spool_name: str) -> None:
        if not url:
            self._log(_logging.INFO, "callback skipped (no url)", spoolName=spool_name)
            return
        delay = 1.0
        last_err: Optional[str] = None
        last_status: Optional[int] = None
        for attempt in range(1, self.retry_max + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, headers=self.headers, json=envelope)
                last_status = resp.status_code
                if resp.status_code < 300:
                    if self.counters:
                        self.counters.inc("batches_sent")
                    self._log(
                        _logging.INFO,
                        "callback delivered",
                        url=url,
                        statusCode=resp.status_code,
                        attempt=attempt,
                        spoolName=spool_name,
                        batchSeq=envelope.get("batchSeq"),
                        totalBatches=envelope.get("totalBatches"),
                        status=envelope.get("status"),
                        pageCount=envelope.get("pageCount"),
                    )
                    return
                last_err = f"http_{resp.status_code}"
                self._log(
                    _logging.WARNING,
                    "callback non-2xx",
                    url=url,
                    statusCode=resp.status_code,
                    attempt=attempt,
                    body=(resp.text or "")[:200],
                )
                # 413 is terminal (batch too large) — spool and move on.
                if resp.status_code == 413:
                    break
            except Exception as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                self._log(
                    _logging.WARNING,
                    "callback transport error",
                    url=url,
                    attempt=attempt,
                    err=last_err,
                )
            if attempt < self.retry_max:
                await asyncio.sleep(min(delay, 30))
                delay *= 2
        # Exhausted retries → spool to disk.
        self._log(
            _logging.ERROR,
            "callback failed — spooling",
            url=url,
            spoolName=spool_name,
            lastStatus=last_status,
            lastErr=last_err,
            retries=self.retry_max,
        )
        self._spool(spool_name, {"url": url, "envelope": envelope})
        if self.counters:
            self.counters.inc("callback_failures")

    def _spool(self, name: str, obj: Dict[str, Any]) -> None:
        path = self.spool_dir / name
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(obj, default=str), encoding="utf-8")
            os.replace(tmp, path)
            if self.counters:
                self.counters.set("spool_depth", len(list(self.spool_dir.glob("*.json"))))
            self._log(_logging.INFO, "callback spooled to disk", path=str(path))
        except Exception as exc:
            self._log(_logging.ERROR, "callback spool write failed", path=str(path), err=str(exc))

    async def replay_spool(self) -> None:
        for path in sorted(self.spool_dir.glob("*.json")):
            try:
                obj = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            url = obj.get("url")
            envelope = obj.get("envelope")
            if not url or envelope is None:
                path.unlink(missing_ok=True)
                continue
            delivered = False
            delay = 1.0
            for attempt in range(1, self.retry_max + 1):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        resp = await client.post(url, headers=self.headers, json=envelope)
                    if resp.status_code < 300:
                        delivered = True
                        break
                except Exception:
                    pass
                await asyncio.sleep(min(delay, 30))
                delay *= 2
            if delivered:
                path.unlink(missing_ok=True)
                self._log(_logging.INFO, "spool replay delivered", path=str(path))
        if self.counters:
            self.counters.set("spool_depth", len(list(self.spool_dir.glob("*.json"))))

    async def send_complete(self, status: str, stats: Dict[str, Any], error: Optional[str]) -> None:
        envelope = {
            "jobId": self.job_id,
            "status": status,
            "totalBatches": self._batch_seq,
            "stats": stats,
            "error": error,
        }
        self._log(
            _logging.INFO,
            "sending complete callback",
            url=self.complete_url,
            status=status,
            totalBatches=self._batch_seq,
            error=error,
            **(stats or {}),
        )
        await self._deliver(self.complete_url, envelope, spool_name="complete.json")
