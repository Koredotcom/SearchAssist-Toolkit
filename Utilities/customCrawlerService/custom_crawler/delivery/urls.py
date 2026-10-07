"""Resolve callback / complete delivery targets.

Priority (per URL):

1. Non-empty ``callbackUrl`` / ``completeUrl`` on the ``/crawl`` payload (any client)
2. Absolute ``CRAWLER_CALLBACK_URL`` / ``CRAWLER_COMPLETE_URL`` in SDK ``.env``
3. Built from ``CRAWLER_CALLBACK_PUBLIC_HOST`` + ``streamId`` + ``jobId``

Findly does not send callback/complete keys; the SDK env is the normal path.
"""
from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional, Tuple


def resolve_delivery_urls(
    submit: Dict[str, Any],
    *,
    callback_public_host: str = "",
    callback_url_default: str = "",
    complete_url_default: str = "",
) -> Tuple[str, str]:
    """Return ``(callback_url, complete_url)`` — /crawl payload wins, else SDK env."""
    job_id = str(submit.get("jobId") or "").strip()
    stream_id = str(submit.get("streamId") or "").strip()
    host = (callback_public_host or "").rstrip("/")

    callback = str(submit.get("callbackUrl") or "").strip()
    complete = str(submit.get("completeUrl") or "").strip()

    if not callback:
        callback = (callback_url_default or "").strip()
    if not complete:
        complete = (complete_url_default or "").strip()

    if not callback and host and stream_id and job_id:
        callback = f"{host}/api/customCrawler/callback/{stream_id}/{job_id}"
    if not complete and host and stream_id and job_id:
        complete = f"{host}/api/customCrawler/complete/{stream_id}/{job_id}"

    return callback, complete


def merge_callback_headers(
    req_headers: Optional[list],
    *,
    callback_auth_header: str = "",
) -> list:
    """Build delivery headers: SDK callback auth fills gaps; payload headers win.

    KoreServer PublicAPI expects an ``auth`` header with a JWT scoped to
    ``search_assist:custom_crawler_callback``. The SDK does **not** mint that JWT —
    Findly (or the operator) must supply it via submit ``reqHeaders`` and/or
    ``CRAWLER_CALLBACK_AUTH_HEADER`` in the SDK ``.env``.
    """
    merged: Dict[str, Dict[str, Any]] = {}
    auth = (callback_auth_header or "").strip()
    if auth:
        # Accept either raw JWT or a full "auth: <jwt>" / "Bearer …" value.
        if ":" in auth and auth.split(":", 1)[0].strip().lower() in ("auth", "authorization"):
            key, value = auth.split(":", 1)
            merged[key.strip().lower()] = {
                "key": key.strip(),
                "value": value.strip(),
                "encodingFormat": "none",
            }
        else:
            merged["auth"] = {"key": "auth", "value": auth, "encodingFormat": "none"}

    for item in req_headers or []:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not key:
            continue
        merged[str(key).lower()] = dict(item)

    return list(merged.values())


def headers_to_dict(req_headers: Optional[List[Dict[str, Any]]]) -> Dict[str, str]:
    """Flatten Custom-Connector style header entries, decoding base64 values."""
    out: Dict[str, str] = {}
    for item in req_headers or []:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        value = item.get("value")
        if not key:
            continue
        if item.get("encodingFormat") == "base64" and isinstance(value, str):
            try:
                value = base64.b64decode(value).decode("utf-8")
            except Exception:
                pass
        out[str(key)] = "" if value is None else str(value)
    return out
