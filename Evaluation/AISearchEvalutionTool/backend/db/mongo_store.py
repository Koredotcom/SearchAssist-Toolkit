from __future__ import annotations

import json
import logging
import platform
import re
import shutil
import subprocess
import time
import uuid
from datetime import datetime
from typing import Any

from config import get_config
from agents.prompts import DEFAULT_PROMPTS

try:
    from pymongo import ASCENDING, DESCENDING, MongoClient
    from pymongo.errors import ServerSelectionTimeoutError
except ImportError as exc:  # pragma: no cover - dependency guard
    raise RuntimeError(
        "pymongo is required when DB_BACKEND=mongodb. Install backend requirements first."
    ) from exc

logger = logging.getLogger(__name__)


DEFAULT_LLM = {
    "agent1":           {"model": "gpt-4.1",      "temperature": 0.0, "max_tokens": 4000},
    "agent2":           {"model": "gpt-4.1",      "temperature": 0.7, "max_tokens": 3000},
    "agent3":           {"model": "gpt-4.1",      "temperature": 0.0, "max_tokens": 2500},
    "judge":            {"model": "gpt-4.1",      "temperature": 0.0, "max_tokens": 800},
    "filter_generator": {"model": "gpt-4.1-mini", "temperature": 0.0, "max_tokens": 800},
    "insights":         {"model": "gpt-4.1",      "temperature": 0.3, "max_tokens": 4000},
    "answer_generator": {"model": "gpt-4.1",      "temperature": 0.2, "max_tokens": 1200},
}

_client: MongoClient | None = None


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _db():
    global _client
    cfg = get_config().database
    if _client is None:
        _client = MongoClient(cfg.mongodb_uri, serverSelectionTimeoutMS=3000)
    return _client[cfg.mongodb_database]


def _c(name: str):
    return _db()[name]


def _clean(doc: dict | None) -> dict | None:
    if not doc:
        return None
    out = dict(doc)
    out.pop("_id", None)
    return out


def _ensure_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value or "[]")
            return parsed if isinstance(parsed, list) else []
        except (TypeError, ValueError):
            return []
    return []


def _ensure_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _decode_app(doc: dict | None) -> dict | None:
    app = _clean(doc)
    if not app:
        return None
    app["racl_entity_ids"] = _ensure_list(app.get("racl_entity_ids"))
    app["banned_topics"] = _ensure_list(app.get("banned_topics"))
    app.setdefault("is_active", True)
    return app


def _is_mongo_reachable(uri: str, timeout_ms: int = 1500) -> bool:
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
        client.admin.command("ping")
        client.close()
        return True
    except ServerSelectionTimeoutError:
        return False
    except Exception:
        return False


def _try_start_local_mongo(uri: str) -> bool:
    """Attempt to bring up a local MongoDB if the configured URI points at localhost.

    Returns True if the service is reachable after the attempt. macOS / brew only:
    on other platforms (or if mongod is remote) this is a no-op and returns False.
    """
    if "localhost" not in uri and "127.0.0.1" not in uri:
        return False
    if platform.system() != "Darwin":
        return False
    brew = shutil.which("brew")
    if not brew:
        return False
    for label in ("mongodb-community@6.0", "mongodb-community", "mongodb-community@7.0"):
        try:
            proc = subprocess.run(
                [brew, "services", "start", label],
                capture_output=True, text=True, timeout=15,
            )
        except subprocess.SubprocessError:
            continue
        if proc.returncode != 0:
            continue
        logger.info("Mongo | Attempted brew services start %s — waiting for socket…", label)
        for _ in range(15):  # poll up to ~15s
            time.sleep(1)
            if _is_mongo_reachable(uri):
                logger.info("Mongo | Local mongod is now reachable via %s", uri)
                return True
    return False


