from __future__ import annotations

import csv
import hashlib
import os

from db.database import create_golden_set, insert_agent_scores_keep, insert_test_case


def run_import_gt_pipeline(
    gt_paths: list[str], golden_set_version: str, notes: str = ""
) -> dict:
    """Import externally-generated ground truth CSVs into the golden set."""
    create_golden_set(golden_set_version, notes)

    total_count = 0
    for path in gt_paths:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                query = (row.get("Query") or "").strip()
                expected_answer = (row.get("expected_answer") or "").strip()
                if not query or not expected_answer:
                    continue
                doc_id_raw = row.get("doc_id", "").strip()
                tc_id = (
                    "gt-"
                    + hashlib.sha256(
                        (golden_set_version + query + doc_id_raw).encode()
                    ).hexdigest()[:16]
                )
                tc_dict = {
                    "tc_id": tc_id,
                    "question": query,
                    "expected_answer": expected_answer,
                    "expected_behavior": "ANSWER",
                    "question_type": row.get("query_category", "").strip(),
                    "difficulty": 2,
                    "answer_type": "EXTRACTIVE",
                    "reference_doc_ids": [doc_id_raw] if doc_id_raw else [],
                    "reference_title": row.get("Expected Record Title", "").strip() or None,
                    "generation_metadata": {
                        "source": row.get("Expected Source", "").strip(),
                        "source_name": row.get("source name", "").strip(),
                        "subtype": row.get("subtype", "").strip(),
                        "gt_file": os.path.basename(path),
                    },
                    "golden_set_version": golden_set_version,
                    "rationale": f"Imported from ground truth: {row.get('source name', '').strip()}",
                }
                insert_test_case(tc_dict)
                insert_agent_scores_keep(tc_id)
                total_count += 1

    return {"imported": total_count, "files": len(gt_paths)}
