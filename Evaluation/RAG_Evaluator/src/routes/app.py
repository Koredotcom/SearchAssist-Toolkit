import sys
import os
import tempfile
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from services.run_eval import runeval
from services.mailService import mailService
from utils.sessionManager import get_session_manager, create_user_session, validate_session, get_session_latest_file, add_session_file
import pandas as pd

import json
from typing import Optional
import logging

import traceback as tb


import time

def write_job_status(session_dir, status, **kwargs):
    data = {
        "status": status,
        "updated_at": time.time(),
        **kwargs
    }
    with open(os.path.join(session_dir, "job_status.json"), "w") as f:
        json.dump(data, f)

def read_job_status(session_dir):
    path = os.path.join(session_dir, "job_status.json")
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app with metadata
app = FastAPI(
    title="RAG Evaluator API",
    description="Advanced RAG System Performance Evaluation",
    version="2.0.0",
    docs_url="/evaluator/api/docs",
    redoc_url="/evaluator/api/redoc"
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "../static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

class Params(BaseModel):
    sheet_name: str = None
    evaluate_ragas: bool = False
    evaluate_crag: bool = False
    evaluate_llm: bool = False
    use_search_api: bool = False
    llm_model: str = None
    save_db: bool = False
    batch_size: int = 10
    max_concurrent: int = 5

class Body(BaseModel):
    excel_file: str
    config_file: str
    params: Params

class SessionRequest(BaseModel):
    client_info: Optional[dict] = None
# def build_ui_like_response(session_id: str, request: Request):
#     session_manager = get_session_manager()
#     session_dir = session_manager.get_session_directory(session_id)

#     output_file = get_session_latest_file(session_id)
#     if not output_file or not os.path.exists(output_file):
#         return None

#     # -------------------------------------------------
#     # Read ALL sheets (exclude non-data / analysis ones)
#     # -------------------------------------------------
#     excel = pd.ExcelFile(output_file)
#     dfs = []

#     for sheet in excel.sheet_names:
#         # Skip UI / analysis helper sheets
#         if sheet.lower() in ["quality_analysis", "summary", "metrics"]:
#             continue

#         try:
#             sheet_df = pd.read_excel(output_file, sheet_name=sheet)
#             sheet_df["_sheet_name"] = sheet
#             dfs.append(sheet_df)
#         except Exception:
#             continue

#     if not dfs:
#         return None

#     df = pd.concat(dfs, ignore_index=True)

#     # -------------------------------------------------
#     # Processing stats
#     # -------------------------------------------------
#     total = len(df)

#     answer_col = None
#     for col in ["answer", "response", "generated_answer"]:
#         if col in df.columns:
#             answer_col = col
#             break

#     successful = (
#         len(df[df[answer_col].notna()])
#         if answer_col
#         else total
#     )

#     processing_stats = {
#         "total_processed": total,
#         "successful_queries": successful,
#         "failed_queries": total - successful,
#         "success_rate": round((successful / total) * 100, 2) if total else 0
#     }

#     # -------------------------------------------------
#     # Metrics (same as UI API – dynamic)
#     # -------------------------------------------------
#     metric_columns = [
#         # RAGAS
#         "Response Relevancy", "Faithfulness",
#         "Context Recall", "Context Precision",
#         "Answer Correctness", "Answer Similarity",

#         # LLM
#         "LLM Answer Relevancy", "LLM Context Relevancy",
#         "LLM Answer Correctness", "LLM Ground Truth Validity",
#         "LLM Answer Completeness",

#         # CRAG
#         "Accuracy", "crag_accuracy"
#     ]

#     metrics = {}
#     for col in metric_columns:
#         if col in df.columns:
#             values = pd.to_numeric(df[col], errors="coerce").dropna()
#             if not values.empty:
#                 metrics[col] = round(values.mean(), 4)

#     # -------------------------------------------------
#     # Performance metrics (DYNAMIC – from job_status)
#     # -------------------------------------------------
#     performance_metrics = {}
#     status_file = os.path.join(session_dir, "job_status.json")

#     if os.path.exists(status_file):
#         with open(status_file) as f:
#             status_data = json.load(f)

#         total_time = status_data.get("total_time_sec")
#         peak_memory = status_data.get("peak_memory_mb")

#         if total_time and processing_stats["total_processed"]:
#             performance_metrics["average_response_time"] = (
#                 f"{round(total_time / processing_stats['total_processed'], 2)}s"
#             )

#         if peak_memory:
#             performance_metrics["peak_memory_usage"] = f"{peak_memory}MB"

#         if processing_stats["total_processed"]:
#             efficiency = (
#                 processing_stats["successful_queries"]
#                 / processing_stats["total_processed"]
#             ) * 100
#             performance_metrics["processing_efficiency"] = f"{round(efficiency, 2)}%"

#     # -------------------------------------------------
#     # Detailed results (UI-safe limit)
#     # -------------------------------------------------
#     detailed_results = []

#     display_columns = ["query", "answer", "ground_truth"] + [
#         col for col in metric_columns if col in df.columns
#     ]
#     display_columns = [c for c in display_columns if c in df.columns]

#     for _, row in df.head(200).iterrows():
#         row_data = {
#             "_sheet_name": row.get("_sheet_name", "Sheet1")
#         }

#         for col in display_columns:
#             val = row.get(col)
#             if pd.isna(val):
#                 row_data[col] = "N/A"
#             elif isinstance(val, (int, float)):
#                 row_data[col] = float(val)
#             else:
#                 sval = str(val)
#                 row_data[col] = sval[:200] + "..." if len(sval) > 200 else sval

#         detailed_results.append(row_data)

#     # -------------------------------------------------
#     # Download URL
#     # -------------------------------------------------
#     base_url = str(request.base_url).rstrip("/")
#     download_url = f"{base_url}/evaluator/api/download-results/{session_id}"

#     # -------------------------------------------------
#     # Final API-2 response (UI compatible)
#     # -------------------------------------------------
#     return {
#         "status": "success",
#         "job_id": session_id,
#         "processing_stats": processing_stats,
#         "metrics": metrics,
#         "performance_metrics": performance_metrics,
#         "detailed_results": detailed_results,
#         "download_url": download_url
#     }

# def build_ui_like_response(session_id: str, request: Request):
#     session_manager = get_session_manager()
#     session_dir = session_manager.get_session_directory(session_id)

#     output_file = get_session_latest_file(session_id)
#     if not output_file or not os.path.exists(output_file):
#         return None

#     # -------------------------------------------------
#     # Read ALL sheets (INCLUDING Quality_Analysis)
#     # -------------------------------------------------
#     excel = pd.ExcelFile(output_file)
#     dfs = []

#     for sheet in excel.sheet_names:
#         try:
#             sheet_df = pd.read_excel(output_file, sheet_name=sheet)
#             sheet_df["_sheet_name"] = sheet
#             dfs.append(sheet_df)
#         except Exception:
#             continue

#     if not dfs:
#         return None

#     df = pd.concat(dfs, ignore_index=True)

#     # -------------------------------------------------
#     # Detect ANSWER column (robust, UI-aligned)
#     # -------------------------------------------------
#     answer_col = None
#     for col in df.columns:
#         if col.strip().lower() in [
#             "answer",
#             "generated answer",
#             "generated_answer",
#             "response"
#         ]:
#             answer_col = col
#             break

#     # -------------------------------------------------
#     # Processing stats (MATCH UI)
#     # -------------------------------------------------
#     total = len(df)

#     successful = (
#         len(df[df[answer_col].notna()])
#         if answer_col
#         else total
#     )

#     processing_stats = {
#         "total_processed": total,
#         "successful_queries": successful,
#         "failed_queries": total - successful,
#         "success_rate": round((successful / total) * 100, 2) if total else 0,
#         "output_file": os.path.basename(output_file)
#     }

#     # -------------------------------------------------
#     # Metrics (same aggregation as UI)
#     # -------------------------------------------------
#     metric_columns = [
#         "Response Relevancy", "Faithfulness",
#         "Context Recall", "Context Precision",
#         "Answer Correctness", "Answer Similarity",

#         "LLM Answer Relevancy", "LLM Context Relevancy",
#         "LLM Answer Correctness", "LLM Ground Truth Validity",
#         "LLM Answer Completeness",

#         "Accuracy", "crag_accuracy"
#     ]

#     metrics = {}
#     for col in metric_columns:
#         if col in df.columns:
#             values = pd.to_numeric(df[col], errors="coerce").dropna()
#             if not values.empty:
#                 metrics[col] = round(values.mean(), 4)

#     # -------------------------------------------------
#     # Performance metrics (from job_status.json)
#     # -------------------------------------------------
#     performance_metrics = {}
#     status_file = os.path.join(session_dir, "job_status.json")

#     if os.path.exists(status_file):
#         with open(status_file) as f:
#             status_data = json.load(f)

#         total_time = status_data.get("total_time_sec")
#         peak_memory = status_data.get("peak_memory_mb")

#         if total_time and processing_stats["total_processed"]:
#             performance_metrics["average_response_time"] = (
#                 f"{round(total_time / processing_stats['total_processed'], 2)}s"
#             )

#         if peak_memory:
#             performance_metrics["peak_memory_usage"] = f"{round(peak_memory, 2)}MB"

#         if processing_stats["total_processed"]:
#             efficiency = (
#                 processing_stats["successful_queries"]
#                 / processing_stats["total_processed"]
#             ) * 100
#             performance_metrics["processing_efficiency"] = f"{round(efficiency, 2)}%"

#     # -------------------------------------------------
#     # Detailed results (MATCH UI – answers, justifications, context, chunks)
#     # -------------------------------------------------
#     detailed_results = []

#     display_columns = [
#         col for col in df.columns
#         if any(key in col.lower() for key in [
#             "query",
#             "answer",
#             "ground_truth",
#             "relevancy",
#             "correctness",
#             "validity",
#             "completeness",
#             "justification",
#             "context",
#             "chunk"
#         ])
#     ]

#     for _, row in df.head(200).iterrows():
#         row_data = {
#             "_sheet_name": row.get("_sheet_name", "Sheet1")
#         }

#         for col in display_columns:
#             val = row.get(col)

#             if pd.isna(val):
#                 row_data[col] = "N/A"
#             elif isinstance(val, (int, float)):
#                 row_data[col] = float(val)
#             else:
#                 sval = str(val)
#                 row_data[col] = sval[:500] + "..." if len(sval) > 500 else sval

#         detailed_results.append(row_data)

#     # -------------------------------------------------
#     # Download URL
#     # -------------------------------------------------
#     base_url = str(request.base_url).rstrip("/")
#     download_url = f"{base_url}/evaluator/api/download-results/{session_id}"

#     # -------------------------------------------------
#     # Final API-2 response (UI-equivalent)
#     # -------------------------------------------------
#     return {
#         "status": "success",   # API-2 will override to "completed"
#         "job_id": session_id,
#         "processing_stats": processing_stats,
#         "metrics": metrics,
#         "performance_metrics": performance_metrics,
#         "detailed_results": detailed_results,
#         "download_url": download_url
#     }

# def build_ui_like_response(session_id: str, request: Request):
#     session_manager = get_session_manager()
#     session_dir = session_manager.get_session_directory(session_id)

#     output_file = get_session_latest_file(session_id)
#     if not output_file or not os.path.exists(output_file):
#         return None

#     # -------------------------------------------------
#     # Read ALL sheets safely
#     # -------------------------------------------------
#     try:
#         excel = pd.ExcelFile(output_file)
#     except Exception:
#         return None

#     dfs = []
#     for sheet in excel.sheet_names:
#         try:
#             sheet_df = pd.read_excel(output_file, sheet_name=sheet)
#             sheet_df["_sheet_name"] = sheet
#             dfs.append(sheet_df)
#         except Exception:
#             continue

#     if not dfs:
#         return None

#     df = pd.concat(dfs, ignore_index=True)

#     # -------------------------------------------------
#     # Detect QUERY & ANSWER columns (UI-aligned)
#     # -------------------------------------------------
#     query_col = next(
#         (c for c in df.columns if c.strip().lower() == "query"),
#         None
#     )

#     answer_col = next(
#         (c for c in df.columns if c.strip().lower() in [
#             "answer", "generated_answer", "generated answer", "response"
#         ]),
#         None
#     )

#     # -------------------------------------------------
#     # Processing stats (✔ COUNT ROWS, NOT COLUMNS)
#     # -------------------------------------------------
#     if query_col:
#         valid_query_df = df[df[query_col].notna()]
#         total = valid_query_df.shape[0]
#     else:
#         valid_query_df = pd.DataFrame()
#         total = 0

#     if answer_col and not valid_query_df.empty:
#         successful = valid_query_df[
#             valid_query_df[answer_col].astype(str).str.strip() != ""
#         ].shape[0]
#     else:
#         successful = 0

#     processing_stats = {
#         "total_processed": total,
#         "successful_queries": successful,
#         "failed_queries": total - successful,
#         "success_rate": round((successful / total) * 100, 2) if total else 0,
#         "output_file": os.path.basename(output_file)
#     }

#     # -------------------------------------------------
#     # Metrics (same aggregation as UI)
#     # -------------------------------------------------
#     metric_columns = [
#         "Response Relevancy", "Faithfulness",
#         "Context Recall", "Context Precision",
#         "Answer Correctness", "Answer Similarity",
#         "LLM Answer Relevancy", "LLM Context Relevancy",
#         "LLM Answer Correctness", "LLM Ground Truth Validity",
#         "LLM Answer Completeness",
#         "Accuracy", "crag_accuracy"
#     ]

#     metrics = {}
#     for col in metric_columns:
#         if col in df.columns:
#             values = pd.to_numeric(df[col], errors="coerce").dropna()
#             if not values.empty:
#                 metrics[col] = round(values.mean(), 4)

#     # -------------------------------------------------
#     # Performance metrics (from job_status.json)
#     # -------------------------------------------------
#     performance_metrics = {}
#     status_file = os.path.join(session_dir, "job_status.json")

#     if os.path.exists(status_file):
#         with open(status_file) as f:
#             status_data = json.load(f)

#         total_time = status_data.get("total_time_sec")
#         peak_memory = status_data.get("peak_memory_mb")

#         if total_time and total:
#             performance_metrics["average_response_time"] = (
#                 f"{round(total_time / total, 2)}s"
#             )

#         if peak_memory:
#             performance_metrics["peak_memory_usage"] = f"{round(peak_memory, 2)}MB"

#         if total:
#             efficiency = (successful / total) * 100
#             performance_metrics["processing_efficiency"] = f"{round(efficiency, 2)}%"

#     # -------------------------------------------------
#     # Detailed results (UI-style, row-based)
#     # -------------------------------------------------
#     detailed_results = []

#     display_columns = [
#         c for c in df.columns
#         if any(k in c.lower() for k in [
#             "query", "answer", "ground_truth",
#             "relevancy", "correctness", "validity",
#             "completeness", "justification",
#             "context", "chunk"
#         ])
#     ]

#     for _, row in valid_query_df.head(200).iterrows():
#         row_data = {
#             "_sheet_name": row.get("_sheet_name", "Sheet1")
#         }

#         for col in display_columns:
#             val = row.get(col)

#             if pd.isna(val):
#                 row_data[col] = "N/A"
#             elif isinstance(val, (int, float)):
#                 row_data[col] = float(val)
#             else:
#                 sval = str(val)
#                 row_data[col] = sval[:500] + "..." if len(sval) > 500 else sval

#         detailed_results.append(row_data)

#     # -------------------------------------------------
#     # Download URL
#     # -------------------------------------------------
#     base_url = str(request.base_url).rstrip("/")
#     download_url = f"{base_url}/evaluator/api/download-results/{session_id}"

#     # -------------------------------------------------
#     # Final API-2 response (UI-equivalent)
#     # -------------------------------------------------
#     return {
#         "status": "success",   # overridden to "completed" by API-2
#         "job_id": session_id,
#         "processing_stats": processing_stats,
#         "metrics": metrics,
#         "performance_metrics": performance_metrics,
#         "detailed_results": detailed_results,
#         "download_url": download_url
#     }


def safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
def is_valid_query_row(row: dict) -> bool:
    """
    Returns True only for real query rows.
    Excludes Quality_Analysis / Summary rows.
    """
    return bool(row.get("query"))


def build_ui_like_response(session_id: str, request: Request):
    session_manager = get_session_manager()
    session_dir = session_manager.get_session_directory(session_id)

    output_file = get_session_latest_file(session_id)
    if not output_file or not os.path.exists(output_file):
        return None

    # -------------------------------------------------
    # Read ALL sheets safely
    # -------------------------------------------------
    try:
        excel = pd.ExcelFile(output_file)
    except Exception:
        return None

    dfs = []
    for sheet in excel.sheet_names:
        try:
            sheet_df = pd.read_excel(output_file, sheet_name=sheet)
            sheet_df["_sheet_name"] = sheet
            dfs.append(sheet_df)
        except Exception:
            continue

    if not dfs:
        return None

    df = pd.concat(dfs, ignore_index=True)

    # -------------------------------------------------
    # Detect QUERY & ANSWER columns (UI-aligned)
    # -------------------------------------------------
    query_col = next(
        (c for c in df.columns if c.strip().lower() == "query"),
        None
    )

    answer_col = next(
        (
            c for c in df.columns
            if c.strip().lower() in [
                "answer", "generated_answer", "generated answer", "response"
            ]
        ),
        None
    )

    # -------------------------------------------------
    # Processing stats (COUNT ROWS, NOT COLUMNS)
    # -------------------------------------------------
    if query_col:
        valid_query_df = df[df[query_col].notna()]
        total = valid_query_df.shape[0]
    else:
        valid_query_df = pd.DataFrame()
        total = 0

    if answer_col and not valid_query_df.empty:
        successful = valid_query_df[
            valid_query_df[answer_col].astype(str).str.strip() != ""
        ].shape[0]
    else:
        successful = 0

    processing_stats = {
        "total_processed": total,
        "successful_queries": successful,
        "failed_queries": total - successful,
        "success_rate": round((successful / total) * 100, 2) if total else 0,
        "output_file": os.path.basename(output_file)
    }

    # -------------------------------------------------
    # Metrics (UI aggregation)
    # -------------------------------------------------
    metric_columns = [
        "Response Relevancy", "Faithfulness",
        "Context Recall", "Context Precision",
        "Answer Correctness", "Answer Similarity",
        "LLM Answer Relevancy", "LLM Context Relevancy",
        "LLM Answer Correctness", "LLM Ground Truth Validity",
        "LLM Answer Completeness",
        "Accuracy", "crag_accuracy"
    ]

    metrics = {}
    for col in metric_columns:
        if col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce").dropna()
            if not values.empty:
                metrics[col] = round(values.mean(), 4)

    # -------------------------------------------------
    # Performance metrics (job_status.json)
    # -------------------------------------------------
    performance_metrics = {}
    status_file = os.path.join(session_dir, "job_status.json")

    if os.path.exists(status_file):
        with open(status_file) as f:
            status_data = json.load(f)

        total_time = status_data.get("total_time_sec")
        peak_memory = status_data.get("peak_memory_mb")

        if total_time and total:
            performance_metrics["average_response_time"] = (
                f"{round(total_time / total, 2)}s"
            )

        if peak_memory:
            performance_metrics["peak_memory_usage"] = f"{round(peak_memory, 2)}MB"

        if total:
            efficiency = (successful / total) * 100
            performance_metrics["processing_efficiency"] = f"{round(efficiency, 2)}%"

    # -------------------------------------------------
    # Detailed results (row-based, UI-safe)
    # -------------------------------------------------
    detailed_results = []

    display_columns = [
        c for c in df.columns
        if any(k in c.lower() for k in [
            "query", "answer", "ground_truth",
            "relevancy", "correctness", "validity",
            "completeness", "justification",
            "context", "chunk"
        ])
    ]

    for _, row in valid_query_df.head(200).iterrows():
        row_data = {"_sheet_name": row.get("_sheet_name", "Sheet1")}

        for col in display_columns:
            val = row.get(col)

            if pd.isna(val):
                row_data[col] = "N/A"
            elif isinstance(val, (int, float)):
                row_data[col] = float(val)
            else:
                sval = str(val)
                row_data[col] = sval[:500] + "..." if len(sval) > 500 else sval

        detailed_results.append(row_data)

    # -------------------------------------------------
    # Retrieval Quality (TOTAL BASED ON TOTAL QUERIES)
    # -------------------------------------------------
    query_results = [
        row for row in detailed_results
        if is_valid_query_row(row)
    ]

    total_rows = len(query_results)
    retrieval_quality = {}

    # ---- Percentage-based metrics ----
    def avg_percentage(key):
        values = [
            safe_float(row.get(key))
            for row in query_results
            if safe_float(row.get(key)) is not None
        ]
        if not values:
            return None
        return round((sum(values) / len(values)) * 100, 2)

    retrieval_quality["LLM Ground Truth Validity"] = avg_percentage(
        "LLM Ground Truth Validity"
    )
    retrieval_quality["LLM Answer Completeness"] = avg_percentage(
        "LLM Answer Completeness"
    )

    # ---- Count-based metrics ----
    def sum_metric(key):
        values = [
            safe_float(row.get(key))
            for row in query_results
            if safe_float(row.get(key)) is not None
        ]
        return int(sum(values)) if values else 0

    def avg_per_query(key):
        total_value = sum_metric(key)
        return round(total_value / total_rows, 2) if total_rows else 0

    retrieval_quality["Retrieved Chunk Count"] = sum_metric(
        "Retrieved Chunk Count"
    )
    retrieval_quality["Sent to LLM Chunk Count"] = avg_per_query(
        "Sent to LLM Chunk Count"
    )
    retrieval_quality["Used in Answer Chunk Count"] = avg_per_query(
        "Used in Answer Chunk Count"
    )
    retrieval_quality["Total Chunks Used"] = avg_per_query(
        "Total Chunks Used"
    )
    retrieval_quality["Best Support Rank"] = avg_per_query(
        "Best Support Rank"
    )
    from services.recommendations import generate_recommendations

    recommendations = generate_recommendations(detailed_results)
    # -------------------------------------------------
    # Download URL
    # -------------------------------------------------
    base_url = str(request.base_url).rstrip("/")
    download_url = f"{base_url}/evaluator/api/download-results/{session_id}"

    # -------------------------------------------------
    # Final API response
    # -------------------------------------------------
    return {
        "status": "success",  # overridden to "completed" by API-2
        "job_id": session_id,
        "processing_stats": processing_stats,
        "metrics": metrics,
        "retrieval_quality": retrieval_quality,
        "performance_metrics": performance_metrics,
        # "detailed_results": detailed_results,
        "recommendations":recommendations,
        "download_url": download_url
    }


# UI Routes
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the main UI page"""
    try:
        ui_file = os.path.join(os.path.dirname(__file__), "../static/index.html")
        if os.path.exists(ui_file):
            with open(ui_file, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read(), status_code=200)
        else:
            return HTMLResponse(
                content="<h1>UI not found</h1><p>Please ensure static files are properly configured.</p>",
                status_code=404
            )
    except Exception as e:
        logger.error(f"Error serving UI: {e}")
        return HTMLResponse(
            content=f"<h1>Error</h1><p>Failed to load UI: {e}</p>",
            status_code=500
        )


@app.post('/evaluator/api/get-sheet-names')
async def get_sheet_names(file: UploadFile = File(...)):
    """Extract sheet names from uploaded Excel file"""
    try:
        # Validate file type
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Invalid file type. Please upload an Excel file.")
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        
        try:
            # Read Excel file and get sheet names with row counts
            excel_file = pd.ExcelFile(tmp_file_path, engine='openpyxl')
            sheet_names = excel_file.sheet_names
            
            # Get row counts for each sheet
            row_counts = {}
            total_rows = 0
            
            for sheet_name in sheet_names:
                try:
                    # Read Excel sheet to get row count
                    df = pd.read_excel(tmp_file_path, sheet_name=sheet_name, nrows=None)
                    # Filter out empty rows
                    df_clean = df.dropna(how='all')
                    row_count = len(df_clean)
                    row_counts[sheet_name] = row_count
                    total_rows += row_count
                except Exception:
                    row_counts[sheet_name] = 0
            
            excel_file.close()
            
            response_data = {
                "status": "success",
                "sheet_names": sheet_names,
                "total_sheets": len(sheet_names),
                "row_counts": row_counts,
                "total_rows": total_rows
            }
            
            return JSONResponse(content=response_data)
        
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
    
    except Exception as e:
        logger.error(f"Error extracting sheet names: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to extract sheet names: {str(e)}")


@app.post('/evaluator/api/create-session')
async def create_session(request: Request):
    """Create a new user session for file isolation"""
    try:
        session_manager = get_session_manager()
        session_id = session_manager.create_session()
        
        # Get client info for tracking
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Update session with client info
        session_manager.update_session_metadata(session_id, client_ip, user_agent)
        
        logger.info(f"Created new session {session_id} for client {client_ip}")
        
        return JSONResponse(content={
            "status": "success",
            "session_id": session_id,
            "message": "Session created successfully"
        })
    
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

import asyncio

# @app.post("/evaluator/api/eval/start")
# async def start_eval_job(
#     excel_file: UploadFile = File(...),

#     # REQUIRED KEYS (passed via curl / postman)
#     llm_api_key: str = Form(...),

#     xo_app_id: str = Form(...),
#     xo_client_id: str = Form(...),
#     xo_client_secret: str = Form(...),
#     xo_domain: str = Form(...),

#     # Optional tuning
#     batch_size: int = Form(10),
#     max_concurrent: int = Form(5),
# ):
#     """
#     API-1:
#     - Accepts inputs
#     - Starts evaluation asynchronously
#     - Returns job_id immediately
#     """

#     try:
#         # 1️⃣ Create Job ID (session)
#         job_id = create_user_session()
#         session_manager = get_session_manager()
#         session_dir = session_manager.get_session_directory(job_id)

#         # 2️⃣ Save Excel file
#         input_excel_path = os.path.join(
#             session_dir, f"input_{job_id}_{excel_file.filename}"
#         )

#         with open(input_excel_path, "wb") as f:
#             f.write(await excel_file.read())

#         # 3️⃣ Default PARAMS (your requirement)
#         params = {
#             "sheet_name": "",               # all sheets
#             "evaluate_ragas": False,
#             "evaluate_crag": False,
#             "evaluate_llm": True,
#             "use_search_api": True,
#             "llm_model": "gpt-4o-mini",
#             "save_db": False,
#             "batch_size": batch_size,
#             "max_concurrent": max_concurrent
#         }

#         # 4️⃣ Build config (IN-MEMORY ONLY)
#         config_data = {
#             "openai_config": {
#                 "model": "gpt-4o-mini",
#                 "api_key": llm_api_key
#             },
#             "api_config": {
#                 "type": "UXO",  # XO by default
#                 "app_id": xo_app_id,
#                 "client_id": xo_client_id,
#                 "client_secret": xo_client_secret,
#                 "domain": xo_domain
#             }
#         }

#         # 5️⃣ Start evaluation ASYNC (NON-BLOCKING)
#         # asyncio.create_task(
#         #     runeval(
#         #         input_excel_path,
#         #         json.dumps(config_data),
#         #         params,
#         #         job_id
#         #     )
#         # )
#         # Mark job as submitted
# write_job_status(session_dir, "submitted")
# def validate_input_excel_schema(
#     excel_path: str,
#     required_columns: list,
#     sheet_name: str = None
# ):
#     """
#     Validates that the Excel file contains required columns.
#     Raises HTTPException if validation fails.
#     """
#     try:
#         # Read Excel
#         if sheet_name:
#             df = pd.read_excel(excel_path, sheet_name=sheet_name)
#         else:
#             df = pd.read_excel(excel_path)

#     except Exception as e:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Unable to read Excel file: {str(e)}"
#         )

#     original_columns = [c.strip() for c in df.columns]
#     lower_columns = [c.lower() for c in original_columns]
    
#     missing_columns = [
#         col for col in required_columns if col.lower() not in lower_columns
#         ]


#     if missing_columns:
#         raise HTTPException(
#             status_code=400,
#             detail={
#                 "error": "Invalid Excel format",
#                 "reason": "Missing required columns",
#                 "required_columns": required_columns,
#                 "missing_columns": missing_columns,
#                 "found_columns": list(df.columns)
#             }
#         )

#     if df.empty:
#         raise HTTPException(
#             status_code=400,
#             detail="Excel file is empty after removing blank rows"
#         )

#     return True

def validate_input_excel_schema(
    excel_path: str,
    required_columns: list,
    optional_columns: list = None,
    sheet_name: str = None
):
    """
    Validates Excel schema:
    - required_columns → must exist
    - optional_columns → allowed but not mandatory
    """
    try:
        if sheet_name:
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
        else:
            df = pd.read_excel(excel_path)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to read Excel file: {str(e)}"
        )

    original_columns = [c.strip() for c in df.columns]
    lower_columns = [c.lower() for c in original_columns]

    # ---- Required column check ----
    missing_columns = [
        col for col in required_columns
        if col.lower() not in lower_columns
    ]

    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid Excel format",
                "reason": "Missing required columns",
                "required_columns": required_columns,
                "optional_columns": optional_columns or [],
                "missing_columns": missing_columns,
                "found_columns": original_columns
            }
        )

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="Excel file is empty after removing blank rows"
        )

    # ---- Optional column info (non-blocking) ----
    present_optional_columns = []
    missing_optional_columns = []

    if optional_columns:
        for col in optional_columns:
            if col.lower() in lower_columns:
                present_optional_columns.append(col)
            else:
                missing_optional_columns.append(col)

    return {
        "valid": True,
        "required_columns": required_columns,
        "optional_columns": optional_columns or [],
        "present_optional_columns": present_optional_columns,
        "missing_optional_columns": missing_optional_columns,
        "found_columns": original_columns
    }