def _ensure_mongo_running() -> None:
    """Bring up mongod if it's configured to be local and isn't reachable."""
    uri = get_config().database.mongodb_uri
    if _is_mongo_reachable(uri):
        return
    logger.warning("Mongo | %s is not reachable — attempting to start local service", uri)
    if _try_start_local_mongo(uri):
        return
    raise RuntimeError(
        f"MongoDB at {uri} is not reachable and could not be auto-started. "
        "Start it manually (macOS: `brew services start mongodb-community@6.0`) "
        "or set DB_BACKEND=sqlite."
    )


def init_db() -> None:
    _ensure_mongo_running()
    db = _db()
    db.app_config.create_index([("app_id", ASCENDING)], unique=True)
    db.llm_config.create_index([("app_id", ASCENDING), ("agent_name", ASCENDING)], unique=True)
    db.prompt_config.create_index([("app_id", ASCENDING), ("agent_name", ASCENDING), ("version", DESCENDING)])
    db.source_document.create_index([("doc_id", ASCENDING), ("app_id", ASCENDING)], unique=True)
    db.golden_set.create_index([("version", ASCENDING), ("app_id", ASCENDING)], unique=True)
    db.test_case.create_index([("tc_id", ASCENDING)], unique=True)
    db.test_case.create_index([("app_id", ASCENDING), ("golden_set_version", ASCENDING), ("status", ASCENDING)])
    db.agent_scores.create_index([("tc_id", ASCENDING)], unique=True)
    db.job.create_index([("job_id", ASCENDING)], unique=True)
    db.job.create_index([("app_id", ASCENDING), ("created_at", DESCENDING)])
    db.eval_run.create_index([("run_id", ASCENDING)], unique=True)
    db.eval_run.create_index([("app_id", ASCENDING), ("started_at", DESCENDING)])
    db.eval_result.create_index([("run_id", ASCENDING), ("tc_id", ASCENDING)], unique=True)
    db.evaluate_settings.create_index([("app_id", ASCENDING)], unique=True)
    db.perf_run.create_index([("run_id", ASCENDING)], unique=True)
    db.perf_run.create_index([("app_id", ASCENDING), ("started_at", DESCENDING)])
    db.perf_result.create_index([("run_id", ASCENDING), ("seq", ASCENDING)], unique=True)

    for app in db.app_config.find({}, {"app_id": 1}):
        _seed_default_llm_configs(app["app_id"])
        _seed_default_prompts(app["app_id"])


def _seed_default_llm_configs(app_id: str) -> None:
    now = _now()
    for agent, cfg in DEFAULT_LLM.items():
        _c("llm_config").update_one(
            {"app_id": app_id, "agent_name": agent},
            {
                "$setOnInsert": {
                    "id": str(uuid.uuid4()),
                    "app_id": app_id,
                    "agent_name": agent,
                    "model": cfg["model"],
                    "temperature": cfg["temperature"],
                    "max_tokens": cfg["max_tokens"],
                    "updated_at": now,
                }
            },
            upsert=True,
        )


def _seed_default_prompts(app_id: str) -> None:
    now = _now()
    for agent_name, prompt_text in DEFAULT_PROMPTS.items():
        existing = _c("prompt_config").find_one(
            {"app_id": app_id, "agent_name": agent_name, "is_active": True}
        )
        if not existing:
            _c("prompt_config").insert_one({
                "id": str(uuid.uuid4()),
                "app_id": app_id,
                "agent_name": agent_name,
                "prompt_text": prompt_text,
                "version": 1,
                "is_active": True,
                "created_at": now,
            })


