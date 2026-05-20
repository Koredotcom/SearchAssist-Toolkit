from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
import uuid


# ── App Config ──────────────────────────────────────────────────────────────

ANSWER_MODES = {"answer_generation", "extract_only"}


class AppConfigCreate(BaseModel):
    name: str
    host_url: str
    bot_id: str
    stream_id: str | None = None
    client_id: str
    client_secret: str
    racl_entity_ids: list[str] = []
    banned_topics: list[str] = []
    answer_mode: str = "answer_generation"


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


# ── LLM Config ──────────────────────────────────────────────────────────────

class LLMConfigUpdate(BaseModel):
    model: str
    temperature: float = Field(ge=0.0, le=2.0)
    max_tokens: int = Field(gt=0, le=32000)


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
    source_id: str            # extractionSourceId — top-level source metadata
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
    target_language: str = Field(default="English", min_length=1, max_length=80)
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
        pattern="^(none|field_filters|custom_prompt)$",
        description="'none' = no filters, 'field_filters' = use test-case column values as metaFilters, 'custom_prompt' = LLM generates filters per question",
    )
    filter_prompt: str | None = Field(default=None, description="Unused — prompt is read from DB (Prompts & Models page)")
    filter_fields: list[str] | None = Field(
        default=None,
        description="Field names to use when filter_mode='field_filters'. Values are read from each test case's generation_metadata / custom_fields.",
    )
    enable_racl: bool = Field(default=False, description="If true, send user_email as customData.userContext.userId")
    user_email: str | None = Field(default=None, description="RACL user identifier (required when enable_racl=true)")

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

    # ── Per-run verdict configuration overrides ───────────────────────────
    judge_mode: str = Field(
        default="auto",
        pattern="^(auto|force_on|force_off)$",
        description=(
            "'auto' = use the LLM judge if its API key is configured, else "
            "fall back to semantic similarity. 'force_on' = require the judge "
            "(fail if not configured). 'force_off' = skip the judge, use "
            "semantic similarity only."
        ),
    )
    case1_threshold: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="Override Q↔Answer relevance pass threshold for Cases 1 & 3 (no-judge fallback). None = use app setting.",
    )
    case2_threshold: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="Override Answer↔Expected similarity pass threshold for Cases 2 & 4 (no-judge fallback). None = use app setting.",
    )
    top_k_pass: int | None = Field(
        default=None, ge=1, le=100,
        description="Override the top-K chunk pass threshold used in extract_only retrieval verdicts. None = default (5).",
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
    human_validated: bool
    status: str
    decision: str | None
    primary_concern: str | None = None
    rationale: str | None = None
    case_id: int | None = None
    custom_fields: dict[str, Any] = {}
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
    pass_rate: float
    avg_chunk_rank: float | None = None


class DocLabel(BaseModel):
    """Compact per-document label info derived from chunk_signals."""
    title: str | None = None
    url: str | None = None


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
    search_response: dict[str, Any] | None = None
    # 4-case evaluation fields
    case_id: int | None = None
    expected_doc_rank: int | None = None
    recall_at_k: dict[str, int] = {}
    answer_similarity: float | None = None
    verdict: str | None = None
    verdict_source: str | None = None
