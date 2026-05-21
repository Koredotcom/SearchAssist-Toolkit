from __future__ import annotations

import csv
import io
import json

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from models import GoldenSetResponse, TestCaseResponse
from db.database import (
    count_runs_using_golden_set, create_golden_set, delete_golden_set,
    get_app, get_golden_set, get_doc_id_by_title,
    import_uploaded_test_cases, list_golden_sets, list_test_cases,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/apps/{app_id}/golden-sets", tags=["golden-sets"])


@router.get("", response_model=list[GoldenSetResponse])
def get_golden_sets(app_id: str):
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    return list_golden_sets(app_id)


@router.post("/upload")
async def upload_test_cases(
    app_id: str,
    version: str = Form(...),
    file: UploadFile = File(...),
):
    if not get_app(app_id):
        raise HTTPException(404, "App not found")

    gs = get_golden_set(app_id, version)
    if gs and gs.get("frozen_at"):
        raise HTTPException(400, f"Golden set '{version}' is frozen and cannot be modified")

    content = await file.read()
    filename = (file.filename or "").lower()

    try:
        if filename.endswith((".xlsx", ".xls")):
            cases = _parse_excel(content, app_id)
        else:
            cases = _parse_csv(content, app_id)
    except Exception as exc:
        raise HTTPException(400, f"Failed to parse file: {exc}")

    if not cases:
        raise HTTPException(
            400,
            "No valid rows found. Every row must have a 'question'. "
            "Optionally include 'expected_answer' and a reference doc column "
            "(doc_id / docId / record_title / recordTitle) to enable richer evaluation.",
        )

    # Per-row case detection happens at evaluation time. Count what we got so
    # the UI can show a summary.
    case_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for c in cases:
        case_counts[_detect_case(c)] += 1

    create_golden_set(app_id, version)
    imported = import_uploaded_test_cases(app_id, version, cases)
    return {
        "imported": imported,
        "version": version,
        "case_counts": case_counts,
    }


def _detect_case(case: dict) -> int:
    """Detect which of the 4 evaluation cases a row falls into.

    1: question only
    2: question + expected_answer
    3: question + reference_doc(s) (via doc_id, recordUrl, recordTitle, or custom field)
    4: question + expected_answer + reference_doc(s)
    """
    has_answer = bool((case.get("expected_answer") or "").strip())
    has_ref    = bool(case.get("reference_match_spec")) or bool(case.get("reference_doc_ids"))
    if has_answer and has_ref:
        return 4
    if has_ref:
        return 3
    if has_answer:
        return 2
    return 1


# ── Reference-doc column detection ──────────────────────────────────────────────
# Priority order (highest first):
#   1. doc_id / docId / reference_doc_ids → direct ID, matched against chunk["docId"]
#   2. recordUrl / record_url             → matched against chunk["recordUrl"]
#   3. recordTitle / record_title         → looked up in source_document, then matched
#   4. Any other non-standard column      → matched against chunk[<column_name>]
#
# Only ONE field is used per row (the highest-priority one present). The other
# columns are ignored. Standard column names are excluded from custom-field
# treatment.
_DOC_ID_COLS  = ("doc_id", "docid", "reference_doc_ids")
_URL_COLS     = ("recordurl", "record_url")
_TITLE_COLS   = ("recordtitle", "record_title")
_STANDARD_COLS = {
    "question", "expected_answer", "expected_behavior",
    "question_type", "difficulty", "sys_content_type",
}


def _camel_field_name(lowered: str) -> str:
    """Translate the lowercased CSV header to the chunk JSON field name."""
    mapping = {
        "recordurl":    "recordUrl",
        "record_url":   "recordUrl",
        "recordtitle":  "recordTitle",
        "record_title": "recordTitle",
        "docid":        "docId",
        "doc_id":       "docId",
    }
    return mapping.get(lowered, lowered)


def _resolve_match_spec(app_id: str, row_norm: dict[str, str]) -> tuple[list[dict], list[str]]:
    """Return (match_spec, reference_doc_ids).

    match_spec is a list of {"field": <chunk JSON field>, "value": <expected>}.
    reference_doc_ids is populated only when the chosen field is the docId column
    (for backward compatibility with downstream metrics that historically used it).
    """
    # 1. doc_id / docId — direct IDs (semicolon-separated allowed)
    for col in _DOC_ID_COLS:
        val = row_norm.get(col, "").strip()
        if val:
            ids = _parse_ids(val)
            return [{"field": "docId", "value": i} for i in ids], ids

    # 2. recordUrl
    for col in _URL_COLS:
        val = row_norm.get(col, "").strip()
        if val:
            return [{"field": "recordUrl", "value": val}], []

    # 3. recordTitle (look up doc_id for back-compat, also store as title field)
    for col in _TITLE_COLS:
        title = row_norm.get(col, "").strip()
        if title:
            doc_id = get_doc_id_by_title(app_id, title)
            spec = [{"field": "recordTitle", "value": title}]
            ids = [doc_id] if doc_id else []
            if doc_id:
                spec.insert(0, {"field": "docId", "value": doc_id})
            return spec, ids

    # 4. Any other custom column the user added — first non-empty wins
    known = set(_DOC_ID_COLS) | set(_URL_COLS) | set(_TITLE_COLS) | _STANDARD_COLS
    for col, val in row_norm.items():
        if col in known or not val:
            continue
        val = val.strip()
        if not val:
            continue
        return [{"field": _camel_field_name(col), "value": val}], []

    return [], []


def _parse_csv(content: bytes, app_id: str) -> list[dict]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict] = []
    for row in reader:
        norm = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
        q = norm.get("question", "")
        if not q:
            continue
        match_spec, ref_ids = _resolve_match_spec(app_id, norm)
        rows.append({
            "question": q,
            "expected_answer": norm.get("expected_answer") or None,
            "question_type": norm.get("question_type") or None,
            "difficulty": _parse_int(norm.get("difficulty")),
            "expected_behavior": norm.get("expected_behavior") or "ANSWER",
            "reference_doc_ids": ref_ids,
            "reference_match_spec": match_spec,
            "sys_content_type": norm.get("sys_content_type") or None,
        })
    return rows