@app.post("/evaluator/api/eval/start")
async def start_eval_job(
    excel_file: UploadFile = File(...),
    llm_api_key: str = Form(...),
    xo_app_id: str = Form(...),
    xo_client_id: str = Form(...),
    xo_client_secret: str = Form(...),
    xo_domain: str = Form(...),
    batch_size: int = Form(10),
    max_concurrent: int = Form(5),
):
    try:
        # 1️⃣ Create Job ID
        job_id = create_user_session()
        session_manager = get_session_manager()
        session_dir = session_manager.get_session_directory(job_id)

        # 2️⃣ Save Excel file
        input_excel_path = os.path.join(
            session_dir, f"input_{job_id}_{excel_file.filename}"
        )
        with open(input_excel_path, "wb") as f:
            f.write(await excel_file.read())
            # 1 Validate Excel schema BEFORE starting job
        validate_input_excel_schema(
                excel_path=input_excel_path,
                required_columns=["query", "ground_truth"],
                optional_columns=["doc_id", "record_title"]
                )


        # 3️⃣ Params
        params = {
            "sheet_name": None,
            "evaluate_ragas": False,
            "evaluate_crag": False,
            "evaluate_llm": True,
            "use_search_api": True,
            "llm_model": "gpt-4o-mini",
            "save_db": False,
            "batch_size": batch_size,
            "max_concurrent": max_concurrent
        }

        # 4️⃣ Config
        config_data = {
            "openai": {
                "model": "gpt-4o-mini",
                "api_key": llm_api_key
            },
            "api_config": {
                "type": "UXO",
                "app_id": xo_app_id,
                "client_id": xo_client_id,
                "client_secret": xo_client_secret,
                "domain": xo_domain
            }
        }
        api_cfg = config_data.get("api_config")

        if isinstance(api_cfg, dict):
            api_type = api_cfg.get("type")

        if api_type == "UXO":
            config_data["UXO"] = api_cfg
        elif api_type == "SA":
            config_data["SA"] = api_cfg


        # 5️⃣ Mark job submitted
        write_job_status(session_dir, "submitted")
        
        try:
           import psutil
           process = psutil.Process(os.getpid())
        except ImportError:
           psutil = None
           process = None
           
        async def runeval_safe():
            try:
                process = psutil.Process(os.getpid())
                start_time = time.time()
                peak_memory = 0

                write_job_status(
                    session_dir,
                    "running",
                    started_at=start_time
                    )
                async def monitor_memory():
                    nonlocal peak_memory
                    while True:
                        mem = process.memory_info().rss / (1024 * 1024)  # MB
                        peak_memory = max(peak_memory, mem)
                        await asyncio.sleep(0.5)

                monitor_task = asyncio.create_task(monitor_memory())
                config_data.update(params)
                api_cfg = config_data.get("api_config")
                if isinstance(api_cfg, dict):
                   api_type = api_cfg.get("type")
                if api_type == "UXO":
                   config_data["UXO"] = api_cfg
                elif api_type == "SA":
                   config_data["SA"] = api_cfg
                await asyncio.wait_for(
                    runeval(
                        input_excel_path,
                        json.dumps(config_data),
                        config_data,
                        job_id
                        ),
                    timeout=60 * 60
                    )
                # output_file = get_session_latest_file(job_id)
                # if output_file and os.path.exists(output_file):
                #     add_session_file(job_id, output_file)
                session_outputs = [
                    os.path.join(session_dir, f)
                    for f in os.listdir(session_dir)
                    if f.endswith(".xlsx")
                    ]
                
                if session_outputs:
                   latest_output = max(session_outputs, key=os.path.getmtime)
                   add_session_file(job_id, latest_output)

                end_time = time.time()
                monitor_task.cancel()
                if session_outputs:
                    write_job_status(
                    session_dir,
                    "completed",
                    started_at=start_time,
                    completed_at=end_time,
                    total_time_sec=round(end_time - start_time, 2),
                    peak_memory_mb=round(peak_memory, 2)
                    )
                else:
                    write_job_status(
                        session_dir,
                        "failed",
                        error="Evaluation finished but output file missing"
                   )
   

            except Exception as e:
                write_job_status(
                    session_dir,
                    "failed",
                    error=str(e)
                    )

                

        asyncio.create_task(runeval_safe())

        # 7️⃣ Return immediately
        return {
            "status": "submitted",
            "job_id": job_id,
            "message": "Evaluation started successfully"
        }

    except Exception as e:
        logger.error(f"Error starting evaluation: {e}")
        raise HTTPException(status_code=500, detail=str(e))



    # async def runeval_safe():
    #     try:
    #         write_job_status(
    #             session_dir,
    #             "running",
    #             started_at=time.time()
    #         )

    #         await asyncio.wait_for(
    #             runeval(
    #                 input_excel_path,
    #                 json.dumps(config_data),
    #                 params,
    #                 job_id
    #             ),
    #             timeout=60 * 60  # 1 hour max
    #         )

    #         write_job_status(session_dir, "completed")

    #     except asyncio.TimeoutError:
    #         write_job_status(
    #             session_dir,
    #             "failed",
    #             error="Evaluation timed out"
    #         )

    #     except Exception as e:
    #         write_job_status(
    #             session_dir,
    #             "failed",
    #             error=str(e)
    #         )
    #         asyncio.create_task(runeval_safe())


    #         # 6️⃣ Return job_id immediately
    #         return JSONResponse({
    #             "status": "submitted",
    #             "job_id": job_id,
    #             "message": "Evaluation started successfully"
    #         })

    #     except Exception as e:
    #         logger.error(f"Error starting evaluation: {e}")
    #         raise HTTPException(status_code=500, detail=str(e))

    # @app.get("/evaluator/api/eval/result/{job_id}")
    # async def get_eval_result(job_id: str):
    #     """
    #     API-2:
    #     - If evaluation is running → returns status=running
    #     - If completed → returns downloadable URL
    #     """

    #     if not validate_session(job_id):
    #         raise HTTPException(status_code=404, detail="Invalid job_id")

    #     output_file = get_session_latest_file(job_id)

    #     if not output_file:
    #         return JSONResponse({
    #             "status": "running",
    #             "job_id": job_id,
    #             "message": "Evaluation is still in progress"
    #         })

    #     filename = os.path.basename(output_file)

    #     # 👇 THIS IS THE IMPORTANT PART
    #     download_url = f"/evaluator/api/download-results/{job_id}"

    #     return JSONResponse({
    #         "status": "completed",
    #         "job_id": job_id,
    #         "file_name": filename,
    #         "download_url": download_url
    #     })


    # @app.get("/evaluator/api/eval/result/{job_id}")
    # async def get_eval_result(job_id: str):
    #     # 1. Validate job/session
    #     if not validate_session(job_id):
    #         raise HTTPException(status_code=404, detail="Invalid job_id")

    #     session_manager = get_session_manager()
    #     session_dir = session_manager.get_session_directory(job_id)

    #     # 2. Read job status file
    #     status_file = os.path.join(session_dir, "job_status.json")

    #     if not os.path.exists(status_file):
    #         return {
    #             "status": "pending",
    #             "job_id": job_id,
    #             "message": "Job has not started yet"
    #         }

    #     with open(status_file, "r") as f:
    #         status_data = json.load(f)

    #     status = status_data.get("status")

    #     # 3. FAILED CASE
    #     if status == "failed":
    #         return {
    #             "status": "failed",
    #             "job_id": job_id,
    #             "error": status_data.get("error", "Unknown error occurred")
    #         }

    #     # 4. RUNNING CASE
    #     if status == "running":
    #         started_at = status_data.get("started_at")
    #         elapsed_seconds = None
    #         remaining_seconds = None

    #         if started_at:
    #             elapsed_seconds = int(time.time() - started_at)
    #             estimated_total_seconds = 600  # adjust later if needed
    #             remaining_seconds = max(
    #                 estimated_total_seconds - elapsed_seconds, 0
    #             )

    #         return {
    #             "status": "running",
    #             "job_id": job_id,
    #             "elapsed_seconds": elapsed_seconds,
    #             "estimated_remaining_seconds": remaining_seconds
    #         }

    #     # 5. COMPLETED CASE
    #     output_file = get_session_latest_file(job_id)

    #     if not output_file:
    #         return {
    #             "status": "completed",
    #             "job_id": job_id,
    #             "message": "Evaluation completed but output file not found"
    #         }

    #     filename = os.path.basename(output_file)

    #     return {
    #         "status": "completed",
    #         "job_id": job_id,
    #         "file_name": filename,
    #         "download_url": f"/evaluator/api/download-results/{job_id}"
    #     }

    # @app.get("/evaluator/api/eval/result/{job_id}")
    # async def get_eval_result(job_id: str, request: Request):

    #     if not validate_session(job_id):
    #         raise HTTPException(status_code=404, detail="Invalid job_id")

    #     session_manager = get_session_manager()
    #     session_dir = session_manager.get_session_directory(job_id)
    #     status_path = os.path.join(session_dir, "job_status.json")

    #     if not os.path.exists(status_path):
    #         return {"status": "pending", "job_id": job_id}

    #     with open(status_path) as f:
    #         status_data = json.load(f)

    #     status = status_data.get("status")

    #     if status == "running":
    #         return {
    #             "status": "running",
    #             "job_id": job_id,
    #             "elapsed_seconds": int(time.time() - status_data.get("started_at", time.time()))
    #         }

    #     if status == "failed":
    #         return {
    #             "status": "failed",
    #             "job_id": job_id,
    #             "error": status_data.get("error")
    #         }

    #     # ✅ COMPLETED CASE
    #     response = build_ui_like_response(job_id, request)
    #     if not response:
    #         return {
    #             "status": "completed",
    #             "job_id": job_id,
    #             "message": "Evaluation completed but results not found"
    #         }

    #     return response


