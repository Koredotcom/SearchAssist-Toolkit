from __future__ import annotations

from fastapi import APIRouter, HTTPException
from models import AppConfigCreate, AppConfigUpdate, AppConfigResponse
from db.database import create_app, delete_app, get_app, list_apps, update_app

router = APIRouter(prefix="/apps", tags=["apps"])


@router.get("", response_model=list[AppConfigResponse])
def get_apps():
    return list_apps()


@router.post("", response_model=AppConfigResponse, status_code=201)
def add_app(body: AppConfigCreate):
    data = body.model_dump()
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
    app = update_app(app_id, data)
    if not app:
        raise HTTPException(404, "App not found")
    return app


@router.delete("/{app_id}", status_code=204)
def delete_app_by_id(app_id: str):
    if not delete_app(app_id):
        raise HTTPException(404, "App not found")
