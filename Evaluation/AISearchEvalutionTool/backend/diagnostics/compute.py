"""Deterministic diagnostics for a finished eval_run.

Funnel + per-case breakdown + judge-metric averages + retrieval stats.
The AI Deep-Dive narrative (Step 4) consumes these so it doesn't have to
re-derive them.
"""
from __future__ import annotations

import logging
import statistics
from datetime import datetime
from typing import Any

from db.database import (
    get_eval_results, get_eval_run, set_run_diagnostics,
)
from diagnostics.rules import evaluate_rules

logger = logging.getLogger(__name__)

ENGINE_VERSION = "1.0"

# Judge rubric metrics tracked for averages
_JUDGE_METRICS = (
    "groundedness", "query_relevance", "ground_truth_relevance",
    "coherence", "fluency", "completeness",
)


def _safe_avg(vals: list[float]) -> float | None:
    return round(sum(vals) / len(vals), 2) if vals else None


def _safe_median(vals: list[float]) -> float | None:
    return round(statistics.median(vals), 2) if vals else None


def _is_pass(r: dict) -> bool:
    return r.get("verdict") == "pass"


def _is_fail(r: dict) -> bool:
    return r.get("verdict") == "fail"


def _no_verdict(r: dict) -> bool:
    return r.get("verdict") not in ("pass", "fail")


def _bucket_count(items, key_fn) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items:
        k = key_fn(it)
        if k is None:
            continue
        k = str(k)
        out[k] = out.get(k, 0) + 1
    return out


def compute_run_diagnostics(run_id: str) -> dict[str, Any]:
    """Compute the full diagnostics dict for a run from its stored results.

    Returns a JSON-serialisable dict. Does NOT persist; callers should use
    ``compute_and_store_diagnostics`` to cache + return.
    """
    run = get_eval_run(run_id)
    if not run:
        raise ValueError(f"run_id {run_id} not found")

    results = get_eval_results(run_id)
    total = len(results)
    passed = sum(1 for r in results if _is_pass(r))
    failed = sum(1 for r in results if _is_fail(r))
    no_verdict = sum(1 for r in results if _no_verdict(r))
    verdicted = passed + failed
    pass_rate = round(passed / verdicted, 4) if verdicted else 0.0

    diag: dict[str, Any] = {
        "computed_at":     datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "engine_version":  ENGINE_VERSION,
        "run_id":          run_id,
        "totals": {
            "total":      total,
            "passed":     passed,
            "failed":     failed,
            "no_verdict": no_verdict,
            "verdicted":  verdicted,
            "pass_rate":  pass_rate,
        },
        "funnel":              _compute_funnel(results),
        "by_case":             _compute_by_case(results),
        "by_question_type":    _compute_by_qtype(results),
        "by_failure_category": _bucket_count(results, lambda r: r.get("failure_category") or "none"),
        "retrieval":           _compute_retrieval(results),
        "judge_metric_avgs":   _compute_judge_avgs(results),
        "weakest_judge_metric": None,  # filled in below
        "latency_ms":          _compute_latency(results),
    }

    # Weakest judge metric — pick the lowest non-null average
    judge_avgs = {k: v for k, v in (diag["judge_metric_avgs"] or {}).items()
                  if isinstance(v, (int, float))}
    if judge_avgs:
        diag["weakest_judge_metric"] = min(judge_avgs.items(), key=lambda kv: kv[1])[0]

    return diag


def compute_and_store_diagnostics(run_id: str) -> dict[str, Any]:
    """Compute + persist + return.

    Wraps ``compute_run_diagnostics`` and writes the result (plus the list of
    fired rule_ids) back to ``eval_run``. Idempotent — re-running overwrites.
    """
    diag = compute_run_diagnostics(run_id)
    results = get_eval_results(run_id)
    fired = evaluate_rules(diag, results)
    diag["fired_rules"] = [r.to_dict() for r in fired]
    fired_ids = [r.rule_id for r in fired]

    set_run_diagnostics(run_id, diag, fired_ids)
    logger.info(
        "Diagnostics | run_id=%s computed | total=%d passed=%d failed=%d rules_fired=%d",
        run_id, diag["totals"]["total"], diag["totals"]["passed"],
        diag["totals"]["failed"], len(fired),
    )
    return diag


# ── Sub-computations ────────────────────────────────────────────────────────

def _compute_funnel(results: list[dict]) -> dict[str, int]:
    """Step-by-step retrieval & answer funnel for the entire run.

    Numbers should generally decrease as you go down (each step is a stricter
    requirement). All Cases participate in the top of the funnel; later steps
    are only meaningful for Cases 3/4 (retrieval) or rows that produced an
    answer.
    """
    queried       = len(results)
    retrieved_any = sum(1 for r in results if (r.get("retrieved_doc_ids") or []))
    answered      = sum(1 for r in results if (r.get("rag_response") or "").strip())

    expected_doc_top1  = 0
    expected_doc_top5  = 0
    expected_doc_top10 = 0
    expected_chunk_top5 = 0
    for r in results:
        rank = r.get("expected_doc_rank")
        if isinstance(rank, int):
            if rank == 1:
                expected_doc_top1 += 1
            if rank <= 5:
                expected_doc_top5 += 1
            if rank <= 10:
                expected_doc_top10 += 1
        cr = (r.get("scores") or {}).get("chunk_rank")
        if isinstance(cr, int) and cr <= 5:
            expected_chunk_top5 += 1

    passed = sum(1 for r in results if _is_pass(r))

    return {
        "queried":              queried,
        "retrieved_any_doc":    retrieved_any,
        "expected_doc_top10":   expected_doc_top10,
        "expected_doc_top5":    expected_doc_top5,
        "expected_doc_top1":    expected_doc_top1,
        "expected_chunk_top5":  expected_chunk_top5,
        "answered":             answered,
        "verdict_pass":         passed,
    }


