from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Config:
    # Kore.ai
    koreai_host_url: str = os.environ["KOREAI_HOST_URL"].rstrip("/")
    koreai_bot_id: str = os.environ["KOREAI_BOT_ID"]
    koreai_jwt_token: str = os.environ["KOREAI_JWT_TOKEN"]
    koreai_racl_entity_ids: list[str] = [
        e.strip()
        for e in os.getenv("KOREAI_RACL_ENTITY_IDS", "").split(",")
        if e.strip()
    ]

    # Models
    agent_model: str = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
    judge_model: str = os.getenv("JUDGE_MODEL", "gpt-4.1")

    # Pipeline limits
    max_docs: int = int(os.getenv("MAX_DOCS", "10"))
    max_run_cost_usd: float = float(os.getenv("MAX_RUN_COST_USD", "5.0"))

    # Paths
    db_path: str = os.getenv("DB_PATH", "data/eval.db")


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()
