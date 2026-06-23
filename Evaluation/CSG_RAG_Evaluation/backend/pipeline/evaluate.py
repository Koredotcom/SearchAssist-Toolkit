from __future__ import annotations

import builtins
import json
import logging
import random
import subprocess
import threading
import time
import uuid
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.filter_generator import build_source_filter, generate_meta_filters
from db.database import (
    create_eval_run, finish_eval_run, get_active_test_cases,
    get_completed_tc_ids, get_doc_source_type, get_eval_thresholds,
    is_stop_requested, update_job, upsert_eval_result,
)
from judge.judge import judge_result
from judge.metrics import (
    answer_similarity, chunks_matched_by_spec, derive_verdict, detect_case,
    expected_doc_rank, first_matched_chunk, first_matched_chunk_rank,
    judge_configured, qualified_chunks_count, question_answer_relevance,
    recall_at_k,
)
from koreai.search import RagApiTimeoutError, query_rag

logger = logging.getLogger(__name__)


# Safe built-ins for Python filter/mapper scripts — no file I/O, no __import__
_SCRIPT_SAFE_BUILTINS = {
    k: getattr(builtins, k) for k in (
        "abs", "all", "any", "bool", "dict", "enumerate", "filter",
        "float", "int", "isinstance", "len", "list", "map", "max",
        "min", "range", "reversed", "set", "sorted", "str", "sum",
        "tuple", "type", "zip", "print", "True", "False", "None",
    ) if hasattr(builtins, k)
}


def _normalize_filters(raw: list) -> list[dict]:
    """Accept either simple [{field, value}] or full Kore.ai metaFilters format.

    Simple format is automatically promoted to Kore.ai format:
      {"field": "sys_content_type", "value": "jiraServer"}
      → {"condition": "AND", "rules": [{"fieldName": ..., "fieldValue": [...], "operator": "equals"}]}
    """
    if not raw or not isinstance(raw, list):
        return []
    # Already Kore.ai native (has 'condition' key)
    if isinstance(raw[0], dict) and "condition" in raw[0]:
        return raw
    # Simple {field, value} → Kore.ai AND group
    result = []
    for f in raw:
        if isinstance(f, dict) and f.get("field") and f.get("value") is not None:
            result.append({
                "condition": "AND",
                "rules": [{"fieldName": f["field"], "fieldValue": [str(f["value"])], "operator": "equals"}],
            })
    return result


def exec_filter_script(
    script: str,
    lang: str,
    input_text: str,
    py_func_names: tuple[str, ...] = ("get_filters", "map_response"),
    js_func_names: tuple[str, ...] = ("getFilters", "mapResponse"),
    timeout: float = 5.0,
) -> list[dict]:
    """Execute a user-provided filter/mapper script and return normalized metaFilters.

    ``input_text`` is passed to the script function as its sole argument —
    either the original question (filter mode) or the raw LLM response (mapper mode).

    Python runs in a restricted exec() sandbox with the ``json`` module available.
    JS runs in a Node.js subprocess.
    Output is normalized: simple [{field, value}] is promoted to Kore.ai format.
    """
    if lang == "python":
        import json as _json_mod  # safe stdlib module; exposed to script namespace

        def _run_python() -> list:
            ns: dict = {
                "__builtins__": _SCRIPT_SAFE_BUILTINS,
                "json": _json_mod,
            }
            exec(compile(script, "<filter_script>", "exec"), ns)  # noqa: S102
            fn = None
            for name in py_func_names:
                fn = ns.get(name)
                if fn is not None:
                    break
            if fn is None:
                raise ValueError(
                    f"Script must define one of: {', '.join(py_func_names + ('(takes one str arg)',))}"
                )
            result = fn(input_text)
            if not isinstance(result, list):
                raise TypeError(f"Script function must return a list, got {type(result).__name__}")
            return result

        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_run_python)
            try:
                raw = fut.result(timeout=timeout)
            except TimeoutError:
                raise TimeoutError(f"Python script timed out after {timeout}s")
        return _normalize_filters(raw)

    if lang == "js":
        # Build JS runner: try each candidate function name
        fn_checks = " || ".join(f'typeof {n} === "function"' for n in js_func_names)
        fn_call = " || ".join(f'(typeof {n} === "function" && {n})' for n in js_func_names)
        runner = (
            f"{script}\n"
            f"const _fn = {fn_call};\n"
            f"if (!_fn) throw new Error('Script must define one of: {', '.join(js_func_names)}');\n"
            f"process.stdout.write(JSON.stringify(_fn({json.dumps(input_text)})));\n"
        )
        try:
            proc = subprocess.run(
                ["node", "-e", runner],
                capture_output=True, text=True, timeout=timeout,
            )
        except FileNotFoundError:
            raise RuntimeError("Node.js is not installed. Install Node.js to run JS filter scripts.")
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"JS script timed out after {timeout}s")
        if proc.returncode != 0:
            raise ValueError(proc.stderr.strip() or "JS execution error")
        return _normalize_filters(json.loads(proc.stdout))

    raise ValueError(f"Unknown script language: {lang}")
