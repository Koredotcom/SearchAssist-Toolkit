from __future__ import annotations
import httpx


def get_headers(jwt_token: str) -> dict[str, str]:
    return {"auth": jwt_token, "Content-Type": "application/json"}


def get_client(app: dict, timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(headers=get_headers(app["jwt_token"]), timeout=timeout)
