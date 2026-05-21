from __future__ import annotations

import io
import json
import logging
import statistics
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from models import EvalRunResponse, EvalResultResponse
from db.database import (
    delete_eval_run, get_app, get_db, get_eval_results, get_eval_run,
    get_run_ai_insights, get_run_diagnostics, list_eval_runs,
    bulk_update_verdicts, update_run_verdict_counts,
)
from diagnostics.ai_narrative import get_or_generate_narrative
from diagnostics.compute import compute_and_store_diagnostics
from diagnostics.trends import compute_run_trends
from judge.metrics import derive_verdict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/apps/{app_id}/results", tags=["results"])


@router.get("", response_model=list[EvalRunResponse])
def get_runs(app_id: str):
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    runs = list_eval_runs(app_id)
    result = []
    for r in runs:
        passed = r.get("passed_cases") or 0
        # Use verdicted_cases (rows with a real pass/fail) as denominator so that
        # null-verdict Case-1 rows (embedding model unavailable) don't drag the rate to 0.
        verdicted = r.get("verdicted_cases") or 0
        denominator = verdicted if verdicted > 0 else (r.get("total_cases") or 1)
        result.append({**r, "pass_rate": round(passed / denominator, 4)})
    return result


def _is_pass(scores: dict, expected_behavior: str = "ANSWER") -> bool:
    if scores.get("toxicity_detected") or scores.get("bias_detected") or scores.get("banned_topic_violation"):
        return False
    return (
        scores.get("doc_retrieved", False)
        and (scores.get("groundedness") or 0) >= 4
        and (scores.get("query_relevance") or 0) >= 4
        and (scores.get("ground_truth_relevance") or 0) >= 3
        and (scores.get("completeness") or 0) >= 3
    )


@router.get("/{run_id}", response_model=list[EvalResultResponse])
def get_run_results(app_id: str, run_id: str):
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    rows = get_eval_results(run_id)
    result = []
    for r in rows:
        scores = r.get("scores", {})
        expected_behavior = r.get("expected_behavior", "ANSWER")
        verdict = r.get("verdict")
        # Prefer the new verdict field; fall back to the legacy score-derived rule
        # so historical runs still display a sensible pass/fail.
        if verdict in ("pass", "fail"):
            passed = verdict == "pass"
        else:
            passed = _is_pass(scores, expected_behavior)
        # Build docId → {title, url} from stored chunk_signals (deduped by docId)
        doc_label_map: dict[str, dict] = {}
        for chunk in r.get("chunk_signals") or []:
            doc_id = chunk.get("docId")
            if doc_id and doc_id not in doc_label_map:
                doc_label_map[doc_id] = {
                    "title": chunk.get("recordTitle"),
                    "url": chunk.get("recordUrl"),
                }
        result.append({
            "tc_id": r["tc_id"],
            "question": r["question"],
            "expected_answer": r.get("expected_answer"),
            "expected_behavior": expected_behavior,
            "question_type": r.get("question_type"),
            "rag_response": r.get("rag_response"),
            "retrieved_doc_ids": r.get("retrieved_doc_ids", []),
            "reference_doc_ids": r.get("reference_doc_ids", []),
            "scores": scores,
            "passed": passed,
            "failure_category": r.get("failure_category"),
            "judge_rationale": r.get("judge_rationale"),
            "latency_llm_ms": r.get("latency_llm_ms"),
            "latency_retrieval_ms": r.get("latency_retrieval_ms"),
            "doc_retrieved": scores.get("doc_retrieved", False),
            "search_payload": r.get("search_payload") or {},
            "search_response": r.get("search_response") or {},
            "doc_label_map": doc_label_map,
            # 4-case fields
            "case_id": r.get("case_id"),
            "expected_doc_rank": r.get("expected_doc_rank"),
            "recall_at_k": r.get("recall_at_k") or {},
            "answer_similarity": r.get("answer_similarity"),
            "verdict": verdict,
            "verdict_source": r.get("verdict_source"),
        })
    return result


# ── Delete a single run ─────────────────────────────────────────────────────

@router.delete("/{run_id}")
def delete_run(app_id: str, run_id: str):
    """Permanently delete a run + all its eval_result rows (cascade).

    Refuses if the run is still ``running`` — caller should ``stop`` first.
    """
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    run = get_eval_run(run_id)
    if not run or run["app_id"] != app_id:
        raise HTTPException(404, "Run not found")
    if run.get("status") == "running":
        raise HTTPException(
            409,
            "Run is currently running — stop the evaluation job first, then delete.",
        )
    deleted = delete_eval_run(app_id, run_id)
    logger.info("Run deleted | app=%s run_id=%s results_removed=%d", app_id, run_id, deleted)
    return {"ok": True, "run_id": run_id, "results_deleted": deleted}


