from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from db.database import (
    create_job, create_perf_run, delete_perf_run, get_app, get_job,
    get_perf_results, get_perf_run, list_jobs, list_perf_runs, request_stop_job,
)
from models import JobResponse
from pipeline.perf_test import run_perf_test


router = APIRouter(prefix="/apps/{app_id}/perf-test", tags=["perf-test"])


class PerfTestStartRequest(BaseModel):
    golden_set_version: str
    concurrency: int = Field(default=5, ge=1, le=200)
    stop_mode: Literal["iterations", "duration"] = "iterations"
    iterations: int | None = Field(default=None, ge=1, le=100000)
    duration_s: int | None = Field(default=None, ge=1, le=3600)
    ramp_up_s: int = Field(default=0, ge=0, le=600)


@router.post("/start", status_code=202)
def start_perf_test(app_id: str, body: PerfTestStartRequest, bg: BackgroundTasks) -> dict[str, Any]:
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    if body.stop_mode == "iterations" and not body.iterations:
        raise HTTPException(400, "iterations is required when stop_mode='iterations'")
    if body.stop_mode == "duration" and not body.duration_s:
        raise HTTPException(400, "duration_s is required when stop_mode='duration'")

    # Pre-create the run synchronously so the frontend can navigate to its
    # detail page immediately and poll for live progress.
    run_id = f"perf-{uuid.uuid4()}"
    create_perf_run({
        "run_id": run_id,
        "app_id": app_id,
        "golden_set_version": body.golden_set_version,
        "concurrency": body.concurrency,
        "stop_mode": body.stop_mode,
        "iterations": body.iterations,
        "duration_s": body.duration_s,
        "ramp_up_s": body.ramp_up_s,
    })

    job_id = create_job(app_id, "perf_test")
    bg.add_task(
        run_perf_test,
        app=app,
        golden_set_version=body.golden_set_version,
        concurrency=body.concurrency,
        stop_mode=body.stop_mode,
        iterations=body.iterations,
        duration_s=body.duration_s,
        ramp_up_s=body.ramp_up_s,
        job_id=job_id,
        run_id=run_id,
    )
    job = get_job(job_id)
    return {**(job or {}), "run_id": run_id}


@router.get("/jobs", response_model=list[JobResponse])
def list_perf_jobs(app_id: str):
    return [j for j in list_jobs(app_id) if j["job_type"] == "perf_test"]


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_perf_job(app_id: str, job_id: str):
    job = get_job(job_id)
    if not job or job["app_id"] != app_id:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/jobs/{job_id}/stop", status_code=200)
def stop_perf_job(app_id: str, job_id: str):
    job = get_job(job_id)
    if not job or job["app_id"] != app_id:
        raise HTTPException(404, "Job not found")
    if job["status"] != "running":
        raise HTTPException(400, "Job is not running")
    request_stop_job(job_id)
    return {"ok": True}


@router.get("/runs")
def list_runs(app_id: str):
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    return list_perf_runs(app_id)


@router.get("/runs/{run_id}")
def get_run(app_id: str, run_id: str):
    run = get_perf_run(run_id)
    if not run or run.get("app_id") != app_id:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/runs/{run_id}/results")
def get_run_results(app_id: str, run_id: str, limit: int = 500, offset: int = 0):
    run = get_perf_run(run_id)
    if not run or run.get("app_id") != app_id:
        raise HTTPException(404, "Run not found")
    return {
        "run_id": run_id,
        "results": get_perf_results(run_id, limit=limit, offset=offset),
        "limit": limit, "offset": offset,
    }


@router.delete("/runs/{run_id}")
def delete_run(app_id: str, run_id: str):
    if not delete_perf_run(app_id, run_id):
        raise HTTPException(404, "Run not found")
    return {"ok": True, "run_id": run_id}
