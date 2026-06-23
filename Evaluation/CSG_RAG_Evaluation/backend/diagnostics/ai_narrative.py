"""AI Deep Dive — LLM-generated narrative analysis of a single evaluation run.

The LLM is fed the precomputed diagnostics + fired rules + a small sample of
failed cases (by severity) so it can focus on patterns the deterministic engine
missed instead of re-deriving funnel stats.

Caching: the produced markdown is stored on ``eval_run.ai_insights_md`` and
returned immediately on subsequent calls unless ``regenerate=True``.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from agents.llm_client import call_llm
from agents.prompts import INSIGHTS_PROMPT
from db.database import (
    get_active_prompt, get_eval_results, get_eval_run, get_llm_config,
    get_run_ai_insights, get_run_diagnostics, set_run_ai_insights,
)
from diagnostics.compute import compute_and_store_diagnostics

logger = logging.getLogger(__name__)

# Cost guardrail — the prompt header explains why we cap.
MAX_SAMPLE_CASES = 15

# Per-field truncation when serialising a case into the LLM context
TRUNC_QUESTION         = 200
TRUNC_EXPECTED_ANSWER  = 300
TRUNC_RAG_ANSWER       = 400
TRUNC_JUDGE_RATIONALE  = 300


# ── Public API ──────────────────────────────────────────────────────────────

def get_or_generate_narrative(run_id: str, regenerate: bool = False) -> dict[str, Any]:
    """Return the AI narrative for a run, generating + caching on miss.

    Response shape:
      {
        "markdown":      "...",
        "model":         "gpt-4.1",
        "generated_at":  "ISO ts",
        "cached":        true|false,
        "warnings":      [str, ...],     # e.g. "no judge rationale available"
      }
    """
    run = get_eval_run(run_id)
    if not run:
        raise ValueError(f"run_id {run_id} not found")

    if not regenerate:
        cached = get_run_ai_insights(run_id)
        if cached:
            return {**cached, "cached": True, "warnings": []}

    diag, _fired = get_run_diagnostics(run_id)
    if diag is None:
        diag = compute_and_store_diagnostics(run_id)

    results = get_eval_results(run_id)
    sample, warnings = _sample_failed_cases(results, diag)

    user_msg = _build_user_message(run, diag, sample)
    system_prompt = _resolve_system_prompt(run["app_id"])

    cfg = get_llm_config(run["app_id"], "insights")
    model = cfg.get("model", "gpt-4.1")

    logger.info(
        "AI insights | starting | run_id=%s model=%s sample_size=%d warnings=%d",
        run_id, model, len(sample), len(warnings),
    )
    # call_llm raises EmptyLLMResponseError on empty content with finish_reason + hint
    markdown = call_llm(run["app_id"], "insights", system_prompt, user_msg).strip()

    set_run_ai_insights(run_id, markdown, model)
    cached_row = get_run_ai_insights(run_id) or {}
    logger.info(
        "AI insights | done | run_id=%s model=%s chars=%d",
        run_id, model, len(markdown),
    )
    return {
        **cached_row,
        "cached": False,
        "warnings": warnings,
    }


# ── Internal helpers ────────────────────────────────────────────────────────

def _resolve_system_prompt(app_id: str) -> str:
    """Prefer the app's editable insights prompt; fall back to the built-in default."""
    row = get_active_prompt(app_id, "insights")
    return row["prompt_text"] if row and row.get("prompt_text") else INSIGHTS_PROMPT


def _sample_failed_cases(
    results: list[dict],
    diag: dict,
) -> tuple[list[dict], list[str]]:
    """Pick at most ``MAX_SAMPLE_CASES`` failed cases prioritised by signal.

    Selection strategy (by_severity):
      1. Start with evidence_tc_ids from every high-severity fired rule
      2. Then medium-severity rule evidence
      3. Fill remaining slots with the worst-rated failures
         (lowest overall judge score, then lowest answer_similarity)

    Returns (sample, warnings).
    """
    warnings: list[str] = []
    fails_by_id: dict[str, dict] = {
        str(r["tc_id"]): r for r in results if r.get("verdict") == "fail"
    }

    has_any_judge = any(
        (r.get("judge_rationale") or "").strip() for r in results
    )
    if not has_any_judge:
        warnings.append(
            "No judge rationale found on any result — narrative quality will be lower. "
            "Configure an LLM judge for richer feedback."
        )

    fired = diag.get("fired_rules") or []
    high_ids: list[str] = []
    med_ids: list[str] = []
    for rule in fired:
        sev = rule.get("severity")
        for tc_id in (rule.get("evidence_tc_ids") or []):
            tc_id = str(tc_id)
            if tc_id not in fails_by_id:
                continue
            if sev == "high" and tc_id not in high_ids:
                high_ids.append(tc_id)
            elif sev == "medium" and tc_id not in med_ids:
                med_ids.append(tc_id)

    picked: list[dict] = []
    picked_ids: set[str] = set()

    def _add(tc_id: str) -> None:
        if tc_id in picked_ids or tc_id not in fails_by_id:
            return
        if len(picked) >= MAX_SAMPLE_CASES:
            return
        picked.append(fails_by_id[tc_id])
        picked_ids.add(tc_id)

    for tc_id in high_ids:
        _add(tc_id)
    for tc_id in med_ids:
        _add(tc_id)

    if len(picked) < MAX_SAMPLE_CASES:
        remaining = [r for r in fails_by_id.values() if str(r["tc_id"]) not in picked_ids]
        remaining.sort(key=_failure_signal_key)
        for r in remaining:
            _add(str(r["tc_id"]))
            if len(picked) >= MAX_SAMPLE_CASES:
                break

    return picked, warnings


