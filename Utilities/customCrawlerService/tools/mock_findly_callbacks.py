#!/usr/bin/env python3
"""Local mock Findly callback + complete endpoints for custom crawler E2E testing.

Listens on http://127.0.0.1:9999
  POST /callback  — page batches (gzip+base64 payload)
  POST /complete  — job completion signal

Pretty-prints decoded payloads under ./callback_inbox/
"""
from __future__ import annotations

import base64
import gzip
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 9999
INBOX = Path(__file__).resolve().parent / "callback_inbox"
INBOX.mkdir(parents=True, exist_ok=True)

_batch_n = 0
_complete_n = 0


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def _decode_payload(body: dict):
    raw = body.get("payloadGzipBase64")
    if not raw:
        return None
    try:
        return json.loads(gzip.decompress(base64.b64decode(raw)))
    except Exception as exc:
        return {"_decode_error": str(exc)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))
        sys.stdout.flush()

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {"_raw": raw.decode("utf-8", "replace")}

    def _ok(self, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        global _batch_n, _complete_n
        body = self._read_json()
        path = self.path.split("?", 1)[0]

        if path.rstrip("/") == "/callback":
            _batch_n += 1
            decoded = _decode_payload(body)
            pages = []
            if isinstance(decoded, dict):
                pages = decoded.get("pages") or decoded.get("items") or []
            if not isinstance(pages, list):
                pages = []
            summary = {
                "jobId": body.get("jobId"),
                "batchSeq": body.get("batchSeq"),
                "isLast": body.get("isLast"),
                "pageCount": len(pages),
                "pageUrls": [
                    (p.get("page_url") or p.get("url")) for p in pages if isinstance(p, dict)
                ][:20],
            }
            stamp = _ts()
            (INBOX / f"callback-{_batch_n:04d}-{stamp}.json").write_text(
                json.dumps({"envelope": body, "decoded": decoded, "summary": summary}, indent=2),
                encoding="utf-8",
            )
            print(
                f"\n=== CALLBACK #{_batch_n} jobId={summary['jobId']} "
                f"batchSeq={summary['batchSeq']} isLast={summary['isLast']} "
                f"pages={summary['pageCount']} ==="
            )
            for u in summary["pageUrls"]:
                print(f"  - {u}")
            sys.stdout.flush()
            self._ok({"status": "accepted", "batch": _batch_n})
            return

        if path.rstrip("/") == "/complete":
            _complete_n += 1
            stamp = _ts()
            (INBOX / f"complete-{_complete_n:04d}-{stamp}.json").write_text(
                json.dumps(body, indent=2),
                encoding="utf-8",
            )
            print(
                f"\n=== COMPLETE #{_complete_n} jobId={body.get('jobId')} "
                f"status={body.get('status')} stats={body.get('stats')} "
                f"error={body.get('error')} ===\n"
            )
            sys.stdout.flush()
            self._ok({"status": "accepted", "complete": _complete_n})
            return

        self.send_response(404)
        self.end_headers()
        self.wfile.write(b'{"error":"not found"}')

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("", "/health"):
            self._ok(
                {
                    "status": "ok",
                    "callbacks": _batch_n,
                    "completes": _complete_n,
                    "inbox": str(INBOX),
                }
            )
            return
        self.send_response(404)
        self.end_headers()


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Mock Findly callbacks listening on http://{HOST}:{PORT}")
    print(f"  POST /callback")
    print(f"  POST /complete")
    print(f"  GET  /health")
    print(f"Inbox: {INBOX}")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        server.server_close()


if __name__ == "__main__":
    main()
