from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from config import get_config

# ── Database connection ───────────────────────────────────────────────────────
# Priority:
#   1. Turso (TURSO_DATABASE_URL + TURSO_AUTH_TOKEN) — remote hosted SQLite
#   2. Local SQLite via DB_PATH env var or default ./data/eval.db

_TURSO_URL   = os.getenv("TURSO_DATABASE_URL", "")
_TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

DB_PATH = get_config().database.sqlite_db_path


def _connect() -> sqlite3.Connection:
    if _TURSO_URL:
        import libsql_experimental as libsql  # type: ignore
        # Embedded replica: local cache at /tmp synced from Turso
        conn = libsql.connect("/tmp/eval_turso.db", sync_url=_TURSO_URL, auth_token=_TURSO_TOKEN)
        conn.sync()
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn  # type: ignore[return-value]

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = _connect()
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
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    migrations = [
        "ALTER TABLE app_config ADD COLUMN client_id TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE app_config ADD COLUMN client_secret TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE app_config ADD COLUMN anthropic_key TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE app_config ADD COLUMN openai_key TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE app_config ADD COLUMN banned_topics TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE eval_result ADD COLUMN search_payload TEXT DEFAULT '{}'",
        "ALTER TABLE app_config ADD COLUMN answer_mode TEXT NOT NULL DEFAULT 'answer_generation'",
        "ALTER TABLE eval_run ADD COLUMN avg_chunk_rank REAL",
        "ALTER TABLE job ADD COLUMN stop_requested INTEGER DEFAULT 0",
        # 4-case evaluation columns
        "ALTER TABLE eval_result ADD COLUMN case_id INTEGER",
        "ALTER TABLE eval_result ADD COLUMN expected_doc_rank INTEGER",
        "ALTER TABLE eval_result ADD COLUMN recall_at_k TEXT DEFAULT '{}'",
        "ALTER TABLE eval_result ADD COLUMN answer_similarity REAL",
        "ALTER TABLE eval_result ADD COLUMN verdict TEXT",
        "ALTER TABLE eval_result ADD COLUMN verdict_source TEXT",
        # Per-app custom LLM endpoints (Azure / OpenRouter / vLLM / Ollama etc.)
        "ALTER TABLE app_config ADD COLUMN anthropic_base_url TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE app_config ADD COLUMN openai_base_url TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE app_config ADD COLUMN gemini_key TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE app_config ADD COLUMN gemini_base_url TEXT NOT NULL DEFAULT ''",
        # Semantic similarity pass thresholds for Cases 1 & 2 (judge-less mode)
        "ALTER TABLE app_config ADD COLUMN case1_threshold REAL NOT NULL DEFAULT 0.5",
        "ALTER TABLE app_config ADD COLUMN case2_threshold REAL NOT NULL DEFAULT 0.5",
        # Flexible match spec: [{"field": "recordUrl", "value": "..."}] — any chunk JSON field
        "ALTER TABLE test_case ADD COLUMN reference_match_spec TEXT DEFAULT '[]'",
        # Rows with a real pass/fail verdict (excludes null-verdict Case-1 rows)
        "ALTER TABLE eval_run ADD COLUMN verdicted_cases INTEGER DEFAULT 0",
        # ── Phase 2: Insights (diagnostics + rules + AI narrative cache) ─────
        "ALTER TABLE eval_run ADD COLUMN diagnostics_json TEXT",
        "ALTER TABLE eval_run ADD COLUMN fired_rule_ids TEXT",
        "ALTER TABLE eval_run ADD COLUMN ai_insights_md TEXT",
        "ALTER TABLE eval_run ADD COLUMN ai_insights_model TEXT",
        "ALTER TABLE eval_run ADD COLUMN ai_insights_generated_at TEXT",
        # Full raw Kore.ai response per test case (for debugging / UI display)
        "ALTER TABLE eval_result ADD COLUMN search_response TEXT DEFAULT '{}'",
        # Source record title each generated test case came from
        "ALTER TABLE test_case ADD COLUMN record_title TEXT DEFAULT ''",
        # App-wide default LLM (model / Azure deployment) that agents inherit
        "ALTER TABLE app_config ADD COLUMN default_model TEXT NOT NULL DEFAULT ''",
        # Dedicated Azure OpenAI provider (key + endpoint + deployment + api version)
        "ALTER TABLE app_config ADD COLUMN azure_key TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE app_config ADD COLUMN azure_endpoint TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE app_config ADD COLUMN azure_deployment TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE app_config ADD COLUMN azure_api_version TEXT NOT NULL DEFAULT ''",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            pass  # column already exists

    # Make test_case.expected_answer nullable for legacy DBs (SQLite can't ALTER
    # COLUMN, so rebuild only if the NOT NULL constraint is still present).
    _migrate_expected_answer_nullable(conn)

    # Data migration: switch any rows still using the old Anthropic-only defaults
    # to gpt-4.1 so apps without an Anthropic key work out of the box.
    conn.execute(
        """UPDATE llm_config SET model='gpt-4.1'
           WHERE agent_name IN ('agent1','agent2','agent3')
             AND model='claude-sonnet-4-6'"""
    )
    conn.commit()

    # Phase 2: backfill the new 'insights' agent row + prompt for existing apps
    _backfill_insights_agent(conn)
    # Backfill the new 'answer_generator' agent row + prompt for existing apps
    _backfill_agent(conn, "answer_generator")

    # One-time bump: any insights row still at the old 2000-token default is too
    # tight for the ~600-word markdown report and outright unusable for reasoning
    # models (o-series / gpt-5) where thinking tokens consume the budget before
    # any visible content is emitted. Bump to the new 4000 floor; preserves any
    # value the user has deliberately customised (>= 4000).
    conn.execute(
        """UPDATE llm_config SET max_tokens=4000
            WHERE agent_name='insights' AND max_tokens < 4000"""
    )
    conn.commit()


def _backfill_insights_agent(conn: sqlite3.Connection) -> None:
    """Seed the new 'insights' agent (LLM config + prompt) for pre-Phase-2 apps.

    Skips apps that already have an insights row, so re-running is safe.
    """
    _backfill_agent(conn, "insights")


def _backfill_agent(conn: sqlite3.Connection, agent_name: str) -> None:
    """Seed an agent's default LLM config + active prompt for every existing app.

    Idempotent: relies on ``INSERT OR IGNORE`` for the llm_config row and on an
    existence check for the prompt row, so re-running is safe.
    Imported lazily inside the function to avoid bootstrap-import cycles.
    """
    from agents.prompts import DEFAULT_PROMPTS
    prompt_text = DEFAULT_PROMPTS.get(agent_name)
    cfg = DEFAULT_LLM.get(agent_name)
    if not prompt_text or not cfg:
        return
    rows = conn.execute("SELECT app_id FROM app_config").fetchall()
    for r in rows:
        app_id = r["app_id"]
        conn.execute(
            """INSERT OR IGNORE INTO llm_config
                 (id, app_id, agent_name, model, temperature, max_tokens)
               VALUES (?,?,?,?,?,?)""",
            (str(uuid.uuid4()), app_id, agent_name,
             cfg["model"], cfg["temperature"], cfg["max_tokens"]),
        )
        existing = conn.execute(
            "SELECT id FROM prompt_config WHERE app_id=? AND agent_name=? AND is_active=1",
            (app_id, agent_name),
        ).fetchone()
        if not existing:
            conn.execute(
                """INSERT INTO prompt_config (id, app_id, agent_name, prompt_text, version, is_active)
                   VALUES (?,?,?,?,1,1)""",
                (str(uuid.uuid4()), app_id, agent_name, prompt_text),
            )
    conn.commit()


def _migrate_expected_answer_nullable(conn: sqlite3.Connection) -> None:
    """Drop NOT NULL on test_case.expected_answer if present. SQLite-safe rebuild."""
    try:
        cols = conn.execute("PRAGMA table_info(test_case)").fetchall()
    except Exception:
        return
    for c in cols:
        # PRAGMA table_info columns: cid, name, type, notnull, dflt_value, pk
        if c["name"] == "expected_answer" and c["notnull"] == 1:
            break
    else:
        return  # already nullable or column missing

    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("BEGIN")
        conn.execute("""
            CREATE TABLE test_case__new (
                tc_id               TEXT PRIMARY KEY,
                app_id              TEXT NOT NULL REFERENCES app_config(app_id) ON DELETE CASCADE,
                golden_set_version  TEXT NOT NULL,
                question            TEXT NOT NULL,
                expected_answer     TEXT,
                expected_behavior   TEXT CHECK(expected_behavior IN ('ANSWER','REFUSE','CLARIFY')) DEFAULT 'ANSWER',
                question_type       TEXT,
                difficulty          INTEGER CHECK(difficulty IN (1,2,3)),
                answer_type         TEXT,
                reference_doc_ids   TEXT DEFAULT '[]',
                reference_match_spec TEXT DEFAULT '[]',
                generation_metadata TEXT DEFAULT '{}',
                human_validated     INTEGER DEFAULT 0,
                status              TEXT DEFAULT 'active' CHECK(status IN ('active','retired','invalidated')),
                rationale           TEXT,
                created_at          TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            INSERT INTO test_case__new
            SELECT tc_id, app_id, golden_set_version, question, expected_answer,
                   expected_behavior, question_type, difficulty, answer_type,
                   reference_doc_ids, '[]', generation_metadata, human_validated,
                   status, rationale, created_at
            FROM test_case
        """)
        conn.execute("DROP TABLE test_case")
        conn.execute("ALTER TABLE test_case__new RENAME TO test_case")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


# ── App Config ──────────────────────────────────────────────────────────────

def create_app(data: dict) -> dict:
    app_id = f"app-{uuid.uuid4()}"
    with get_db() as conn:
        conn.execute(
            """INSERT INTO app_config
               (app_id, name, host_url, bot_id, stream_id,
                client_id, client_secret, jwt_token, racl_entity_ids,
                anthropic_key, anthropic_base_url,
                openai_key, openai_base_url,
                gemini_key, gemini_base_url, answer_mode)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (app_id, data["name"], data["host_url"], data["bot_id"],
             data.get("stream_id"), data.get("client_id", ""),
             data.get("client_secret", ""), data["jwt_token"],
             json.dumps(data.get("racl_entity_ids", [])),
             data.get("anthropic_key", ""),
             data.get("anthropic_base_url", ""),
             data.get("openai_key", ""),
             data.get("openai_base_url", ""),
             data.get("gemini_key", ""),
             data.get("gemini_base_url", ""),
             data.get("answer_mode", "answer_generation")),
        )
        _seed_default_llm_configs(conn, app_id)
        _seed_default_prompts(conn, app_id)
    return get_app(app_id)


def _decode_app_row(row) -> dict:
    d = dict(row)
    d["racl_entity_ids"] = json.loads(d.get("racl_entity_ids") or "[]")
    d["banned_topics"] = json.loads(d.get("banned_topics") or "[]")
    return d


def get_app(app_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM app_config WHERE app_id=?", (app_id,)
        ).fetchone()
        return _decode_app_row(row) if row else None


def list_apps() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM app_config ORDER BY created_at DESC"
        ).fetchall()
        return [_decode_app_row(r) for r in rows]


def update_app(app_id: str, data: dict) -> dict | None:
    fields = {k: v for k, v in data.items() if v is not None}
    if "racl_entity_ids" in fields:
        fields["racl_entity_ids"] = json.dumps(fields["racl_entity_ids"])
    if "banned_topics" in fields:
        fields["banned_topics"] = json.dumps(fields["banned_topics"])
    if not fields:
        return get_app(app_id)
    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [app_id]
    with get_db() as conn:
        conn.execute(
            f"UPDATE app_config SET {set_clause}, updated_at=datetime('now') WHERE app_id=?",
            values,
        )
    return get_app(app_id)


def delete_app(app_id: str) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM app_config WHERE app_id=?", (app_id,))
        return cur.rowcount > 0


def get_api_key(app_id: str, provider: str) -> str | None:
    """Return the app-specific API key stored in the database."""
    app = get_app(app_id)
    return (app or {}).get(f"{provider}_key") or None


def get_base_url(app_id: str, provider: str) -> str | None:
    """Return the app-specific LLM base URL (custom endpoint), or None to use the SDK default."""
    app = get_app(app_id)
    url = (app or {}).get(f"{provider}_base_url") or ""
    return url.strip() or None


def get_eval_thresholds(app_id: str) -> dict[str, float]:
    """Return Case 1 / Case 2 semantic similarity pass thresholds for the app."""
    app = get_app(app_id) or {}
    return {
        "case1_threshold": float(app.get("case1_threshold") or 0.5),
        "case2_threshold": float(app.get("case2_threshold") or 0.5),
    }


# ── LLM Config ──────────────────────────────────────────────────────────────

DEFAULT_LLM = {
    "agent1":           {"model": "gpt-4.1",      "temperature": 0.0, "max_tokens": 4000},
    "agent2":           {"model": "gpt-4.1",      "temperature": 0.7, "max_tokens": 3000},
    "agent3":           {"model": "gpt-4.1",      "temperature": 0.0, "max_tokens": 2500},
    "judge":            {"model": "gpt-4.1",      "temperature": 0.0, "max_tokens": 800},
    "filter_generator": {"model": "gpt-4.1-mini", "temperature": 0.0, "max_tokens": 800},
    # Phase 2 — AI Deep Dive narrative. User-configurable via LLM Config UI.
    # 4000 tokens covers the ~600-word markdown report comfortably and gives
    # reasoning models (o-series, gpt-5) some headroom for internal thinking.
    "insights":         {"model": "gpt-4.1",      "temperature": 0.3, "max_tokens": 4000},
    # Answer generator — RAG-style "given context + question produce an answer"
    # prompt. Editable + tunable; the actual answer rendering still goes through
    # Kore.ai today, this row exists so users can manage / fine-tune the prompt.
    "answer_generator": {"model": "gpt-4.1",      "temperature": 0.2, "max_tokens": 1200},
}


def _seed_default_llm_configs(conn: sqlite3.Connection, app_id: str) -> None:
    for agent, cfg in DEFAULT_LLM.items():
        conn.execute(
            """INSERT OR IGNORE INTO llm_config (id, app_id, agent_name, model, temperature, max_tokens)
               VALUES (?,?,?,?,?,?)""",
            (str(uuid.uuid4()), app_id, agent, cfg["model"], cfg["temperature"], cfg["max_tokens"]),
        )


def get_llm_configs(app_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM llm_config WHERE app_id=?", (app_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_llm_config(app_id: str, agent_name: str) -> dict:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM llm_config WHERE app_id=? AND agent_name=?",
            (app_id, agent_name),
        ).fetchone()
        if row:
            cfg = dict(row)
        else:
            cfg = {**DEFAULT_LLM.get(agent_name, DEFAULT_LLM["agent1"]),
                   "app_id": app_id, "agent_name": agent_name}
    return _apply_default_model(app_id, agent_name, cfg)


def _apply_default_model(app_id: str, agent_name: str, cfg: dict) -> dict:
    """Resolve an empty per-agent model by inheriting the app's default_model
    (configured on the API Keys page), then the built-in DEFAULT_LLM model."""
    if (cfg.get("model") or "").strip():
        cfg["inherited"] = False
        return cfg
    default_model = ((get_app(app_id) or {}).get("default_model") or "").strip()
    cfg["model"] = default_model or DEFAULT_LLM.get(agent_name, DEFAULT_LLM["agent1"])["model"]
    cfg["inherited"] = bool(default_model)
    return cfg


def upsert_llm_config(app_id: str, agent_name: str, data: dict) -> dict:
    with get_db() as conn:
        conn.execute(
            """INSERT INTO llm_config (id, app_id, agent_name, model, temperature, max_tokens)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(app_id, agent_name) DO UPDATE SET
                 model=excluded.model, temperature=excluded.temperature,
                 max_tokens=excluded.max_tokens, updated_at=datetime('now')""",
            (str(uuid.uuid4()), app_id, agent_name,
             data["model"], data["temperature"], data["max_tokens"]),
        )
    return get_llm_config(app_id, agent_name)


# ── Prompt Config ────────────────────────────────────────────────────────────

from agents.prompts import DEFAULT_PROMPTS


def _seed_default_prompts(conn: sqlite3.Connection, app_id: str) -> None:
    for agent_name, prompt_text in DEFAULT_PROMPTS.items():
        existing = conn.execute(
            "SELECT id FROM prompt_config WHERE app_id=? AND agent_name=? AND is_active=1",
            (app_id, agent_name),
        ).fetchone()
        if not existing:
            conn.execute(
                """INSERT INTO prompt_config (id, app_id, agent_name, prompt_text, version, is_active)
                   VALUES (?,?,?,?,1,1)""",
                (str(uuid.uuid4()), app_id, agent_name, prompt_text),
            )


def get_prompts(app_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM prompt_config WHERE app_id=? ORDER BY agent_name, version DESC",
            (app_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_active_prompt(app_id: str, agent_name: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            """SELECT * FROM prompt_config
               WHERE app_id=? AND agent_name=? AND is_active=1
               ORDER BY version DESC LIMIT 1""",
            (app_id, agent_name),
        ).fetchone()
        return dict(row) if row else None


def save_prompt(app_id: str, agent_name: str, prompt_text: str) -> dict:
    with get_db() as conn:
        # Deactivate existing
        conn.execute(
            "UPDATE prompt_config SET is_active=0 WHERE app_id=? AND agent_name=?",
            (app_id, agent_name),
        )
        # Get next version
        row = conn.execute(
            "SELECT MAX(version) as v FROM prompt_config WHERE app_id=? AND agent_name=?",
            (app_id, agent_name),
        ).fetchone()
        version = (row["v"] or 0) + 1
        prompt_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO prompt_config (id, app_id, agent_name, prompt_text, version, is_active)
               VALUES (?,?,?,?,?,1)""",
            (prompt_id, app_id, agent_name, prompt_text, version),
        )
    return get_active_prompt(app_id, agent_name)


# ── Source Documents ─────────────────────────────────────────────────────────

def get_doc_source_type(app_id: str, doc_id: str) -> str | None:
    """Lookup sys_content_type (Kore.ai source type) for a document."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT sys_content_type FROM source_document WHERE app_id=? AND doc_id=?",
            (app_id, doc_id),
        ).fetchone()
        return row["sys_content_type"] if row else None


def get_doc_id_by_title(app_id: str, title: str) -> str | None:
    """Find a doc_id by matching title (case-insensitive) in source_document."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT doc_id FROM source_document WHERE app_id=? AND title=? COLLATE NOCASE LIMIT 1",
            (app_id, title),
        ).fetchone()
        return row["doc_id"] if row else None