def _parse_excel(content: bytes, app_id: str) -> list[dict]:
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("openpyxl is required for Excel uploads. Install it with: pip install openpyxl")
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    raw_headers = next(rows_iter, [])
    headers = [str(h).strip().lower() if h is not None else "" for h in raw_headers]
    if not headers:
        return []

    def _cell(row_vals: tuple, col: str) -> str:
        idx = headers.index(col) if col in headers else -1
        if idx < 0 or idx >= len(row_vals):
            return ""
        v = row_vals[idx]
        return str(v).strip() if v is not None else ""

    cases: list[dict] = []
    for row_vals in rows_iter:
        norm = {h: _cell(row_vals, h) for h in headers if h}
        q = norm.get("question", "")
        if not q:
            continue
        match_spec, ref_ids = _resolve_match_spec(app_id, norm)
        cases.append({
            "question": q,
            "expected_answer": norm.get("expected_answer") or None,
            "question_type": norm.get("question_type") or None,
            "difficulty": _parse_int(norm.get("difficulty")),
            "expected_behavior": norm.get("expected_behavior") or "ANSWER",
            "reference_doc_ids": ref_ids,
            "reference_match_spec": match_spec,
            "sys_content_type": norm.get("sys_content_type") or None,
        })
    wb.close()
    return cases


def _parse_int(val: str | None) -> int | None:
    try:
        v = int(str(val).strip())
        return v if v in (1, 2, 3) else None
    except (TypeError, ValueError):
        return None


def _parse_ids(val: str | None) -> list[str]:
    if not val:
        return []
    return [s.strip() for s in str(val).replace(",", ";").split(";") if s.strip()]


