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
import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.llm_client import call_llm, parse_json_loose
from agents.prompts import DEFAULT_PROMPTS, PROMPT_TUNER_PROMPT
from db.database import (
    get_active_prompt, get_api_key, get_app, get_eval_results, get_eval_run,
    get_llm_config, list_eval_runs,
)

logger = logging.getLogger(__name__)

# Desired output budget for the tuner. Rewriting a long prompt (5k+ chars)
# plus summary/patterns plus the reasoning tokens that o-series / gpt-5 /
# gemini-thinking models silently consume can easily exceed 10k tokens, and
# truncation mid-output is the #1 cause of unparseable responses. We aim high
# (64k) and then cap per-model below so we never request more than the provider
# accepts — most providers 400 if max_tokens exceeds the model's output limit.
TUNER_DESIRED_OUTPUT_TOKENS = 65_000


def _model_output_cap(model: str) -> int:
    """Conservative per-model upper bound on output tokens.

    Values below the documented maxes so we don't get 400s after a provider
    bumps a hard limit downward. When unsure, prefer the smaller number.
    """
    name = (model or "").lower()
    # OpenAI reasoning models — huge output windows.
    if name.startswith("gpt-5") or name.startswith("gpt5"):
        return 128_000
    if name.startswith("o1") or name.startswith("o3") or name.startswith("o4"):
        return 100_000
    # OpenAI chat models.
    if name.startswith("gpt-4.1"):
        return 32_768
    if name.startswith("gpt-4o") or name.startswith("gpt-4-turbo"):
        return 16_384
    if name.startswith("gpt-4"):
        return 8_192
    if name.startswith("gpt-3.5"):
        return 4_096
    # Anthropic.
    if "opus-4" in name:
        return 32_000
    if "claude-3-7" in name or "claude-3.7" in name:
        return 64_000
    if "claude-3-5" in name or "claude-3.5" in name:
        return 8_192
    if name.startswith("claude"):
        return 8_192
    # Gemini.
    if "gemini-2.5" in name or "gemini-2-5" in name:
        return 65_536
    if "gemini-1.5" in name or "gemini-1-5" in name:
        return 8_192
    if name.startswith("gemini") or name.startswith("models/gemini"):
        return 8_192
    return 8_192

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


# ── Tuner response parsing ─────────────────────────────────────────────────
# The tuner output is a multi-thousand-character prompt full of quotes,
# newlines, backslashes and {{template}} markers. Forcing the LLM to wrap that
# into a JSON string was the original design and proved fragile — even small
# escaping mistakes (a stray unescaped quote, a raw newline, an off-by-one
# truncation) made json.loads fail and produced the "couldn't parse as JSON"
# error users hit in the UI. We now accept three formats, in order of
# preference:
#   1. Sentinel-delimited blocks (the new default — zero escaping required).
#   2. Strict JSON object (kept for backward compat / model variance).
#   3. Regex rescue: pull "improved_prompt" out of a partially-broken JSON
#      body so a near-miss still produces something useful for the user.

_BLOCK_PATTERNS: dict[str, re.Pattern[str]] = {
    "improved_prompt": re.compile(
        r"<<<\s*IMPROVED_PROMPT\s*>>>\s*\n?(.*?)\n?\s*<<<\s*END_IMPROVED_PROMPT\s*>>>",
        re.DOTALL | re.IGNORECASE,
    ),
    "summary_of_changes": re.compile(
        r"<<<\s*SUMMARY_OF_CHANGES\s*>>>\s*\n?(.*?)\n?\s*<<<\s*END_SUMMARY_OF_CHANGES\s*>>>",
        re.DOTALL | re.IGNORECASE,
    ),
    "failure_patterns": re.compile(
        r"<<<\s*FAILURE_PATTERNS\s*>>>\s*\n?(.*?)\n?\s*<<<\s*END_FAILURE_PATTERNS\s*>>>",
        re.DOTALL | re.IGNORECASE,
    ),
}


def _parse_sentinel_blocks(raw: str) -> dict[str, Any] | None:
    """Extract the three sentinel blocks from the LLM response.

    Returns ``None`` if no IMPROVED_PROMPT block is present — that's the only
    field we strictly require; summary/patterns are nice-to-have.
    """
    improved_match = _BLOCK_PATTERNS["improved_prompt"].search(raw or "")
    if not improved_match:
        return None
    improved = improved_match.group(1).strip()
    if not improved:
        return None

    summary_match = _BLOCK_PATTERNS["summary_of_changes"].search(raw)
    summary = summary_match.group(1).strip() if summary_match else ""

    patterns_match = _BLOCK_PATTERNS["failure_patterns"].search(raw)
    patterns: list[str] = []
    if patterns_match:
        for line in patterns_match.group(1).splitlines():
            label = line.strip().lstrip("-*•").strip().strip("\"',")
            if label:
                patterns.append(label)
    return {
        "improved_prompt": improved,
        "summary_of_changes": summary,
        "failure_patterns": patterns,
    }