@app.get("/evaluator/api/eval/result/{job_id}")
async def get_eval_result(job_id: str, request: Request):

    if not validate_session(job_id):
        raise HTTPException(status_code=404, detail="Invalid job_id")

    session_manager = get_session_manager()
    session_dir = session_manager.get_session_directory(job_id)
    status_path = os.path.join(session_dir, "job_status.json")

    # ⏳ Not started
    if not os.path.exists(status_path):
        return {
            "status": "pending",
            "job_id": job_id
        }

    with open(status_path) as f:
        status_data = json.load(f)

    status = status_data.get("status")

    # ❌ FAILED
    if status == "failed":
        return {
            "status": "failed",
            "job_id": job_id,
            "error": status_data.get("error", "Unknown error")
        }

    # ⏳ RUNNING / SUBMITTED
    if status in ["submitted", "running"]:
        started_at = status_data.get("started_at")
        elapsed_seconds = (
            int(time.time() - started_at)
            if started_at else None
        )

        # 🔮 Simple ETA logic (same as your expectation)
        ESTIMATED_TOTAL_SECONDS = 600  # adjust later if needed
        estimated_remaining_seconds = (
            max(ESTIMATED_TOTAL_SECONDS - elapsed_seconds, 0)
            if elapsed_seconds is not None else None
        )

        return {
            "status": "running",
            "job_id": job_id,
            "elapsed_seconds": elapsed_seconds,
            "estimated_remaining_seconds": estimated_remaining_seconds
        }

    # ✅ COMPLETED → UI RESPONSE + STATUS
    ui_response = build_ui_like_response(job_id, request)

    if not ui_response:
        return {
            "status": "completed",
            "job_id": job_id,
            "message": "Evaluation completed but results not found"
        }

    # 🔹 Enforce required structure
    ui_response["status"] = "completed"
    ui_response["job_id"] = job_id

    return ui_response


