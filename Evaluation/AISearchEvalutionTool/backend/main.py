from __future__ import annotations

import logging
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Suppress noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

from db.database import init_db
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


@app.on_event("startup")
def startup():
    logger.info("Starting RAG Evaluator API — initialising database")
    init_db()
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