def create_app(data: dict) -> dict:
    app_id = f"app-{uuid.uuid4()}"
    now = _now()
    _c("app_config").insert_one({
        "app_id": app_id,
        "name": data["name"],
        "host_url": data["host_url"],
        "bot_id": data["bot_id"],
        "stream_id": data.get("stream_id"),
        "client_id": data.get("client_id", ""),
        "client_secret": data.get("client_secret", ""),
        "jwt_token": data.get("jwt_token", ""),
        "racl_entity_ids": data.get("racl_entity_ids", []),
        "anthropic_key": data.get("anthropic_key", ""),
        "anthropic_base_url": data.get("anthropic_base_url", ""),
        "openai_key": data.get("openai_key", ""),
        "openai_base_url": data.get("openai_base_url", ""),
        "gemini_key": data.get("gemini_key", ""),
        "gemini_base_url": data.get("gemini_base_url", ""),
        "banned_topics": data.get("banned_topics", []),
        "answer_mode": data.get("answer_mode", "answer_generation"),
        "case1_threshold": float(data.get("case1_threshold") or 0.5),
        "case2_threshold": float(data.get("case2_threshold") or 0.5),
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    })
    _seed_default_llm_configs(app_id)
    _seed_default_prompts(app_id)
    return get_app(app_id)


def get_app(app_id: str) -> dict | None:
    return _decode_app(_c("app_config").find_one({"app_id": app_id}))


def list_apps() -> list[dict]:
    return [
        _decode_app(row)
        for row in _c("app_config").find({}).sort("created_at", DESCENDING)
    ]


def update_app(app_id: str, data: dict) -> dict | None:
    fields = {k: v for k, v in data.items() if v is not None}
    if not fields:
        return get_app(app_id)
    fields["updated_at"] = _now()
    result = _c("app_config").update_one({"app_id": app_id}, {"$set": fields})
    return get_app(app_id) if result.matched_count else None


def delete_app(app_id: str) -> bool:
    result = _c("app_config").delete_one({"app_id": app_id})
    if not result.deleted_count:
        return False
    tc_ids = [d["tc_id"] for d in _c("test_case").find({"app_id": app_id}, {"tc_id": 1})]
    run_ids = [d["run_id"] for d in _c("eval_run").find({"app_id": app_id}, {"run_id": 1})]
    for name in (
        "llm_config", "prompt_config", "source_document", "golden_set",
        "test_case", "job", "eval_run",
    ):
        _c(name).delete_many({"app_id": app_id})
    if tc_ids:
        _c("agent_scores").delete_many({"tc_id": {"$in": tc_ids}})
    if run_ids:
        _c("eval_result").delete_many({"run_id": {"$in": run_ids}})
    return True


def get_api_key(app_id: str, provider: str) -> str | None:
    app = get_app(app_id)
    return (app or {}).get(f"{provider}_key") or None


def get_base_url(app_id: str, provider: str) -> str | None:
    app = get_app(app_id)
    url = (app or {}).get(f"{provider}_base_url") or ""
    return url.strip() or None


def get_eval_thresholds(app_id: str) -> dict[str, float]:
    app = get_app(app_id) or {}
    return {
        "case1_threshold": float(app.get("case1_threshold") or 0.5),
        "case2_threshold": float(app.get("case2_threshold") or 0.5),
    }


def get_llm_configs(app_id: str) -> list[dict]:
    return [_clean(r) for r in _c("llm_config").find({"app_id": app_id})]


def get_llm_config(app_id: str, agent_name: str) -> dict:
    row = _c("llm_config").find_one({"app_id": app_id, "agent_name": agent_name})
    if row:
        cfg = _clean(row)
    else:
        cfg = {**DEFAULT_LLM.get(agent_name, DEFAULT_LLM["agent1"]), "app_id": app_id, "agent_name": agent_name}
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
    _c("llm_config").update_one(
        {"app_id": app_id, "agent_name": agent_name},
        {
            "$set": {
                "model": data["model"],
                "temperature": data["temperature"],
                "max_tokens": data["max_tokens"],
                "updated_at": _now(),
            },
            "$setOnInsert": {"id": str(uuid.uuid4()), "app_id": app_id, "agent_name": agent_name},
        },
        upsert=True,
    )
    return get_llm_config(app_id, agent_name)


def get_prompts(app_id: str) -> list[dict]:
    return [_clean(r) for r in _c("prompt_config").find({"app_id": app_id}).sort([("agent_name", ASCENDING), ("version", DESCENDING)])]


