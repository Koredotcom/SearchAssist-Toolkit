from __future__ import annotations

import logging
import logging.config
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# ── Log file lives next to the database in ../data/logs/ ─────────────────────
_LOG_DIR = Path(__file__).parent.parent / "data" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "backend.log"

# Archive the previous session once per process start (not on every --reload
# hot-reload, which re-imports this module without restarting the process).
# Uses a timestamp suffix so the archive never collides with RotatingFileHandler's
# own .1 / .2 / ... backups.
_ARCHIVE_DONE = "_rag_log_archived" in globals()
if not _ARCHIVE_DONE and _LOG_FILE.exists() and _LOG_FILE.stat().st_size > 0:
    from datetime import datetime as _dt
    _stamp = _dt.now().strftime("%Y%m%d_%H%M%S")
    _LOG_FILE.replace(_LOG_DIR / f"backend.{_stamp}.log")
_rag_log_archived = True  # sentinel — survives subsequent re-imports

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "detailed": {
            "format": "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "[%(levelname)-8s] %(name)s — %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "simple",
            "level": "DEBUG",
        },
        "file": {
            # Rotates at 10 MB, keeps 5 backups → max ~50 MB on disk
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(_LOG_FILE),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "detailed",
            "level": "DEBUG",
        },
    },
    "loggers": {
        # Third-party — only warnings to avoid noise in the log file
        "httpx":      {"level": "WARNING", "propagate": True},
        "httpcore":   {"level": "WARNING", "propagate": True},
        "anthropic":  {"level": "WARNING", "propagate": True},
        "openai":     {"level": "WARNING", "propagate": True},
        "urllib3":    {"level": "WARNING", "propagate": True},
        "uvicorn.access": {"level": "WARNING", "propagate": True},
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["console", "file"],
    },
})

logger = logging.getLogger(__name__)

from db.database import init_db, mark_stale_jobs_failed
from routers import apps, sources, llm_config, prompts, generation, evaluation, golden_sets, results, app_api_keys, query

app = FastAPI(title="RAG Evaluator API", version="1.0.1")

_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "https://searchai-evaluation.vercel.app",
]
_extra = os.getenv("FRONTEND_URL", "").strip()
if _extra:
    _origins.append(_extra)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _log_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    req_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()
    logger.info("→ %s %s [%s]", request.method, request.url.path, req_id)
    try:
        response: Response = await call_next(request)
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        logger.error("✗ %s %s [%s] UNHANDLED %s (%.0fms)",
                     request.method, request.url.path, req_id, type(exc).__name__, elapsed,
                     exc_info=True)
        raise
    elapsed = (time.perf_counter() - start) * 1000
    level = logging.WARNING if response.status_code >= 400 else logging.INFO
    logger.log(level, "← %s %s %d [%s] %.0fms",
               request.method, request.url.path, response.status_code, req_id, elapsed)
    return response


@app.on_event("startup")
def startup():
    logger.info("Starting RAG Evaluator API — initialising database")
    init_db()
    stale = mark_stale_jobs_failed()
    if stale:
        logger.warning("Startup | Marked %d stale running job(s)/run(s) as failed", stale)
    logger.info("Database ready")


app.include_router(apps.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(llm_config.router, prefix="/api")
app.include_router(prompts.router, prefix="/api")
app.include_router(generation.router, prefix="/api")
app.include_router(evaluation.router, prefix="/api")
app.include_router(golden_sets.router, prefix="/api")
app.include_router(results.router, prefix="/api")
app.include_router(app_api_keys.router, prefix="/api")
app.include_router(query.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/debug/db")
def debug_db():
    """Shows database location, size, and table row counts."""
    import sqlite3 as _sq
    from db.database import DB_PATH
    import os
    path = str(DB_PATH)
    exists = os.path.exists(path)
    size_kb = round(os.path.getsize(path) / 1024, 2) if exists else 0
    tables = {}
    if exists:
        conn = _sq.connect(path)
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        for (t,) in rows:
            count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            tables[t] = count
        conn.close()
    return {
        "db_path": path,
        "exists": exists,
        "size_kb": size_kb,
        "tables": tables,
    }
