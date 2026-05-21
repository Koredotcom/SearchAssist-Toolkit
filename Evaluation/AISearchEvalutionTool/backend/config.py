from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class DatabaseConfig:
    backend: str
    sqlite_db_path: Path
    mongodb_uri: str
    mongodb_database: str


@dataclass(frozen=True)
class BackendConfig:
    database: DatabaseConfig


def _default_sqlite_path() -> Path:
    return Path(__file__).parent.parent / "data" / "eval.db"


def _config_path() -> Path:
    return Path(os.getenv("BACKEND_CONFIG_PATH") or Path(__file__).with_name("config.json"))


def _load_file_config() -> dict:
    path = _config_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _resolve_path(value: str | None) -> Path:
    if not value:
        return _default_sqlite_path()
    path = Path(value)
    if not path.is_absolute():
        path = Path(__file__).parent / path
    return path.resolve()


@lru_cache(maxsize=1)
def get_config() -> BackendConfig:
    file_cfg = _load_file_config()
    db_cfg = file_cfg.get("database", {}) if isinstance(file_cfg.get("database", {}), dict) else {}

    backend = (
        os.getenv("DB_BACKEND")
        or os.getenv("DATABASE_BACKEND")
        or db_cfg.get("backend")
        or "sqlite"
    ).strip().lower()
    if backend not in {"sqlite", "mongodb"}:
        raise ValueError("DB_BACKEND must be either 'sqlite' or 'mongodb'")

    sqlite_path = (
        os.getenv("SQLITE_DB_PATH")
        or os.getenv("DB_PATH")
        or db_cfg.get("sqlite_db_path")
    )
    return BackendConfig(
        database=DatabaseConfig(
            backend=backend,
            sqlite_db_path=_resolve_path(sqlite_path),
            mongodb_uri=os.getenv("MONGODB_URI") or db_cfg.get("mongodb_uri") or "mongodb://localhost:27017",
            mongodb_database=os.getenv("MONGODB_DATABASE") or db_cfg.get("mongodb_database") or "searchassist_eval",
        )
    )


def db_backend() -> str:
    return get_config().database.backend