def get_active_prompt(app_id: str, agent_name: str) -> dict | None:
    return _clean(_c("prompt_config").find_one(
        {"app_id": app_id, "agent_name": agent_name, "is_active": True},
        sort=[("version", DESCENDING)],
    ))


def save_prompt(app_id: str, agent_name: str, prompt_text: str) -> dict:
    coll = _c("prompt_config")
    coll.update_many({"app_id": app_id, "agent_name": agent_name}, {"$set": {"is_active": False}})
    latest = coll.find_one({"app_id": app_id, "agent_name": agent_name}, sort=[("version", DESCENDING)])
    version = int((latest or {}).get("version") or 0) + 1
    coll.insert_one({
        "id": str(uuid.uuid4()),
        "app_id": app_id,
        "agent_name": agent_name,
        "prompt_text": prompt_text,
        "version": version,
        "is_active": True,
        "created_at": _now(),
    })
    return get_active_prompt(app_id, agent_name)


def get_doc_source_type(app_id: str, doc_id: str) -> str | None:
    row = _c("source_document").find_one({"app_id": app_id, "doc_id": doc_id}, {"sys_content_type": 1})
    return row.get("sys_content_type") if row else None


def get_doc_id_by_title(app_id: str, title: str) -> str | None:
    row = _c("source_document").find_one(
        {"app_id": app_id, "title": {"$regex": f"^{re.escape(title)}$", "$options": "i"}},
        {"doc_id": 1},
    )
    return row.get("doc_id") if row else None


def upsert_source_document(doc: dict) -> None:
    payload = {
        "doc_id": doc["doc_id"],
        "app_id": doc["app_id"],
        "title": doc.get("title"),
        "content_hash": doc.get("content_hash"),
        "content": doc.get("content"),
        "metadata": _ensure_dict(doc.get("metadata")),
        "sys_content_type": doc.get("sys_content_type"),
        "source_url": doc.get("source_url"),
        "connector_id": doc.get("connector_id"),
        "ingested_at": _now(),
    }
    _c("source_document").update_one(
        {"doc_id": doc["doc_id"], "app_id": doc["app_id"]},
        {"$set": payload},
        upsert=True,
    )


def get_golden_set(app_id: str, version: str) -> dict | None:
    return _clean(_c("golden_set").find_one({"app_id": app_id, "version": version}))


def create_golden_set(app_id: str, version: str, notes: str = "") -> None:
    _c("golden_set").update_one(
        {"app_id": app_id, "version": version},
        {"$setOnInsert": {"version": version, "app_id": app_id, "created_at": _now(), "frozen_at": None, "parent_version": None, "notes": notes}},
        upsert=True,
    )


def freeze_golden_set(app_id: str, version: str) -> None:
    _c("golden_set").update_one({"app_id": app_id, "version": version}, {"$set": {"frozen_at": _now()}})


def list_golden_sets(app_id: str) -> list[dict]:
    out = []
    for gs in _c("golden_set").find({"app_id": app_id}).sort("created_at", DESCENDING):
        d = _clean(gs)
        cases = list(_c("test_case").find({"app_id": app_id, "golden_set_version": d["version"]}, {"tc_id": 1}))
        tc_ids = [c["tc_id"] for c in cases]
        scores = list(_c("agent_scores").find({"tc_id": {"$in": tc_ids}}, {"decision": 1})) if tc_ids else []
        d["total_cases"] = len(cases)
        d["kept_cases"] = sum(1 for s in scores if s.get("decision") == "KEEP")
        d["borderline_cases"] = sum(1 for s in scores if s.get("decision") == "BORDERLINE")
        out.append(d)
    return out


def _decode_match_spec(row: dict) -> list[dict]:
    spec = _ensure_list(row.get("reference_match_spec"))
    if spec:
        return spec
    return [{"field": "docId", "value": d} for d in _ensure_list(row.get("reference_doc_ids")) if d]