MAX_EVAL_WORKERS = 1  # sequential — one query at a time
# First entry is delay before retry-1, second is delay before retry-2.
RETRY_DELAYS = [6, 6]
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1  # 3 total: first try + 2 retries


def run_evaluation(
    app: dict,
    golden_set_version: str,
    rag_version: str,
    job_id: str,
    max_cases: int | None = None,
    sample_mode: str = "first",
    filter_mode: str = "none",
    filter_prompt: str | None = None,
    enable_racl: bool = False,
    user_email: str | None = None,
    answer_mode_override: str | None = None,
    question_types: list[str] | None = None,
    racl_entity_ids_override: list[str] | None = None,
) -> dict[str, Any]:
    # Apply per-run overrides onto a shallow copy of app so the DB record is unchanged
    overrides: dict = {}
    if answer_mode_override:
        overrides["answer_mode"] = answer_mode_override
    if racl_entity_ids_override is not None:
        overrides["racl_entity_ids"] = racl_entity_ids_override
    if overrides:
        app = {**app, **overrides}

    app_id = app["app_id"]
    run_id = f"run-{uuid.uuid4()}"

    logger.info(
        "Eval | Starting evaluation | app=%s version=%s rag_version=%s run_id=%s "
        "max_cases=%s sample_mode=%s filter_mode=%s racl=%s answer_mode=%s",
        app_id, golden_set_version, rag_version, run_id,
        max_cases, sample_mode, filter_mode, enable_racl, app.get("answer_mode"),
    )

    try:
        test_cases = get_active_test_cases(app_id, golden_set_version)
        if not test_cases:
            logger.warning("Eval | No active test cases found | app=%s version=%s", app_id, golden_set_version)
            update_job(job_id, "failed", error="No active test cases found.")
            return {}

        logger.info("Eval | Loaded %d test cases from golden set", len(test_cases))

        # Filter by question types if specified
        if question_types:
            before = len(test_cases)
            test_cases = [tc for tc in test_cases if tc.get("question_type") in question_types]
            logger.info("Eval | Question type filter %s → %d / %d cases", question_types, len(test_cases), before)
            if not test_cases:
                update_job(job_id, "failed", error=f"No test cases match question types: {question_types}")
                return {}

        # Apply case limit with optional random sampling
        if max_cases and max_cases < len(test_cases):
            if sample_mode == "random":
                test_cases = random.sample(test_cases, max_cases)
                logger.info("Eval | Random sample: %d / %d cases selected", max_cases, len(test_cases) + max_cases)
            else:
                test_cases = test_cases[:max_cases]
                logger.info("Eval | Taking first %d cases", max_cases)
        else:
            logger.info("Eval | Running all %d cases", len(test_cases))

        effective_answer_mode = answer_mode_override or app.get("answer_mode", "answer_generation")
        effective_racl = racl_entity_ids_override if racl_entity_ids_override is not None else (app.get("racl_entity_ids") or [])
        effective_identity = user_email or app.get("identity", "")
        create_eval_run({
            "run_id": run_id, "app_id": app_id, "rag_version": rag_version,
            "judge_model": None, "golden_set_version": golden_set_version,
            "trigger": "manual", "total_cases": len(test_cases),
            "identity": effective_identity,
            "racl_entity_ids": effective_racl,
            "answer_mode": effective_answer_mode,
        })
        update_job(job_id, "running", progress=5)

        completed = get_completed_tc_ids(run_id)
        remaining = [tc for tc in test_cases if tc["tc_id"] not in completed]
        passed = len(completed)

        logger.info(
            "Eval | run_id=%s | total=%d already_done=%d remaining=%d | workers=%d",
            run_id, len(test_cases), len(completed), len(remaining), MAX_EVAL_WORKERS,
        )

        completed_counter = [0]
        verdicted_counter = [0]
        chunk_ranks: list[int] = []
        lock = threading.Lock()
        stopped_early = False

        racl_user = user_email if enable_racl else None

        def _run_one(tc: dict) -> tuple[dict | None, dict]:
            meta_filters = _resolve_meta_filters(
                tc=tc,
                app_id=app_id,
                filter_mode=filter_mode,
                filter_prompt=filter_prompt,
            )
            return _evaluate_one(
                run_id, tc, app,
                meta_filters=meta_filters,
                user_email=racl_user,
            ), tc

        executor = ThreadPoolExecutor(max_workers=MAX_EVAL_WORKERS)
        try:
            futures = {executor.submit(_run_one, tc): tc for tc in remaining}
            for future in as_completed(futures):
                tc = futures[future]
                try:
                    result, _ = future.result()
                except Exception as exc:
                    logger.error("Eval | Unexpected error for tc_id=%s | %s", tc["tc_id"], exc, exc_info=True)
                    result = None

                with lock:
                    completed_counter[0] += 1
                    done = completed_counter[0]
                    pct = 5 + int(done / len(remaining) * 90)

                if result:
                    scores = result.get("scores", {})
                    verdict = result.get("verdict")  # 'pass' | 'fail' | None
                    is_pass = verdict == "pass"
                    cr = scores.get("chunk_rank")
                    with lock:
                        if is_pass:
                            passed += 1
                        if verdict in ("pass", "fail"):
                            verdicted_counter[0] += 1
                        if isinstance(cr, int):
                            chunk_ranks.append(cr)
                    upsert_eval_result(result)
                    logger.info(
                        "Eval | %d/%d %s | tc_id=%s case=%s source=%s failure=%s",
                        done, len(remaining),
                        verdict.upper() if verdict else "N/A",
                        tc["tc_id"],
                        result.get("case_id"),
                        result.get("verdict_source"),
                        result.get("failure_category", "?"),
                    )
                else:
                    logger.warning(
                        "Eval | %d/%d SKIPPED (retries exhausted) | tc_id=%s",
                        done, len(remaining), tc["tc_id"],
                    )

                # Check stop AFTER saving the completed result so it's not lost
                if is_stop_requested(job_id):
                    logger.info("Eval | Stop requested — cancelling queued futures | run_id=%s", run_id)
                    for f in futures:
                        f.cancel()
                    # Don't wait for already-running workers — they'll finish naturally
                    executor.shutdown(wait=False)
                    stopped_early = True
                    break

                update_job(job_id, "running", progress=pct, result={
                    "done": completed_counter[0],
                    "total": len(remaining),
                    "passed": passed,
                    "verdicted": verdicted_counter[0],
                })
        finally:
            executor.shutdown(wait=False)

        total = len(test_cases)
        verdicted = verdicted_counter[0]
        denominator = verdicted if verdicted > 0 else total
        pass_rate = (passed / denominator) if denominator else 0.0

        final_status = "partial" if stopped_early else "complete"
        logger.info(
            "Eval | %s | run_id=%s total=%d done=%d passed=%d verdicted=%d pass_rate=%.2f%%",
            final_status.upper(), run_id, total,
            completed_counter[0], passed, verdicted, pass_rate * 100,
        )

        avg_chunk_rank = round(sum(chunk_ranks) / len(chunk_ranks), 1) if chunk_ranks else None
        finish_eval_run(
            run_id, passed=passed, cost=0.0,
            avg_chunk_rank=avg_chunk_rank,
            status=final_status,
            verdicted=verdicted,
        )

        # ── Phase 2: compute diagnostics + fire rules ────────────────────────
        # Best-effort — failures here should not mask a completed eval.
        try:
            from diagnostics.compute import compute_and_store_diagnostics
            compute_and_store_diagnostics(run_id)
        except Exception as diag_exc:
            logger.warning(
                "Eval | Diagnostics compute failed (non-fatal) | run_id=%s | %s",
                run_id, diag_exc, exc_info=True,
            )

        result_summary = {
            "run_id": run_id,
            "total": total,
            "done": completed_counter[0],
            "passed": passed,
            "verdicted": verdicted,
            "pass_rate": round(pass_rate, 4),
            "stopped_early": stopped_early,
        }
        update_job(job_id, final_status, progress=100 if not stopped_early else 5 + int(completed_counter[0] / max(len(remaining), 1) * 90), result=result_summary)
        return result_summary

    except Exception as exc:
        logger.error("Eval | FAILED | app=%s run_id=%s | error: %s", app_id, run_id, exc, exc_info=True)
        update_job(job_id, "failed", error=str(exc))
        raise


