from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from models import EvaluationRequest, FilterPromptTestRequest, MapperTestRequest, JobResponse
from db.database import (
    create_job, get_app, get_job, list_jobs, request_stop_job, get_active_prompt,
    get_evaluate_settings, upsert_evaluate_settings,
)
from pipeline.evaluate import exec_filter_script, run_evaluation

router = APIRouter(prefix="/apps/{app_id}/evaluation", tags=["evaluation"])


class EvaluateSettingsBody(BaseModel):
    settings: dict[str, Any]


@router.get("/settings")
def get_settings(app_id: str):
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    row = get_evaluate_settings(app_id)
    if not row:
        return {"settings": None, "updated_at": None}
    return row


@router.put("/settings")
def put_settings(app_id: str, body: EvaluateSettingsBody):
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    upsert_evaluate_settings(app_id, body.settings)
    return {"ok": True}


@router.post("/start", response_model=JobResponse, status_code=202)
def start_evaluation(app_id: str, body: EvaluationRequest, bg: BackgroundTasks):
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    job_id = create_job(app_id, "evaluation")
    bg.add_task(
        run_evaluation,
        app=app,
        golden_set_version=body.golden_set_version,
        rag_version=body.rag_version,
        max_cases=body.max_cases,
        sample_mode=body.sample_mode,
        filter_mode=body.filter_mode,
        filter_prompt=body.filter_prompt,
        filter_fields=body.filter_fields,
        enable_racl=body.enable_racl,
        user_email=body.user_email,
        answer_mode_override=body.answer_mode_override,
        question_types=body.question_types,
        judge_mode=body.judge_mode,
        case1_threshold=body.case1_threshold,
        case2_threshold=body.case2_threshold,
        top_k_pass=body.top_k_pass,
        chunk_scoring_mode=body.chunk_scoring_mode,
        job_id=job_id,
    )
    return get_job(job_id)


@router.get("/jobs", response_model=list[JobResponse])
def get_jobs(app_id: str):
    return [j for j in list_jobs(app_id) if j["job_type"] == "evaluation"]


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_status(app_id: str, job_id: str):
    job = get_job(job_id)
    if not job or job["app_id"] != app_id:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/test-filter-prompt")
def test_filter_prompt(app_id: str, body: FilterPromptTestRequest):
    """Run a question through the Filter Generator prompt and return the raw LLM response."""
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    try:
        from agents.llm_client import call_llm_json
        from agents.prompts import FILTER_GENERATOR_PROMPT

        if body.prompt_text is not None:
            system_prompt = body.prompt_text
        else:
            row = get_active_prompt(app_id, "filter_generator")
            system_prompt = row["prompt_text"] if row else FILTER_GENERATOR_PROMPT

        raw = call_llm_json(app_id, "filter_generator", system_prompt, f"Question: {body.question}")
        return {"raw_response": raw, "error": None}
    except Exception as exc:
        return {"raw_response": None, "error": str(exc)}


@router.post("/test-mapper")
def test_mapper(app_id: str, body: MapperTestRequest):
    """Test a response mapper script against a sample LLM response string."""
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    try:
        result = exec_filter_script(
            body.script, body.lang, input_text=body.llm_response,
            py_func_names=("map_response", "get_filters"),
            js_func_names=("mapResponse", "getFilters"),
        )
        return {"output": result, "error": None}
    except Exception as exc:
        return {"output": None, "error": str(exc)}


@router.post("/jobs/{job_id}/stop", status_code=200)
def stop_job(app_id: str, job_id: str):
    job = get_job(job_id)
    if not job or job["app_id"] != app_id:
        raise HTTPException(404, "Job not found")
    if job["status"] != "running":
        raise HTTPException(400, "Job is not running")
    request_stop_job(job_id)
    return {"ok": True}
