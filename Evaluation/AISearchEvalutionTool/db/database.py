from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from config import get_config


def _get_connection() -> sqlite3.Connection:
    cfg = get_config()
    Path(cfg.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(cfg.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    schema = (Path(__file__).parent / "schema.sql").read_text()
    with get_db() as conn:
        conn.executescript(schema)


def insert_source_document(doc: dict[str, Any]) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO source_document
                (doc_id, title, content_hash, content, metadata, sys_content_type, source_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc["doc_id"],
                doc.get("title"),
                doc.get("content_hash"),
                doc.get("content"),
                json.dumps(doc.get("metadata", {})),
                doc.get("sys_content_type"),
                doc.get("source_url"),
            ),
        )


def insert_test_case(tc: dict[str, Any]) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO test_case
                (tc_id, golden_set_version, question, expected_answer, expected_behavior,
                 question_type, difficulty, answer_type, reference_doc_ids,
                 generation_metadata, rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tc["tc_id"],
                tc.get("golden_set_version"),
                tc["question"],
                tc["expected_answer"],
                tc.get("expected_behavior", "ANSWER"),
                tc.get("question_type"),
                tc.get("difficulty"),
                tc.get("answer_type"),
                json.dumps(tc.get("reference_doc_ids", [])),
                json.dumps(tc.get("generation_metadata", {})),
                tc.get("rationale"),
            ),
        )


def insert_agent_scores(scores: dict[str, Any]) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO agent_scores
                (tc_id, clarity, specificity, meaningfulness, answerability,
                 reference_verifiability, answer_uniqueness, decision, primary_concern, rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scores["tc_id"],
                scores.get("clarity"),
                scores.get("specificity"),
                scores.get("meaningfulness"),
                scores.get("answerability"),
                scores.get("reference_verifiability"),
                scores.get("answer_uniqueness"),
                scores.get("decision"),
                scores.get("primary_concern"),
                scores.get("rationale"),
            ),
        )


def create_golden_set(version: str, notes: str = "") -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO golden_set (version, notes) VALUES (?, ?)",
            (version, notes),
        )


def freeze_golden_set(version: str) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE golden_set SET frozen_at = datetime('now') WHERE version = ?",
            (version,),
        )


def create_eval_run(run: dict[str, Any]) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO eval_run
                (run_id, rag_version, judge_model, golden_set_version, trigger, total_cases)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run["run_id"],
                run.get("rag_version", "unknown"),
                run.get("judge_model"),
                run.get("golden_set_version"),
                run.get("trigger", "manual"),
                run.get("total_cases", 0),
            ),
        )


def upsert_eval_result(result: dict[str, Any]) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO eval_result
                (run_id, tc_id, rag_response, retrieved_doc_ids, chunk_signals,
                 scores, failure_category, judge_rationale,
                 latency_llm_ms, latency_retrieval_ms, search_request_id, attempt_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["run_id"],
                result["tc_id"],
                result.get("rag_response"),
                json.dumps(result.get("retrieved_doc_ids", [])),
                json.dumps(result.get("chunk_signals", {})),
                json.dumps(result.get("scores", {})),
                result.get("failure_category"),
                result.get("judge_rationale"),
                result.get("latency_llm_ms"),
                result.get("latency_retrieval_ms"),
                result.get("search_request_id"),
                result.get("attempt_count", 1),
            ),
        )


def finish_eval_run(run_id: str, passed: int, cost: float, status: str = "complete") -> None:
    with get_db() as conn:
        conn.execute(
            """
            UPDATE eval_run
            SET finished_at = datetime('now'), status = ?, passed_cases = ?, cost_usd = ?
            WHERE run_id = ?
            """,
            (status, passed, cost, run_id),
        )


def get_active_test_cases(golden_set_version: str) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT tc.*, s.decision
            FROM test_case tc
            LEFT JOIN agent_scores s ON s.tc_id = tc.tc_id
            WHERE tc.golden_set_version = ?
              AND tc.status = 'active'
              AND (s.decision = 'KEEP' OR s.decision = 'BORDERLINE')
            """,
            (golden_set_version,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_completed_tc_ids(run_id: str) -> set[str]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT tc_id FROM eval_result WHERE run_id = ?", (run_id,)
        ).fetchall()
        return {r["tc_id"] for r in rows}