def _failure_signal_key(r: dict) -> tuple[float, float, float]:
    """Sort key — most informative failure first.

    Lower judge composite → more failure signal.
    Lower answer similarity → more failure signal.
    Higher chunk rank (or none) → more failure signal.
    """
    scores = r.get("scores") or {}
    judge_metrics = (
        scores.get("groundedness"), scores.get("query_relevance"),
        scores.get("ground_truth_relevance"), scores.get("completeness"),
    )
    judge_avg = sum(v for v in judge_metrics if isinstance(v, (int, float)))
    judge_avg_count = sum(1 for v in judge_metrics if isinstance(v, (int, float)))
    judge_composite = (judge_avg / judge_avg_count) if judge_avg_count else 99.0  # missing = deprioritise
    similarity = r.get("answer_similarity")
    sim = similarity if isinstance(similarity, (int, float)) else 99.0
    chunk_rank = scores.get("chunk_rank")
    cr = chunk_rank if isinstance(chunk_rank, int) else 9999
    return (judge_composite, sim, -cr)  # ascending


def _truncate(text: str | None, limit: int) -> str:
    if not text:
        return ""
    text = str(text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _serialise_case(r: dict) -> dict[str, Any]:
    """Minimal-fidelity view of a single failed case for the LLM."""
    scores = r.get("scores") or {}
    return {
        "tc_id":            r.get("tc_id"),
        "case_id":          r.get("case_id"),
        "question_type":    r.get("question_type"),
        "question":         _truncate(r.get("question"), TRUNC_QUESTION),
        "expected_answer":  _truncate(r.get("expected_answer"), TRUNC_EXPECTED_ANSWER),
        "rag_answer":       _truncate(r.get("rag_response"), TRUNC_RAG_ANSWER),
        "failure_category": r.get("failure_category"),
        "verdict_source":   r.get("verdict_source"),
        "judge_rationale":  _truncate(r.get("judge_rationale"), TRUNC_JUDGE_RATIONALE),
        "expected_doc_rank": r.get("expected_doc_rank"),
        "chunk_rank":       scores.get("chunk_rank"),
        "answer_similarity": r.get("answer_similarity"),
        "key_judge_scores": {
            k: scores.get(k) for k in
            ("groundedness", "query_relevance", "ground_truth_relevance", "completeness")
            if isinstance(scores.get(k), (int, float))
        },
    }


def _build_user_message(run: dict, diag: dict, sample: list[dict]) -> str:
    """Compose the structured payload the LLM analyses.

    Sections are clearly labelled so the model doesn't have to guess. JSON for
    machine-readable parts; prose framing around them.
    """
    fired_rules_view = [
        {
            "rule_id":      r.get("rule_id"),
            "severity":     r.get("severity"),
            "title":        r.get("title"),
            "description":  r.get("description"),
            "impact_count": r.get("impact_count"),
        }
        for r in (diag.get("fired_rules") or [])
    ]
    diag_view = {
        "totals":              diag.get("totals"),
        "funnel":              diag.get("funnel"),
        "by_case":             diag.get("by_case"),
        "by_question_type":    diag.get("by_question_type"),
        "by_failure_category": diag.get("by_failure_category"),
        "retrieval":           diag.get("retrieval"),
        "judge_metric_avgs":   diag.get("judge_metric_avgs"),
        "weakest_judge_metric": diag.get("weakest_judge_metric"),
    }
    return (
        f"# Evaluation run summary\n"
        f"- run_id: {run.get('run_id')}\n"
        f"- app_id: {run.get('app_id')}\n"
        f"- golden_set_version: {run.get('golden_set_version')}\n"
        f"- rag_version: {run.get('rag_version')}\n"
        f"- total_cases: {run.get('total_cases')}\n\n"
        f"# Computed diagnostics (JSON)\n"
        f"```json\n{json.dumps(diag_view, indent=2)}\n```\n\n"
        f"# Fired rules — already detected by the deterministic engine\n"
        f"```json\n{json.dumps(fired_rules_view, indent=2)}\n```\n\n"
        f"# Sample of {len(sample)} failed cases (prioritised by severity / informativeness)\n"
        f"```json\n{json.dumps([_serialise_case(c) for c in sample], indent=2)}\n```\n\n"
        f"Now write the markdown report following the exact section headers in the system prompt."
    )