@router.get("/template")
def download_template(app_id: str):
    """Stream a sample .xlsx demonstrating all 4 case shapes."""
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise HTTPException(500, "openpyxl is required. Install with: pip install openpyxl")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Golden Set"

    headers = [
        "question", "expected_answer",
        "doc_id", "recordUrl", "record_title",
        "expected_behavior", "question_type", "difficulty",
        "sys_content_type",
    ]
    ws.append(headers)

    # Style header row
    header_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="left", vertical="center")

    # Sample rows — one per case + a recordUrl example
    examples = [
        # Case 1: question only
        ["What is the refund policy?", "",
         "", "", "",
         "ANSWER", "factual", 1, ""],
        # Case 2: question + expected_answer
        ["How long does shipping take?",
         "Standard shipping takes 3-5 business days.",
         "", "", "",
         "ANSWER", "factual", 1, ""],
        # Case 3a: question + recordTitle
        ["What are the warranty terms for laptops?", "",
         "", "", "Laptop Warranty Policy",
         "ANSWER", "policy", 2, ""],
        # Case 3b: question + recordUrl
        ["How do I reset my password?", "",
         "", "https://docs.example.com/account/password-reset", "",
         "ANSWER", "procedural", 1, ""],
        # Case 4 with sys_content_type filter: narrows the RAG search to one source type
        ["Can I return an opened product?",
         "Yes, opened products can be returned within 14 days if unused.",
         "doc-abc-123", "", "",
         "ANSWER", "policy", 2, "confluence"],
    ]
    for row in examples:
        ws.append(row)

    # Column widths
    widths = [40, 50, 22, 45, 30, 18, 15, 10, 20]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    # Notes sheet
    notes = wb.create_sheet("Instructions")
    instructions = [
        ["Golden Set Upload — Column Guide", ""],
        ["", ""],
        ["Column", "Required?"],
        ["question", "Yes — every row must have this"],
        ["expected_answer", "Optional — enables answer-correctness scoring"],
        ["doc_id  (or docId)", "Optional — direct Kore.ai document ID (highest priority)"],
        ["recordUrl  (or record_url)", "Optional — matched against chunk['recordUrl']"],
        ["record_title  (or recordTitle)", "Optional — looked up to find doc_id, or matched against chunk['recordTitle']"],
        ["<any custom field>", "Optional — any other column name is matched against chunk[<column>] in the retrieved JSON"],
        ["expected_behavior", "Optional — ANSWER (default) | REFUSE | CLARIFY"],
        ["question_type", "Optional — free text (factual, procedural, policy, ...)"],
        ["difficulty", "Optional — 1, 2, or 3"],
        ["sys_content_type", "Optional — Kore.ai source type (e.g. confluence, sharepoint, servicenow). "
         "When set, the RAG query is filtered to only search within that content type."],
        ["", ""],
        ["Expected-document Priority (one per row)", ""],
        ["1. doc_id / docId", "Wins if present"],
        ["2. recordUrl / record_url", "Used if no doc_id"],
        ["3. record_title / recordTitle", "Used if no doc_id and no recordUrl"],
        ["4. any other column", "Used last; matches chunk[<column>] verbatim"],
        ["", ""],
        ["Case Detection (per row)", ""],
        ["Case 1", "question only — observation + LLM self-eval"],
        ["Case 2", "question + expected_answer — correctness eval"],
        ["Case 3", "question + any reference column — retrieval eval"],
        ["Case 4", "question + expected_answer + any reference column — full eval"],
    ]
    for r in instructions:
        notes.append(r)
    notes.column_dimensions["A"].width = 40
    notes.column_dimensions["B"].width = 70
    # Bold the title and section headers
    notes["A1"].font = Font(bold=True, size=14)
    notes["A3"].font = Font(bold=True)
    notes["B3"].font = Font(bold=True)
    notes["A14"].font = Font(bold=True, size=12)
    notes["A20"].font = Font(bold=True, size=12)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="golden-set-template.xlsx"'},
    )


@router.get("/{version}/test-cases", response_model=list[TestCaseResponse])
def get_test_cases(app_id: str, version: str):
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    rows = list_test_cases(app_id, version)
    result = []
    for r in rows:
        scores = None
        if r.get("clarity") is not None:
            scores = {
                "clarity": r.get("clarity"), "specificity": r.get("specificity"),
                "meaningfulness": r.get("meaningfulness"), "answerability": r.get("answerability"),
                "reference_verifiability": r.get("reference_verifiability"),
                "answer_uniqueness": r.get("answer_uniqueness"),
            }
        result.append({
            "tc_id": r["tc_id"], "question": r["question"],
            "expected_answer": r["expected_answer"],
            "expected_behavior": r.get("expected_behavior", "ANSWER"),
            "question_type": r.get("question_type"),
            "difficulty": r.get("difficulty"),
            "reference_doc_ids": r.get("reference_doc_ids", []),
            "human_validated": bool(r.get("human_validated")),
            "status": r.get("status", "active"),
            "decision": r.get("decision"),
            "scores": scores,
        })
    return result


# ── Delete ──────────────────────────────────────────────────────────────────

@router.get("/{version}/delete-impact")
def get_delete_impact(app_id: str, version: str):
    """Preview what deleting this golden set would remove.

    Used by the confirmation modal so users can see how many test cases
    will go and whether existing eval runs reference this version.
    """
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    gs = get_golden_set(app_id, version)
    if not gs:
        raise HTTPException(404, f"Golden set '{version}' not found")
    cases = list_test_cases(app_id, version)
    run_refs = count_runs_using_golden_set(app_id, version)
    return {
        "version":          version,
        "frozen":           bool(gs.get("frozen_at")),
        "test_cases_count": len(cases),
        "eval_runs_count":  run_refs,
    }


@router.delete("/{version}")
def delete_golden_set_endpoint(app_id: str, version: str):
    """Permanently delete a golden set, its test_cases, and their agent_scores.

    Existing eval_runs that referenced this golden set are NOT deleted —
    they remain as historical records (their golden_set_version text becomes
    a dangling reference). Confirm dialog should surface this.
    """
    if not get_app(app_id):
        raise HTTPException(404, "App not found")
    gs = get_golden_set(app_id, version)
    if not gs:
        raise HTTPException(404, f"Golden set '{version}' not found")
    deleted = delete_golden_set(app_id, version)
    logger.info(
        "Golden set deleted | app=%s version=%s test_cases=%d runs_orphaned=%d",
        app_id, version,
        deleted["test_cases_deleted"], deleted["eval_runs_orphaned"],
    )
    return {"ok": True, "version": version, **deleted}