def _with_score(tc: dict) -> dict:
    d = _clean(tc)
    score = _clean(_c("agent_scores").find_one({"tc_id": d["tc_id"]})) or {}
    d.update({k: v for k, v in score.items() if k not in {"tc_id"}})
    d["reference_doc_ids"] = _ensure_list(d.get("reference_doc_ids"))
    d["reference_match_spec"] = _decode_match_spec(d)
    return d


def list_test_cases(app_id: str, golden_set_version: str) -> list[dict]:
    rows = _c("test_case").find({"app_id": app_id, "golden_set_version": golden_set_version}).sort("created_at", DESCENDING)
    return [_with_score(r) for r in rows]


def get_active_test_cases(app_id: str, golden_set_version: str) -> list[dict]:
    rows = _c("test_case").find({"app_id": app_id, "golden_set_version": golden_set_version, "status": "active"}).sort("created_at", ASCENDING)
    out = []
    for row in rows:
        d = _with_score(row)
        if d.get("decision") in ("KEEP", "BORDERLINE"):
            d["generation_metadata"] = _ensure_dict(d.get("generation_metadata"))
            out.append(d)
    return out


def insert_test_case(tc: dict) -> None:
    payload = {
        **tc,
        "reference_doc_ids": _ensure_list(tc.get("reference_doc_ids")),
        "reference_match_spec": _ensure_list(tc.get("reference_match_spec")),
        "generation_metadata": _ensure_dict(tc.get("generation_metadata")),
        "human_validated": bool(tc.get("human_validated", False)),
        "status": tc.get("status", "active"),
        "created_at": tc.get("created_at") or _now(),
    }
    _c("test_case").update_one({"tc_id": tc["tc_id"]}, {"$set": payload}, upsert=True)


def import_uploaded_test_cases(app_id: str, version: str, cases: list[dict]) -> int:
    count = 0
    for case in cases:
        tc_id = f"tc-{uuid.uuid4()}"
        meta = {}
        if case.get("sys_content_type"):
            meta["sys_content_type"] = case["sys_content_type"]
        insert_test_case({
            "tc_id": tc_id,
            "app_id": app_id,
            "golden_set_version": version,
            "question": case["question"],
            "expected_answer": case.get("expected_answer") or None,
            "expected_behavior": case.get("expected_behavior", "ANSWER"),
            "question_type": case.get("question_type") or None,
            "difficulty": case.get("difficulty") or None,
            "reference_doc_ids": case.get("reference_doc_ids", []),
            "reference_match_spec": case.get("reference_match_spec", []),
            "generation_metadata": meta,
            "human_validated": True,
            "status": "active",
        })
        insert_agent_scores({"tc_id": tc_id, "decision": "KEEP"})
        count += 1
    return count


def insert_agent_scores(scores: dict) -> None:
    payload = {
        "tc_id": scores["tc_id"],
        "clarity": scores.get("clarity"),
        "specificity": scores.get("specificity"),
        "meaningfulness": scores.get("meaningfulness"),
        "answerability": scores.get("answerability"),
        "reference_verifiability": scores.get("reference_verifiability"),
        "answer_uniqueness": scores.get("answer_uniqueness"),
        "decision": scores.get("decision"),
        "primary_concern": scores.get("primary_concern"),
        "rationale": scores.get("rationale"),
    }
    if isinstance(scores.get("scores"), dict):
        payload.update(scores["scores"])
    _c("agent_scores").update_one({"tc_id": scores["tc_id"]}, {"$set": payload}, upsert=True)


def create_job(app_id: str, job_type: str) -> str:
    job_id = f"job-{uuid.uuid4()}"
    now = _now()
    _c("job").insert_one({
        "job_id": job_id, "app_id": app_id, "job_type": job_type,
        "status": "running", "progress": 0, "result": None, "error": None,
        "stop_requested": False, "created_at": now, "updated_at": now,
    })
    return job_id


def update_job(job_id: str, status: str, progress: int = 0, result: dict | None = None, error: str | None = None) -> None:
    _c("job").update_one(
        {"job_id": job_id},
        {"$set": {"status": status, "progress": progress, "result": result, "error": error, "updated_at": _now()}},
    )


