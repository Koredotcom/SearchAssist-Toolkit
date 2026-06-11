from __future__ import annotations

import anthropic
import httpx
import openai
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.database import get_app, update_app
from agents.llm_client import (
    _extract_gemini_text,
    _gemini_endpoint,
    _gemini_payload,
    _azure_client_and_model,
    _openai_client_and_model,
    _openai_call_kwargs,
    _parse_azure_endpoint,
)

router = APIRouter(prefix="/apps/{app_id}/api-keys", tags=["app-api-keys"])


class AppApiKeyUpdate(BaseModel):
    anthropic_key: str | None = None
    anthropic_base_url: str | None = None
    openai_key: str | None = None
    openai_base_url: str | None = None
    gemini_key: str | None = None
    gemini_base_url: str | None = None
    azure_key: str | None = None
    azure_endpoint: str | None = None
    azure_deployment: str | None = None
    azure_api_version: str | None = None
    default_model: str | None = None
    case1_threshold: float | None = None
    case2_threshold: float | None = None


def _mask(key: str) -> str:
    if not key:
        return ""
    return key[:16] + "..." if len(key) > 16 else key


@router.get("")
def get_app_api_keys(app_id: str):
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    ant_key = app.get("anthropic_key", "")
    oai_key = app.get("openai_key", "")
    gemini_key = app.get("gemini_key", "")
    azure_key = app.get("azure_key", "")
    return {
        "anthropic_key_set": bool(ant_key),
        "anthropic_key_preview": _mask(ant_key),
        "anthropic_base_url": app.get("anthropic_base_url", "") or "",
        "openai_key_set": bool(oai_key),
        "openai_key_preview": _mask(oai_key),
        "openai_base_url": app.get("openai_base_url", "") or "",
        "gemini_key_set": bool(gemini_key),
        "gemini_key_preview": _mask(gemini_key),
        "gemini_base_url": app.get("gemini_base_url", "") or "",
        "azure_key_set": bool(azure_key),
        "azure_key_preview": _mask(azure_key),
        "azure_endpoint": app.get("azure_endpoint", "") or "",
        "azure_deployment": app.get("azure_deployment", "") or "",
        "azure_api_version": app.get("azure_api_version", "") or "",
        "default_model": app.get("default_model", "") or "",
        "case1_threshold": float(app.get("case1_threshold") or 0.5),
        "case2_threshold": float(app.get("case2_threshold") or 0.5),
    }


@router.post("")
def set_app_api_keys(app_id: str, body: AppApiKeyUpdate):
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    data: dict = {}
    if body.anthropic_key is not None:
        data["anthropic_key"] = body.anthropic_key.strip()
    if body.anthropic_base_url is not None:
        data["anthropic_base_url"] = body.anthropic_base_url.strip()
    if body.openai_key is not None:
        data["openai_key"] = body.openai_key.strip()
    if body.openai_base_url is not None:
        data["openai_base_url"] = body.openai_base_url.strip()
    if body.gemini_key is not None:
        data["gemini_key"] = body.gemini_key.strip()
    if body.gemini_base_url is not None:
        data["gemini_base_url"] = body.gemini_base_url.strip()
    if body.azure_key is not None:
        data["azure_key"] = body.azure_key.strip()
    if body.azure_endpoint is not None:
        data["azure_endpoint"] = body.azure_endpoint.strip()
    if body.azure_deployment is not None:
        data["azure_deployment"] = body.azure_deployment.strip()
    if body.azure_api_version is not None:
        data["azure_api_version"] = body.azure_api_version.strip()
    if body.default_model is not None:
        data["default_model"] = body.default_model.strip()
    if body.case1_threshold is not None:
        data["case1_threshold"] = max(0.0, min(1.0, float(body.case1_threshold)))
    if body.case2_threshold is not None:
        data["case2_threshold"] = max(0.0, min(1.0, float(body.case2_threshold)))
    if data:
        update_app(app_id, data)
    return {"ok": True}


class TestKeyRequest(BaseModel):
    key: str | None = None        # if provided, test this key instead of the saved one
    base_url: str | None = None   # if provided, test against this endpoint


