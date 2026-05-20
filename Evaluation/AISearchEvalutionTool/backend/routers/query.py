from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.database import get_app
from koreai.search import query_rag

router = APIRouter(prefix="/apps/{app_id}", tags=["query"])


class QueryRequest(BaseModel):
    question: str
    meta_filters: list[dict] = []
    user_email: str | None = None
    answer_mode_override: str | None = None


@router.post("/query")
def run_live_query(app_id: str, body: QueryRequest):
    app = get_app(app_id)
    if not app:
        raise HTTPException(404, "App not found")
    if body.answer_mode_override:
        app = {**app, "answer_mode": body.answer_mode_override}
    result = query_rag(
        app, body.question,
        meta_filters=body.meta_filters or [],
        user_email=body.user_email,
    )
    return {
        "answer": result["answer"],
        "is_valid_answer": result["is_valid_answer"],
        "cited_doc_ids": result["cited_doc_ids"],
        "result_doc_ids": result["result_doc_ids"],
        "answer_mode": result["answer_mode"],
        "latency_llm_ms": result.get("latency_llm_ms"),
        "latency_retrieval_ms": result.get("latency_retrieval_ms"),
    }
