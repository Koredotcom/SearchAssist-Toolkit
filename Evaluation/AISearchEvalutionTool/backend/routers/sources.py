from fastapi import APIRouter, HTTPException
from models import ContentSourceResponse, SourceResponse
from db.database import get_app
from koreai.connectors import list_connectors, list_content_sources
from koreai.client import get_client

router = APIRouter(prefix="/apps/{app_id}/sources", tags=["sources"])


@router.get("", response_model=list[SourceResponse])
def get_sources(app_id: str):
    """List Kore.ai *connector* sources (Jira, Confluence, Wolken, YouTube, …).

    Web crawls and uploaded files live under separate endpoints because
    Kore.ai exposes them only via the content index, not as connectors.
    """
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    try:
        return list_connectors(app)
    except Exception as exc:
        raise HTTPException(502, f"Failed to fetch sources from Kore.ai: {exc}")


@router.get("/web-crawls", response_model=list[ContentSourceResponse])
def get_web_crawls(app_id: str):
    """List the website crawls feeding this app (sys_content_type='web')."""
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    try:
        return list_content_sources(app, "web")
    except Exception as exc:
        raise HTTPException(502, f"Failed to fetch web crawls from Kore.ai: {exc}")


@router.get("/documents", response_model=list[ContentSourceResponse])
def get_uploaded_documents(app_id: str):
    """List the uploaded-document containers feeding this app (sys_content_type='file')."""
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    try:
        return list_content_sources(app, "file")
    except Exception as exc:
        raise HTTPException(502, f"Failed to fetch documents from Kore.ai: {exc}")


@router.get("/{connector_id}/debug-content")
def debug_content(app_id: str, connector_id: str):
    """Return raw content-by-cond response for a connector — debug only."""
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    url = f"{app['host_url']}/api/public/bot/{app['bot_id']}/content-by-cond"
    payload = {"query": {"connectorId": connector_id}}
    try:
        with get_client(app) as client:
            resp = client.post(url, json=payload)
            return {"status": resp.status_code, "body": resp.json()}
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.get("/debug-chunks/{doc_id}")
def debug_chunks(app_id: str, doc_id: str):
    """Test the Kore.ai chunk/list API for a specific doc — returns raw response."""
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    url = f"{app['host_url']}/api/public/bot/{app['bot_id']}/chunk/list"
    payload = {
        "filters": {
            "conditions": [{"key": "docId", "op": "equals", "value": doc_id}],
            "operand": "and",
        },
        "enableFilters": True,
    }
    try:
        with get_client(app) as client:
            resp = client.post(url, json=payload)
            return {
                "status": resp.status_code,
                "url": url,
                "payload": payload,
                "body": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
            }
    except Exception as exc:
        return {"error": str(exc), "url": url, "payload": payload}
