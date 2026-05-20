from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from pymongo import ASCENDING, MongoClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import get_config  # noqa: E402


COLLECTIONS = [
    "app_config", "llm_config", "prompt_config", "source_document",
    "golden_set", "test_case", "agent_scores", "job", "eval_run", "eval_result",
]

JSON_FIELDS = {
    "app_config": {"racl_entity_ids": [], "banned_topics": []},
    "source_document": {"metadata": {}},
    "test_case": {"reference_doc_ids": [], "reference_match_spec": [], "generation_metadata": {}},
    "job": {"result": None},
    "eval_run": {"diagnostics_json": None, "fired_rule_ids": None},
    "eval_result": {
        "retrieved_doc_ids": [],
        "chunk_signals": [],
        "scores": {},
        "search_payload": {},
        "recall_at_k": {},
    },
}

KEYS = {
    "app_config": ("app_id",),
    "llm_config": ("app_id", "agent_name"),
    "prompt_config": ("id",),
    "source_document": ("doc_id", "app_id"),
    "golden_set": ("version", "app_id"),
    "test_case": ("tc_id",),
    "agent_scores": ("tc_id",),
    "job": ("job_id",),
    "eval_run": ("run_id",),
    "eval_result": ("run_id", "tc_id"),
}


def _decode(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _read_table(conn: sqlite3.Connection, table: str) -> list[dict]:
    try:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    except sqlite3.OperationalError:
        return []
    result = []
    for row in rows:
        doc = dict(row)
        for field, default in JSON_FIELDS.get(table, {}).items():
            if field in doc:
                doc[field] = _decode(doc[field], default)
        if "is_active" in doc:
            doc["is_active"] = bool(doc["is_active"])
        if "human_validated" in doc:
            doc["human_validated"] = bool(doc["human_validated"])
        if "stop_requested" in doc:
            doc["stop_requested"] = bool(doc["stop_requested"])
        result.append(doc)
    return result


def _ensure_indexes(db) -> None:
    db.app_config.create_index([("app_id", ASCENDING)], unique=True)
    db.llm_config.create_index([("app_id", ASCENDING), ("agent_name", ASCENDING)], unique=True)
    db.prompt_config.create_index([("id", ASCENDING)], unique=True)
    db.source_document.create_index([("doc_id", ASCENDING), ("app_id", ASCENDING)], unique=True)
    db.golden_set.create_index([("version", ASCENDING), ("app_id", ASCENDING)], unique=True)
    db.test_case.create_index([("tc_id", ASCENDING)], unique=True)
    db.agent_scores.create_index([("tc_id", ASCENDING)], unique=True)
    db.job.create_index([("job_id", ASCENDING)], unique=True)
    db.eval_run.create_index([("run_id", ASCENDING)], unique=True)
    db.eval_result.create_index([("run_id", ASCENDING), ("tc_id", ASCENDING)], unique=True)


def migrate(sqlite_path: Path, mongo_uri: str, mongo_db: str, dry_run: bool) -> None:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")

    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
    db = client[mongo_db]

    if not dry_run:
        _ensure_indexes(db)

    print(f"SQLite: {sqlite_path}")
    print(f"MongoDB: {mongo_uri}/{mongo_db}")
    print(f"Mode: {'dry-run' if dry_run else 'write'}")

    for table in COLLECTIONS:
        docs = _read_table(conn, table)
        print(f"{table}: {len(docs)} row(s)")
        if dry_run:
            continue
        key_fields = KEYS[table]
        coll = db[table]
        for doc in docs:
            query = {field: doc[field] for field in key_fields}
            coll.update_one(query, {"$set": doc}, upsert=True)

    conn.close()
    client.close()


def main() -> None:
    cfg = get_config().database
    parser = argparse.ArgumentParser(description="Migrate AISearch evaluator SQLite data into MongoDB.")
    parser.add_argument("--sqlite-path", default=str(cfg.sqlite_db_path))
    parser.add_argument("--mongo-uri", default=cfg.mongodb_uri)
    parser.add_argument("--mongo-db", default=cfg.mongodb_database)
    parser.add_argument("--dry-run", action="store_true", help="Print counts without writing to MongoDB.")
    args = parser.parse_args()
    migrate(Path(args.sqlite_path), args.mongo_uri, args.mongo_db, args.dry_run)


if __name__ == "__main__":
    main()