# ── Re-verdict (apply updated logic to stored results) ──────────────────────

_JUDGE_SCORE_KEYS = (
    "groundedness", "query_relevance", "ground_truth_relevance",
    "coherence", "fluency", "completeness", "paraphrasing", "gpt_similarity",
    "toxicity_detected", "bias_detected", "banned_topic_violation", "doc_retrieved",
)


def _re_verdict_row(r: dict) -> tuple[str | None, str]:
    """Re-apply the current derive_verdict logic to one stored eval_result row."""
    scores = r.get("scores") or {}
    case_id = r.get("case_id") or 1
    chunk_rank = scores.get("chunk_rank")

    judge_scores = {k: scores.get(k) for k in _JUDGE_SCORE_KEYS}
    has_judge = any(
        isinstance(scores.get(k), (int, float))
        for k in ("groundedness", "query_relevance", "ground_truth_relevance",
                  "coherence", "fluency", "completeness")
    )

    similarity = r.get("answer_similarity")
    qa_relevance = similarity if case_id == 1 else None

    return derive_verdict(
        case_id=case_id,
        has_judge=has_judge,
        judge_scores=judge_scores,
        expected_doc_rank_val=r.get("expected_doc_rank"),
        similarity=similarity,
        qa_relevance=qa_relevance,
        chunk_rank=chunk_rank,
    )


@router.post("/{run_id}/re-verdict")
def re_verdict_run(app_id: str, run_id: str):
    """Re-apply the current verdict rules to every stored result in a run."""
    if not get_app(app_id):
        raise HTTPException(404, "App not found")

    raw_rows = get_eval_results(run_id)
    if not raw_rows:
        raise HTTPException(404, "No results found for this run")

    updates: list[tuple[str, str | None, str]] = []
    for r in raw_rows:
        new_verdict, new_source = _re_verdict_row(r)
        updates.append((str(r["tc_id"]), new_verdict, new_source))

    bulk_update_verdicts(run_id, updates)

    passed = sum(1 for _, v, _ in updates if v == "pass")
    verdicted = sum(1 for _, v, _ in updates if v in ("pass", "fail"))
    update_run_verdict_counts(run_id, passed=passed, verdicted=verdicted)

    return {"run_id": run_id, "total": len(updates), "passed": passed, "verdicted": verdicted}


@router.post("/re-verdict-all")
def re_verdict_all_runs(app_id: str):
    """Re-apply current verdict rules to ALL completed runs for this app."""
    if not get_app(app_id):
        raise HTTPException(404, "App not found")

    runs = list_eval_runs(app_id)
    summary = []
    for run in runs:
        if run.get("status") != "complete":
            continue
        rid = run["run_id"]
        raw_rows = get_eval_results(rid)
        if not raw_rows:
            continue

        updates: list[tuple[str, str | None, str]] = []
        for r in raw_rows:
            new_verdict, new_source = _re_verdict_row(r)
            updates.append((str(r["tc_id"]), new_verdict, new_source))

        bulk_update_verdicts(rid, updates)

        passed = sum(1 for _, v, _ in updates if v == "pass")
        verdicted = sum(1 for _, v, _ in updates if v in ("pass", "fail"))
        update_run_verdict_counts(rid, passed=passed, verdicted=verdicted)
        summary.append({"run_id": rid, "total": len(updates), "passed": passed, "verdicted": verdicted})

    return {"runs_updated": len(summary), "details": summary}


# ── Diagnostics (Phase 2) ───────────────────────────────────────────────────