def _resolve_meta_filters(
    tc: dict,
    app_id: str,
    filter_mode: str,
    filter_prompt: str | None,
) -> list[dict]:
    """Resolve metaFilters for a single test case based on the configured mode.

    Priority:
      1. auto_source  — look up sys_content_type from source_document table
      2. custom_prompt — LLM-generated filters from question
      3. per-row      — sys_content_type stored in the test case's generation_metadata
                        (set when the Excel sheet has a sys_content_type column)
    """
    if filter_mode == "auto_source":
        ref_docs = tc.get("reference_doc_ids") or []
        if ref_docs:
            sys_type = get_doc_source_type(app_id, ref_docs[0])
            if sys_type:
                logger.debug("Eval | tc=%s auto source filter: sys_content_type=%s", tc["tc_id"], sys_type)
                return build_source_filter(sys_type)
            logger.debug("Eval | tc=%s could not resolve sys_content_type for doc=%s", tc["tc_id"], ref_docs[0])
        # No doc_id — fall back to per-row sys_content_type from generation_metadata
        meta = tc.get("generation_metadata") or {}
        sys_type = meta.get("sys_content_type")
        if sys_type:
            logger.debug("Eval | tc=%s auto_source fallback to per-row sys_content_type=%s", tc["tc_id"], sys_type)
            return build_source_filter(sys_type)
        logger.debug("Eval | tc=%s has no reference docs and no per-row sys_content_type — no source filter", tc["tc_id"])
        return []

    if filter_mode == "custom_prompt":
        return generate_meta_filters(tc["question"], app_id)

    # Per-row filter: sys_content_type column from the uploaded Excel/CSV
    meta = tc.get("generation_metadata") or {}
    sys_type = meta.get("sys_content_type")
    if sys_type:
        logger.debug("Eval | tc=%s per-row sys_content_type filter: %s", tc["tc_id"], sys_type)
        return build_source_filter(sys_type)

    return []