def get_job(job_id: str) -> dict | None:
    return _clean(_c("job").find_one({"job_id": job_id}))


def list_jobs(app_id: str) -> list[dict]:
    return [_clean(r) for r in _c("job").find({"app_id": app_id}).sort("created_at", DESCENDING).limit(50)]


def request_stop_job(job_id: str) -> None:
    _c("job").update_one({"job_id": job_id}, {"$set": {"stop_requested": True, "updated_at": _now()}})


def is_stop_requested(job_id: str) -> bool:
    row = _c("job").find_one({"job_id": job_id}, {"stop_requested": 1})
    return bool(row and row.get("stop_requested"))


def create_eval_run(run: dict) -> None:
    _c("eval_run").insert_one({
        "run_id": run["run_id"],
        "app_id": run["app_id"],
        "started_at": run.get("started_at") or _now(),
        "finished_at": None,
        "rag_version": run.get("rag_version", "unknown"),
        "judge_model": run.get("judge_model"),
        "golden_set_version": run["golden_set_version"],
        "trigger": run.get("trigger", "manual"),
        "status": "running",
        "cost_usd": 0,
        "total_cases": run.get("total_cases", 0),
        "passed_cases": 0,
        "verdicted_cases": 0,
    })


def upsert_eval_result(result: dict) -> None:
    payload = {
        **result,
        "retrieved_doc_ids": _ensure_list(result.get("retrieved_doc_ids")),
        "chunk_signals": _ensure_list(result.get("chunk_signals")),
        "scores": _ensure_dict(result.get("scores")),
        "search_payload": _ensure_dict(result.get("search_payload")),
        "search_response": _ensure_dict(result.get("search_response")),
        "recall_at_k": _ensure_dict(result.get("recall_at_k")),
        "attempt_count": result.get("attempt_count", 1),
    }
    _c("eval_result").update_one(
        {"run_id": result["run_id"], "tc_id": result["tc_id"]},
        {"$set": payload},
        upsert=True,
    )


def bulk_update_verdicts(run_id: str, verdicts: list[tuple[str, str | None, str]]) -> None:
    coll = _c("eval_result")
    for tc_id, verdict, source in verdicts:
        coll.update_one({"run_id": run_id, "tc_id": tc_id}, {"$set": {"verdict": verdict, "verdict_source": source}})


def update_run_verdict_counts(run_id: str, passed: int, verdicted: int) -> None:
    _c("eval_run").update_one({"run_id": run_id}, {"$set": {"passed_cases": passed, "verdicted_cases": verdicted}})


def finish_eval_run(run_id: str, passed: int, cost: float, status: str = "complete", avg_chunk_rank: float | None = None, verdicted: int | None = None) -> None:
    _c("eval_run").update_one(
        {"run_id": run_id},
        {"$set": {
            "finished_at": _now(), "status": status, "passed_cases": passed,
            "cost_usd": cost, "avg_chunk_rank": avg_chunk_rank,
            "verdicted_cases": verdicted if verdicted is not None else passed,
        }},
    )


def list_eval_runs(app_id: str) -> list[dict]:
    return [_clean(r) for r in _c("eval_run").find({"app_id": app_id}).sort("started_at", DESCENDING)]


def get_eval_results(run_id: str) -> list[dict]:
    out = []
    for er in _c("eval_result").find({"run_id": run_id}):
        d = _clean(er)
        tc = _clean(_c("test_case").find_one({"tc_id": d["tc_id"]})) or {}
        d.update({
            "question": tc.get("question"),
            "expected_answer": tc.get("expected_answer"),
            "expected_behavior": tc.get("expected_behavior", "ANSWER"),
            "question_type": tc.get("question_type"),
            "difficulty": tc.get("difficulty"),
            "reference_doc_ids": _ensure_list(tc.get("reference_doc_ids")),
        })
        d["retrieved_doc_ids"] = _ensure_list(d.get("retrieved_doc_ids"))
        d["scores"] = _ensure_dict(d.get("scores"))
        d["search_payload"] = _ensure_dict(d.get("search_payload"))
        d["search_response"] = _ensure_dict(d.get("search_response"))
        d["recall_at_k"] = _ensure_dict(d.get("recall_at_k"))
        out.append(d)
    return sorted(out, key=lambda r: str(r.get("question_type") or ""))