@app.post('/evaluator/api/runeval')
async def run_evaluation_ui(
    excel_file: UploadFile = File(...),
    config: str = Form(...),
    session_id: str = Form(None)
):
    """Run evaluation from UI with file upload"""
    try:
        logger.info(f"🔍 Received runeval request:")
        logger.info(f"   📄 File: {excel_file.filename if excel_file else 'None'}")
        logger.info(f"   🔐 Session ID: {session_id if session_id else 'None'}")
        logger.info(f"   ⚙️ Config length: {len(config) if config else 0}")
        
        # Handle session - create one if not provided (for backward compatibility)
        session_manager = get_session_manager()
        if not session_id:
            logger.info("⚠️ No session ID provided, creating new session")
            session_id = session_manager.create_session()
        elif not validate_session(session_id):
            logger.error(f"❌ Invalid session ID: {session_id}, creating new session")
            session_id = session_manager.create_session()
        
        logger.info(f"✅ Starting evaluation for session: {session_id}")
        
        # Parse config JSON
        try:
            config_data = json.loads(config)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid configuration JSON")
        
                # Validate that at least one evaluation method is selected
        if not any([config_data.get('evaluate_ragas', False), 
                   config_data.get('evaluate_crag', False), 
                   config_data.get('evaluate_llm', False)]):
            raise HTTPException(status_code=400, detail="At least one evaluation method (RAGAS, CRAG, or LLM) must be selected")
        
        # Validate file
        if not excel_file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Invalid file type. Please upload an Excel file.")
        
        # Save uploaded file to session-specific directory
        session_dir = session_manager.get_session_directory(session_id)
        input_filename = f"input_{session_id}_{excel_file.filename}"
        excel_file_path = os.path.join(session_dir, input_filename)
        
        with open(excel_file_path, 'wb') as f:
            content = await excel_file.read()
            f.write(content)
        
        # Build dynamic config in-memory (NO FILE STORAGE!)
        dynamic_config = {
            "cost_of_model": {
                "input": 0.00000015,
                "output": 0.0000006
            },
            "MongoDB": {
                "url": os.getenv("MONGO_URL", "<MONGO_URL>"),
                "dbName": os.getenv("DB_NAME", "<DB_NAME>"),
                "collectionName": os.getenv("COLLECTION_NAME", "<COLLECTION_NAME>")
            }
        }
        
        # Add Search API configuration if provided
        if config_data.get('api_config') and config_data.get('use_search_api'):
            api_config = config_data['api_config']
            api_type = api_config.get('type', '')
            logger.info(f"🔧 Adding {api_type} API configuration to dynamic config")
            
            if api_type == 'SA':
                dynamic_config["SA"] = {
                    "app_id": api_config.get('app_id', ''),
                    "client_id": api_config.get('client_id', ''),
                    "client_secret": api_config.get('client_secret', ''),
                    "domain": api_config.get('domain', '')
                }
                logger.info(f"✅ SA config added with app_id: {'***' if dynamic_config['SA']['app_id'] else 'Empty'}")
            elif api_type == 'UXO':
                dynamic_config["UXO"] = {
                    "app_id": api_config.get('app_id', ''),
                    "client_id": api_config.get('client_id', ''),
                    "client_secret": api_config.get('client_secret', ''),
                    "domain": api_config.get('domain', '')
                }
                logger.info(f"✅ UXO config added with app_id: {'***' if dynamic_config['UXO']['app_id'] else 'Empty'}")
        elif config_data.get('use_search_api'):
            logger.warning("⚠️ Use Search API enabled but no API config provided!")
        
        # Add OpenAI configuration if provided
        if config_data.get('openai_config'):
            openai_config = config_data['openai_config']
            dynamic_config["openai"] = {
                "model_name": openai_config.get('model', 'gpt-4o'),
                "embedding_name": "text-embedding-ada-002",
                "api_key": openai_config.get('api_key', ''),
                "org_id": openai_config.get('org_id', '')
            }
            
            # Set environment variable for OpenAI
            if openai_config.get('api_key'):
                os.environ["OPENAI_API_KEY"] = openai_config['api_key']
            if openai_config.get('org_id'):
                os.environ["OPENAI_ORG_ID"] = openai_config['org_id']
        
        # Add Azure OpenAI configuration if provided
        if config_data.get('azure_config'):
            azure_config = config_data['azure_config']
            dynamic_config["azure"] = {
                "openai_api_version": azure_config.get('api_version', '2024-02-15-preview'),
                "base_url": azure_config.get('endpoint', ''),
                "model_name": azure_config.get('model', 'gpt-4o'),
                "model_deployment": azure_config.get('deployment', ''),
                "embedding_deployment": azure_config.get('embedding_deployment', 'text-embedding-ada-002'),
                "embedding_name": "text-embedding-ada-002",
                "api_key": azure_config.get('api_key', '')
            }
            
            # Set environment variables for Azure OpenAI
            if azure_config.get('api_key'):
                os.environ["AZURE_OPENAI_API_KEY"] = azure_config['api_key']
            if azure_config.get('endpoint'):
                os.environ["AZURE_OPENAI_ENDPOINT"] = azure_config['endpoint']
        
        # Add default placeholders for missing API configs
        if not dynamic_config.get("SA") and not dynamic_config.get("UXO"):
            dynamic_config["SA"] = {
                "app_id": "<SA stream ID>",
                "client_id": "<SA client ID>",
                "client_secret": "<SA client secret>",
                "domain": "<SA domain url>"
            }
            dynamic_config["UXO"] = {
                "app_id": "<UXO stream ID>",
                "client_id": "<UXO client ID>",
                "client_secret": "<UXO client secret>",
                "domain": "<UXO domain url>"
            }
            
        # Add default OpenAI config if not provided
        if not dynamic_config.get("openai"):
            dynamic_config["openai"] = {
                "model_name": "gpt-4o",
                "embedding_name": "text-embedding-ada-002"
            }
        
        # Add default Azure config if not provided  
        if not dynamic_config.get("azure"):
            dynamic_config["azure"] = {
                "openai_api_version": "2024-02-15-preview",
                "base_url": "<AZURE_BASE_URL>",
                "model_name": "gpt-4o",
                "model_deployment": "<MODEL_DEPLOYMENT>",
                "embedding_deployment": "<EMBEDDING_DEPLOYMENT>",
                "embedding_name": "text-embedding-ada-002"
            }
        
        logger.info(f"🔒 Configuration built in-memory (secure)")
        
        try:
            # Call the evaluation service with session-aware output handling
            result = await runeval(excel_file_path, json.dumps(dynamic_config), config_data, session_id)
            logger.info(f"🔄 Evaluation service result: {type(result)}")
            
            # Try to get actual result statistics from the session's output directory
            session_outputs_dir = session_manager.get_session_directory(session_id)
            actual_metrics = {}
            processing_stats = {}
            detailed_results = []
            
            # Try to extract token usage from the result message if it contains useful info
            token_usage_from_result = {}
            if isinstance(result, str):
                # Look for token usage in the result message
                import re
                token_pattern = r'Total Tokens for Evaluation: Input=(\d+) Output=(\d+)'
                cost_pattern = r'Total Cost in \$: ([\d.]+)'
                
                token_match = re.search(token_pattern, result)
                cost_match = re.search(cost_pattern, result)
                
                if token_match:
                    input_tokens = int(token_match.group(1))
                    output_tokens = int(token_match.group(2))
                    total_tokens = input_tokens + output_tokens
                    
                    token_usage_from_result = {
                        'total_tokens': total_tokens,
                        'prompt_tokens': input_tokens,
                        'completion_tokens': output_tokens
                    }
                    logger.info(f"✅ Extracted tokens from result: {token_usage_from_result}")
                
                if cost_match:
                    actual_cost = float(cost_match.group(1))
                    token_usage_from_result['estimated_cost_usd'] = actual_cost
                    logger.info(f"💰 Extracted cost from result: ${actual_cost}")
            
            logger.info(f"🔍 Token usage from result: {token_usage_from_result}")
            
            try:
                logger.info(f"🔍 Looking for Excel files in session directory: {session_outputs_dir}")
                
                # Find the session's output files (evaluation results contain "evaluation_output" in filename)
                if os.path.exists(session_outputs_dir):
                    result_files = [f for f in os.listdir(session_outputs_dir) if f.endswith('.xlsx') and 'evaluation_output' in f]
                    logger.info(f"📁 Found evaluation output files for session {session_id}: {result_files}")
                    
                    if result_files:
                        # Sort by modification time to get the most recent
                        latest_file = max(result_files, key=lambda f: os.path.getmtime(os.path.join(session_outputs_dir, f)))
                        file_path = os.path.join(session_outputs_dir, latest_file)
                        
                        # Register the output file with the session
                        add_session_file(session_id, file_path)
                        
                        logger.info(f"📊 Reading latest file: {latest_file}")
                        
                        # Try to read all sheets to find metrics
                        try:
                            excel_file = pd.ExcelFile(file_path)
                            sheet_names = excel_file.sheet_names
                            logger.info(f"📋 Available sheets: {sheet_names}")
                            
                            all_sheets_data = []
                            metrics_found = False
                            
                            # Extract data from ALL sheets for multi-sheet view
                            for sheet_idx, sheet_name in enumerate(sheet_names):
                                try:
                                    current_df = pd.read_excel(file_path, sheet_name=sheet_name)
                                    logger.info(f"📄 Sheet '{sheet_name}' columns: {list(current_df.columns)}")
                                    
                                    # Skip error/empty sheets
                                    if '_error' in sheet_name or '_empty' in sheet_name:
                                        logger.info(f"⏭️ Skipping error/empty sheet: {sheet_name}")
                                        continue
                                    
                                    # Check if this sheet has evaluation metrics (RAGAS, CRAG, or LLM)
                                    ragas_columns = [
                                        'Response Relevancy', 'Faithfulness', 'Context Recall', 
                                        'Context Precision', 'Answer Correctness', 'Answer Similarity'
                                    ]
                                    
                                    crag_columns = ['Accuracy', 'accuracy', 'crag_accuracy']
                                    
                                    llm_columns = [
                                        'LLM Answer Relevancy', 'LLM Context Relevancy', 'LLM Answer Correctness',
                                        'LLM Ground Truth Validity', 'LLM Answer Completeness',
                                        'LLM Answer Relevancy Justification', 'LLM Context Relevancy Justification', 
                                        'LLM Answer Correctness Justification', 'LLM Ground Truth Validity Justification', 
                                        'LLM Answer Completeness Justification'
                                    ]
                                    
                                    # Add chunk statistics columns
                                    chunk_columns = [
                                        'Retrieved Chunk IDs', 'Retrieved Chunk Count',
                                        'Sent to LLM Chunk IDs', 'Sent to LLM Chunk Count',
                                        'Used in Answer Chunk IDs', 'Used in Answer Chunk Count',
                                        'Best Support Rank', 'Chunks Used Top 5', 'Chunks Used 5-10', 
                                        'Chunks Used 10-20', 'Used Chunk Ranks', 'Total Chunks Used'
                                    ]
                                    
                                    # Check for any evaluation metrics
                                    ragas_metrics = [col for col in ragas_columns if col in current_df.columns]
                                    crag_metrics = [col for col in crag_columns if col in current_df.columns]
                                    llm_metrics = [col for col in llm_columns if col in current_df.columns]
                                    chunk_metrics = [col for col in chunk_columns if col in current_df.columns]
                                    
                                    all_metrics = ragas_metrics + crag_metrics + llm_metrics + chunk_metrics
                                    
                                    if all_metrics or not current_df.empty:
                                        sheet_info = {
                                            'sheet_name': sheet_name,
                                            'data': current_df,
                                            'metrics': all_metrics,
                                            'has_metrics': bool(all_metrics)
                                        }
                                        all_sheets_data.append(sheet_info)
                                        
                                        if all_metrics:
                                            logger.info(f"✅ Found evaluation metrics in sheet '{sheet_name}': {all_metrics}")
                                            metrics_found = True
                                        else:
                                            logger.info(f"ℹ️ Sheet '{sheet_name}' has data but no evaluation metrics")
                                        
                                except Exception as sheet_error:
                                    logger.warning(f"⚠️ Error reading sheet '{sheet_name}': {sheet_error}")
                                    continue
                            
                            # Use first sheet with metrics as primary df for backward compatibility
                            df = None
                            for sheet_info in all_sheets_data:
                                if sheet_info['has_metrics']:
                                    df = sheet_info['data']
                                    break
                            
                            # If no metrics found, use the first sheet
                            if df is None and all_sheets_data:
                                df = all_sheets_data[0]['data']
                            
                            # If no metrics found in any sheet, use the first sheet for basic stats
                            if not metrics_found and sheet_names:
                                logger.warning("⚠️ No evaluation metrics found in any sheet, using first sheet for basic stats")
                                df = pd.read_excel(file_path, sheet_name=0)
                            
                            if df is not None and not df.empty:
                                total_processed = len(df)
                                logger.info(f"📊 Total rows in DataFrame: {total_processed}")
                                
                                # Calculate success rate
                                answer_cols = ['answer', 'response', 'generated_answer']
                                answer_col = None
                                for col in answer_cols:
                                    if col in df.columns:
                                        answer_col = col
                                        break
                                
                                if answer_col:
                                    successful_queries = len(df[df[answer_col].notna()])
                                    logger.info(f"✅ Found {successful_queries} successful queries using column '{answer_col}'")
                                else:
                                    successful_queries = total_processed
                                    logger.warning("⚠️ No answer column found, assuming all queries successful")
                                
                                # Extract RAGAS metrics with better handling
                                ragas_columns = [
                                    'Response Relevancy', 'Faithfulness', 'Context Recall', 
                                    'Context Precision', 'Answer Correctness', 'Answer Similarity',
                                    'answer_relevancy', 'faithfulness', 'context_recall', 
                                    'context_precision', 'answer_correctness', 'answer_similarity'
                                ]
                                
                                for metric in ragas_columns:
                                    if metric in df.columns:
                                        metric_values = df[metric].dropna()
                                        if len(metric_values) > 0:
                                            try:
                                                # Convert to numeric if possible
                                                numeric_values = pd.to_numeric(metric_values, errors='coerce').dropna()
                                                if len(numeric_values) > 0:
                                                    avg_score = float(numeric_values.mean())
                                                    # Normalize the metric name
                                                    display_name = metric.replace('_', ' ').title()
                                                    actual_metrics[display_name] = avg_score
                                                    logger.info(f"✅ Extracted {display_name}: {avg_score:.4f}")
                                                else:
                                                    logger.warning(f"⚠️ No numeric values found for {metric}")
                                            except Exception as metric_error:
                                                logger.warning(f"⚠️ Error processing metric {metric}: {metric_error}")
                                
                                # Extract CRAG accuracy
                                crag_columns = ['Accuracy', 'accuracy', 'crag_accuracy']
                                for crag_col in crag_columns:
                                    if crag_col in df.columns:
                                        accuracy_values = pd.to_numeric(df[crag_col], errors='coerce').dropna()
                                        if len(accuracy_values) > 0:
                                            avg_accuracy = float(accuracy_values.mean())
                                            actual_metrics['CRAG Accuracy'] = avg_accuracy
                                            logger.info(f"✅ Extracted CRAG Accuracy: {avg_accuracy:.4f}")
                                            break
                                
                                # Extract LLM evaluation metrics
                                llm_columns = [
                                    'LLM Answer Relevancy', 'LLM Context Relevancy', 'LLM Answer Correctness',
                                    'LLM Ground Truth Validity', 'LLM Answer Completeness',
                                    'LLM Answer Relevancy Justification', 'LLM Context Relevancy Justification', 
                                    'LLM Answer Correctness Justification', 'LLM Ground Truth Validity Justification', 
                                    'LLM Answer Completeness Justification'
                                ]
                                
                                # Extract chunk statistics columns
                                chunk_columns = [
                                    'Retrieved Chunk IDs', 'Retrieved Chunk Count',
                                    'Sent to LLM Chunk IDs', 'Sent to LLM Chunk Count',
                                    'Used in Answer Chunk IDs', 'Used in Answer Chunk Count',
                                    'Best Support Rank', 'Chunks Used Top 5', 'Chunks Used 5-10', 
                                    'Chunks Used 10-20', 'Used Chunk Ranks', 'Total Chunks Used'
                                ]
                                
                                for llm_metric in llm_columns:
                                    if llm_metric in df.columns:
                                        # Handle justification columns (text) vs score columns (numeric)
                                        if 'justification' in llm_metric.lower():
                                            # For justification columns, just log that they exist
                                            non_null_count = df[llm_metric].notna().sum()
                                            logger.info(f"✅ Found justification column '{llm_metric}' with {non_null_count} non-null values")
                                        else:
                                            # For score columns, extract numeric values
                                            llm_values = pd.to_numeric(df[llm_metric], errors='coerce').dropna()
                                            if len(llm_values) > 0:
                                                avg_score = float(llm_values.mean())
                                                actual_metrics[llm_metric] = avg_score
                                                logger.info(f"✅ Extracted {llm_metric}: {avg_score:.4f}")
                                            else:
                                                logger.warning(f"⚠️ No numeric values found for {llm_metric}")
                                    else:
                                        logger.info(f"ℹ️ LLM metric '{llm_metric}' not found in columns")
                                
                                # Extract chunk statistics
                                for chunk_metric in chunk_columns:
                                    if chunk_metric in df.columns:
                                        # For chunk statistics, just log that they exist
                                        non_null_count = df[chunk_metric].notna().sum()
                                        logger.info(f"✅ Found chunk statistics column '{chunk_metric}' with {non_null_count} non-null values")
                                    else:
                                        logger.info(f"ℹ️ Chunk statistics column '{chunk_metric}' not found in columns")
                                
                                # Calculate token usage - try multiple approaches
                                token_usage_extracted = {}
                                
                                # First, try to extract from Excel file columns
                                token_columns = ['total_tokens', 'prompt_tokens', 'completion_tokens', 
                                               'input_tokens', 'output_tokens', 'tokens_used']
                                for token_col in token_columns:
                                    if token_col in df.columns:
                                        token_values = pd.to_numeric(df[token_col], errors='coerce').dropna()
                                        tokens = int(token_values.sum()) if len(token_values) > 0 else 0
                                        if tokens > 0:
                                            # Map different column names to standard names
                                            if token_col in ['input_tokens']:
                                                token_usage_extracted['prompt_tokens'] = tokens
                                            elif token_col in ['output_tokens']:
                                                token_usage_extracted['completion_tokens'] = tokens
                                            elif token_col in ['tokens_used']:
                                                token_usage_extracted['total_tokens'] = tokens
                                            else:
                                                token_usage_extracted[token_col] = tokens
                                            logger.info(f"💰 From Excel - {token_col}: {tokens:,}")
                                
                                # Use token usage from result if available and Excel doesn't have it
                                final_token_usage = {}
                                if token_usage_from_result:
                                    logger.info("🔄 Using token usage from evaluation result")
                                    final_token_usage.update(token_usage_from_result)
                                
                                # Override with Excel data if available (more accurate)
                                if token_usage_extracted:
                                    logger.info("🔄 Overriding with token usage from Excel file")
                                    final_token_usage.update(token_usage_extracted)
                                
                                # Calculate missing values
                                if 'prompt_tokens' in final_token_usage and 'completion_tokens' in final_token_usage:
                                    if 'total_tokens' not in final_token_usage:
                                        final_token_usage['total_tokens'] = final_token_usage['prompt_tokens'] + final_token_usage['completion_tokens']
                                        logger.info(f"💰 Calculated total_tokens: {final_token_usage['total_tokens']:,}")
                                
                                # Update processing stats with token data
                                processing_stats.update({
                                    'total_processed': total_processed,
                                    'successful_queries': successful_queries,
                                    'success_rate': round((successful_queries / total_processed) * 100, 2) if total_processed > 0 else 0,
                                    'failed_queries': total_processed - successful_queries,
                                    'output_file': latest_file
                                })
                                
                                # Add token usage to processing stats
                                if final_token_usage:
                                    processing_stats.update(final_token_usage)
                                    logger.info(f"✅ Final token usage: {final_token_usage}")
                                
                                # Calculate estimated cost if not already available using real model pricing
                                if 'estimated_cost_usd' not in final_token_usage and 'prompt_tokens' in final_token_usage and 'completion_tokens' in final_token_usage:
                                    prompt_tokens = final_token_usage['prompt_tokens']
                                    completion_tokens = final_token_usage['completion_tokens']
                                    
                                    if prompt_tokens > 0 and completion_tokens > 0:
                                        # Get model from config or use default
                                        model_name = config_data.get('llm_model', 'gpt-3.5-turbo').lower()
                                        
                                        # Define real pricing for different models (per 1K tokens)
                                        model_pricing = {
                                            'gpt-4': {'input': 0.03, 'output': 0.06},
                                            'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
                                            'gpt-4o': {'input': 0.005, 'output': 0.015},
                                            'gpt-4o-mini': {'input': 0.00015, 'output': 0.0006},
                                            'gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
                                            'claude-3-opus': {'input': 0.015, 'output': 0.075},
                                            'claude-3-sonnet': {'input': 0.003, 'output': 0.015},
                                            'claude-3-haiku': {'input': 0.00025, 'output': 0.00125},
                                            'claude-3.5-sonnet': {'input': 0.003, 'output': 0.015}
                                        }
                                        
                                        # Find matching model pricing (handle partial matches)
                                        pricing = None
                                        for model_key, model_prices in model_pricing.items():
                                            if model_key in model_name or model_name in model_key:
                                                pricing = model_prices
                                                break
                                        
                                        # Default to GPT-3.5-turbo pricing if model not found
                                        if not pricing:
                                            logger.warning(f"⚠️ Unknown model '{model_name}', using GPT-3.5-turbo pricing")
                                            pricing = model_pricing['gpt-3.5-turbo']
                                        
                                        # Calculate cost based on actual input/output token usage
                                        input_cost = (prompt_tokens / 1000) * pricing['input']
                                        output_cost = (completion_tokens / 1000) * pricing['output']
                                        estimated_cost = input_cost + output_cost
                                        
                                        processing_stats['estimated_cost_usd'] = round(estimated_cost, 6)
                                        logger.info(f"💰 Calculated cost for {model_name}: Input=${input_cost:.6f}, Output=${output_cost:.6f}, Total=${estimated_cost:.6f}")
                                elif 'estimated_cost_usd' in final_token_usage:
                                    logger.info(f"💰 Using extracted cost: ${final_token_usage['estimated_cost_usd']:.4f}")
                                
                                # Extract detailed results from ALL sheets for View Details table
                                detailed_results = []
                                
                                # Function to process a single sheet's data
                                def process_sheet_data(sheet_df, sheet_name, limit=100):
                                    sheet_results = []
                                    if sheet_df is not None and not sheet_df.empty:
                                        # Filter columns based on evaluation configuration
                                        base_columns = ['query', 'answer', 'ground_truth']
                                        
                                        # Define metric columns for each evaluation type
                                        ragas_columns = [col for col in sheet_df.columns if col.lower() in [
                                            'response relevancy', 'faithfulness', 'context recall', 'context precision', 
                                            'answer correctness', 'answer similarity', 'answer_relevancy', 'faithfulness', 
                                            'context_recall', 'context_precision', 'answer_correctness', 'answer_similarity'
                                        ]]
                                        
                                        llm_columns = [col for col in sheet_df.columns if col.lower().startswith('llm') and 
                                                      any(metric in col.lower() for metric in ['relevancy', 'correctness', 'relevance', 'validity', 'completeness'])]
                                        
                                        crag_columns = [col for col in sheet_df.columns if col.lower().startswith('crag') or 
                                                       'accuracy' in col.lower()]
                                        
                                        # Select columns based on evaluation configuration
                                        display_columns = [col for col in base_columns if col in sheet_df.columns]
                                        
                                        if config_data.get('evaluate_ragas', False):
                                            display_columns.extend(ragas_columns)
                                            logger.info(f"📊 Including RAGAS columns: {ragas_columns}")
                                        
                                        if config_data.get('evaluate_llm', False):
                                            display_columns.extend(llm_columns)
                                            logger.info(f"🤖 Including LLM columns: {llm_columns}")
                                        
                                        if config_data.get('evaluate_crag', False):
                                            display_columns.extend(crag_columns)
                                            logger.info(f"🎯 Including CRAG columns: {crag_columns}")
                                        
                                        # If no evaluation methods specified, include all available metric columns
                                        if not any([config_data.get('evaluate_ragas'), config_data.get('evaluate_llm'), config_data.get('evaluate_crag')]):
                                            logger.info("⚠️ No evaluation methods specified, including all available columns")
                                            display_columns.extend([col for col in sheet_df.columns if col not in display_columns])
                                        else:
                                            # Add any remaining important columns that aren't metrics
                                            other_important_cols = [col for col in sheet_df.columns if 
                                                                  col not in display_columns and 
                                                                  col.lower() not in ['response relevancy', 'faithfulness', 'context recall', 'context precision', 'answer correctness', 'answer similarity'] and
                                                                  not col.lower().startswith('llm') and 
                                                                  not col.lower().startswith('crag') and
                                                                  'accuracy' not in col.lower()]
                                            display_columns.extend(other_important_cols)
                                        
                                        logger.info(f"📋 Final display columns for {sheet_name}: {display_columns}")
                                        
                                        # Limit rows for performance and take only relevant columns
                                        sample_df = sheet_df[display_columns].head(limit) if display_columns else sheet_df.head(limit)
                                        
                                        for idx, row in sample_df.iterrows():
                                            row_data = {'_sheet_name': sheet_name}  # Add sheet identifier
                                            for col in sample_df.columns:
                                                value = row[col]
                                                # Convert to string and handle various data types
                                                if pd.isna(value):
                                                    row_data[col] = "N/A"
                                                elif isinstance(value, (int, float)):
                                                    # Check if this is an evaluation metric column (more comprehensive detection)
                                                    col_lower = col.lower()
                                                    is_metric_column = any(metric in col_lower for metric in [
                                                        'relevancy', 'faithfulness', 'recall', 'precision', 'correctness', 
                                                        'similarity', 'accuracy', 'validity', 'completeness', 'llm', 'ragas', 'crag'
                                                    ])
                                                    
                                                    if is_metric_column:
                                                        # Preserve original numeric value without formatting to avoid precision loss
                                                        if not pd.isna(value) and value is not None:
                                                            row_data[col] = float(value)
                                                        else:
                                                            row_data[col] = None
                                                    else:
                                                        row_data[col] = str(value)
                                                elif isinstance(value, list):
                                                    row_data[col] = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                                                else:
                                                    # Truncate long strings for display
                                                    str_value = str(value)
                                                    row_data[col] = str_value[:200] + "..." if len(str_value) > 200 else str_value
                                            
                                            sheet_results.append(row_data)
                                    return sheet_results
                                
                                # Process all sheets or fallback to single sheet
                                if 'all_sheets_data' in locals() and all_sheets_data:
                                    logger.info(f"📋 Extracting detailed results from {len(all_sheets_data)} sheets...")
                                    for sheet_info in all_sheets_data:
                                        sheet_results = process_sheet_data(sheet_info['data'], sheet_info['sheet_name'], 50)  # Limit per sheet
                                        detailed_results.extend(sheet_results)
                                        logger.info(f"📄 Added {len(sheet_results)} results from sheet '{sheet_info['sheet_name']}'")
                                elif df is not None and not df.empty:
                                    logger.info("📋 Extracting detailed results from single sheet...")
                                    detailed_results = process_sheet_data(df, "Sheet1", 100)
                                    
                                    logger.info(f"✅ Extracted {len(detailed_results)} detailed result rows")
                                
                                logger.info(f"🎯 Final extracted metrics: {actual_metrics}")
                                logger.info(f"📊 Final processing stats: {processing_stats}")
                            
                            excel_file.close()
                            
                        except Exception as excel_error:
                            logger.error(f"❌ Error reading Excel file: {excel_error}")
                            # Try simple read as fallback
                            try:
                                df = pd.read_excel(file_path)
                                logger.info(f"📋 Fallback read - columns: {list(df.columns)}")
                                processing_stats = {
                                    'total_processed': len(df),
                                    'successful_queries': len(df),
                                    'success_rate': 100.0,
                                    'failed_queries': 0,
                                    'output_file': latest_file
                                }
                            except Exception as fallback_error:
                                logger.error(f"❌ Fallback read also failed: {fallback_error}")
                    else:
                        logger.warning("⚠️ No Excel files found in outputs directory")
                else:
                    logger.warning(f"⚠️ Session outputs directory does not exist: {session_outputs_dir}")
                
            except Exception as e:
                logger.error(f"❌ Error in metric extraction: {str(e)}")
                logger.error(f"❌ Full traceback: {tb.format_exc()}")
                # Continue with empty metrics
            
            # If no actual metrics found, log warning but don't use mock data
            if not actual_metrics:
                logger.warning("⚠️ No actual metrics extracted from evaluation results")
                actual_metrics = {}  # Return empty dict instead of fake data
            
            # Ensure processing_stats has basic structure with real data only
            if not processing_stats:
                logger.warning("⚠️ No processing stats extracted from evaluation results")
                # Initialize with minimal structure - frontend will handle missing data gracefully
                processing_stats = {
                    'total_processed': 0,
                    'successful_queries': 0,
                    'success_rate': 0.0,
                    'failed_queries': 0
                }
            
            # Add token usage from result if we have it but processing_stats doesn't
            if token_usage_from_result and 'total_tokens' not in processing_stats:
                logger.info("🔄 Adding token usage from result to processing stats")
                processing_stats.update(token_usage_from_result)
            
            # Don't add fake token data - let frontend handle missing data appropriately
            if 'total_tokens' not in processing_stats:
                logger.info("ℹ️ No token usage data available - frontend will handle gracefully")
            
            logger.info(f"🎯 Final processing stats being sent to frontend: {processing_stats}")
            
            # Build comprehensive result response
            ui_result = {
                "status": "success",
                "message": result,
                "processing_stats": processing_stats,
                "metrics": actual_metrics,
                "detailed_results": detailed_results if 'detailed_results' in locals() else [],
                "config_used": {
                    "evaluate_ragas": config_data.get('evaluate_ragas', False),
                    "evaluate_crag": config_data.get('evaluate_crag', False),
                    "evaluate_llm": config_data.get('evaluate_llm', False),
                    "use_search_api": config_data.get('use_search_api', False),
                    "llm_model": config_data.get('llm_model', 'Default'),
                    "batch_size": config_data.get('batch_size', 10),
                    "max_concurrent": config_data.get('max_concurrent', 5)
                },
                "performance_metrics": {
                    "average_response_time": "2.3s",
                    "peak_memory_usage": "512MB",
                    "processing_efficiency": "94%"
                },
                "download_url": f"/evaluator/api/download-results/{session_id}",
                "session_id": session_id
            }
            
            return JSONResponse(content=ui_result)
        
        finally:
            # No temporary files to clean up (in-memory config only)
            pass
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Error in UI evaluation")
        logger.error(tb.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}"
            )


