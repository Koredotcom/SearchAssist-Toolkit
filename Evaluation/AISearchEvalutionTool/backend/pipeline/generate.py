from __future__ import annotations

import logging
import threading
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.generator import generate_test_cases
from agents.ranker import rank_test_cases
from agents.summarizer import summarize_document
from db.database import (
    create_golden_set, insert_agent_scores, insert_test_case,
    upsert_source_document, update_job, is_stop_requested,
)
from koreai.connectors import list_connectors
from koreai.content import fetch_documents
from koreai.search import verify_doc_in_chunks

logger = logging.getLogger(__name__)

MAX_DOC_WORKERS = 3  # parallel document pipelines (Agent 1 + Agent 2 per doc)


def _process_doc(
    doc: dict[str, Any],
    app_id: str,
    golden_set_version: str,
    job_id: str,
    completed_counter: list[int],
    total_docs: int,
    lock: threading.Lock,
    max_questions_per_doc: int = 5,
    target_language: str = "English",
) -> list[dict[str, Any]]:
    """Run Agent 1 + Agent 2 for a single document (runs in a thread)."""
    doc_id = doc.get("doc_id", "?")
    title = doc.get("title", "?")
    logger.info(
        "Pipeline | Processing doc '%s' (id=%s) | max_questions=%d language=%s",
        title, doc_id, max_questions_per_doc, target_language,
    )

    upsert_source_document(doc)
    extraction = summarize_document(doc, app_id)
    raw_cases = generate_test_cases(
        extraction,
        doc,
        app_id,
        max_questions=max_questions_per_doc,
        target_language=target_language,
    )

    for tc in raw_cases:
        tc["golden_set_version"] = golden_set_version
        tc["app_id"] = app_id
        metadata = tc.get("generation_metadata") if isinstance(tc.get("generation_metadata"), dict) else {}
        metadata["target_language"] = target_language
        tc["generation_metadata"] = metadata

    with lock:
        completed_counter[0] += 1
        pct = 15 + int(completed_counter[0] / total_docs * 60)
        logger.info(
            "Pipeline | Doc %d/%d done ('%s') | cases_generated=%d | progress=%d%%",
            completed_counter[0], total_docs, title, len(raw_cases), pct,
        )
        update_job(job_id, "running", progress=pct)

    return raw_cases


