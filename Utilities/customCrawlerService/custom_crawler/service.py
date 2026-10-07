"""FastAPI entrypoint for the custom crawler SDK.

Endpoints: GET /health, POST /crawl, profile capture, GET /ui.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .capture.manager import CaptureManager
from .capture.persist import profile_is_warmed
from .capture.proxy import proxy_vnc_http, proxy_vnc_ws
from .engine.xvfb import XvfbDisplay
from .job import CrawlJob
from .browser.fetch import fetch_page
from .browser.session import BrowserSession, profile_key_for_host, profile_key_for_url
from .obs.logging import log, setup_logger
from .settings import ServiceConfig, ensure_data_dirs

logger = setup_logger("custom_crawler.service")

_UI_DIR = Path(__file__).resolve().parent.parent / "ui"


class SubmitRequest(BaseModel):
    jobId: str = ""
    streamId: str = ""
    baseUrl: str
    # url | uploadUrl | uploadSitemap | crawl_retry | recrawl_page
    sourceType: str = "url"
    fileUrl: str = ""
    fileId: str = ""
    # Findly extraction source; required for crawl_retry (get-content-by-status).
    extractionSourceId: str = ""
    sourceId: str = ""
    # Explicit page list for recrawl_page (the caller already knows the URL).
    urls: List[str] = Field(default_factory=list)
    callbackUrl: str = ""
    completeUrl: str = ""
    callbackBatchSize: int = 10
    callbackMaxBytes: int = 1048576
    advanceSettings: Dict[str, Any] = Field(default_factory=dict)
    reqHeaders: Optional[List[Dict[str, Any]]] = None
    auth: Optional[Dict[str, Any]] = None


class CaptureUrlRequest(BaseModel):
    baseUrl: str


class CancelRequest(BaseModel):
    jobId: str


class ValidateUrlRequest(BaseModel):
    url: str


class AppState:
    def __init__(self) -> None:
        self.cfg = ServiceConfig()
        self.xvfb: Optional[XvfbDisplay] = None
        self.playwright: Any = None
        self.jobs: Dict[str, CrawlJob] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self.captures = CaptureManager(self.cfg)


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from playwright.async_api import async_playwright

    # Fail fast if profiles/spool are root-owned or otherwise unwritable — otherwise Chrome
    # starts, Cloudflare gets solved (or not), and cf_clearance never persists.
    profile_root, spool_dir = ensure_data_dirs(state.cfg)
    log(
        logger,
        logging.INFO,
        "data dirs ready",
        profileRoot=str(profile_root),
        spoolDir=str(spool_dir),
        uid=os.getuid(),
    )

    state.xvfb = XvfbDisplay(mode=state.cfg.xvfb_mode)
    display = state.xvfb.start()
    # Xvfb must be up before Playwright: the driver process inherits DISPLAY at spawn time.
    log(
        logger,
        logging.INFO,
        "service starting",
        display=display,
        xvfbMode=state.cfg.xvfb_mode,
        xvfbOwned=state.xvfb.owned,
        browserVisible=not state.xvfb.owned,
    )
    state._pw_ctx = async_playwright()
    state.playwright = await state._pw_ctx.__aenter__()
    state.captures.playwright = state.playwright
    try:
        yield
    finally:
        await state.captures.stop_all()
        for job in state.jobs.values():
            job.cancel()
        for task in state.tasks.values():
            task.cancel()
        try:
            await state._pw_ctx.__aexit__(None, None, None)
        except Exception:
            pass
        if state.xvfb:
            state.xvfb.stop()


app = FastAPI(title="customCrawlerService", lifespan=lifespan)


@app.get("/health")
async def health() -> Dict[str, Any]:
    active = {jid: job.status for jid, job in state.jobs.items()}
    return {
        "status": "ok",
        "activeJobs": sum(1 for s in active.values() if s == "running"),
        "jobs": active,
        "display": state.xvfb.display if state.xvfb else None,
        "xvfbMode": state.cfg.xvfb_mode,
        "xvfbOwned": state.xvfb.owned if state.xvfb else False,
        "browserVisible": not state.xvfb.owned if state.xvfb else True,
        "chromeChannel": state.cfg.chrome_channel,
        "profileRoot": state.cfg.profile_root,
        "spoolDir": state.cfg.spool_dir,
        "vncEnabled": state.cfg.vnc_enabled,
        "uid": os.getuid(),
    }


async def _run_job(job: CrawlJob) -> None:
    try:
        await job.run()
    finally:
        state.tasks.pop(job.job_id, None)


def _job_wants_profile(req: SubmitRequest) -> bool:
    if "useProfile" in (req.advanceSettings or {}):
        return bool(req.advanceSettings["useProfile"])
    return bool(state.cfg.use_profile)


@app.post("/crawl", status_code=202)
async def crawl(req: SubmitRequest) -> Dict[str, Any]:
    job_id = (req.jobId or "").strip() or f"ui-{int(time.time())}"
    if job_id in state.jobs and state.jobs[job_id].status == "running":
        raise HTTPException(status_code=409, detail="job already running")
    if _job_wants_profile(req):
        host = profile_key_for_url(req.baseUrl)
        if not profile_is_warmed(state.cfg.profile_root, host):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "profile_not_warmed",
                    "profileKey": host,
                    "message": "Capture a cleared Chrome profile before crawling with useProfile",
                },
            )
    req.jobId = job_id
    payload = req.model_dump()
    # Exact Findly → SDK submit body (secrets redacted by JsonFormatter).
    log(
        logger,
        logging.INFO,
        "crawl submit payload from Findly",
        jobId=req.jobId,
        payload=payload,
        sourceType=req.sourceType,
        maxUrlLimit=(payload.get("advanceSettings") or {}).get("maxUrlLimit"),
        crawlBeyondSitemaps=(payload.get("advanceSettings") or {}).get("crawlBeyondSitemaps"),
        useProfile=(payload.get("advanceSettings") or {}).get("useProfile"),
        crawlDepth=(payload.get("advanceSettings") or {}).get("crawlDepth"),
    )
    job = CrawlJob(submit=payload, service_cfg=state.cfg, playwright=state.playwright)
    state.jobs[req.jobId] = job
    task = asyncio.create_task(_run_job(job))
    state.tasks[req.jobId] = task
    log(
        logger,
        logging.INFO,
        "crawl accepted",
        jobId=req.jobId,
        baseUrl=req.baseUrl,
        sourceType=job.source_type,
        externalJobId=job.external_job_id,
        maxUrlLimit=job.max_url_limit,
        crawlBeyondSitemaps=job.engine.crawlBeyondSitemaps,
        useProfile=job.engine.useProfile,
    )
    return {"jobId": job.job_id, "externalJobId": job.external_job_id, "accepted": True}


@app.post("/crawl/cancel")
async def cancel(req: CancelRequest) -> Dict[str, Any]:
    job = state.jobs.get(req.jobId)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    job.cancel()
    log(logger, logging.INFO, "crawl cancel requested", jobId=req.jobId)
    return {"cancelled": True, "jobId": req.jobId}


@app.get("/crawl/{job_id}")
async def crawl_status(job_id: str) -> Dict[str, Any]:
    job = state.jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return job.status_doc()


@app.post("/validate-url")
async def validate_url(req: ValidateUrlRequest) -> Dict[str, Any]:
    """Open the URL in real Chrome and report reachability.

    Sitemap discovery is deliberately left to the crawl job: probing robots.txt and
    every common sitemap path costs minutes on a challenged host, and this endpoint
    is synchronous (Findly's client gives it 30s, the UI blocks its button on it).
    """
    session = BrowserSession(
        state.playwright,
        profile_root=state.cfg.profile_root,
        profile_key=profile_key_for_url(req.url),
        channel=state.cfg.chrome_channel,
        use_profile=False,
    )
    profile_warmed = session.warmed()
    cf_wait = float(state.cfg.challenge_wait_seconds)
    try:
        await session.start()
        result = await fetch_page(
            session.page,
            req.url,
            cf_wait=cf_wait,
            page_timeout_ms=state.cfg.page_timeout_ms,
        )
    finally:
        await session.close()

    reachable = result.status == "success" or (
        result.status_code is not None and result.status_code < 500
    )
    return {
        "reachable": reachable,
        "statusCode": result.status_code,
        "finalUrl": result.redirected_url or req.url,
        "contentType": result.content_type,
        "profileKey": session.profile_key,
        "profileWarmed": profile_warmed,
        "cloudflareBlocked": result.challenged,
        "error": result.error,
    }


@app.post("/profile/capture/start", status_code=202)
async def capture_start(req: CaptureUrlRequest) -> Dict[str, Any]:
    if not (req.baseUrl or "").strip():
        raise HTTPException(status_code=400, detail="baseUrl required")
    if not state.cfg.vnc_enabled:
        raise HTTPException(status_code=503, detail="VNC capture is disabled (CRAWLER_VNC_ENABLED)")
    try:
        return await state.captures.start(req.baseUrl.strip())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/profile/capture/complete")
async def capture_complete(req: CaptureUrlRequest) -> Dict[str, Any]:
    if not (req.baseUrl or "").strip():
        raise HTTPException(status_code=400, detail="baseUrl required")
    result = await state.captures.complete(req.baseUrl.strip())
    if not result.get("ok"):
        code = 404 if result.get("error") == "no_capture" else 409
        raise HTTPException(status_code=code, detail=result)
    return result


@app.post("/profile/capture/cancel")
async def capture_cancel(req: CaptureUrlRequest) -> Dict[str, Any]:
    if not (req.baseUrl or "").strip():
        raise HTTPException(status_code=400, detail="baseUrl required")
    return await state.captures.cancel(req.baseUrl.strip())


@app.get("/profile/{host}")
async def profile_status(host: str) -> Dict[str, Any]:
    key = profile_key_for_host(host)
    return state.captures.status(key)


@app.get("/ui")
@app.get("/ui/")
async def ui_index() -> FileResponse:
    index = _UI_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="ui not packaged")
    return FileResponse(index)


@app.websocket("/vnc-proxy/{token}/{ws_port}/websockify")
async def vnc_ws_proxy(websocket: WebSocket, token: str, ws_port: int) -> None:
    await proxy_vnc_ws(websocket, token, ws_port, state.captures)


@app.api_route("/vnc-proxy/{token}/{ws_port}", methods=["GET", "HEAD"])
@app.api_route("/vnc-proxy/{token}/{ws_port}/{path:path}", methods=["GET", "HEAD"])
async def vnc_http_proxy(
    request: Request, token: str, ws_port: int, path: str = ""
) -> Any:
    return await proxy_vnc_http(request, token, ws_port, path, state.captures)


def main() -> None:
    import uvicorn

    from .settings import load_env

    load_env()
    uvicorn.run(
        "custom_crawler.service:app",
        host="0.0.0.0",
        port=state.cfg.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
