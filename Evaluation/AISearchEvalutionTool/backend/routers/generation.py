from fastapi import APIRouter, BackgroundTasks, HTTPException
from models import GenerationRequest, JobResponse
from db.database import create_job, get_app, get_job, list_jobs, freeze_golden_set, request_stop_job
from pipeline.generate import run_generation

router = APIRouter(prefix="/apps/{app_id}/generation", tags=["generation"])


@router.post("/start", response_model=JobResponse, status_code=202)
def start_generation(app_id: str, body: GenerationRequest, bg: BackgroundTasks):
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    job_id = create_job(app_id, "generation")
    bg.add_task(
        run_generation,
        app=app,
        golden_set_version=body.golden_set_version,
        connector_ids=body.connector_ids,
        web_source_ids=body.web_source_ids,
        file_source_ids=body.file_source_ids,
        max_docs_per_source=body.max_docs_per_source,
        max_questions_per_doc=body.max_questions_per_doc,
        filters=body.filters,
        job_id=job_id,
    )
    return get_job(job_id)


@router.post("/freeze/{version}", status_code=200)
def freeze(app_id: str, version: str):
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    freeze_golden_set(app_id, version)
    return {"message": f"Golden set {version} frozen."}


@router.get("/jobs", response_model=list[JobResponse])
def get_jobs(app_id: str):
    return [j for j in list_jobs(app_id) if j["job_type"] == "generation"]


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_status(app_id: str, job_id: str):
    job = get_job(job_id)
    if not job or job["app_id"] != app_id:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/jobs/{job_id}/stop", status_code=200)
def stop_job(app_id: str, job_id: str):
    job = get_job(job_id)
    if not job or job["app_id"] != app_id:
        raise HTTPException(404, "Job not found")
    if job["status"] != "running":
        raise HTTPException(400, "Job is not running")
    request_stop_job(job_id)
    return {"message": "Stop requested. Generation will pause after the current document."}