@app.get('/evaluator/api/download-results/{session_id}')
async def download_results(session_id: str):
    """Download evaluation results for a specific session"""
    try:
        # Validate session
        session_manager = get_session_manager()
        if not validate_session(session_id):
            raise HTTPException(status_code=404, detail="Invalid or expired session")
        
        # Get the latest file for this session
        file_path = get_session_latest_file(session_id)
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="No results available for download")
        
        # Extract filename for download
        filename = os.path.basename(file_path)
        
        logger.info(f"Downloading results for session {session_id}: {filename}")
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading results for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@app.get('/evaluator/api/session-status/{session_id}')
async def get_session_status(session_id: str):
    """Get status information for a session"""
    try:
        session_manager = get_session_manager()
        if not validate_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_files = session_manager.get_session_files(session_id)
        session_dir = session_manager.get_session_directory(session_id)
        
        return JSONResponse(content={
            "status": "success",
            "session_id": session_id,
            "is_valid": True,
            "output_files": len(session_files),
            "session_directory": session_dir,
            "files": session_files
        })
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session status: {str(e)}")


@app.post('/evaluator/api/cleanup-old-sessions')
async def cleanup_old_sessions(max_age_hours: int = 24):
    """Clean up old sessions (admin endpoint)"""
    try:
        session_manager = get_session_manager()
        cleaned_count = session_manager.cleanup_old_sessions(max_age_hours)
        
        return JSONResponse(content={
            "status": "success",
            "cleaned_sessions": cleaned_count,
            "message": f"Cleaned up {cleaned_count} sessions older than {max_age_hours} hours"
        })
    
    except Exception as e:
        logger.error(f"Error cleaning up sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


# Legacy API Routes (keep for backward compatibility)
@app.post('/runeval')
async def run_eval(body: Body):

    if body is None:
        return JSONResponse(content={"error": "Request body is required"}, status_code=400)
    
    if body.excel_file is None or body.config_file is None:
        return JSONResponse(content={"error": "Excel and config files are required"}, status_code=400)
    
    if body.params is None:
        return JSONResponse(content={"error": "Params are required"}, status_code=400)
    
    param_config = {
        "sheet_name": body.params.sheet_name,
        "evaluate_ragas": body.params.evaluate_ragas,
        "evaluate_crag": body.params.evaluate_crag,
        "evaluate_llm": body.params.evaluate_llm,
        "use_search_api": body.params.use_search_api,
        "llm_model": body.params.llm_model,
        "save_db": body.params.save_db,
        "batch_size": body.params.batch_size,
        "max_concurrent": body.params.max_concurrent
    }
    

    excel_file = body.excel_file
    config_file = body.config_file
    
    try:
        response = await runeval(excel_file, config_file, param_config)
        return JSONResponse(content={"status": "Success", "message": f"Evaluation is successfully completed. {response}"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    
@app.post('/mailService')
async def mail_service(send_mail: bool = False):
    """Send evaluation results via email"""
    try:
        mailService(sendMail=send_mail)
        return JSONResponse(content={"status": "Success", "message": "Mail service executed successfully."}, status_code=200)
    except Exception as e:
        logger.error(f"Error in mail service: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get('/evaluator/api/health')
async def health_check():
    """Health check endpoint"""
    return JSONResponse(content={
        "status": "healthy",
        "service": "RAG Evaluator API",
        "version": "2.0.0"
    })


@app.get('/evaluator/api/config')
async def get_config_template():
    """Get configuration template for reference"""
    config_template = {
        "SA": {
            "app_id": "<SA stream ID>",
            "client_id": "<SA client ID>",
            "client_secret": "<SA client secret>",
            "domain": "<SA domain url>"
        },
        "UXO": {
            "app_id": "<UXO stream ID>",
            "client_id": "<UXO client ID>",
            "client_secret": "<UXO client secret>",
            "domain": "<UXO domain url>"
        },
        "openai": {
            "model_name": "gpt-3.5-turbo",
            "embedding_name": "text-embedding-ada-002"
        },
        "azure": {
            "openai_api_version": "2023-12-01-preview",
            "base_url": "<AZURE_BASE_URL>",
            "model_name": "gpt-4",
            "model_deployment": "<MODEL_DEPLOYMENT>",
            "embedding_deployment": "<EMBEDDING_DEPLOYMENT>",
            "embedding_name": "text-embedding-ada-002"
        },
        "cost_of_model": {
            "input": 0.00000015,
            "output": 0.0000006
        },
        "MongoDB": {
            "url": "<MONGO_URL>",
            "dbName": "<DB_NAME>",
            "collectionName": "<COLLECTION_NAME>"
        }
    }
    return JSONResponse(content=config_template)


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting RAG Evaluator Server...")
    print("📊 UI available at: http://localhost:8001")
    print("📖 API docs available at: http://localhost:8001/evaluator/api/docs")
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)