# Last-ditch rescue for malformed JSON: pull the improved_prompt value even when
# the surrounding object is broken (e.g. unterminated due to truncation, or has
# an unescaped quote later in the body). Captures everything between the
# opening quote of the value and the closing quote that comes before either the
# next top-level key or end-of-string.
_JSON_RESCUE_RE = re.compile(
    r'"improved_prompt"\s*:\s*"(.*?)"\s*(?:,\s*"(?:summary_of_changes|failure_patterns)"|\}|\Z)',
    re.DOTALL,
)


def _rescue_from_broken_json(raw: str) -> dict[str, Any] | None:
    """Best-effort recovery when the LLM emits almost-valid JSON.

    Only used when both the sentinel parser and json.loads have failed. The
    rescued prompt will have JSON escape sequences (\\n, \\", \\\\) decoded
    back to their literal characters.
    """
    if not raw:
        return None
    m = _JSON_RESCUE_RE.search(raw)
    if not m:
        return None
    payload = m.group(1)
    try:
        improved = json.loads(f'"{payload}"')
    except json.JSONDecodeError:
        improved = (
            payload.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
        )
    improved = improved.strip()
    if not improved:
        return None
    return {
        "improved_prompt": improved,
        "summary_of_changes": "(Recovered from a partially-malformed model response — review carefully.)",
        "failure_patterns": ["recovered_from_broken_json"],
    }


def parse_tuner_response(raw: str) -> dict[str, Any] | None:
    """Try every supported tuner output format, returning the first that yields a usable prompt."""
    sentinel = _parse_sentinel_blocks(raw)
    if sentinel:
        return sentinel

    parsed = parse_json_loose(raw, expect="object", agent_name="prompt_tuner")
    if isinstance(parsed, dict) and (parsed.get("improved_prompt") or "").strip():
        patterns = parsed.get("failure_patterns") or []
        if not isinstance(patterns, list):
            patterns = [str(patterns)]
        return {
            "improved_prompt": str(parsed["improved_prompt"]).strip(),
            "summary_of_changes": str(parsed.get("summary_of_changes") or "").strip(),
            "failure_patterns": [str(p) for p in patterns],
        }

    return _rescue_from_broken_json(raw)


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

    # Headroom for a full rewrite + summary + patterns. Without this floor, a
    # 5k-char input prompt routinely truncates the output mid-block and the
    # parser sees an incomplete IMPROVED_PROMPT sentinel. We aim for 65k but
    # cap at the model's documented output limit so providers like OpenAI
    # don't 400 the request for asking for more than the model can produce.
    stored_max = int((cfg or {}).get("max_tokens") or 0)
    model_cap = _model_output_cap(model)
    effective_max = min(max(stored_max, TUNER_DESIRED_OUTPUT_TOKENS), model_cap)
    if effective_max != stored_max:
        logger.info(
            "Prompt tuner | output budget | stored=%d desired=%d model_cap=%d "
            "-> effective=%d (slot=%s model=%s)",
            stored_max, TUNER_DESIRED_OUTPUT_TOKENS, model_cap, effective_max,
            llm_slot, model,
        )

    logger.info(
        "Prompt tuner | starting | app=%s target=%s llm_slot=%s model=%s "
        "samples=%d max_tokens=%d prompt_chars=%d",
        app_id, body.agent_name, llm_slot, model, len(samples),
        effective_max, len(current_prompt),
    )

    # Route through the picked slot so call_llm reads its model / temp config,
    # but pass the meta tuner prompt as the system message. We don't use
    # call_llm_json anymore: forcing JSON mode for a multi-thousand-char string
    # value made every escaping mistake fatal. The tuner now emits
    # sentinel-delimited blocks (no escaping needed); parse_tuner_response
    # still falls back to JSON / regex rescue for older / divergent responses.
    try:
        raw = call_llm(
            app_id, llm_slot, PROMPT_TUNER_PROMPT, user_msg,
            max_tokens_override=effective_max,
        )
    except Exception as exc:
        msg, status = _humanise_llm_error(exc, model=model, llm_slot=llm_slot)
        logger.error(
            "Prompt tuner | LLM call failed | model=%s slot=%s | %s",
            model, llm_slot, exc, exc_info=True,
        )
        raise HTTPException(status, msg)

    parsed = parse_tuner_response(raw)
    if not parsed:
        snippet = (raw or "").strip()
        head = snippet[:300]
        tail = snippet[-300:] if len(snippet) > 600 else ""
        logger.error(
            "Prompt tuner | could not parse response | model=%s slot=%s "
            "raw_chars=%d | head=%r | tail=%r",
            model, llm_slot, len(snippet), head, tail,
        )
        raise HTTPException(
            502,
            "The model returned a response the tuner couldn't parse. This "
            "usually means the output was truncated or the model ignored the "
            "format instructions. Try again, lower the sample count, or pick "
            f"a different model. (Model: {model}, response start: {head[:120]!r})",
        )

    improved = parsed["improved_prompt"]
    summary = parsed["summary_of_changes"]
    patterns = parsed["failure_patterns"]

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
