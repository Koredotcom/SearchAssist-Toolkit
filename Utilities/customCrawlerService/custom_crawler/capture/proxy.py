"""Same-origin reverse proxy for noVNC → localhost websockify.

Token + ws_port must match an in-progress capture so this is not an open SSRF hole.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx
from fastapi import Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

try:
    import websockets as _websockets
except ImportError:
    _websockets = None

if TYPE_CHECKING:
    from .manager import CaptureManager

_HOP = {
    "content-encoding",
    "content-length",
    "transfer-encoding",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "upgrade",
}


async def proxy_vnc_http(
    request: Request,
    token: str,
    ws_port: int,
    path: str,
    manager: "CaptureManager",
) -> Response:
    if not manager.vnc_allowed(token, ws_port):
        return Response("forbidden", status_code=403)
    target = f"http://127.0.0.1:{ws_port}/{path}".rstrip("/")
    if not path:
        target = f"http://127.0.0.1:{ws_port}/vnc.html"
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        r = await client.request(
            request.method,
            target,
            params=request.query_params,
            headers={"Accept": request.headers.get("accept", "*/*")},
        )
    headers = {k: v for k, v in r.headers.items() if k.lower() not in _HOP}
    return Response(content=r.content, status_code=r.status_code, headers=headers)


async def proxy_vnc_ws(websocket: WebSocket, token: str, ws_port: int, manager: "CaptureManager") -> None:
    if not manager.vnc_allowed(token, ws_port):
        await websocket.close(code=1008)
        return
    if _websockets is None:
        await websocket.close(code=1011)
        return
    offered = websocket.headers.get("sec-websocket-protocol", "")
    subprotocol = "binary" if "binary" in offered else None
    await websocket.accept(subprotocol=subprotocol)
    backend = None
    try:
        kwargs: dict = {"open_timeout": 8, "max_size": None}
        if subprotocol:
            kwargs["subprotocols"] = [subprotocol]
        backend = await _websockets.connect(
            f"ws://127.0.0.1:{ws_port}/",
            **kwargs,
        )
    except Exception:
        await websocket.close(code=1011)
        return

    async def client_to_backend() -> None:
        try:
            while True:
                msg = await websocket.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                if msg.get("bytes") is not None:
                    await backend.send(msg["bytes"])
                elif msg.get("text") is not None:
                    await backend.send(msg["text"])
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    async def backend_to_client() -> None:
        try:
            async for data in backend:
                if isinstance(data, bytes):
                    await websocket.send_bytes(data)
                else:
                    await websocket.send_text(str(data))
        except Exception:
            pass

    try:
        await asyncio.gather(client_to_backend(), backend_to_client())
    finally:
        try:
            await backend.close()
        except Exception:
            pass
