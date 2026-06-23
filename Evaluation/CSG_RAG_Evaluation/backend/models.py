from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
import uuid


# ── App Config ──────────────────────────────────────────────────────────────

ANSWER_MODES = {"answer_generation", "extract_only"}


class AppConfigCreate(BaseModel):
    name: str
    host_url: str = ""
    bot_id: str = ""
    stream_id: str | None = None
    client_id: str = ""
    client_secret: str = ""
    racl_entity_ids: list[str] = []
    banned_topics: list[str] = []
    answer_mode: str = "answer_generation"
    # New Kore.ai Agent Platform fields
    process_id: str = ""
    cf_version_id: str = ""
    x_api_key: str = ""
    identity: str = ""


class AppConfigUpdate(BaseModel):
    name: str | None = None
    host_url: str | None = None
    bot_id: str | None = None
    stream_id: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    racl_entity_ids: list[str] | None = None
    banned_topics: list[str] | None = None
    answer_mode: str | None = None
    is_active: bool | None = None
    # New Kore.ai Agent Platform fields
    process_id: str | None = None
    cf_version_id: str | None = None
    x_api_key: str | None = None
    identity: str | None = None


class AppConfigResponse(BaseModel):
    app_id: str
    name: str
    host_url: str
    bot_id: str
    stream_id: str | None
    client_id: str
    racl_entity_ids: list[str]
    banned_topics: list[str] = []
    answer_mode: str = "answer_generation"
    is_active: bool
    created_at: str
    updated_at: str
    # New Kore.ai Agent Platform fields
    process_id: str = ""
    cf_version_id: str = ""
    x_api_key_preview: str = ""  # last-4 mask of x_api_key, never the full key
    identity: str = ""


# ── LLM Config ──────────────────────────────────────────────────────────────

class LLMConfigUpdate(BaseModel):
    model: str
    temperature: float = Field(ge=0.0, le=2.0)
    max_tokens: int = Field(gt=0, le=16000)


class LLMConfigResponse(BaseModel):
    app_id: str
    agent_name: str
    model: str
    temperature: float
    max_tokens: int
    updated_at: str


# ── Prompt Config ────────────────────────────────────────────────────────────

class PromptConfigCreate(BaseModel):
    agent_name: str
    prompt_text: str


class PromptConfigResponse(BaseModel):
    id: str
    app_id: str
    agent_name: str
    prompt_text: str
    version: int
    is_active: bool
    created_at: str


# ── Sources ──────────────────────────────────────────────────────────────────

class SourceResponse(BaseModel):
    connector_id: str
    name: str
    type: str
    is_active: bool
    records_count: int
    size: int


class ContentSourceResponse(BaseModel):
    """A parent source container derived by aggregating content-by-cond.

    Used for Websites (sys_content_type=web) and Documents (sys_content_type=file),
    which Kore.ai's public API does not expose via a dedicated listing endpoint.
    """
    source_id: str            # extractionSourceId — the parent container
    name: str                 # sys_source_name (falls back to URL or source_id)
    sys_content_type: str     # echoed for the UI badge ("web" | "file")
    records_count: int        # docs observed in this source
    sample_url: str = ""      # first non-empty url we saw
    base_url: str = ""        # first non-empty base_url we saw


# ── Generation ───────────────────────────────────────────────────────────────

class GenerationRequest(BaseModel):
    golden_set_version: str
    # Empty connector_ids means "all connectors" (back-compat). web/file source
    # lists default to empty — opt-in, since users may want connectors only.
    connector_ids: list[str] = []
    web_source_ids: list[str] = []      # extractionSourceId for sys_content_type=web crawls
    file_source_ids: list[str] = []     # extractionSourceId for sys_content_type=file uploads
    max_docs_per_source: int = Field(default=10, ge=0, description="Max docs per source. 0 = all documents (no cap).")
    max_questions_per_doc: int = Field(default=5, ge=1, le=5)
    filters: dict[str, Any] = {}


# ── Evaluation ───────────────────────────────────────────────────────────────