def _evaluate_one(
    run_id: str,
    tc: dict,
    app: dict,
    meta_filters: list[dict] | None = None,
    user_email: str | None = None,
) -> dict | None:
    expected_behavior = tc.get("expected_behavior", "ANSWER")
    banned_topics = app.get("banned_topics") or []
    tc_id = tc["tc_id"]

    # Match spec drives chunk matching; reference_doc_ids is the legacy fallback
    match_spec = tc.get("reference_match_spec") or []
    legacy_ref_ids = tc.get("reference_doc_ids") or []
    if not match_spec and legacy_ref_ids:
        match_spec = [{"field": "doc_id", "value": d} for d in legacy_ref_ids]

    case_id = detect_case(tc)
    has_judge = judge_configured(app)
    thresholds = get_eval_thresholds(app["app_id"])

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.debug("Eval | Querying RAG | tc_id=%s attempt=%d case=%d judge=%s",
                         tc_id, attempt, case_id, has_judge)
            rag = query_rag(app, tc["question"], meta_filters=meta_filters, user_email=user_email)

            retrieved_ids = rag.get("cited_doc_ids") or []
            rag_answer = rag.get("answer") or ""
            chunks = rag.get("chunk_signals", []) or []
            # False when the API returns only retrieved chunks (no LLM-generated answer).
            # In that case all answer-quality paths (judge, similarity, qa_relevance) are skipped.
            has_llm_answer: bool = rag.get("has_llm_answer", True)

            # Resolve which retrieved docs satisfy the match spec.
            # Supports doc_id and recordTitle fields — never uses internal docId UUIDs.
            effective_ref_ids = chunks_matched_by_spec(chunks, match_spec) if match_spec else []
            # Fallback if there are no chunks: use direct doc_id values from the spec
            if not effective_ref_ids and match_spec:
                effective_ref_ids = [r["value"] for r in match_spec if r.get("field") == "doc_id"]

            # ── Non-LLM metrics — always computed ───────────────────────────
            rank = expected_doc_rank(retrieved_ids, effective_ref_ids)
            chunk_rank = first_matched_chunk_rank(chunks, match_spec) if match_spec else None
            # When the expected doc wasn't found in chunks (effective_ref_ids empty)
            # but a match_spec exists, record all-zero recall so the row counts as
            # a miss in the denominator rather than being excluded entirely.
            if effective_ref_ids:
                recall = recall_at_k(retrieved_ids, effective_ref_ids)
            elif match_spec:
                from judge.metrics import RECALL_K_LEVELS
                recall = {str(k): 0 for k in RECALL_K_LEVELS}
            else:
                recall = {}
            # Retrieval scoring signals (per-chunk)
            qualified_count = qualified_chunks_count(chunks)
            matched_chunk = first_matched_chunk(chunks, match_spec) if match_spec else None
            matched_scores = {
                "vector":     (matched_chunk or {}).get("vector_score"),
                "keyword":    (matched_chunk or {}).get("keyword_score"),
                "positional": (matched_chunk or {}).get("positional_score"),
                "combined":   (matched_chunk or {}).get("score"),
            } if matched_chunk else {}

            _answer_mode = app.get("answer_mode", "answer_generation")

            # ── Answer-quality metrics — only when an LLM answer exists ─────
            # When has_llm_answer=False (Agent Platform) these are all None so
            # verdict derivation falls back to pure retrieval metrics.
            similarity: float | None = None
            qa_relevance: float | None = None
            judge_scores: dict | None = None
            failure_category: str | None = None
            judge_rationale: str | None = None

            if has_llm_answer:
                similarity = (
                    answer_similarity(rag_answer, tc.get("expected_answer"))
                    if tc.get("expected_answer") else None
                )
                # Q↔Answer relevance — used for Cases 1 & 3 without a judge
                qa_relevance = (
                    question_answer_relevance(tc.get("question"), rag_answer)
                    if (not has_judge and _answer_mode == "answer_generation" and case_id in (1, 3))
                    else None
                )
                if has_judge:
                    logger.debug("Eval | Running judge | tc_id=%s attempt=%d", tc_id, attempt)
                    verdict_obj = judge_result(
                        question=tc["question"],
                        expected_answer=tc.get("expected_answer") or "",
                        expected_behavior=expected_behavior,
                        rag_response=rag_answer,
                        retrieved_doc_ids=retrieved_ids,
                        reference_doc_ids=effective_ref_ids,
                        app_id=app["app_id"],
                        banned_topics=banned_topics,
                    )
                    judge_scores     = verdict_obj["scores"]
                    failure_category = verdict_obj["failure_category"]
                    judge_rationale  = verdict_obj["judge_rationale"]
            else:
                logger.debug(
                    "Eval | No LLM answer from API — skipping judge/similarity/qa_relevance | tc_id=%s",
                    tc_id,
                )

            # When there's no LLM answer, force retrieval-only verdict regardless
            # of what answer_mode the app is configured with.
            effective_answer_mode = _answer_mode if has_llm_answer else "extract_only"

            verdict, verdict_source = derive_verdict(
                case_id=case_id, has_judge=has_judge and has_llm_answer,
                judge_scores=judge_scores,
                expected_doc_rank_val=rank, similarity=similarity,
                qa_relevance=qa_relevance,
                case1_threshold=thresholds["case1_threshold"],
                case2_threshold=thresholds["case2_threshold"],
                chunk_rank=chunk_rank,
                answer_mode=effective_answer_mode,
            )

            # Compose stored "scores" payload — includes legacy fields the UI uses
            scores: dict = dict(judge_scores or {})
            scores.setdefault("doc_retrieved", bool(rank))
            scores["answer_mode"] = effective_answer_mode
            scores["has_llm_answer"] = has_llm_answer
            scores["chunk_rank"]  = chunk_rank
            scores["qualified_chunks_count"] = qualified_count
            if matched_chunk:
                scores["matched_vector_score"]     = matched_scores.get("vector")
                scores["matched_keyword_score"]    = matched_scores.get("keyword")
                scores["matched_positional_score"] = matched_scores.get("positional")
                scores["matched_combined_score"]   = matched_scores.get("combined")
                # Per-chunk lifecycle flags for the expected-document chunk
                scores["matched_chunk_qualified"]      = matched_chunk.get("chunkQualified")
                scores["matched_chunk_sent_to_llm"]    = matched_chunk.get("sentToLLM")
                scores["matched_chunk_used_in_answer"] = matched_chunk.get("usedInAnswer")

            if not (has_judge and has_llm_answer) and failure_category is None:
                if effective_answer_mode == "extract_only" and case_id in (3, 4):
                    failure_category = "retrieval_miss" if not rank else "none"
                elif case_id in (1, 3):
                    # Q↔Answer relevance proxy
                    if qa_relevance is not None and qa_relevance < thresholds["case1_threshold"]:
                        failure_category = "off_topic"
                    else:
                        failure_category = "none"
                elif case_id in (2, 4):
                    # Answer↔Expected similarity
                    if similarity is not None and similarity < thresholds["case2_threshold"]:
                        failure_category = "low_similarity"
                    else:
                        failure_category = "none"
                else:
                    failure_category = "none"

            # For Case 1 (no expected answer) the "similarity" field carries
            # the Q↔Answer relevance score instead.
            stored_similarity = similarity if similarity is not None else qa_relevance

            return {
                "run_id": run_id, "tc_id": tc_id,
                "rag_response": rag_answer,
                "retrieved_doc_ids": retrieved_ids,
                "chunk_signals": chunks,
                "scores": scores,
                "failure_category": failure_category,
                "judge_rationale": judge_rationale,
                "latency_llm_ms": rag.get("latency_llm_ms"),
                "latency_retrieval_ms": rag.get("latency_retrieval_ms"),
                "search_request_id": rag.get("search_request_id"),
                "search_payload": rag.get("search_payload"),
                "attempt_count": attempt,
                # 4-case fields
                "case_id": case_id,
                "expected_doc_rank": rank,
                "recall_at_k": recall,
                "answer_similarity": stored_similarity,
                "verdict": verdict,
                "verdict_source": verdict_source,
            }

        except RagApiTimeoutError as exc:
            logger.warning(
                "Eval | API timeout attempt %d/%d | tc_id=%s",
                attempt, MAX_ATTEMPTS, tc_id,
            )
            if attempt < MAX_ATTEMPTS:
                delay = RETRY_DELAYS[attempt - 1]
                logger.debug("Eval | Retrying in %ds | tc_id=%s", delay, tc_id)
                time.sleep(delay)
            else:
                logger.error(
                    "Eval | All retries exhausted (timeout) | tc_id=%s — recording api_timeout failure",
                    tc_id,
                )
                return _timeout_result(run_id, tc_id, case_id, str(exc))

        except Exception as exc:
            logger.warning(
                "Eval | Attempt %d/%d failed | tc_id=%s | error: %s",
                attempt, MAX_ATTEMPTS, tc_id, exc,
            )
            if attempt < MAX_ATTEMPTS:
                delay = RETRY_DELAYS[attempt - 1]
                logger.debug("Eval | Retrying in %ds | tc_id=%s", delay, tc_id)
                time.sleep(delay)
            else:
                logger.error(
                    "Eval | All %d attempts exhausted | tc_id=%s | last error: %s",
                    MAX_ATTEMPTS, tc_id, exc, exc_info=True,
                )

    return None