@router.post("/test-anthropic")
def test_app_anthropic(app_id: str, body: TestKeyRequest = TestKeyRequest()):
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    key = (body.key or "").strip() or app.get("anthropic_key", "")
    if not key:
        raise HTTPException(400, "No Anthropic key provided or saved")
    raw_url = (body.base_url if body.base_url is not None else app.get("anthropic_base_url", "")) or ""
    base_url = raw_url.strip() or None
    try:
        client = anthropic.Anthropic(api_key=key, base_url=base_url)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=60,
            messages=[{"role": "user", "content": "Say hello in exactly 3 words."}],
        )
        return {"ok": True, "response": msg.content[0].text.strip()}
    except anthropic.AuthenticationError:
        raise HTTPException(401, "Invalid Anthropic API key")
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/test-gemini")
def test_app_gemini(app_id: str, body: TestKeyRequest = TestKeyRequest()):
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    key = (body.key or "").strip() or app.get("gemini_key", "")
    if not key:
        raise HTTPException(400, "No Gemini API key provided or saved")

    raw_url = (body.base_url if body.base_url is not None else app.get("gemini_base_url", "")) or ""
    base_url = raw_url.strip()
    if base_url and not base_url.startswith("http"):
        raise HTTPException(400, "Invalid base URL — must start with http(s)://")

    test_app = {**app, "gemini_key": key, "gemini_base_url": base_url}
    try:
        endpoint, api_key = _gemini_endpoint(test_app["app_id"], "gemini-2.5-flash", _app_override=test_app)
        resp = httpx.post(
            endpoint,
            params={"key": api_key},
            json=_gemini_payload("", "Say hello in exactly 3 words.", 60, 0.0),
            timeout=60.0,
        )
        resp.raise_for_status()
        text, _finish_reason = _extract_gemini_text(resp.json())
        return {"ok": True, "response": text.strip()}
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        detail = exc.response.text
        if status in (401, 403):
            raise HTTPException(status, "Invalid Gemini API key or insufficient permissions")
        raise HTTPException(502, detail)
    except Exception as exc:
        raise HTTPException(502, str(exc))


@router.post("/test-openai")
def test_app_openai(app_id: str, body: TestKeyRequest = TestKeyRequest()):
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    key = (body.key or "").strip() or app.get("openai_key", "")
    if not key:
        raise HTTPException(400, "No OpenAI key provided or saved")

    raw_url = (body.base_url if body.base_url is not None else app.get("openai_base_url", "")) or ""
    base_url = raw_url.strip()
    azure = _parse_azure_endpoint(base_url) if base_url else None
    if base_url and azure is None and not base_url.startswith("http"):
        raise HTTPException(400, "Invalid base URL — must start with http(s)://")
    # For Azure, the deployment comes from the URL if present, else from the
    # configured default_model (the model picked on this page).
    default_model = (app.get("default_model") or "").strip()
    if azure and not azure.get("deployment") and not default_model:
        raise HTTPException(
            400,
            "Azure needs a deployment — set the Default model on this page, "
            "or use the full chat-completions URL with the deployment path.",
        )
    test_model = default_model or "gpt-4.1-mini"

    # Build a temporary app dict so _openai_client_and_model picks up the test key/url
    test_app = {**app, "openai_key": key}
    if base_url:
        test_app["openai_base_url"] = base_url
    client, effective_model = _openai_client_and_model(test_app["app_id"], test_model, _app_override=test_app)
    try:
        resp = client.chat.completions.create(
            model=effective_model,
            messages=[{"role": "user", "content": "Say hello in exactly 3 words."}],
            **_openai_call_kwargs(effective_model, 60, 0.0),
        )
        return {"ok": True, "response": resp.choices[0].message.content.strip()}
    except openai.AuthenticationError:
        raise HTTPException(401, "Invalid OpenAI / Azure API key")
    except openai.NotFoundError as exc:
        raise HTTPException(
            404,
            f"Endpoint or deployment not found. "
            f"{'Verify the Azure deployment name and api-version.' if azure else 'Check the base URL.'} ({exc})",
        )
    except Exception as exc:
        raise HTTPException(502, str(exc))


class TestAzureRequest(BaseModel):
    key: str | None = None
    endpoint: str | None = None
    deployment: str | None = None
    api_version: str | None = None


@router.post("/test-azure")
def test_app_azure(app_id: str, body: TestAzureRequest = TestAzureRequest()):
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    key = (body.key or "").strip() or app.get("azure_key", "")
    endpoint = ((body.endpoint if body.endpoint is not None else app.get("azure_endpoint", "")) or "").strip()
    deployment = ((body.deployment if body.deployment is not None else app.get("azure_deployment", "")) or "").strip()
    api_version = ((body.api_version if body.api_version is not None else app.get("azure_api_version", "")) or "").strip()
    if not key:
        raise HTTPException(400, "No Azure API key provided or saved")
    if not endpoint:
        raise HTTPException(400, "Azure endpoint is required (e.g. https://<resource>.openai.azure.com)")
    if not endpoint.startswith("http"):
        raise HTTPException(400, "Invalid endpoint — must start with http(s)://")
    if not deployment:
        raise HTTPException(400, "Azure deployment name is required")

    test_app = {
        **app, "azure_key": key, "azure_endpoint": endpoint,
        "azure_deployment": deployment, "azure_api_version": api_version,
    }
    try:
        client, model = _azure_client_and_model(app_id, _app_override=test_app)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say hello in exactly 3 words."}],
            **_openai_call_kwargs(model, 60, 0.0),
        )
        return {"ok": True, "response": resp.choices[0].message.content.strip()}
    except openai.AuthenticationError:
        raise HTTPException(401, "Invalid Azure API key")
    except openai.NotFoundError as exc:
        raise HTTPException(
            404,
            f"Deployment or endpoint not found. Verify the deployment name and api-version. ({exc})",
        )
    except Exception as exc:
        raise HTTPException(502, str(exc))