def get_completed_tc_ids(run_id: str) -> set[str]:
    return {r["tc_id"] for r in _c("eval_result").find({"run_id": run_id}, {"tc_id": 1})}


def delete_eval_run(app_id: str, run_id: str) -> int:
    n = _c("eval_result").count_documents({"run_id": run_id})
    result = _c("eval_run").delete_one({"run_id": run_id, "app_id": app_id})
    if result.deleted_count:
        _c("eval_result").delete_many({"run_id": run_id})
    return int(n)


def count_runs_using_golden_set(app_id: str, version: str) -> int:
    return int(_c("eval_run").count_documents({"app_id": app_id, "golden_set_version": version}))


def delete_golden_set(app_id: str, version: str) -> dict:
    tc_ids = [r["tc_id"] for r in _c("test_case").find({"app_id": app_id, "golden_set_version": version}, {"tc_id": 1})]
    run_refs = count_runs_using_golden_set(app_id, version)
    deleted = _c("test_case").delete_many({"app_id": app_id, "golden_set_version": version}).deleted_count
    if tc_ids:
        _c("agent_scores").delete_many({"tc_id": {"$in": tc_ids}})
    _c("golden_set").delete_one({"app_id": app_id, "version": version})
    return {"test_cases_deleted": int(deleted), "eval_runs_orphaned": int(run_refs)}


def get_eval_run(run_id: str) -> dict | None:
    return _clean(_c("eval_run").find_one({"run_id": run_id}))


def get_previous_completed_run(app_id: str, golden_set_version: str, before_run_id: str) -> dict | None:
    anchor = get_eval_run(before_run_id)
    if not anchor:
        return None
    return _clean(_c("eval_run").find_one(
        {
            "app_id": app_id,
            "golden_set_version": golden_set_version,
            "status": {"$in": ["complete", "partial"]},
            "run_id": {"$ne": before_run_id},
            "started_at": {"$lt": anchor.get("started_at", "")},
        },
        sort=[("started_at", DESCENDING)],
    ))


def list_completed_runs(app_id: str, limit: int = 50) -> list[dict]:
    return [_clean(r) for r in _c("eval_run").find(
        {"app_id": app_id, "status": {"$in": ["complete", "partial"]}}
    ).sort("started_at", DESCENDING).limit(limit)]


def get_run_diagnostics(run_id: str) -> tuple[dict | None, list[str] | None]:
    row = _c("eval_run").find_one({"run_id": run_id}, {"diagnostics_json": 1, "fired_rule_ids": 1})
    if not row:
        return None, None
    return _ensure_dict(row.get("diagnostics_json")) or None, _ensure_list(row.get("fired_rule_ids")) or None


def set_run_diagnostics(run_id: str, diagnostics: dict, fired_rule_ids: list[str]) -> None:
    _c("eval_run").update_one(
        {"run_id": run_id},
        {"$set": {"diagnostics_json": diagnostics, "fired_rule_ids": fired_rule_ids}},
    )


def get_run_ai_insights(run_id: str) -> dict | None:
    row = _c("eval_run").find_one({"run_id": run_id}, {"ai_insights_md": 1, "ai_insights_model": 1, "ai_insights_generated_at": 1})
    if not row or not row.get("ai_insights_md"):
        return None
    return {
        "markdown": row.get("ai_insights_md"),
        "model": row.get("ai_insights_model"),
        "generated_at": row.get("ai_insights_generated_at"),
    }


def set_run_ai_insights(run_id: str, markdown: str, model: str) -> None:
    _c("eval_run").update_one(
        {"run_id": run_id},
        {"$set": {"ai_insights_md": markdown, "ai_insights_model": model, "ai_insights_generated_at": _now()}},
    )


