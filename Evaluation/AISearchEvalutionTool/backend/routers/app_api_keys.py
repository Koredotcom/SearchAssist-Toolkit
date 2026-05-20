from __future__ import annotations

import anthropic
import openai
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.database import get_app, update_app
from agents.llm_client import _openai_client_and_model, _openai_call_kwargs, _parse_azure_endpoint

router = APIRouter(prefix="/apps/{app_id}/api-keys", tags=["app-api-keys"])


class AppApiKeyUpdate(BaseModel):
    anthropic_key: str | None = None
    anthropic_base_url: str | None = None
    openai_key: str | None = None
    openai_base_url: str | None = None
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
    return {
        "anthropic_key_set": bool(ant_key),
        "anthropic_key_preview": _mask(ant_key),
        "anthropic_base_url": app.get("anthropic_base_url", "") or "",
        "openai_key_set": bool(oai_key),
        "openai_key_preview": _mask(oai_key),
        "openai_base_url": app.get("openai_base_url", "") or "",
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
    if azure and not azure.get("deployment"):
        raise HTTPException(
            400,
            "Azure URL is missing the deployment path. Use the full chat-completions URL.",
        )

    # Build a temporary app dict so _openai_client_and_model picks up the test key/url
    test_app = {**app, "openai_key": key}
    if base_url:
        test_app["openai_base_url"] = base_url
    client, effective_model = _openai_client_and_model(test_app["app_id"], "gpt-4.1-mini", _app_override=test_app)
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
