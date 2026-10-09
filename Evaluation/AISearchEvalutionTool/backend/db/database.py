from __future__ import annotations

from typing import Any

from config import get_config

_cfg = get_config().database

if _cfg.backend == "mongodb":
    from db import mongo_store as _store
else:
    from db import sqlite_store as _store

DB_BACKEND = _cfg.backend
DB_PATH = getattr(_store, "DB_PATH", _cfg.sqlite_db_path)

# Compatibility for the few modules that import get_db directly. MongoDB does
# not expose a SQL connection, so get_db is only available in sqlite mode.
if hasattr(_store, "get_db"):
    get_db = _store.get_db  # type: ignore[attr-defined]
else:
    def get_db() -> Any:  # pragma: no cover - defensive compatibility shim
        raise RuntimeError("get_db() is only available when DB_BACKEND=sqlite")

init_db = _store.init_db
create_app = _store.create_app
get_app = _store.get_app
list_apps = _store.list_apps
update_app = _store.update_app
delete_app = _store.delete_app
get_api_key = _store.get_api_key
get_base_url = _store.get_base_url
get_eval_thresholds = _store.get_eval_thresholds
get_llm_configs = _store.get_llm_configs
get_llm_config = _store.get_llm_config
upsert_llm_config = _store.upsert_llm_config
get_prompts = _store.get_prompts
get_active_prompt = _store.get_active_prompt
save_prompt = _store.save_prompt
get_doc_source_type = _store.get_doc_source_type
get_doc_id_by_title = _store.get_doc_id_by_title
upsert_source_document = _store.upsert_source_document
get_golden_set = _store.get_golden_set
create_golden_set = _store.create_golden_set
freeze_golden_set = _store.freeze_golden_set
list_golden_sets = _store.list_golden_sets
list_test_cases = _store.list_test_cases
get_active_test_cases = _store.get_active_test_cases
insert_test_case = _store.insert_test_case
import_uploaded_test_cases = _store.import_uploaded_test_cases
insert_agent_scores = _store.insert_agent_scores
create_job = _store.create_job
update_job = _store.update_job
get_job = _store.get_job
list_jobs = _store.list_jobs
request_stop_job = _store.request_stop_job
is_stop_requested = _store.is_stop_requested
create_eval_run = _store.create_eval_run
upsert_eval_result = _store.upsert_eval_result
bulk_update_verdicts = _store.bulk_update_verdicts
update_run_verdict_counts = _store.update_run_verdict_counts
finish_eval_run = _store.finish_eval_run
list_eval_runs = _store.list_eval_runs
get_eval_results = _store.get_eval_results
get_completed_tc_ids = _store.get_completed_tc_ids
delete_eval_run = _store.delete_eval_run
count_runs_using_golden_set = _store.count_runs_using_golden_set
delete_golden_set = _store.delete_golden_set
get_eval_run = _store.get_eval_run
get_previous_completed_run = _store.get_previous_completed_run
list_completed_runs = _store.list_completed_runs
get_run_diagnostics = _store.get_run_diagnostics
set_run_diagnostics = _store.set_run_diagnostics
get_run_ai_insights = _store.get_run_ai_insights
set_run_ai_insights = _store.set_run_ai_insights
get_evaluate_settings = _store.get_evaluate_settings
upsert_evaluate_settings = _store.upsert_evaluate_settings
create_perf_run = _store.create_perf_run
insert_perf_result = _store.insert_perf_result
finalize_perf_run = _store.finalize_perf_run
update_perf_run_counters = _store.update_perf_run_counters
get_perf_run = _store.get_perf_run
list_perf_runs = _store.list_perf_runs
get_perf_results = _store.get_perf_results
delete_perf_run = _store.delete_perf_run
