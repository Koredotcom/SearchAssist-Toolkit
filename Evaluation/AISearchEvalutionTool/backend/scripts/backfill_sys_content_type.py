"""
Backfill sys_content_type into generation_metadata for existing test cases.

For each test case that has at least one reference_doc_id, this script looks up
sys_content_type from the source_document table and writes it into the test
case's generation_metadata JSON column.

Run from the backend/ directory:
    python scripts/backfill_sys_content_type.py

Supports both SQLite and MongoDB backends (reads config.json / env vars).
"""
from __future__ import annotations

import json
import sys
import os

# Ensure backend package root is on the path when run from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_config

_cfg = get_config().database


def _backfill_sqlite() -> None:
    import sqlite3
    from pathlib import Path

    db_path = _cfg.sqlite_db_path
    print(f"[SQLite] Connecting to {db_path} ...")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    rows = conn.execute(
        "SELECT tc_id, app_id, reference_doc_ids, generation_metadata FROM test_case"
    ).fetchall()

    print(f"[SQLite] Found {len(rows)} test cases to inspect.")

    updated = skipped_no_doc = skipped_already_set = skipped_no_src_type = 0

    for row in rows:
        tc_id = row["tc_id"]
        app_id = row["app_id"]
        ref_ids = json.loads(row["reference_doc_ids"] or "[]")
        metadata = json.loads(row["generation_metadata"] or "{}")

        if metadata.get("sys_content_type"):
            skipped_already_set += 1
            continue

        if not ref_ids:
            skipped_no_doc += 1
            continue

        # Use first reference doc to look up source type
        doc_id = ref_ids[0]
        src_row = conn.execute(
            "SELECT sys_content_type FROM source_document WHERE doc_id = ? AND app_id = ?",
            (doc_id, app_id),
        ).fetchone()

        if not src_row or not src_row["sys_content_type"]:
            skipped_no_src_type += 1
            continue

        metadata["sys_content_type"] = src_row["sys_content_type"]
        conn.execute(
            "UPDATE test_case SET generation_metadata = ? WHERE tc_id = ?",
            (json.dumps(metadata), tc_id),
        )
        updated += 1

    conn.commit()
    conn.close()

    print(f"\n[SQLite] Backfill complete.")
    print(f"  Updated              : {updated}")
    print(f"  Already had type     : {skipped_already_set}")
    print(f"  No reference doc     : {skipped_no_doc}")
    print(f"  Source doc not found : {skipped_no_src_type}")


def _backfill_mongodb() -> None:
    from pymongo import MongoClient

    mongo_uri = _cfg.mongo_uri
    mongo_db  = _cfg.mongo_db
    print(f"[MongoDB] Connecting to {mongo_uri} / db={mongo_db} ...")

    client: MongoClient = MongoClient(mongo_uri)
    db = client[mongo_db]

    test_cases   = db["test_case"]
    source_docs  = db["source_document"]

    all_tcs = list(test_cases.find({}, {"tc_id": 1, "app_id": 1, "reference_doc_ids": 1, "generation_metadata": 1}))
    print(f"[MongoDB] Found {len(all_tcs)} test cases to inspect.")

    updated = skipped_no_doc = skipped_already_set = skipped_no_src_type = 0

    for tc in all_tcs:
        tc_id    = tc.get("tc_id") or str(tc["_id"])
        app_id   = tc.get("app_id", "")
        ref_ids  = tc.get("reference_doc_ids") or []
        metadata = tc.get("generation_metadata") or {}

        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}

        if metadata.get("sys_content_type"):
            skipped_already_set += 1
            continue

        if not ref_ids:
            skipped_no_doc += 1
            continue

        doc_id = ref_ids[0]
        src = source_docs.find_one(
            {"doc_id": doc_id, "app_id": app_id},
            {"sys_content_type": 1},
        )

        if not src or not src.get("sys_content_type"):
            skipped_no_src_type += 1
            continue

        metadata["sys_content_type"] = src["sys_content_type"]
        test_cases.update_one(
            {"_id": tc["_id"]},
            {"$set": {"generation_metadata": metadata}},
        )
        updated += 1

    client.close()

    print(f"\n[MongoDB] Backfill complete.")
    print(f"  Updated              : {updated}")
    print(f"  Already had type     : {skipped_already_set}")
    print(f"  No reference doc     : {skipped_no_doc}")
    print(f"  Source doc not found : {skipped_no_src_type}")


if __name__ == "__main__":
    if _cfg.backend == "mongodb":
        _backfill_mongodb()
    else:
        _backfill_sqlite()