# ── Evaluate-page settings (auto-saved per app) ─────────────────────────────

def get_evaluate_settings(app_id: str) -> dict | None:
    row = _c("evaluate_settings").find_one({"app_id": app_id})
    if not row:
        return None
    return {"settings": row.get("settings") or {}, "updated_at": row.get("updated_at")}


def upsert_evaluate_settings(app_id: str, settings: dict) -> None:
    _c("evaluate_settings").update_one(
        {"app_id": app_id},
        {"$set": {"settings": settings, "updated_at": _now()}},
        upsert=True,
    )


# ── Performance test runs ───────────────────────────────────────────────────

def create_perf_run(run: dict) -> None:
    _c("perf_run").insert_one({
        "run_id": run["run_id"],
        "app_id": run["app_id"],
        "golden_set_version": run["golden_set_version"],
        "concurrency": run["concurrency"],
        "stop_mode": run["stop_mode"],
        "iterations": run.get("iterations"),
        "duration_s": run.get("duration_s"),
        "ramp_up_s": run.get("ramp_up_s", 0),
        "status": "running",
        "started_at": _now(),
        "finished_at": None,
        "total_requests": 0,
        "success_count": 0,
        "error_count": 0,
        "p50_ms": None, "p95_ms": None, "p99_ms": None,
        "avg_ms": None, "max_ms": None,
        "error_message": None,
    })


def insert_perf_result(result: dict) -> None:
    _c("perf_result").update_one(
        {"run_id": result["run_id"], "seq": result["seq"]},
        {"$set": {
            "tc_id": result.get("tc_id"),
            "status_code": result.get("status_code"),
            "latency_ms": result["latency_ms"],
            "error": result.get("error"),
            "started_at": _now(),
        }},
        upsert=True,
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
    _c("perf_run").update_one(
        {"run_id": run_id},
        {"$set": {
            "status": status,
            "finished_at": _now(),
            "total_requests": total_requests,
            "success_count": success_count,
            "error_count": error_count,
            "p50_ms": aggregates.get("p50"),
            "p95_ms": aggregates.get("p95"),
            "p99_ms": aggregates.get("p99"),
            "avg_ms": aggregates.get("avg"),
            "max_ms": aggregates.get("max"),
            "error_message": error_message,
        }},
    )


def update_perf_run_counters(
    run_id: str, total_requests: int, success_count: int, error_count: int,
    aggregates: dict | None = None,
) -> None:
    update: dict[str, Any] = {
        "total_requests": total_requests,
        "success_count": success_count,
        "error_count": error_count,
    }
    if aggregates is not None:
        update.update({
            "p50_ms": aggregates.get("p50"),
            "p95_ms": aggregates.get("p95"),
            "p99_ms": aggregates.get("p99"),
            "avg_ms": aggregates.get("avg"),
            "max_ms": aggregates.get("max"),
        })
    _c("perf_run").update_one({"run_id": run_id}, {"$set": update})


def get_perf_run(run_id: str) -> dict | None:
    return _clean(_c("perf_run").find_one({"run_id": run_id}))


def list_perf_runs(app_id: str, limit: int = 50) -> list[dict]:
    return [
        _clean(r)
        for r in _c("perf_run").find({"app_id": app_id}).sort("started_at", DESCENDING).limit(limit)
    ]


def get_perf_results(run_id: str, limit: int = 500, offset: int = 0) -> list[dict]:
    cursor = (
        _c("perf_result")
        .find({"run_id": run_id})
        .sort("seq", ASCENDING)
        .skip(offset)
        .limit(limit)
    )
    return [_clean(r) for r in cursor]


def delete_perf_run(app_id: str, run_id: str) -> bool:
    result = _c("perf_run").delete_one({"run_id": run_id, "app_id": app_id})
    if not result.deleted_count:
        return False
    _c("perf_result").delete_many({"run_id": run_id})
    return True
