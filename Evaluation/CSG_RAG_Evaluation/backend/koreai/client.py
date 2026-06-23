from __future__ import annotations
import httpx


def get_client(app: dict, timeout: float = 30.0) -> httpx.Client:
    """Return an httpx.Client with the appropriate auth for this app.

    New Agent Platform apps use x-api-key.
    Legacy SearchAI apps use jwt_token in the 'auth' header.
    Priority: x_api_key > jwt_token (fallback for old connectors/content endpoints).
    """
    x_api_key = app.get("x_api_key", "")
    jwt_token = app.get("jwt_token", "")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if x_api_key:
        headers["x-api-key"] = x_api_key
    elif jwt_token:
        headers["auth"] = jwt_token
    return httpx.Client(headers=headers, timeout=timeout)
