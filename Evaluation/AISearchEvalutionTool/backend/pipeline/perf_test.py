from __future__ import annotations

import logging
import statistics
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any

import httpx

from db.database import (
    create_perf_run, finalize_perf_run, get_active_test_cases,
    insert_perf_result, is_stop_requested, update_job, update_perf_run_counters,
)
from koreai.client import get_headers

logger = logging.getLogger(__name__)


def _build_payload(app: dict, question: str) -> dict[str, Any]:
    """Mirror koreai.search.query_rag's payload shape so perf == eval."""
    answer_mode = app.get("answer_mode", "answer_generation")
    payload: dict[str, Any] = {
        "query": question,
        "answerSearch": answer_mode != "extract_only",
        "searchResults": True,
        "includeChunksInResponse": True,
        "maxNumOfChunks": 100,
    }
    if app.get("racl_entity_ids"):
        payload["raclEntityIds"] = app["racl_entity_ids"]
    return payload


def _aggregates(latencies: list[float]) -> dict[str, float | None]:
    if not latencies:
        return {"p50": None, "p95": None, "p99": None, "avg": None, "max": None}
    s = sorted(latencies)

    def _pct(p: float) -> float:
        if len(s) == 1:
            return s[0]
        k = (len(s) - 1) * p
        f = int(k)
        c = min(f + 1, len(s) - 1)
        return s[f] + (s[c] - s[f]) * (k - f)

    return {
        "p50": _pct(0.50),
        "p95": _pct(0.95),
        "p99": _pct(0.99),
        "avg": statistics.fmean(latencies),
        "max": max(latencies),
    }