class EvaluationRequest(BaseModel):
    golden_set_version: str
    rag_version: str = "unknown"
    max_cases: int | None = Field(default=None, ge=1, description="Limit number of cases to evaluate. None = all cases.")
    sample_mode: str = Field(default="first", pattern="^(first|random)$", description="'first' = top N by insertion order, 'random' = random sample")

    # ── Meta-filter / RACL controls ──────────────────────────────────────
    filter_mode: str = Field(
        default="none",
        pattern="^(none|auto_source|custom_prompt)$",
        description="'none' = no filters, 'auto_source' = derive sys_content_type from each TC's reference doc, 'custom_prompt' = LLM generates filters per question (mapper script loaded from DB if configured)",
    )
    filter_prompt: str | None = Field(default=None, description="Unused — prompt is read from DB (Prompts & Models page)")
    enable_racl: bool = Field(default=False, description="If true, override the identity for RACL-filtered queries")
    user_email: str | None = Field(default=None, description="RACL identity override (sent as input.identity). Falls back to app default identity.")
    identity: str | None = Field(default=None, description="Alias for user_email — RACL identity for the Agent Platform API")

    # ── Question type filter ──────────────────────────────────────────────
    question_types: list[str] | None = Field(
        default=None,
        description="Limit evaluation to these question types. None = all types.",
    )

    # ── Answer config override ────────────────────────────────────────────
    answer_mode_override: str | None = Field(
        default=None,
        pattern="^(answer_generation|extract_only)$",
        description="Override the app's answer_mode for this run. None = use app default.",
    )

    # ── Per-run RACL override ─────────────────────────────────────────────
    racl_entity_ids_override: list[str] | None = Field(
        default=None,
        description="Override the app's RACL entity IDs for this run. None = use app default.",
    )


class MapperTestRequest(BaseModel):
    script: str
    lang: str = Field(pattern="^(python|js)$")
    llm_response: str


class FilterPromptTestRequest(BaseModel):
    question: str
    prompt_text: str | None = None


# ── Jobs ─────────────────────────────────────────────────────────────────────

class JobResponse(BaseModel):
    job_id: str
    app_id: str
    job_type: str
    status: str
    progress: int
    result: dict[str, Any] | None
    error: str | None
    created_at: str
    updated_at: str


# ── Golden Sets ──────────────────────────────────────────────────────────────

class GoldenSetResponse(BaseModel):
    version: str
    app_id: str
    created_at: str
    frozen_at: str | None
    notes: str | None
    total_cases: int
    kept_cases: int
    borderline_cases: int


class TestCaseResponse(BaseModel):
    tc_id: str
    question: str
    expected_answer: str | None
    expected_behavior: str
    question_type: str | None
    difficulty: int | None
    reference_doc_ids: list[str]
    reference_match_spec: list[dict[str, Any]]
    human_validated: bool
    status: str
    decision: str | None
    scores: dict[str, Any] | None


# ── Results ──────────────────────────────────────────────────────────────────

class EvalRunResponse(BaseModel):
    run_id: str
    app_id: str
    started_at: str
    finished_at: str | None
    rag_version: str
    judge_model: str | None
    golden_set_version: str
    trigger: str
    status: str
    total_cases: int
    passed_cases: int
    done_cases: int = 0  # live count of completed eval_result rows (useful during running)
    pass_rate: float
    avg_chunk_rank: float | None = None
    identity: str = ""
    racl_entity_ids: list[str] = []
    answer_mode: str = ""


class EvalResultResponse(BaseModel):
    tc_id: str
    question: str
    expected_answer: str | None
    expected_behavior: str
    question_type: str | None
    rag_response: str | None
    retrieved_doc_ids: list[str]
    reference_doc_ids: list[str] = []
    scores: dict[str, Any]
    passed: bool
    failure_category: str | None
    judge_rationale: str | None
    latency_llm_ms: float | None
    latency_retrieval_ms: float | None
    doc_retrieved: bool
    search_payload: dict[str, Any] | None = None
    # 4-case evaluation fields
    case_id: int | None = None
    expected_doc_rank: int | None = None
    recall_at_k: dict[str, int] = {}
    answer_similarity: float | None = None
    verdict: str | None = None
    verdict_source: str | None = None
    chunk_signals: list[dict[str, Any]] = []