def _compute_by_case(results: list[dict]) -> dict[str, dict[str, Any]]:
    """Per-case totals + pass rate."""
    out: dict[str, dict[str, Any]] = {}
    for case_id in (1, 2, 3, 4):
        rows = [r for r in results if r.get("case_id") == case_id]
        total = len(rows)
        passed = sum(1 for r in rows if _is_pass(r))
        failed = sum(1 for r in rows if _is_fail(r))
        verdicted = passed + failed
        out[str(case_id)] = {
            "total":      total,
            "passed":     passed,
            "failed":     failed,
            "verdicted":  verdicted,
            "no_verdict": total - verdicted,
            "pass_rate":  round(passed / verdicted, 4) if verdicted else 0.0,
        }
    return out


def _compute_by_qtype(results: list[dict]) -> dict[str, dict[str, Any]]:
    """Per-question-type pass rate. Rows missing question_type are skipped."""
    out: dict[str, dict[str, Any]] = {}
    by_type: dict[str, list[dict]] = {}
    for r in results:
        qt = r.get("question_type")
        if not qt:
            continue
        by_type.setdefault(qt, []).append(r)
    for qt, rows in by_type.items():
        total = len(rows)
        passed = sum(1 for r in rows if _is_pass(r))
        failed = sum(1 for r in rows if _is_fail(r))
        verdicted = passed + failed
        out[qt] = {
            "total":     total,
            "passed":    passed,
            "failed":    failed,
            "pass_rate": round(passed / verdicted, 4) if verdicted else 0.0,
        }
    return out


def _compute_retrieval(results: list[dict]) -> dict[str, Any]:
    """Retrieval-only stats — chunk rank, doc rank, recall@k."""
    chunk_ranks = [
        (r.get("scores") or {}).get("chunk_rank")
        for r in results
    ]
    chunk_ranks = [v for v in chunk_ranks if isinstance(v, int)]

    doc_ranks = [r.get("expected_doc_rank") for r in results]
    doc_ranks = [v for v in doc_ranks if isinstance(v, int)]

    recall_sums = {"1": 0, "3": 0, "5": 0, "10": 0}
    recall_denoms = {"1": 0, "3": 0, "5": 0, "10": 0}
    for r in results:
        rec = r.get("recall_at_k") or {}
        for k in recall_sums:
            if k in rec:
                recall_sums[k] += int(rec[k] or 0)
                recall_denoms[k] += 1

    recall = {
        f"recall_at_{k}": (
            round(recall_sums[k] / recall_denoms[k], 4) if recall_denoms[k] else None
        )
        for k in recall_sums
    }

    return {
        "cases_with_chunk_rank": len(chunk_ranks),
        "avg_chunk_rank":         _safe_avg(chunk_ranks),
        "median_chunk_rank":      _safe_median(chunk_ranks),
        "cases_with_doc_rank":    len(doc_ranks),
        "avg_doc_rank":           _safe_avg(doc_ranks),
        "median_doc_rank":        _safe_median(doc_ranks),
        **recall,
    }


def _compute_judge_avgs(results: list[dict]) -> dict[str, float | None]:
    """Run-wide average of each judge rubric metric (1-5 scale)."""
    out: dict[str, float | None] = {}
    for k in _JUDGE_METRICS:
        vals = [
            (r.get("scores") or {}).get(k) for r in results
        ]
        vals = [v for v in vals if isinstance(v, (int, float))]
        out[k] = _safe_avg(vals)
    return out


def _compute_latency(results: list[dict]) -> dict[str, float | None]:
    """LLM + retrieval latency stats."""
    llm = [r.get("latency_llm_ms") for r in results
           if isinstance(r.get("latency_llm_ms"), (int, float))]
    retr = [r.get("latency_retrieval_ms") for r in results
            if isinstance(r.get("latency_retrieval_ms"), (int, float))]

    def _pct(arr: list[float], q: float) -> float | None:
        if not arr:
            return None
        s = sorted(arr)
        idx = min(len(s) - 1, int(len(s) * q))
        return round(s[idx], 1)

    return {
        "llm_avg_ms":         _safe_avg(llm),
        "llm_p50_ms":         _pct(llm, 0.5),
        "llm_p95_ms":         _pct(llm, 0.95),
        "retrieval_avg_ms":   _safe_avg(retr),
        "retrieval_p50_ms":   _pct(retr, 0.5),
        "retrieval_p95_ms":   _pct(retr, 0.95),
    }