def run_perf_test(
    app: dict,
    golden_set_version: str,
    concurrency: int,
    stop_mode: str,
    iterations: int | None,
    duration_s: int | None,
    ramp_up_s: int,
    job_id: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Orchestrate a Postman-style parallel load against the Kore.ai search API.

    The same JSON body / headers as a real eval run are sent; what varies is
    only the loop control (iterations vs. duration) and how many workers run at
    once. Per-request latency / status / error is persisted to perf_result and
    aggregates are written back to perf_run on completion.

    ``run_id`` may be supplied by the caller (router) so the frontend can
    navigate to the detail page before this background task begins emitting.
    """
    app_id = app["app_id"]
    if run_id is None:
        run_id = f"perf-{uuid.uuid4()}"
    bot_id = app.get("bot_id", "?")
    url = f"{app['host_url']}/api/public/bot/{bot_id}/search/v2/advanced-search"
    headers = get_headers(app["jwt_token"])

    try:
        test_cases = get_active_test_cases(app_id, golden_set_version)
        if not test_cases:
            update_job(job_id, "failed", error="No active test cases in the selected golden set")
            return {}

        # If the router pre-created the perf_run row, this is a no-op upsert
        # against a duplicate key; otherwise create it now.
        from db.database import get_perf_run as _get_perf_run
        if _get_perf_run(run_id) is None:
            create_perf_run({
                "run_id": run_id,
                "app_id": app_id,
                "golden_set_version": golden_set_version,
                "concurrency": concurrency,
                "stop_mode": stop_mode,
                "iterations": iterations,
                "duration_s": duration_s,
                "ramp_up_s": ramp_up_s,
            })
        update_job(job_id, "running", progress=2, result={
            "run_id": run_id, "done": 0,
            "total": iterations or 0, "success": 0, "errors": 0,
        })

        # ── State shared across worker threads ───────────────────────────
        latencies: list[float] = []
        success_count = 0
        error_count = 0
        completed = 0
        next_seq = 0
        stopped_early = False
        lock = threading.Lock()

        # Concurrency limiter — ramps from 1 → target if ramp_up_s > 0.
        sem = threading.Semaphore(1 if ramp_up_s > 0 else concurrency)
        ramp_state = {"current": 1 if ramp_up_s > 0 else concurrency}

        def _ramp_up_releaser() -> None:
            if ramp_up_s <= 0:
                return
            steps = max(concurrency - 1, 0)
            if steps == 0:
                return
            interval = ramp_up_s / steps
            for _ in range(steps):
                time.sleep(interval)
                if is_stop_requested(job_id):
                    return
                sem.release()
                ramp_state["current"] += 1

        ramp_thread = threading.Thread(target=_ramp_up_releaser, daemon=True)
        ramp_thread.start()

        def _execute_one(seq: int, tc: dict) -> None:
            nonlocal success_count, error_count, completed
            sem.acquire()
            try:
                if is_stop_requested(job_id):
                    sem.release()
                    return
                payload = _build_payload(app, tc["question"])
                t0 = time.perf_counter()
                status_code: int | None = None
                err: str | None = None
                try:
                    with httpx.Client(headers=headers, timeout=60.0) as client:
                        resp = client.post(url, json=payload)
                    status_code = resp.status_code
                    if resp.status_code >= 400:
                        err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                except Exception as exc:
                    err = f"{type(exc).__name__}: {exc}"
                latency_ms = (time.perf_counter() - t0) * 1000.0

                insert_perf_result({
                    "run_id": run_id, "seq": seq,
                    "tc_id": tc.get("tc_id"),
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                    "error": err,
                })

                with lock:
                    completed += 1
                    latencies.append(latency_ms)
                    if err is None:
                        success_count += 1
                    else:
                        error_count += 1
            finally:
                sem.release()

        # ── Main scheduling loop ─────────────────────────────────────────
        start_time = time.perf_counter()

        def _should_stop() -> bool:
            if is_stop_requested(job_id):
                return True
            if stop_mode == "iterations":
                return next_seq >= (iterations or 0)
            if stop_mode == "duration":
                return (time.perf_counter() - start_time) >= (duration_s or 0)
            return True

        # Larger pool than concurrency so the semaphore is what truly gates.
        with ThreadPoolExecutor(max_workers=max(concurrency * 2, 4)) as executor:
            in_flight: list[Future] = []
            last_progress_emit = 0.0
            while not _should_stop():
                tc = test_cases[next_seq % len(test_cases)]
                fut = executor.submit(_execute_one, next_seq, tc)
                in_flight.append(fut)
                next_seq += 1

                # Cooperative pacing: small sleep so we don't busy-loop submits.
                # The semaphore handles the actual concurrency cap.
                if next_seq % concurrency == 0:
                    time.sleep(0.005)

                now = time.perf_counter()
                if now - last_progress_emit >= 1.0:
                    last_progress_emit = now
                    with lock:
                        done = completed
                        succ = success_count
                        errs = error_count
                        snap = list(latencies)
                    live_agg = _aggregates(snap)
                    if stop_mode == "iterations" and iterations:
                        pct = 2 + int(done / iterations * 96)
                    elif stop_mode == "duration" and duration_s:
                        pct = 2 + int(((now - start_time) / duration_s) * 96)
                    else:
                        pct = 2
                    update_perf_run_counters(run_id, done, succ, errs, aggregates=live_agg)
                    update_job(job_id, "running", progress=min(98, pct), result={
                        "run_id": run_id, "done": done,
                        "total": iterations or 0, "success": succ, "errors": errs,
                        "elapsed_s": round(now - start_time, 2),
                        "current_concurrency": ramp_state["current"],
                        **{f"{k}_ms": live_agg[k] for k in ("p50", "p95", "p99", "avg", "max")},
                    })

            stopped_early = is_stop_requested(job_id)

            # Drain
            for fut in in_flight:
                try:
                    fut.result()
                except Exception:
                    pass

        with lock:
            final_done = completed
            final_succ = success_count
            final_errs = error_count
            final_lat = list(latencies)

        agg = _aggregates(final_lat)
        final_status = "stopped" if stopped_early else "complete"
        finalize_perf_run(
            run_id=run_id,
            status=final_status,
            total_requests=final_done,
            success_count=final_succ,
            error_count=final_errs,
            aggregates=agg,
        )

        summary = {
            "run_id": run_id,
            "done": final_done,
            "total": iterations or final_done,
            "success": final_succ,
            "errors": final_errs,
            **{f"{k}_ms": agg[k] for k in ("p50", "p95", "p99", "avg", "max")},
        }
        update_job(job_id, final_status if final_status != "stopped" else "complete",
                   progress=100, result=summary)
        return summary

    except Exception as exc:
        logger.error("PerfTest | FAILED | app=%s | %s", app_id, exc, exc_info=True)
        try:
            finalize_perf_run(
                run_id=run_id, status="failed",
                total_requests=0, success_count=0, error_count=0,
                aggregates=_aggregates([]), error_message=str(exc),
            )
        except Exception:
            pass
        update_job(job_id, "failed", error=str(exc))
        raise