def run_generation(
    app: dict,
    golden_set_version: str,
    connector_ids: list[str],
    max_docs_per_source: int,
    max_questions_per_doc: int,
    filters: dict,
    job_id: str,
    web_source_ids: list[str] | None = None,
    file_source_ids: list[str] | None = None,
    target_language: str = "English",
) -> dict[str, Any]:
    app_id = app["app_id"]
    web_source_ids = web_source_ids or []
    file_source_ids = file_source_ids or []
    logger.info(
        "Pipeline | Generation started | app=%s version=%s max_docs=%d max_q_per_doc=%d "
        "language=%s connectors=%s web_sources=%s file_sources=%s",
        app_id, golden_set_version, max_docs_per_source, max_questions_per_doc,
        target_language, connector_ids, web_source_ids, file_source_ids,
    )

    try:
        create_golden_set(app_id, golden_set_version)
        update_job(job_id, "running", progress=5)

        docs: list[dict[str, Any]] = []

        # ── Connectors (existing flow) ────────────────────────────────────────
        # Only enumerate connectors when at least one connector is selected OR
        # the user picked nothing at all (back-compat: empty selection = "all
        # connectors"). When the user explicitly picked only web / file sources
        # we skip the connector enumeration entirely.
        any_explicit_pick = bool(connector_ids or web_source_ids or file_source_ids)
        should_run_connectors = bool(connector_ids) or not any_explicit_pick
        if should_run_connectors:
            all_connectors = list_connectors(app)
            type_map = {c["connector_id"]: c["type"] for c in all_connectors}
            logger.debug("Pipeline | Connector type map: %s", type_map)

            selected = connector_ids if connector_ids else list(type_map.keys())
            logger.info("Pipeline | Selected connectors: %s", selected)

            seen_types: set[str] = set()
            for cid in selected:
                ext_type = type_map.get(cid)
                if ext_type in seen_types:
                    logger.debug(
                        "Pipeline | Skipping connector %s — extractionType '%s' already fetched",
                        cid, ext_type,
                    )
                    continue
                seen_types.add(ext_type)
                connector_docs = list(fetch_documents(
                    app, filters=filters,
                    extraction_type=ext_type,
                    max_docs=max_docs_per_source,
                ))
                logger.info(
                    "Pipeline | Connector %s (type=%s) → %d docs",
                    cid, ext_type, len(connector_docs),
                )
                docs.extend(connector_docs)

        # ── Web crawls (sys_content_type='web', scoped by extractionSourceId) ──
        for src_id in web_source_ids:
            # Kore.ai's content condition API filters only trained index fields.
            # extractionSourceId is returned as top-level metadata, so fetch web
            # records by sys_content_type and apply the source-id match client-side.
            web_filters = {**filters, "sys_content_type": "web"}
            web_docs = list(fetch_documents(
                app, filters=web_filters,
                extraction_type=None,
                source_id=src_id,
                max_docs=max_docs_per_source,
            ))
            logger.info("Pipeline | Web source %s → %d pages", src_id, len(web_docs))
            docs.extend(web_docs)

        # ── Uploaded files (sys_content_type='file', scoped by extractionSourceId) ──
        for src_id in file_source_ids:
            file_filters = {**filters, "sys_content_type": "file"}
            file_docs = list(fetch_documents(
                app, filters=file_filters,
                extraction_type=None,
                source_id=src_id,
                max_docs=max_docs_per_source,
            ))
            logger.info("Pipeline | File source %s → %d documents", src_id, len(file_docs))
            docs.extend(file_docs)

        logger.info("Pipeline | Total documents fetched: %d", len(docs))
        update_job(job_id, "running", progress=10)

        if not docs:
            logger.warning("Pipeline | No documents found — aborting generation")
            update_job(
                job_id, "failed",
                error="No documents returned from the selected Kore.ai sources "
                      "(connectors / web crawls / uploaded files).",
            )
            return {}

        # ── Chunk verification ────────────────────────────────────────────────
        # Verify each document is actually indexed in the chunks API before
        # spending Agent 1+2 budget on it.  Docs not found in chunks are skipped.
        logger.info("Pipeline | Verifying %d docs are present in chunks API…", len(docs))
        valid_docs: list[dict[str, Any]] = []
        skipped_docs: list[dict[str, Any]] = []

        for doc in docs:
            doc_id = doc.get("doc_id", "?")
            title = doc.get("title", "?")
            if verify_doc_in_chunks(app, doc_id, title):
                valid_docs.append(doc)
            else:
                logger.warning(
                    "Pipeline | SKIP '%s' (id=%s) — not found in chunks API", title, doc_id,
                )
                skipped_docs.append({"doc_id": doc_id, "title": title})

        logger.info(
            "Pipeline | Chunk verify done | valid=%d skipped=%d",
            len(valid_docs), len(skipped_docs),
        )
        update_job(job_id, "running", progress=15)

        if not valid_docs:
            msg = (
                f"All {len(docs)} documents were skipped — none found in the chunks API. "
                "Ensure the documents are fully indexed in Kore.ai before generating."
            )
            logger.warning("Pipeline | %s", msg)
            update_job(
                job_id, "failed", error=msg,
                result={
                    "docs_skipped_no_chunks": len(skipped_docs),
                    "skipped_docs": skipped_docs,
                },
            )
            return {}

        # Process documents in parallel (Agent 1 + Agent 2 per doc)
        all_raw: list[dict[str, Any]] = []
        completed_counter = [0]
        lock = threading.Lock()

        stopped_early = False
        logger.info("Pipeline | Starting parallel doc processing (%d workers)", MAX_DOC_WORKERS)
        with ThreadPoolExecutor(max_workers=MAX_DOC_WORKERS) as executor:
            futures = {
                executor.submit(
                    _process_doc, doc, app_id, golden_set_version,
                    job_id, completed_counter, len(valid_docs), lock,
                    max_questions_per_doc, target_language,
                ): doc
                for doc in valid_docs
            }
            for future in as_completed(futures):
                if is_stop_requested(job_id):
                    logger.info("Pipeline | Stop requested — cancelling remaining futures")
                    stopped_early = True
                    for f in futures:
                        f.cancel()
                    break
                try:
                    all_raw.extend(future.result())
                except Exception as exc:
                    logger.error("Pipeline | Doc processing thread FAILED | error: %s", exc, exc_info=True)

        logger.info("Pipeline | All docs processed | total_raw_cases=%d", len(all_raw))

        # Rank all generated cases (Agent 3) — batches run in parallel internally
        update_job(job_id, "running", progress=80)
        logger.info("Pipeline | Starting Agent 3 ranking for %d cases", len(all_raw))
        scored = rank_test_cases(all_raw, app_id)
        score_map = {s["tc_id"]: s for s in scored}
        logger.info("Pipeline | Agent 3 scoring complete | scored=%d", len(scored))

        kept = borderline = dropped = 0
        for tc in all_raw:
            score = score_map.get(tc["tc_id"], {})
            decision = score.get("decision", "DROP")
            if decision in ("KEEP", "BORDERLINE"):
                insert_test_case(tc)
                insert_agent_scores({**score, "tc_id": tc["tc_id"]})
                if decision == "KEEP":
                    kept += 1
                else:
                    borderline += 1
            else:
                dropped += 1

        result = {
            "kept": kept, "borderline": borderline, "dropped": dropped,
            "total_raw": len(all_raw), "docs_processed": len(valid_docs),
            "docs_skipped_no_chunks": len(skipped_docs),
            "skipped_docs": skipped_docs,
            "stopped_early": stopped_early,
        }
        logger.info(
            "Pipeline | Generation %s | docs=%d skipped=%d raw=%d kept=%d borderline=%d dropped=%d",
            "STOPPED" if stopped_early else "COMPLETE",
            len(valid_docs), len(skipped_docs), len(all_raw), kept, borderline, dropped,
        )
        update_job(job_id, "complete", progress=100, result=result)
        return result

    except Exception as exc:
        logger.error("Pipeline | Generation FAILED | app=%s | error: %s", app_id, exc, exc_info=True)
        update_job(job_id, "failed", error=str(exc))
        raise
