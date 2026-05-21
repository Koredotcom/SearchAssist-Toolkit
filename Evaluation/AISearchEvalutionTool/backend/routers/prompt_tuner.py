"""Prompt Fine-Tuner — produces a revised system prompt from real failure samples.

Workflow (frontend):
  1. Pick an agent (which prompt to improve).
  2. Pick an evaluation run that has failed cases.
  3. The UI shows the active prompt + a sample of failed (question / expected / generated) trios.
  4. User clicks "Generate improved prompt" → POST /finetune.
  5. Backend asks the configured LLM to rewrite the prompt around those failures.
  6. UI shows the diff; user can save the result as a new prompt version
     (via the existing PUT /apps/{app_id}/prompts/{agent_name} endpoint).

The router intentionally does NOT persist the new prompt — the user must
explicitly confirm and save through the existing prompts endpoint. This keeps
the regular prompt-edit history and version semantics intact.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.llm_client import call_llm_json, parse_json_loose
from agents.prompts import DEFAULT_PROMPTS, PROMPT_TUNER_PROMPT
from db.database import (
    get_active_prompt, get_api_key, get_app, get_eval_results, get_eval_run,
    get_llm_config, list_eval_runs,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/apps/{app_id}/prompt-tuner", tags=["prompt-tuner"])

TUNABLE_AGENTS = {
    "agent1", "agent2", "agent3", "judge",
    "filter_generator", "insights", "answer_generator",
}

# Friendly descriptions surfaced to the LLM so it knows what the prompt is for.
AGENT_ROLES = {
    "agent1":           "Document analyst — extracts distinctive, content-specific facts from a single document so a retriever can later match questions back to it.",
    "agent2":           "Test-case generator — writes search-engine-style Q&A pairs that can ONLY be answered using the given document.",
    "agent3":           "Test-case quality auditor — scores generated Q&A pairs on a 6-dimensional rubric and decides KEEP / BORDERLINE / DROP.",
    "judge":            "RAG response judge — scores a RAG system's answer vs. the expected answer across groundedness, relevance, completeness, safety, etc.",
    "filter_generator": "Search filter generator — converts a user question into Kore.ai Advance Search metaFilter groups.",
    "insights":         "Run-level analyst — writes a markdown report explaining what's going right / wrong in one evaluation run.",
    "answer_generator": "Answer generator — given a question and retrieved CONTEXT chunks, produces the final grounded answer the RAG system serves to the user. This is the prompt whose failures show up as 'generated_answer' in the evaluation results.",
}

MAX_FAILURE_SAMPLES = 20
TRUNC_QUESTION = 240
TRUNC_EXPECTED = 400
TRUNC_GENERATED = 500
TRUNC_RATIONALE = 300


# ── Schemas ─────────────────────────────────────────────────────────────────


class FailureSample(BaseModel):
    tc_id: str
    question: str
    expected_answer: str | None = None
    generated_answer: str | None = None
    failure_category: str | None = None
    judge_rationale: str | None = None
    expected_doc_rank: int | None = None
    question_type: str | None = None
    case_id: int | None = None


class FailuresResponse(BaseModel):
    run_id: str
    agent_name: str
    total_failures: int
    returned: int
    failures: list[FailureSample]


class FineTuneRequest(BaseModel):
    agent_name: str = Field(..., description="Which agent's prompt to fine-tune")
    current_prompt: str | None = Field(
        default=None,
        description="Existing prompt to improve. If omitted, the app's active prompt for this agent is used.",
    )
    run_id: str | None = Field(
        default=None,
        description="Evaluation run to pull failures from. If omitted, supply failures explicitly.",
    )
    failures: list[FailureSample] | None = Field(
        default=None,
        description="Optional explicit list of failure samples (overrides run-derived sampling).",
    )
    max_samples: int = Field(
        default=10, ge=1, le=MAX_FAILURE_SAMPLES,
        description="Cap on how many failures to send to the LLM.",
    )
    user_notes: str | None = Field(
        default=None,
        description="Optional free-form guidance (e.g. 'be stricter on hallucination', 'shorter answers').",
    )


class FineTuneResponse(BaseModel):
    agent_name: str
    model: str
    llm_slot: str | None = None
    current_prompt: str
    improved_prompt: str
    summary_of_changes: str
    failure_patterns: list[str]
    samples_used: int
    raw_response: str


# ── Helpers ─────────────────────────────────────────────────────────────────


def _truncate(text: str | None, limit: int) -> str:
    if not text:
        return ""
    text = str(text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _resolve_current_prompt(app_id: str, agent_name: str, override: str | None) -> str:
    """Pick the prompt to improve. Prefer the explicit override, then the active row, then the default."""
    if override is not None and override.strip():
        return override
    row = get_active_prompt(app_id, agent_name)
    if row and row.get("prompt_text"):
        return row["prompt_text"]
    default = DEFAULT_PROMPTS.get(agent_name)
    if not default:
        raise HTTPException(
            404,
            f"No active or default prompt found for agent '{agent_name}'. "
            "Set a prompt first on the Prompts & Models page.",
        )
    return default


def _failed_rows_from_run(run_id: str) -> list[dict]:
    """Return rows from the run that look like failures (verdict=fail OR passed=False)."""
    rows = get_eval_results(run_id)
    fails: list[dict] = []
    for r in rows:
        verdict = r.get("verdict")
        if verdict == "fail":
            fails.append(r)
        elif verdict not in ("pass", "fail"):
            # No verdict — only treat as a failure if the judge clearly disliked it.
            scores = r.get("scores") or {}
            judge_red_flags = (
                scores.get("toxicity_detected") or scores.get("bias_detected")
                or scores.get("banned_topic_violation")
            )
            if judge_red_flags:
                fails.append(r)
    return fails


def _row_to_sample(r: dict) -> FailureSample:
    scores = r.get("scores") or {}
    return FailureSample(
        tc_id=str(r.get("tc_id") or ""),
        question=_truncate(r.get("question"), TRUNC_QUESTION),
        expected_answer=_truncate(r.get("expected_answer"), TRUNC_EXPECTED) or None,
        generated_answer=_truncate(r.get("rag_response"), TRUNC_GENERATED) or None,
        failure_category=r.get("failure_category"),
        judge_rationale=_truncate(r.get("judge_rationale"), TRUNC_RATIONALE) or None,
        expected_doc_rank=r.get("expected_doc_rank"),
        question_type=r.get("question_type"),
        case_id=r.get("case_id"),
    )


def _infer_provider(model: str) -> str:
    """Same logic the LLM client uses — picks the right key by model prefix."""
    name = (model or "").lower()
    if name.startswith("claude"):
        return "anthropic"
    if name.startswith("gemini") or name.startswith("models/gemini"):
        return "gemini"
    return "openai"


def _available_providers(app_id: str) -> set[str]:
    """Return the set of provider keys that are currently stored for this app."""
    out: set[str] = set()
    for provider in ("openai", "anthropic", "gemini"):
        if (get_api_key(app_id, provider) or "").strip():
            out.add(provider)
    return out


def _pick_llm_slot(
    app_id: str, target_agent: str, providers: set[str],
) -> tuple[str | None, dict]:
    """Choose which agent's LLM config to drive the tuner with.

    Preference order:
      1. The target agent's own slot (most predictable for the user).
      2. The 'insights' slot — heavy-reasoning workhorse.
      3. Any other tunable agent whose model maps to a configured provider.
    Returns ``(slot_name, cfg)`` or ``(None, {})`` when nothing fits.
    """
    preference: list[str] = [target_agent]
    if "insights" not in preference:
        preference.append("insights")
    for name in sorted(TUNABLE_AGENTS):
        if name not in preference:
            preference.append(name)

    for slot in preference:
        try:
            cfg = get_llm_config(app_id, slot)
        except Exception:
            continue
        model = (cfg or {}).get("model") or ""
        if not model:
            continue
        if _infer_provider(model) in providers:
            return slot, cfg
    return None, {}


def _humanise_llm_error(exc: Exception, *, model: str, llm_slot: str) -> tuple[str, int]:
    """Turn raw provider errors into a short, actionable message + HTTP status."""
    try:
        import openai
        if isinstance(exc, openai.AuthenticationError):
            return (
                f"The LLM provider rejected the API key for model '{model}' "
                f"(agent slot '{llm_slot}'). Open the API Keys page, save a "
                f"valid key for that provider, then retry.",
                401,
            )
        if isinstance(exc, openai.PermissionDeniedError):
            return (
                f"The API key for model '{model}' does not have access to that "
                f"model. Check the key's permissions or switch to a model the "
                f"key can use on the Prompts & Models page.",
                403,
            )
        if isinstance(exc, openai.RateLimitError):
            return (
                f"Rate-limited by the LLM provider while tuning with '{model}'. "
                f"Wait a moment and try again, or pick a different model.",
                429,
            )
    except ImportError:
        pass
    try:
        import anthropic
        if isinstance(exc, anthropic.AuthenticationError):
            return (
                f"Invalid Anthropic API key for model '{model}'. Set a working "
                f"key on the API Keys page and retry.",
                401,
            )
    except ImportError:
        pass

    # Default: keep the message short so the frontend can render it cleanly.
    detail = str(exc)
    if len(detail) > 400:
        detail = detail[:400] + "…"
    return (f"LLM call failed ({model}): {detail}", 502)


def _rank_failures(rows: list[dict]) -> list[dict]:
    """Order failures so the LLM sees the most informative ones first.

    Priority:
      1. Rows where both expected_answer and rag_response are non-empty
         (these give the clearest signal of where the prompt diverges).
      2. Rows with a judge_rationale (explains *why* it failed).
      3. Rows with a specific failure_category that isn't 'none'.
      4. Everything else.
    """
    def key(r: dict) -> tuple:
        has_pair = bool((r.get("expected_answer") or "").strip()) and bool((r.get("rag_response") or "").strip())
        has_rationale = bool((r.get("judge_rationale") or "").strip())
        has_category = bool((r.get("failure_category") or "").strip()) and r.get("failure_category") != "none"
        # Lower tuple sorts first — invert booleans
        return (not has_pair, not has_rationale, not has_category)

    return sorted(rows, key=key)


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/agents")
def list_tunable_agents(app_id: str) -> dict[str, Any]:
    """Return the agents that have tunable prompts, with their role descriptions."""
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    return {
        "agents": [
            {"agent_name": name, "description": AGENT_ROLES.get(name, "")}
            for name in sorted(TUNABLE_AGENTS)
        ]
    }


@router.get("/runs")
def list_runs_with_failures(app_id: str) -> dict[str, Any]:
    """List completed runs along with a failure_count, sorted by most recent first."""
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    runs = list_eval_runs(app_id)
    out = []
    for r in runs:
        total = r.get("total_cases") or 0
        passed = r.get("passed_cases") or 0
        verdicted = r.get("verdicted_cases") or 0
        # Best-effort failure count: prefer (verdicted - passed), fall back to (total - passed).
        if verdicted:
            failed = max(verdicted - passed, 0)
        else:
            failed = max(total - passed, 0)
        out.append({
            "run_id": r.get("run_id"),
            "started_at": r.get("started_at"),
            "finished_at": r.get("finished_at"),
            "status": r.get("status"),
            "golden_set_version": r.get("golden_set_version"),
            "rag_version": r.get("rag_version"),
            "total_cases": total,
            "failure_count": failed,
        })
    return {"runs": out}


@router.get("/runs/{run_id}/failures", response_model=FailuresResponse)
def get_run_failures(
    app_id: str,
    run_id: str,
    agent_name: str,
    limit: int = 20,
) -> FailuresResponse:
    """Return a ranked list of failure samples (Q + expected + generated) for the run.

    The agent_name is accepted for parity with the fine-tune endpoint but
    currently doesn't filter the rows — every agent reuses the same RAG
    failure trace. Future versions could attach per-agent metadata.
    """
    if agent_name not in TUNABLE_AGENTS:
        raise HTTPException(400, f"agent_name must be one of {sorted(TUNABLE_AGENTS)}")
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    run = get_eval_run(run_id)
    if not run or run.get("app_id") != app_id:
        raise HTTPException(404, "Run not found")

    fails = _failed_rows_from_run(run_id)
    ranked = _rank_failures(fails)
    limit = max(1, min(limit, MAX_FAILURE_SAMPLES))
    samples = [_row_to_sample(r) for r in ranked[:limit]]
    return FailuresResponse(
        run_id=run_id,
        agent_name=agent_name,
        total_failures=len(fails),
        returned=len(samples),
        failures=samples,
    )


@router.post("/finetune", response_model=FineTuneResponse)
def finetune_prompt(app_id: str, body: FineTuneRequest) -> FineTuneResponse:
    """Generate an improved prompt by feeding the current prompt + real failures to an LLM."""
    if body.agent_name not in TUNABLE_AGENTS:
        raise HTTPException(400, f"agent_name must be one of {sorted(TUNABLE_AGENTS)}")
    if not get_app(app_id):
        raise HTTPException(404, "App not found")

    current_prompt = _resolve_current_prompt(app_id, body.agent_name, body.current_prompt)

    # Gather failure samples — either from a run or from the explicit list.
    samples: list[FailureSample]
    if body.failures:
        samples = body.failures[: body.max_samples]
    elif body.run_id:
        run = get_eval_run(body.run_id)
        if not run or run.get("app_id") != app_id:
            raise HTTPException(404, "Run not found")
        fails = _failed_rows_from_run(body.run_id)
        ranked = _rank_failures(fails)
        samples = [_row_to_sample(r) for r in ranked[: body.max_samples]]
    else:
        raise HTTPException(
            400,
            "Provide either run_id or an explicit failures list to fine-tune against.",
        )

    if not samples:
        raise HTTPException(
            422,
            "No failure samples available — nothing to learn from. Pick a run with failures "
            "or supply failures explicitly.",
        )

    # Pick the LLM slot to drive the tuner. Try, in order:
    #   1. The target agent's own LLM config (whatever model the user already
    #      trusts for this prompt). Usually the safest choice.
    #   2. The 'insights' slot (heavy-reasoning workhorse).
    #   3. Any other tunable agent whose model maps to a provider with a key.
    # If nothing has a configured key, fail early with an actionable 400.
    available_providers = _available_providers(app_id)
    if not available_providers:
        raise HTTPException(
            400,
            "No LLM API key configured for this app. Open the API Keys page and "
            "set at least one provider key (OpenAI, Anthropic or Gemini) before "
            "running the prompt tuner.",
        )

    llm_slot, cfg = _pick_llm_slot(app_id, body.agent_name, available_providers)
    if not llm_slot:
        raise HTTPException(
            400,
            "No agent has an LLM model configured for a provider whose API key "
            "is set. Either add an API key for the model you want to use "
            "(API Keys page) or change an agent's model on the Prompts & Models "
            "page to a provider whose key is set: "
            f"{', '.join(sorted(available_providers))}.",
        )
    model = cfg.get("model", "")

    user_msg = _build_user_message(
        agent_name=body.agent_name,
        current_prompt=current_prompt,
        samples=samples,
        user_notes=body.user_notes,
    )

    logger.info(
        "Prompt tuner | starting | app=%s target=%s llm_slot=%s model=%s samples=%d",
        app_id, body.agent_name, llm_slot, model, len(samples),
    )

    # Route the call through the picked agent slot so call_llm_json reads its
    # model / temp / max_tokens. The system_prompt stays the meta-prompt — the
    # LLM is rewriting another prompt, not playing whatever role the slot is for.
    try:
        raw = call_llm_json(app_id, llm_slot, PROMPT_TUNER_PROMPT, user_msg)
    except Exception as exc:
        msg, status = _humanise_llm_error(exc, model=model, llm_slot=llm_slot)
        logger.error(
            "Prompt tuner | LLM call failed | model=%s slot=%s | %s",
            model, llm_slot, exc, exc_info=True,
        )
        raise HTTPException(status, msg)

    parsed = parse_json_loose(raw, expect="object", agent_name="prompt_tuner")
    if not isinstance(parsed, dict):
        logger.error(
            "Prompt tuner | could not parse JSON | raw[:500]=%s",
            (raw or "")[:500],
        )
        raise HTTPException(
            502,
            "The LLM returned a response we couldn't parse as JSON. Try again, "
            "or simplify the failures list.",
        )

    improved = (parsed.get("improved_prompt") or "").strip()
    summary = (parsed.get("summary_of_changes") or "").strip()
    patterns = parsed.get("failure_patterns") or []
    if not isinstance(patterns, list):
        patterns = [str(patterns)]
    patterns = [str(p) for p in patterns]

    if not improved:
        improved = current_prompt
        summary = summary or "The model did not propose a change."

    return FineTuneResponse(
        agent_name=body.agent_name,
        model=model,
        llm_slot=llm_slot,
        current_prompt=current_prompt,
        improved_prompt=improved,
        summary_of_changes=summary,
        failure_patterns=patterns,
        samples_used=len(samples),
        raw_response=raw or "",
    )


def _build_user_message(
    *,
    agent_name: str,
    current_prompt: str,
    samples: list[FailureSample],
    user_notes: str | None,
) -> str:
    """Compose the structured payload the meta-LLM sees."""
    role = AGENT_ROLES.get(agent_name, "")
    serialised_samples = [s.model_dump(exclude_none=True) for s in samples]
    parts = [
        f"# PROMPT_ROLE\n{role or agent_name}\n",
        f"# CURRENT_PROMPT (agent_name = {agent_name})\n```\n{current_prompt}\n```\n",
    ]
    if user_notes and user_notes.strip():
        parts.append(f"# USER_NOTES\n{user_notes.strip()}\n")
    parts.append(
        f"# FAILURE_SAMPLES ({len(samples)} cases — JSON array, each item has the "
        f"question, expected_answer, generated_answer, and any judge metadata)\n"
        f"```json\n{json.dumps(serialised_samples, indent=2, ensure_ascii=False)}\n```\n"
    )
    parts.append(
        "Now produce the JSON object specified in the system prompt. "
        "Respond with JSON ONLY, no markdown fences, no extra prose."
    )
    return "\n".join(parts)