def _timeout_result(run_id: str, tc_id: str, case_id: int, reason: str) -> dict:
    """Minimal stored result for a test case that exhausted API timeout retries."""
    return {
        "run_id": run_id, "tc_id": tc_id,
        "rag_response": None,
        "retrieved_doc_ids": [],
        "chunk_signals": [],
        "scores": {"doc_retrieved": False, "has_llm_answer": False},
        "failure_category": "api_timeout",
        "judge_rationale": reason,
        "latency_llm_ms": None,
        "latency_retrieval_ms": None,
        "search_request_id": None,
        "search_payload": None,
        "attempt_count": MAX_ATTEMPTS,
        "case_id": case_id,
        "expected_doc_rank": None,
        "recall_at_k": {},
        "answer_similarity": None,
        "verdict": "fail",
        "verdict_source": "api_timeout",
    }


def _is_pass(scores: dict, expected_behavior: str = "ANSWER") -> bool:
    """Pass criteria for the new 11-metric judge output.

    Pass requires:
      - the correct document is retrieved
      - groundedness >= 4
      - query_relevance >= 4
      - ground_truth_relevance >= 3
      - completeness >= 3
      - NO safety violation (toxicity / bias / banned topic)
    """
    if scores.get("toxicity_detected") or scores.get("bias_detected") or scores.get("banned_topic_violation"):
        return False
    return (
        scores.get("doc_retrieved", False)
        and (scores.get("groundedness") or 0) >= 4
        and (scores.get("query_relevance") or 0) >= 4
        and (scores.get("ground_truth_relevance") or 0) >= 3
        and (scores.get("completeness") or 0) >= 3
    )
