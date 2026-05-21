from __future__ import annotations

import base64
import hashlib
import hmac
import json

from fastapi import APIRouter, HTTPException
from models import AppConfigCreate, AppConfigUpdate, AppConfigResponse
from db.database import create_app, delete_app, get_app, list_apps, update_app

router = APIRouter(prefix="/apps", tags=["apps"])


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_jwt(client_id: str, client_secret: str) -> str:
    """Generate HS256 JWT with payload {"appId": client_id} signed by client_secret."""
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(json.dumps({"appId": client_id}, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}"
    sig = hmac.new(client_secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(sig)}"


@router.get("", response_model=list[AppConfigResponse])
def get_apps():
    return list_apps()


@router.post("", response_model=AppConfigResponse, status_code=201)
def add_app(body: AppConfigCreate):
    data = body.model_dump()
    data["jwt_token"] = make_jwt(body.client_id, body.client_secret)
    return create_app(data)


@router.get("/{app_id}", response_model=AppConfigResponse)
def get_app_by_id(app_id: str):
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    return app


@router.put("/{app_id}", response_model=AppConfigResponse)
def update_app_by_id(app_id: str, body: AppConfigUpdate):
    existing = get_app(app_id)
    if not existing:
        raise HTTPException(404, "App not found")
    data = body.model_dump(exclude_none=True)
    # Regenerate JWT if either credential changed
    if "client_id" in data or "client_secret" in data:
        new_client_id = data.get("client_id", existing["client_id"])
        new_client_secret = data.get("client_secret", existing["client_secret"])
        data["jwt_token"] = make_jwt(new_client_id, new_client_secret)
    app = update_app(app_id, data)
    if not app:
        raise HTTPException(404, "App not found")
    return app


@router.delete("/{app_id}", status_code=204)
def delete_app_by_id(app_id: str):
    if not delete_app(app_id):
        raise HTTPException(404, "App not found")
