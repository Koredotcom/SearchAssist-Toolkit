from __future__ import annotations

import json
import time
import uuid
from typing import Any

from rich.console import Console
from rich.progress import track

from config import get_config
from db.database import (
    create_eval_run,
    finish_eval_run,
    get_active_test_cases,
    get_completed_tc_ids,
    upsert_eval_result,
)
from judge.judge import judge_result
from koreai.search import query_rag

console = Console()

MAX_RETRIES = 3
RETRY_DELAYS = [1, 4, 16]


def run_evaluation_pipeline(
    golden_set_version: str,
    rag_version: str = "unknown",
    trigger: str = "manual",
    run_id: str | None = None,
) -> dict[str, Any]:
    """
    Full evaluation pipeline: fetch golden set → query RAG → judge → persist.
    Supports resumption: skips already-completed test cases.
    """
    cfg = get_config()
    run_id = run_id or f"run-{uuid.uuid4()}"

    test_cases = get_active_test_cases(golden_set_version)
    if not test_cases:
        console.print("[red]No active test cases found for this golden set version.[/red]")
        return {}

    create_eval_run(
        {
            "run_id": run_id,
            "rag_version": rag_version,
            "judge_model": cfg.judge_model,
            "golden_set_version": golden_set_version,
            "trigger": trigger,
            "total_cases": len(test_cases),
        }
    )

    console.print(
        f"\n[bold]Evaluation run[/bold] [cyan]{run_id}[/cyan]\n"
        f"  Golden set: {golden_set_version} | Cases: {len(test_cases)}"
    )

    completed_ids = get_completed_tc_ids(run_id)
    remaining = [tc for tc in test_cases if tc["tc_id"] not in completed_ids]
    if completed_ids:
        console.print(f"  Resuming — {len(completed_ids)} already done, {len(remaining)} remaining")

    passed = len(completed_ids)
    failed_tc_ids: list[str] = []
    status = "complete"

    for tc in track(remaining, description="Querying RAG + judging"):
        result = _evaluate_one(run_id, tc)
        if result is None:
            failed_tc_ids.append(tc["tc_id"])
            continue

        scores = result.get("scores", {})
        is_pass = _is_pass(scores, tc.get("expected_behavior", "ANSWER"))
        if is_pass:
            passed += 1

        upsert_eval_result(result)

    if failed_tc_ids:
        status = "partial"
        console.print(f"\n[yellow]Warning:[/yellow] {len(failed_tc_ids)} cases failed after retries")

    total = len(test_cases)
    pass_rate = (passed / total * 100) if total else 0

    finish_eval_run(run_id, passed=passed, cost=0.0, status=status)

    console.print(
        f"\n[bold]Evaluation complete[/bold]\n"
        f"  Pass rate: [green]{pass_rate:.1f}%[/green] ({passed}/{total})\n"
        f"  Run ID: {run_id}"
    )

    return {
        "run_id": run_id,
        "total": total,
        "passed": passed,
        "pass_rate": pass_rate,
        "status": status,
    }


def _evaluate_one(run_id: str, tc: dict[str, Any]) -> dict[str, Any] | None:
    tc_id = tc["tc_id"]
    reference_doc_ids = json.loads(tc.get("reference_doc_ids") or "[]")
    expected_behavior = tc.get("expected_behavior", "ANSWER")

    for attempt, delay in enumerate(RETRY_DELAYS, 1):
        try:
            rag = query_rag(tc["question"])

            verdict = judge_result(
                question=tc["question"],
                expected_answer=tc["expected_answer"],
                expected_behavior=expected_behavior,
                rag_response=rag["answer"],
                retrieved_doc_ids=rag["cited_doc_ids"],
                reference_doc_ids=reference_doc_ids,
            )

            return {
                "run_id": run_id,
                "tc_id": tc_id,
                "rag_response": rag["answer"],
                "retrieved_doc_ids": rag["cited_doc_ids"],
                "chunk_signals": rag["chunk_signals"],
                "scores": verdict["scores"],
                "failure_category": verdict["failure_category"],
                "judge_rationale": verdict["judge_rationale"],
                "latency_llm_ms": rag.get("latency_llm_ms"),
                "latency_retrieval_ms": rag.get("latency_retrieval_ms"),
                "search_request_id": rag.get("search_request_id"),
                "attempt_count": attempt,
            }

        except Exception as exc:
            if attempt < MAX_RETRIES:
                time.sleep(delay)
            else:
                console.print(f"[red]Failed tc_id={tc_id} after {MAX_RETRIES} attempts: {exc}[/red]")
                return None

    return None


def _is_pass(scores: dict[str, Any], expected_behavior: str) -> bool:
    if expected_behavior in ("REFUSE", "CLARIFY"):
        return scores.get("refusal_correct") is True

    faithfulness = scores.get("faithfulness") or 0
    relevance = scores.get("relevance") or 0
    completeness = scores.get("completeness") or 0
    doc_retrieved = scores.get("doc_retrieved", False)

    return (
        doc_retrieved
        and faithfulness >= 4
        and relevance >= 4
        and completeness >= 3
    )
