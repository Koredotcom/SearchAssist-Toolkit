from __future__ import annotations

import httpx

from config import get_config


def get_headers() -> dict[str, str]:
    cfg = get_config()
    return {
        "auth": cfg.koreai_jwt_token,
        "Content-Type": "application/json",
    }


def get_client(timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(headers=get_headers(), timeout=timeout)