@router.get("/{run_id}/diagnostics")
def get_diagnostics(app_id: str, run_id: str, recompute: bool = False):
    """Return precomputed diagnostics for a run.

    Behaviour:
      • If cached → return immediately.
      • If missing (older run before Phase 2, or never computed) → compute,
        cache, and return (lazy backfill).
      • ``recompute=true`` forces a re-run (e.g. after re-verdicting).
    """
    run = get_eval_run(run_id)
    if not run or run["app_id"] != app_id:
        raise HTTPException(404, "Run not found")

    if not recompute:
        diag, fired_ids = get_run_diagnostics(run_id)
        if diag is not None:
            return diag

    try:
        return compute_and_store_diagnostics(run_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        logger.error("Diagnostics | compute FAILED | run_id=%s | %s", run_id, exc, exc_info=True)
        raise HTTPException(500, f"Failed to compute diagnostics: {exc}")


@router.get("/{run_id}/ai-insights")
def get_ai_insights(app_id: str, run_id: str):
    """Return the cached AI narrative for a run, or 204 if never generated.

    Lightweight read — never triggers an LLM call. Use POST to generate.
    """
    run = get_eval_run(run_id)
    if not run or run["app_id"] != app_id:
        raise HTTPException(404, "Run not found")
    cached = get_run_ai_insights(run_id)
    if not cached:
        return {"markdown": None, "model": None, "generated_at": None, "cached": False}
    return {**cached, "cached": True}


@router.post("/{run_id}/ai-insights")
def generate_ai_insights(app_id: str, run_id: str, regenerate: bool = False):
    """Generate (or return cached) AI narrative.

    With ``regenerate=true`` the cached value is overwritten with a fresh call.
    The LLM is whatever the 'insights' agent is configured with in LLM Config
    (defaults to gpt-4.1).
    """
    run = get_eval_run(run_id)
    if not run or run["app_id"] != app_id:
        raise HTTPException(404, "Run not found")
    try:
        return get_or_generate_narrative(run_id, regenerate=regenerate)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        logger.error("AI insights | generation FAILED | run_id=%s | %s", run_id, exc, exc_info=True)
        raise HTTPException(500, f"Failed to generate AI insights: {exc}")


@router.get("/{run_id}/trends")
def get_trends(app_id: str, run_id: str):
    """Return the trend payload comparing this run to its predecessor.

    If no previous completed run exists for the same (app_id, golden_set_version),
    ``has_baseline`` will be false and ``deltas`` carries current values with
    null previouses.
    """
    run = get_eval_run(run_id)
    if not run or run["app_id"] != app_id:
        raise HTTPException(404, "Run not found")
    try:
        return compute_run_trends(run_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        logger.error("Trends | compute FAILED | run_id=%s | %s", run_id, exc, exc_info=True)
        raise HTTPException(500, f"Failed to compute trends: {exc}")


# ── Excel export ────────────────────────────────────────────────────────────

_RUBRIC_KEYS = (
    "groundedness", "query_relevance", "ground_truth_relevance",
    "coherence", "fluency", "completeness", "paraphrasing", "gpt_similarity",
)
_SAFETY_KEYS = ("toxicity_detected", "bias_detected", "banned_topic_violation")


def _pct(arr: list[float], q: float) -> float | None:
    if not arr:
        return None
    s = sorted(arr)
    idx = min(len(s) - 1, int(len(s) * q))
    return round(s[idx], 1)


def _avg(arr: list[float]) -> float | None:
    return round(sum(arr) / len(arr), 1) if arr else None


@router.get("/{run_id}/export")
def export_run(app_id: str, run_id: str):
    """Stream a 4-sheet .xlsx: Summary, Results (colour-coded), Retrieval, Glossary."""
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    rows = get_eval_results(run_id)
    if not rows:
        raise HTTPException(404, "No results found for run")

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise HTTPException(500, "openpyxl is required")

    wb = openpyxl.Workbook()

    # ── Shared styles ──────────────────────────────────────────────────
    HDR_FILL  = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
    HDR_FONT  = Font(color="FFFFFF", bold=True)
    PASS_FILL = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
    FAIL_FILL = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    GREY_FILL = PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid")
    SEC_FONT  = Font(bold=True, size=11, color="1F2937")
    THIN      = Border(
        bottom=Side(border_style="thin", color="D1D5DB"),
    )

    def _h(ws, row_idx):
        """Style a section-header row."""
        ws.cell(row=row_idx, column=1).font = SEC_FONT
        ws.cell(row=row_idx, column=1).fill = GREY_FILL
        ws.cell(row=row_idx, column=2).fill = GREY_FILL

    def _bool_label(v):
        if v is True:  return "Yes"
        if v is False: return "No"
        return ""

    # ── Aggregate metrics ──────────────────────────────────────────────
    pass_count  = sum(1 for r in rows if r.get("verdict") == "pass")
    fail_count  = sum(1 for r in rows if r.get("verdict") == "fail")
    no_verdict  = sum(1 for r in rows if r.get("verdict") not in ("pass", "fail"))
    total       = len(rows)
    verdicted   = pass_count + fail_count
    pass_rate   = round(pass_count / verdicted * 100, 1) if verdicted else None

    case_counts: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
    for r in rows:
        c = r.get("case_id")
        if c in case_counts:
            case_counts[c] += 1

    llm_lat  = [r["latency_llm_ms"]        for r in rows if isinstance(r.get("latency_llm_ms"),        (int, float))]
    ret_lat  = [r["latency_retrieval_ms"]   for r in rows if isinstance(r.get("latency_retrieval_ms"),  (int, float))]
    sim_vals = [r["answer_similarity"]      for r in rows if isinstance(r.get("answer_similarity"),     (int, float))]

    # Per-metric averages (judge rubric)
    rubric_avgs: dict[str, float | None] = {}
    for k in _RUBRIC_KEYS:
        vals = [r.get("scores", {}).get(k) for r in rows if isinstance((r.get("scores") or {}).get(k), (int, float))]
        rubric_avgs[k] = _avg(vals)

    failure_breakdown: dict[str, int] = {}
    for r in rows:
        fc = r.get("failure_category") or "none"
        failure_breakdown[fc] = failure_breakdown.get(fc, 0) + 1

    qtype_pass: dict[str, list[int]] = {}
    for r in rows:
        qt = r.get("question_type") or "unspecified"
        if qt not in qtype_pass:
            qtype_pass[qt] = [0, 0]  # [pass, total]
        if r.get("verdict") in ("pass", "fail"):
            qtype_pass[qt][1] += 1
            if r.get("verdict") == "pass":
                qtype_pass[qt][0] += 1

    # ── Sheet 1: Summary ───────────────────────────────────────────────
    ws = wb.active
    ws.title = "Summary"
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 28

    def _row(ws, a, b=""):
        ws.append([a, b])

    # Title
    ws.append(["RAG Evaluation Report", ""])
    ws["A1"].font = Font(bold=True, size=16, color="1F2937")
    ws["A1"].fill = PatternFill(start_color="EDE9FE", end_color="EDE9FE", fill_type="solid")
    ws.append(["Generated (UTC)", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")])
    ws.append(["Run ID", run_id])
    ws.append(["", ""])

    # Overall results
    ws.append(["OVERALL RESULTS", ""])
    _h(ws, ws.max_row)
    _row(ws, "Total test cases evaluated", total)
    _row(ws, "Passed ✓", pass_count)
    _row(ws, "Failed ✗", fail_count)
    _row(ws, "No verdict (Case 1 without judge)", no_verdict)
    _row(ws, "Pass rate (verdicted cases only)",
         f"{pass_rate}%" if pass_rate is not None else "—")
    ws.append(["", ""])

    # Evaluation case breakdown
    ws.append(["TEST CASE TYPES", ""])
    _h(ws, ws.max_row)
    _row(ws, "Case 1 — Question only (no expected answer/doc)",  case_counts[1])
    _row(ws, "Case 2 — Question + Expected answer",              case_counts[2])
    _row(ws, "Case 3 — Question + Reference document",           case_counts[3])
    _row(ws, "Case 4 — Question + Answer + Reference document",  case_counts[4])
    ws.append(["", ""])

    # Failure breakdown
    ws.append(["FAILURE BREAKDOWN", ""])
    _h(ws, ws.max_row)
    for cat, n in sorted(failure_breakdown.items(), key=lambda x: -x[1]):
        labels = {
            "retrieval_miss":  "Retrieval miss — correct document not retrieved",
            "off_topic":       "Off-topic — answer not relevant to the question",
            "low_similarity":  "Low similarity — answer differs from expected",
            "retrieval_error": "Retrieval error — RAG API error",
            "toxic":           "Safety — toxic content detected",
            "biased":          "Safety — bias detected",
            "banned_topic":    "Safety — banned topic mentioned",
            "none":            "Passed / no failure",
        }
        _row(ws, f"  {labels.get(cat, cat)}", n)
    ws.append(["", ""])

    # Per question type pass rate
    if qtype_pass:
        ws.append(["PASS RATE BY QUESTION TYPE", ""])
        _h(ws, ws.max_row)
        for qt, (p, t) in sorted(qtype_pass.items(), key=lambda x: -x[1][1]):
            rate = f"{round(p / t * 100, 1)}%" if t else "—"
            _row(ws, f"  {qt}", f"{p}/{t} ({rate})")
        ws.append(["", ""])

    # Judge rubric averages
    has_rubric = any(v is not None for v in rubric_avgs.values())
    if has_rubric:
        ws.append(["JUDGE SCORES (average, scale 1–5)", ""])
        _h(ws, ws.max_row)
        rubric_labels = {
            "groundedness":            "Groundedness — answer supported by retrieved docs",
            "query_relevance":         "Query relevance — answer addresses the question",
            "ground_truth_relevance":  "Ground truth relevance — matches expected answer",
            "coherence":               "Coherence — logically well-structured",
            "fluency":                 "Fluency — grammatically correct",
            "completeness":            "Completeness — covers all aspects of the question",
            "paraphrasing":            "Paraphrasing — rephrased rather than verbatim copy",
            "gpt_similarity":          "GPT similarity — overall text similarity score",
        }
        for k, avg in rubric_avgs.items():
            if avg is not None:
                _row(ws, f"  {rubric_labels.get(k, k)}", avg)
        ws.append(["", ""])

    # Latency
    ws.append(["LATENCY", ""])
    _h(ws, ws.max_row)
    _row(ws, "LLM answer latency — average (ms)",  _avg(llm_lat))
    _row(ws, "LLM answer latency — median (ms)",   _pct(llm_lat, 0.5))
    _row(ws, "LLM answer latency — p95 (ms)",      _pct(llm_lat, 0.95))
    _row(ws, "Retrieval latency — average (ms)",   _avg(ret_lat))
    _row(ws, "Retrieval latency — median (ms)",    _pct(ret_lat, 0.5))
    _row(ws, "Retrieval latency — p95 (ms)",       _pct(ret_lat, 0.95))
    ws.append(["", ""])

    # Similarity
    if sim_vals:
        ws.append(["ANSWER SIMILARITY (0 = no match, 1 = identical)", ""])
        _h(ws, ws.max_row)
        _row(ws, "Average similarity",  round(statistics.mean(sim_vals), 3))
        _row(ws, "Median similarity",   round(statistics.median(sim_vals), 3))
        _row(ws, "Minimum similarity",  round(min(sim_vals), 3))
        _row(ws, "Maximum similarity",  round(max(sim_vals), 3))

    # ── Sheet 2: Results (colour-coded) ────────────────────────────────
    results = wb.create_sheet("Results")

    col_headers = [
        # Question
        "Question",
        "Expected Answer",
        "RAG Generated Answer",
        # Verdict
        "Verdict",
        "Verdict Source\n(how the verdict was decided)",
        "Failure Category",
        # Retrieval
        "Evaluation Case\n(1–4)",
        "Expected Doc Retrieved?\n(Yes / No)",
        "Expected Doc Rank\n(position in results, 1=top)",
        "Chunk Rank\n(chunk-level position)",
        "Qualified Chunks\n(chunks scored by Kore.ai)",
        # Matched chunk lifecycle
        "Matched Chunk — Search Qualified?\n(entered Kore.ai scoring)",
        "Matched Chunk — Sent to LLM?\n(used to build the answer)",
        "Matched Chunk — Used in Answer?\n(cited in final response)",
        # Chunk retrieval scores
        "Matched Vector Score\n(semantic similarity, 0–1)",
        "Matched Keyword Score\n(keyword match, 0–1)",
        "Matched Positional Score",
        "Matched Combined Score",
        # Answer quality
        "Answer Similarity\n(0=different, 1=identical)",
        # Latency
        "LLM Latency (ms)",
        "Retrieval Latency (ms)",
        # Judge rubric
        "Groundedness\n(1–5: answer supported by docs)",
        "Query Relevance\n(1–5: answers the question)",
        "Ground Truth Relevance\n(1–5: matches expected answer)",
        "Coherence\n(1–5: logical structure)",
        "Fluency\n(1–5: grammatical quality)",
        "Completeness\n(1–5: covers all aspects)",
        "Paraphrasing\n(1–5: rephrased not copied)",
        "GPT Similarity\n(1–5: overall text match)",
        # Safety
        "Toxicity Detected?",
        "Bias Detected?",
        "Banned Topic Violation?",
        # Judge reasoning
        "Judge Rationale\n(LLM explanation of scores)",
    ]

    results.append(col_headers)
    for cell in results[1]:
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    results.row_dimensions[1].height = 48

    for r in rows:
        scores  = r.get("scores") or {}
        verdict = r.get("verdict")
        row_data = [
            r.get("question"),
            r.get("expected_answer"),
            r.get("rag_response"),
            verdict,
            r.get("verdict_source"),
            r.get("failure_category"),
            r.get("case_id"),
            "Yes" if scores.get("doc_retrieved") else "No",
            r.get("expected_doc_rank"),
            scores.get("chunk_rank"),
            scores.get("qualified_chunks_count"),
            _bool_label(scores.get("matched_chunk_qualified")),
            _bool_label(scores.get("matched_chunk_sent_to_llm")),
            _bool_label(scores.get("matched_chunk_used_in_answer")),
            scores.get("matched_vector_score"),
            scores.get("matched_keyword_score"),
            scores.get("matched_positional_score"),
            scores.get("matched_combined_score"),
            r.get("answer_similarity"),
            r.get("latency_llm_ms"),
            r.get("latency_retrieval_ms"),
            *[scores.get(k) for k in _RUBRIC_KEYS],
            _bool_label(scores.get("toxicity_detected")),
            _bool_label(scores.get("bias_detected")),
            _bool_label(scores.get("banned_topic_violation")),
            r.get("judge_rationale"),
        ]
        results.append(row_data)

        # Colour-code the row
        row_idx = results.max_row
        fill = PASS_FILL if verdict == "pass" else (FAIL_FILL if verdict == "fail" else None)
        if fill:
            for col_idx in range(1, len(col_headers) + 1):
                results.cell(row=row_idx, column=col_idx).fill = fill

    # Column widths
    col_widths = [
        55, 50, 65,          # question / expected / generated
        10, 32, 20,          # verdict / source / failure
        8,  10, 14, 12, 12,  # case / doc_retrieved / rank / chunk_rank / qualified
        14, 14, 14,          # lifecycle flags
        14, 14, 14, 14,      # scores
        14, 14, 14,          # similarity / latencies
        12, 12, 14, 12, 12, 12, 12, 12,  # rubric
        12, 12, 14,          # safety
        60,                  # rationale
    ]
    for i, w in enumerate(col_widths, start=1):
        results.column_dimensions[get_column_letter(i)].width = w
    results.freeze_panes = "A2"

    # ── Sheet 3: Retrieval ─────────────────────────────────────────────
    retrieval = wb.create_sheet("Retrieval")
    ret_headers = [
        "Test Case ID",
        "Question",
        "Expected Doc Rank\n(1 = retrieved first, blank = not found)",
        "Recall@1\n(1 if correct doc is #1 result)",
        "Recall@3", "Recall@5", "Recall@10",
        "Top-20 Retrieved Document IDs",
        "Expected Reference Doc IDs",
    ]
    retrieval.append(ret_headers)
    for cell in retrieval[1]:
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    retrieval.row_dimensions[1].height = 36

    for r in rows:
        retrieved = r.get("retrieved_doc_ids") or []
        ref_docs  = r.get("reference_doc_ids") or []
        recall    = r.get("recall_at_k") or {}
        retrieval.append([
            r.get("tc_id"),
            r.get("question"),
            r.get("expected_doc_rank"),
            recall.get("1"), recall.get("3"), recall.get("5"), recall.get("10"),
            ", ".join(str(x) for x in retrieved[:20]),
            ", ".join(str(x) for x in ref_docs),
        ])

    retrieval.column_dimensions["A"].width = 24
    retrieval.column_dimensions["B"].width = 55
    retrieval.column_dimensions["C"].width = 18
    retrieval.column_dimensions["D"].width = 12
    retrieval.column_dimensions["E"].width = 12
    retrieval.column_dimensions["F"].width = 12
    retrieval.column_dimensions["G"].width = 12
    retrieval.column_dimensions["H"].width = 80
    retrieval.column_dimensions["I"].width = 40
    retrieval.freeze_panes = "A2"

    # ── Sheet 4: Glossary ─────────────────────────────────────────────
    glossary = wb.create_sheet("Glossary")
    glossary.column_dimensions["A"].width = 35
    glossary.column_dimensions["B"].width = 75
    glossary.column_dimensions["C"].width = 25

    glossary.append(["METRIC GLOSSARY", "", ""])
    glossary["A1"].font = Font(bold=True, size=15, color="1F2937")
    glossary["A1"].fill = PatternFill(start_color="EDE9FE", end_color="EDE9FE", fill_type="solid")
    glossary.append(["This sheet explains every column and score in the Results sheet.", "", ""])
    glossary.append(["", "", ""])

    def _g_section(ws, title):
        ws.append([title, "", ""])
        row = ws.max_row
        for col in (1, 2, 3):
            ws.cell(row=row, column=col).fill = GREY_FILL
        ws.cell(row=row, column=1).font = SEC_FONT

    def _g_row(ws, name, desc, scale=""):
        ws.append([name, desc, scale])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
        ws.cell(row=ws.max_row, column=2).alignment = Alignment(wrap_text=True)

    # Section: Verdict
    _g_section(glossary, "VERDICT & FAILURE")
    _g_row(glossary, "Verdict",
           "Final result for this test case: 'pass' (green) or 'fail' (red). "
           "Blank means no verdict was possible (e.g. Case 1 without a judge or embeddings).\n"
           "Cases 3 & 4 (retrieval): PASS if the expected document chunk is in the top 5 retrieved chunks. "
           "Cases 1 & 2 (non-retrieval): PASS based on LLM judge scores or semantic similarity.",
           "pass / fail / blank")
    _g_row(glossary, "Verdict Source",
           "Explains how the verdict was determined — e.g. 'Judge LLM', "
           "'Semantic Q↔Answer similarity ≥ 0.50', or 'Document rank ≤ 10'.",
           "Text description")
    _g_row(glossary, "Failure Category",
           "Root cause of failure when verdict is 'fail':\n"
           "  • retrieval_miss — the correct document was not retrieved\n"
           "  • off_topic — the answer is not relevant to the question\n"
           "  • low_similarity — answer differs too much from expected\n"
           "  • toxic / biased / banned_topic — safety policy violation\n"
           "  • none — passed",
           "Text label")
    glossary.append(["", "", ""])

    # Section: Evaluation Cases
    _g_section(glossary, "EVALUATION CASES (Case 1–4)")
    _g_row(glossary, "Case 1 — Question only",
           "Only a question is provided. Verdict is based on whether the RAG answer "
           "is relevant to the question (semantic similarity). No document or answer check.",
           "No expected doc or answer")
    _g_row(glossary, "Case 2 — Question + Expected Answer",
           "The expected answer is provided. Verdict checks whether the RAG answer "
           "semantically matches the expected answer.",
           "Needs expected_answer column")
    _g_row(glossary, "Case 3 — Question + Reference Document",
           "A reference document ID, URL, or title is provided. Verdict checks "
           "whether that document appears in the retrieval results.",
           "Needs doc_id / recordUrl / record_title")
    _g_row(glossary, "Case 4 — All fields",
           "Both expected answer and reference document are provided. Verdict checks "
           "both retrieval correctness and answer quality.",
           "Full evaluation")
    glossary.append(["", "", ""])

    # Section: Retrieval
    _g_section(glossary, "RETRIEVAL METRICS")
    _g_row(glossary, "Expected Doc Retrieved?",
           "Yes if the reference document appears anywhere in the list of documents "
           "returned by Kore.ai. No means the correct document was completely missed.",
           "Yes / No")
    _g_row(glossary, "Expected Doc Rank",
           "Position (1-indexed) of the reference document in the list of all retrieved "
           "documents. 1 means it was the top result. Blank means not found.",
           "Integer ≥ 1 or blank")
    _g_row(glossary, "Chunk Rank",
           "Position of the first matching chunk (not document) in the chunk-level "
           "retrieval list. Lower is better.",
           "Integer ≥ 1 or blank")
    _g_row(glossary, "Qualified Chunks",
           "Number of chunks that passed Kore.ai's internal scoring threshold and "
           "were eligible to be sent to the LLM.",
           "Integer")
    _g_row(glossary, "Recall@K (1 / 3 / 5 / 10)",
           "1 if the expected document appeared in the top-K retrieved documents, "
           "0 if not. E.g. Recall@5 = 1 means the correct doc was in the top 5.",
           "0 or 1")
    glossary.append(["", "", ""])

    # Section: Chunk lifecycle
    _g_section(glossary, "CHUNK LIFECYCLE FLAGS (for the matched/expected document chunk)")
    _g_row(glossary, "Matched Chunk — Search Qualified?",
           "Whether Kore.ai scored this chunk as 'qualified' — i.e. it passed the "
           "internal relevance threshold and was a candidate for the LLM.",
           "Yes / No")
    _g_row(glossary, "Matched Chunk — Sent to LLM?",
           "Whether this chunk was actually included in the LLM prompt to generate "
           "the answer. A chunk can be qualified but not sent if the context limit is hit.",
           "Yes / No")
    _g_row(glossary, "Matched Chunk — Used in Answer?",
           "Whether the LLM used this chunk when writing the final answer. "
           "This is the strongest signal that the document influenced the response.",
           "Yes / No")
    glossary.append(["", "", ""])

    # Section: Chunk scores
    _g_section(glossary, "CHUNK RETRIEVAL SCORES (0–1, higher = better match)")
    _g_row(glossary, "Matched Vector Score",
           "Semantic (embedding) similarity between the query and the matched chunk. "
           "High = the chunk is semantically close to the question.",
           "0.0 – 1.0")
    _g_row(glossary, "Matched Keyword Score",
           "Keyword overlap score between the query and the matched chunk. "
           "High = the chunk contains the exact words from the question.",
           "0.0 – 1.0")
    _g_row(glossary, "Matched Positional Score",
           "Score based on where in the document the chunk appears. "
           "Used by Kore.ai's hybrid ranking algorithm.",
           "0.0 – 1.0")
    _g_row(glossary, "Matched Combined Score",
           "Kore.ai's final combined relevance score for the matched chunk, "
           "blending vector, keyword, and positional signals.",
           "0.0 – 1.0")
    glossary.append(["", "", ""])

    # Section: Answer quality
    _g_section(glossary, "ANSWER QUALITY")
    _g_row(glossary, "Answer Similarity",
           "Semantic text similarity between the RAG-generated answer and the "
           "expected answer (or between question and answer for Case 1). "
           "Computed using sentence-transformers (all-MiniLM-L6-v2).",
           "0.0 – 1.0")
    glossary.append(["", "", ""])

    # Section: Judge rubric
    _g_section(glossary, "JUDGE RUBRIC SCORES (1–5, higher = better; only when LLM judge is configured)")
    rubric_descs = {
        "groundedness":           "Is the answer supported by the retrieved documents? "
                                  "A score of 5 means every claim is traceable to a retrieved source.",
        "query_relevance":        "Does the answer actually address what was asked? "
                                  "5 = fully answers the question, 1 = completely off-topic.",
        "ground_truth_relevance": "How closely does the answer match the expected/reference answer? "
                                  "5 = equivalent content, 1 = contradicts or misses the point.",
        "coherence":              "Is the answer logically structured and easy to follow? "
                                  "5 = clear and well-organised, 1 = confusing or contradictory.",
        "fluency":                "Is the answer grammatically correct and well-written? "
                                  "5 = professional quality, 1 = grammatically broken.",
        "completeness":           "Does the answer cover all aspects of the question? "
                                  "5 = fully complete, 1 = only a partial or superficial answer.",
        "paraphrasing":           "Does the answer paraphrase rather than copy verbatim from the source? "
                                  "5 = well-rephrased, 1 = exact copy of source text.",
        "gpt_similarity":         "Overall similarity between the generated answer and the expected answer "
                                  "as judged by the LLM. 5 = essentially identical in meaning.",
    }
    for k in _RUBRIC_KEYS:
        _g_row(glossary, k.replace("_", " ").title(), rubric_descs.get(k, ""), "1 – 5")
    glossary.append(["", "", ""])

    # Section: Safety
    _g_section(glossary, "SAFETY FLAGS")
    _g_row(glossary, "Toxicity Detected?",
           "Yes if the judge LLM flagged the answer as containing toxic, offensive, "
           "or harmful language.",
           "Yes / No")
    _g_row(glossary, "Bias Detected?",
           "Yes if the judge LLM detected unfair bias (gender, racial, political, etc.) "
           "in the generated answer.",
           "Yes / No")
    _g_row(glossary, "Banned Topic Violation?",
           "Yes if the answer discusses a topic that was configured as banned for this app "
           "(e.g. competitor names, internal salary data).",
           "Yes / No")
    glossary.append(["", "", ""])

    # Section: Latency
    _g_section(glossary, "LATENCY")
    _g_row(glossary, "LLM Latency (ms)",
           "Time in milliseconds for Kore.ai's LLM to generate the answer "
           "after the documents were retrieved.",
           "Milliseconds")
    _g_row(glossary, "Retrieval Latency (ms)",
           "Time in milliseconds for Kore.ai to retrieve and rank documents "
           "for the query.",
           "Milliseconds")
    glossary.append(["", "", ""])

    # Section: Colour guide
    _g_section(glossary, "COLOUR GUIDE (Results sheet)")
    glossary.append(["Green row", "Test case PASSED", ""])
    glossary.cell(row=glossary.max_row, column=1).fill = PASS_FILL
    glossary.cell(row=glossary.max_row, column=1).font = Font(bold=True)
    glossary.append(["Red row", "Test case FAILED", ""])
    glossary.cell(row=glossary.max_row, column=1).fill = FAIL_FILL
    glossary.cell(row=glossary.max_row, column=1).font = Font(bold=True)
    glossary.append(["White row", "No verdict (Case 1 without judge or embeddings)", ""])
    glossary.cell(row=glossary.max_row, column=1).font = Font(bold=True)

    # Freeze and header for glossary
    glossary.freeze_panes = "A2"
    glossary.append(["", "", ""])
    glossary.append(["Column", "Description", "Range / Values"])
    hdr_row = glossary.max_row
    for col in (1, 2, 3):
        glossary.cell(row=hdr_row, column=col).fill = HDR_FILL
        glossary.cell(row=hdr_row, column=col).font = HDR_FONT

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"eval-{run_id[:12]}-{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