def upsert_source_document(doc: dict) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO source_document
               (doc_id, app_id, title, content_hash, content, metadata,
                sys_content_type, source_url, connector_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (doc["doc_id"], doc["app_id"], doc.get("title"), doc.get("content_hash"),
             doc.get("content"), json.dumps(doc.get("metadata", {})),
             doc.get("sys_content_type"), doc.get("source_url"), doc.get("connector_id")),
        )


# ── Golden Sets ──────────────────────────────────────────────────────────────

def get_golden_set(app_id: str, version: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM golden_set WHERE app_id=? AND version=?",
            (app_id, version),
        ).fetchone()
        return dict(row) if row else None


def create_golden_set(app_id: str, version: str, notes: str = "") -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO golden_set (version, app_id, notes) VALUES (?,?,?)",
            (version, app_id, notes),
        )


def freeze_golden_set(app_id: str, version: str) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE golden_set SET frozen_at=datetime('now') WHERE version=? AND app_id=?",
            (version, app_id),
        )


def list_golden_sets(app_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT g.*,
                 COUNT(tc.tc_id) as total_cases,
                 COALESCE(SUM(CASE WHEN s.decision='KEEP' THEN 1 ELSE 0 END), 0) as kept_cases,
                 COALESCE(SUM(CASE WHEN s.decision='BORDERLINE' THEN 1 ELSE 0 END), 0) as borderline_cases
               FROM golden_set g
               LEFT JOIN test_case tc ON tc.golden_set_version=g.version AND tc.app_id=g.app_id
               LEFT JOIN agent_scores s ON s.tc_id=tc.tc_id
               WHERE g.app_id=?
               GROUP BY g.version, g.app_id
               ORDER BY g.created_at DESC""",
            (app_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_test_cases(app_id: str, golden_set_version: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT tc.*, s.decision,
                 s.clarity, s.specificity, s.meaningfulness,
                 s.answerability, s.reference_verifiability, s.answer_uniqueness
               FROM test_case tc
               LEFT JOIN agent_scores s ON s.tc_id=tc.tc_id
               WHERE tc.app_id=? AND tc.golden_set_version=?
               ORDER BY tc.created_at DESC""",
            (app_id, golden_set_version),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["reference_doc_ids"] = json.loads(d.get("reference_doc_ids") or "[]")
            d["reference_match_spec"] = _decode_match_spec(d)
            result.append(d)
        return result


def _decode_match_spec(row: dict) -> list[dict]:
    """Decode match_spec JSON. Falls back to legacy docId-only spec if empty."""
    spec_json = row.get("reference_match_spec") or "[]"
    try:
        spec = json.loads(spec_json)
    except (TypeError, ValueError):
        spec = []
    if spec:
        return spec
    # Legacy rows: synthesize spec from reference_doc_ids
    doc_ids = row.get("reference_doc_ids") or []
    if isinstance(doc_ids, str):
        try:
            doc_ids = json.loads(doc_ids)
        except (TypeError, ValueError):
            doc_ids = []
    return [{"field": "docId", "value": d} for d in doc_ids if d]


def get_active_test_cases(app_id: str, golden_set_version: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT tc.*, s.decision
               FROM test_case tc
               LEFT JOIN agent_scores s ON s.tc_id=tc.tc_id
               WHERE tc.app_id=? AND tc.golden_set_version=?
                 AND tc.status='active'
                 AND s.decision IN ('KEEP','BORDERLINE')
               ORDER BY tc.created_at""",
            (app_id, golden_set_version),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["reference_doc_ids"] = json.loads(d.get("reference_doc_ids") or "[]")
            d["reference_match_spec"] = _decode_match_spec(d)
            d["generation_metadata"] = json.loads(d.get("generation_metadata") or "{}")
            result.append(d)
        return result


def insert_test_case(tc: dict) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO test_case
               (tc_id, app_id, golden_set_version, question, expected_answer,
                expected_behavior, question_type, difficulty, answer_type,
                record_title, reference_doc_ids, reference_match_spec,
                generation_metadata, rationale)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (tc["tc_id"], tc["app_id"], tc["golden_set_version"],
             tc["question"], tc["expected_answer"],
             tc.get("expected_behavior", "ANSWER"), tc.get("question_type"),
             tc.get("difficulty"), tc.get("answer_type"),
             tc.get("record_title", ""),
             json.dumps(tc.get("reference_doc_ids", [])),
             json.dumps(tc.get("reference_match_spec", [])),
             json.dumps(tc.get("generation_metadata", {})),
             tc.get("rationale")),
        )


def import_uploaded_test_cases(app_id: str, version: str, cases: list[dict]) -> int:
    """Bulk-insert manually uploaded test cases and auto-approve them with KEEP decision.

    `expected_answer` and `reference_doc_ids` may be missing — per-row case
    detection happens at evaluation time based on which fields are populated.
    """
    count = 0
    with get_db() as conn:
        for case in cases:
            tc_id = f"tc-{uuid.uuid4()}"
            meta: dict = {}
            if case.get("sys_content_type"):
                meta["sys_content_type"] = case["sys_content_type"]
            conn.execute(
                """INSERT INTO test_case
                   (tc_id, app_id, golden_set_version, question, expected_answer,
                    expected_behavior, question_type, difficulty, reference_doc_ids,
                    reference_match_spec, generation_metadata, human_validated, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,1,'active')""",
                (
                    tc_id, app_id, version,
                    case["question"], case.get("expected_answer") or None,
                    case.get("expected_behavior", "ANSWER"),
                    case.get("question_type") or None,
                    case.get("difficulty") or None,
                    json.dumps(case.get("reference_doc_ids", [])),
                    json.dumps(case.get("reference_match_spec", [])),
                    json.dumps(meta),
                ),
            )
            conn.execute(
                "INSERT OR REPLACE INTO agent_scores (tc_id, decision) VALUES (?,?)",
                (tc_id, "KEEP"),
            )
            count += 1
    return count


def insert_agent_scores(scores: dict) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO agent_scores
               (tc_id, clarity, specificity, meaningfulness, answerability,
                reference_verifiability, answer_uniqueness, decision, primary_concern, rationale)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (scores["tc_id"], scores.get("clarity"), scores.get("specificity"),
             scores.get("meaningfulness"), scores.get("answerability"),
             scores.get("reference_verifiability"), scores.get("answer_uniqueness"),
             scores.get("decision"), scores.get("primary_concern"), scores.get("rationale")),
        )


# ── Jobs ─────────────────────────────────────────────────────────────────────

def create_job(app_id: str, job_type: str) -> str:
    job_id = f"job-{uuid.uuid4()}"
    with get_db() as conn:
        conn.execute(
            "INSERT INTO job (job_id, app_id, job_type) VALUES (?,?,?)",
            (job_id, app_id, job_type),
        )
    return job_id


def update_job(job_id: str, status: str, progress: int = 0,
               result: dict | None = None, error: str | None = None) -> None:
    with get_db() as conn:
        conn.execute(
            """UPDATE job SET status=?, progress=?, result=?, error=?,
               updated_at=datetime('now') WHERE job_id=?""",
            (status, progress, json.dumps(result) if result else None, error, job_id),
        )


def get_job(job_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM job WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("result"):
            d["result"] = json.loads(d["result"])
        return d


def list_jobs(app_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM job WHERE app_id=? ORDER BY created_at DESC LIMIT 50",
            (app_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("result"):
                d["result"] = json.loads(d["result"])
            result.append(d)
        return result


def request_stop_job(job_id: str) -> None:
    """Mark a running job as stop-requested. The pipeline will stop after the current unit."""
    with get_db() as conn:
        conn.execute(
            "UPDATE job SET stop_requested=1, updated_at=datetime('now') WHERE job_id=?",
            (job_id,),
        )


def is_stop_requested(job_id: str) -> bool:
    with get_db() as conn:
        row = conn.execute("SELECT stop_requested FROM job WHERE job_id=?", (job_id,)).fetchone()
        return bool(row and row["stop_requested"])


# ── Eval Runs ────────────────────────────────────────────────────────────────

def create_eval_run(run: dict) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT INTO eval_run
               (run_id, app_id, rag_version, judge_model, golden_set_version, trigger, total_cases)
               VALUES (?,?,?,?,?,?,?)""",
            (run["run_id"], run["app_id"], run.get("rag_version", "unknown"),
             run.get("judge_model"), run["golden_set_version"],
             run.get("trigger", "manual"), run.get("total_cases", 0)),
        )


def upsert_eval_result(result: dict) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO eval_result
               (run_id, tc_id, rag_response, retrieved_doc_ids, chunk_signals,
                scores, failure_category, judge_rationale,
                latency_llm_ms, latency_retrieval_ms, search_request_id,
                search_payload, search_response, attempt_count,
                case_id, expected_doc_rank, recall_at_k, answer_similarity,
                verdict, verdict_source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (result["run_id"], result["tc_id"], result.get("rag_response"),
             json.dumps(result.get("retrieved_doc_ids", [])),
             json.dumps(result.get("chunk_signals", [])),
             json.dumps(result.get("scores", {})),
             result.get("failure_category"), result.get("judge_rationale"),
             result.get("latency_llm_ms"), result.get("latency_retrieval_ms"),
             result.get("search_request_id"),
             json.dumps(result.get("search_payload") or {}),
             json.dumps(result.get("search_response") or {}),
             result.get("attempt_count", 1),
             result.get("case_id"),
             result.get("expected_doc_rank"),
             json.dumps(result.get("recall_at_k") or {}),
             result.get("answer_similarity"),
             result.get("verdict"),
             result.get("verdict_source")),
        )


def bulk_update_verdicts(
    run_id: str,
    verdicts: list[tuple[str, str | None, str]],  # [(tc_id, verdict, verdict_source), ...]
) -> None:
    """Overwrite verdict + verdict_source for a batch of (run_id, tc_id) rows."""
    with get_db() as conn:
        conn.executemany(
            "UPDATE eval_result SET verdict=?, verdict_source=? WHERE run_id=? AND tc_id=?",
            [(v, s, run_id, tc_id) for (tc_id, v, s) in verdicts],
        )


def update_run_verdict_counts(run_id: str, passed: int, verdicted: int) -> None:
    """Update only the pass/verdict counters on eval_run (preserves cost and other fields)."""
    with get_db() as conn:
        conn.execute(
            "UPDATE eval_run SET passed_cases=?, verdicted_cases=? WHERE run_id=?",
            (passed, verdicted, run_id),
        )


def finish_eval_run(
    run_id: str, passed: int, cost: float,
    status: str = "complete", avg_chunk_rank: float | None = None,
    verdicted: int | None = None,
) -> None:
    with get_db() as conn:
        conn.execute(
            """UPDATE eval_run SET finished_at=datetime('now'), status=?,
               passed_cases=?, cost_usd=?, avg_chunk_rank=?,
               verdicted_cases=? WHERE run_id=?""",
            (status, passed, cost, avg_chunk_rank,
             verdicted if verdicted is not None else passed, run_id),
        )


def list_eval_runs(app_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM eval_run WHERE app_id=? ORDER BY started_at DESC",
            (app_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_eval_results(run_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT er.*, tc.question, tc.expected_answer, tc.expected_behavior,
                      tc.question_type, tc.difficulty, tc.reference_doc_ids
               FROM eval_result er
               JOIN test_case tc ON tc.tc_id=er.tc_id
               WHERE er.run_id=?
               ORDER BY tc.question_type""",
            (run_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["retrieved_doc_ids"] = json.loads(d.get("retrieved_doc_ids") or "[]")
            d["reference_doc_ids"] = json.loads(d.get("reference_doc_ids") or "[]")
            d["scores"] = json.loads(d.get("scores") or "{}")
            d["search_payload"] = json.loads(d.get("search_payload") or "{}")
            d["search_response"] = json.loads(d.get("search_response") or "{}")
            d["recall_at_k"] = json.loads(d.get("recall_at_k") or "{}")
            result.append(d)
        return result


def get_completed_tc_ids(run_id: str) -> set[str]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT tc_id FROM eval_result WHERE run_id=?", (run_id,)
        ).fetchall()
        return {r["tc_id"] for r in rows}


def delete_eval_run(app_id: str, run_id: str) -> int:
    """Delete a run and (via ON DELETE CASCADE) its eval_result rows.

    Returns the number of result rows removed. Does NOT remove the underlying
    job row — that's metadata about the trigger, not the run itself.
    """
    with get_db() as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS c FROM eval_result WHERE run_id=?",
            (run_id,),
        ).fetchone()["c"]
        conn.execute(
            "DELETE FROM eval_run WHERE run_id=? AND app_id=?",
            (run_id, app_id),
        )
        return int(n)


def count_runs_using_golden_set(app_id: str, version: str) -> int:
    """How many eval_runs soft-reference this golden_set_version.

    There's no FK enforcing this — golden_set_version is a plain TEXT field on
    eval_run. We surface the count so the delete confirmation modal can warn.
    """
    with get_db() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS c FROM eval_run
                WHERE app_id=? AND golden_set_version=?""",
            (app_id, version),
        ).fetchone()
        return int(row["c"]) if row else 0


def delete_golden_set(app_id: str, version: str) -> dict:
    """Delete a golden set and all its test cases (+ cascade to agent_scores).

    Returns counts of what was removed so the UI can show a confirmation toast.
    Existing eval_runs that reference this version are LEFT INTACT but become
    orphaned references (the `golden_set_version` text simply no longer
    matches any row in `golden_set`).
    """
    with get_db() as conn:
        tc_count = conn.execute(
            "SELECT COUNT(*) AS c FROM test_case WHERE app_id=? AND golden_set_version=?",
            (app_id, version),
        ).fetchone()["c"]
        run_refs = conn.execute(
            "SELECT COUNT(*) AS c FROM eval_run WHERE app_id=? AND golden_set_version=?",
            (app_id, version),
        ).fetchone()["c"]
        # agent_scores cascade off test_case.tc_id (ON DELETE CASCADE in schema)
        conn.execute(
            "DELETE FROM test_case WHERE app_id=? AND golden_set_version=?",
            (app_id, version),
        )
        conn.execute(
            "DELETE FROM golden_set WHERE app_id=? AND version=?",
            (app_id, version),
        )
        return {
            "test_cases_deleted": int(tc_count),
            "eval_runs_orphaned": int(run_refs),
        }


def get_eval_run(run_id: str) -> dict | None:
    """Fetch a single eval_run row (with insights columns) by id."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM eval_run WHERE run_id=?", (run_id,)
        ).fetchone()
        return dict(row) if row else None


def get_previous_completed_run(
    app_id: str,
    golden_set_version: str,
    before_run_id: str,
) -> dict | None:
    """Most recent completed (or partial) run for this app + golden set strictly older
    than ``before_run_id``. Used for cross-run trend deltas.
    """
    with get_db() as conn:
        anchor = conn.execute(
            "SELECT started_at FROM eval_run WHERE run_id=?",
            (before_run_id,),
        ).fetchone()
        if not anchor:
            return None
        row = conn.execute(
            """SELECT * FROM eval_run
                WHERE app_id=? AND golden_set_version=?
                  AND status IN ('complete','partial')
                  AND run_id <> ?
                  AND started_at < ?
                ORDER BY started_at DESC
                LIMIT 1""",
            (app_id, golden_set_version, before_run_id, anchor["started_at"]),
        ).fetchone()
        return dict(row) if row else None


def list_completed_runs(app_id: str, limit: int = 50) -> list[dict]:
    """All completed/partial runs for an app, newest first. Used for recurrence checks."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM eval_run
                WHERE app_id=? AND status IN ('complete','partial')
                ORDER BY started_at DESC
                LIMIT ?""",
            (app_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Diagnostics & Insights cache ────────────────────────────────────────────

def get_run_diagnostics(run_id: str) -> tuple[dict | None, list[str] | None]:
    """Return (diagnostics_dict, fired_rule_ids) cached on the run, or (None, None)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT diagnostics_json, fired_rule_ids FROM eval_run WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if not row:
            return None, None
        diag = json.loads(row["diagnostics_json"]) if row["diagnostics_json"] else None
        fired = json.loads(row["fired_rule_ids"]) if row["fired_rule_ids"] else None
        return diag, fired


def set_run_diagnostics(
    run_id: str,
    diagnostics: dict,
    fired_rule_ids: list[str],
) -> None:
    """Persist computed diagnostics + fired rule ids on the run."""
    with get_db() as conn:
        conn.execute(
            """UPDATE eval_run
                  SET diagnostics_json=?, fired_rule_ids=?
                WHERE run_id=?""",
            (json.dumps(diagnostics), json.dumps(fired_rule_ids), run_id),
        )


def get_run_ai_insights(run_id: str) -> dict | None:
    """Return cached AI-narrative + metadata for the run, or None if never generated."""
    with get_db() as conn:
        row = conn.execute(
            """SELECT ai_insights_md, ai_insights_model, ai_insights_generated_at
                 FROM eval_run WHERE run_id=?""",
            (run_id,),
        ).fetchone()
        if not row or not row["ai_insights_md"]:
            return None
        return {
            "markdown": row["ai_insights_md"],
            "model": row["ai_insights_model"],
            "generated_at": row["ai_insights_generated_at"],
        }


def set_run_ai_insights(run_id: str, markdown: str, model: str) -> None:
    """Cache the LLM-generated narrative on the run."""
    with get_db() as conn:
        conn.execute(
            """UPDATE eval_run
                  SET ai_insights_md=?, ai_insights_model=?,
                      ai_insights_generated_at=datetime('now')
                WHERE run_id=?""",
            (markdown, model, run_id),
        )


# ── Evaluate-page settings (auto-saved per app) ─────────────────────────────

def get_evaluate_settings(app_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT settings_json, updated_at FROM evaluate_settings WHERE app_id=?",
            (app_id,),
        ).fetchone()
        if not row:
            return None
        try:
            return {"settings": json.loads(row["settings_json"]), "updated_at": row["updated_at"]}
        except (TypeError, ValueError):
            return None


def upsert_evaluate_settings(app_id: str, settings: dict) -> None:
    payload = json.dumps(settings)
    with get_db() as conn:
        conn.execute(
            """INSERT INTO evaluate_settings (app_id, settings_json, updated_at)
                 VALUES (?,?,datetime('now'))
               ON CONFLICT(app_id) DO UPDATE SET
                 settings_json=excluded.settings_json,
                 updated_at=excluded.updated_at""",
            (app_id, payload),
        )


# ── Performance test runs ───────────────────────────────────────────────────

def create_perf_run(run: dict) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT INTO perf_run
                 (run_id, app_id, golden_set_version, concurrency,
                  stop_mode, iterations, duration_s, ramp_up_s, status)
               VALUES (?,?,?,?,?,?,?,?, 'running')""",
            (
                run["run_id"], run["app_id"], run["golden_set_version"],
                run["concurrency"], run["stop_mode"],
                run.get("iterations"), run.get("duration_s"),
                run.get("ramp_up_s", 0),
            ),
        )


def insert_perf_result(result: dict) -> None:
    with get_db() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO perf_result
                 (run_id, seq, tc_id, status_code, latency_ms, error, started_at)
               VALUES (?,?,?,?,?,?, datetime('now'))""",
            (
                result["run_id"], result["seq"], result.get("tc_id"),
                result.get("status_code"), result["latency_ms"], result.get("error"),
            ),
        )


def finalize_perf_run(
    run_id: str,
    status: str,
    total_requests: int,
    success_count: int,
    error_count: int,
    aggregates: dict,
    error_message: str | None = None,
) -> None:
    with get_db() as conn:
        conn.execute(
            """UPDATE perf_run
                 SET status=?, finished_at=datetime('now'),
                     total_requests=?, success_count=?, error_count=?,
                     p50_ms=?, p95_ms=?, p99_ms=?, avg_ms=?, max_ms=?,
                     error_message=?
               WHERE run_id=?""",
            (
                status, total_requests, success_count, error_count,
                aggregates.get("p50"), aggregates.get("p95"),
                aggregates.get("p99"), aggregates.get("avg"),
                aggregates.get("max"), error_message, run_id,
            ),
        )


def update_perf_run_counters(
    run_id: str, total_requests: int, success_count: int, error_count: int,
    aggregates: dict | None = None,
) -> None:
    with get_db() as conn:
        if aggregates is None:
            conn.execute(
                """UPDATE perf_run
                     SET total_requests=?, success_count=?, error_count=?
                   WHERE run_id=?""",
                (total_requests, success_count, error_count, run_id),
            )
        else:
            conn.execute(
                """UPDATE perf_run
                     SET total_requests=?, success_count=?, error_count=?,
                         p50_ms=?, p95_ms=?, p99_ms=?, avg_ms=?, max_ms=?
                   WHERE run_id=?""",
                (
                    total_requests, success_count, error_count,
                    aggregates.get("p50"), aggregates.get("p95"),
                    aggregates.get("p99"), aggregates.get("avg"),
                    aggregates.get("max"), run_id,
                ),
            )


def get_perf_run(run_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM perf_run WHERE run_id=?", (run_id,),
        ).fetchone()
        return dict(row) if row else None


def list_perf_runs(app_id: str, limit: int = 50) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM perf_run
                WHERE app_id=?
                ORDER BY started_at DESC
                LIMIT ?""",
            (app_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_perf_results(run_id: str, limit: int = 500, offset: int = 0) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM perf_result
                WHERE run_id=?
                ORDER BY seq
                LIMIT ? OFFSET ?""",
            (run_id, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_perf_run(app_id: str, run_id: str) -> bool:
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM perf_run WHERE run_id=? AND app_id=?", (run_id, app_id),
        )
        return cur.rowcount > 0
