PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ── App configurations (multi-app support) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS app_config (
    app_id          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    host_url        TEXT NOT NULL,
    bot_id          TEXT NOT NULL,
    stream_id       TEXT,
    client_id       TEXT NOT NULL DEFAULT '',
    client_secret   TEXT NOT NULL DEFAULT '',
    jwt_token       TEXT NOT NULL DEFAULT '',
    anthropic_key   TEXT NOT NULL DEFAULT '',
    anthropic_base_url TEXT NOT NULL DEFAULT '',
    openai_key      TEXT NOT NULL DEFAULT '',
    openai_base_url TEXT NOT NULL DEFAULT '',
    banned_topics   TEXT NOT NULL DEFAULT '[]',  -- JSON array of strings
    answer_mode     TEXT NOT NULL DEFAULT 'answer_generation',  -- 'answer_generation' | 'extract_only'
    case1_threshold REAL NOT NULL DEFAULT 0.5,  -- semantic Q↔Answer similarity pass threshold
    case2_threshold REAL NOT NULL DEFAULT 0.5,  -- semantic Answer↔ExpectedAnswer similarity pass threshold
    racl_entity_ids TEXT DEFAULT '[]',      -- JSON array
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- ── LLM configuration per app per agent ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS llm_config (
    id          TEXT PRIMARY KEY,
    app_id      TEXT NOT NULL REFERENCES app_config(app_id) ON DELETE CASCADE,
    agent_name  TEXT NOT NULL,              -- agent1 | agent2 | agent3 | judge
    model       TEXT NOT NULL,
    temperature REAL DEFAULT 0.0,
    max_tokens  INTEGER DEFAULT 4000,
    updated_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(app_id, agent_name)
);

-- ── Custom prompts per app per agent ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prompt_config (
    id          TEXT PRIMARY KEY,
    app_id      TEXT NOT NULL REFERENCES app_config(app_id) ON DELETE CASCADE,
    agent_name  TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    version     INTEGER DEFAULT 1,
    is_active   INTEGER DEFAULT 1,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- ── Source documents (now app-scoped) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS source_document (
    doc_id           TEXT NOT NULL,
    app_id           TEXT NOT NULL REFERENCES app_config(app_id) ON DELETE CASCADE,
    title            TEXT,
    content_hash     TEXT,
    content          TEXT,
    metadata         TEXT,
    sys_content_type TEXT,
    source_url       TEXT,
    connector_id     TEXT,
    ingested_at      TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (doc_id, app_id)
);

-- ── Golden sets (app-scoped) ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS golden_set (
    version     TEXT NOT NULL,
    app_id      TEXT NOT NULL REFERENCES app_config(app_id) ON DELETE CASCADE,
    created_at  TEXT DEFAULT (datetime('now')),
    frozen_at   TEXT,
    parent_version TEXT,
    notes       TEXT,
    PRIMARY KEY (version, app_id)
);

-- ── Test cases ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS test_case (
    tc_id               TEXT PRIMARY KEY,
    app_id              TEXT NOT NULL REFERENCES app_config(app_id) ON DELETE CASCADE,
    golden_set_version  TEXT NOT NULL,
    question            TEXT NOT NULL,
    expected_answer     TEXT,
    expected_behavior   TEXT CHECK(expected_behavior IN ('ANSWER','REFUSE','CLARIFY')) DEFAULT 'ANSWER',
    question_type       TEXT,
    difficulty          INTEGER CHECK(difficulty IN (1,2,3)),
    answer_type         TEXT,
    reference_doc_ids   TEXT DEFAULT '[]',  -- JSON array (legacy + populated when match field is docId)
    reference_match_spec TEXT DEFAULT '[]', -- JSON: [{"field": "recordUrl", "value": "..."}, ...]
    generation_metadata TEXT DEFAULT '{}',  -- JSON
    human_validated     INTEGER DEFAULT 0,
    status              TEXT DEFAULT 'active' CHECK(status IN ('active','retired','invalidated')),
    rationale           TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

-- ── Agent 3 scores ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_scores (
    tc_id                   TEXT PRIMARY KEY REFERENCES test_case(tc_id) ON DELETE CASCADE,
    clarity                 INTEGER,
    specificity             INTEGER,
    meaningfulness          INTEGER,
    answerability           INTEGER,
    reference_verifiability INTEGER,
    answer_uniqueness       INTEGER,
    decision                TEXT CHECK(decision IN ('KEEP','DROP','BORDERLINE')),
    primary_concern         TEXT,
    rationale               TEXT
);

-- ── Background jobs ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS job (
    job_id      TEXT PRIMARY KEY,
    app_id      TEXT NOT NULL REFERENCES app_config(app_id) ON DELETE CASCADE,
    job_type    TEXT NOT NULL,              -- generation | evaluation
    status      TEXT DEFAULT 'running' CHECK(status IN ('running','complete','failed')),
    progress    INTEGER DEFAULT 0,
    result          TEXT,                       -- JSON
    error           TEXT,
    stop_requested  INTEGER DEFAULT 0,          -- 1 = user requested stop
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- ── Evaluation runs ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS eval_run (
    run_id              TEXT PRIMARY KEY,
    app_id              TEXT NOT NULL REFERENCES app_config(app_id) ON DELETE CASCADE,
    started_at          TEXT DEFAULT (datetime('now')),
    finished_at         TEXT,
    rag_version         TEXT,
    judge_model         TEXT,
    golden_set_version  TEXT NOT NULL,
    trigger             TEXT DEFAULT 'manual' CHECK(trigger IN ('ci','manual','cron')),
    status              TEXT DEFAULT 'running' CHECK(status IN ('running','complete','failed','partial')),
    cost_usd            REAL DEFAULT 0,
    total_cases         INTEGER DEFAULT 0,
    passed_cases        INTEGER DEFAULT 0,
    verdicted_cases     INTEGER DEFAULT 0,  -- rows with a real pass/fail verdict (excludes null)
    -- ── Phase 2: Insights ─────────────────────────────────────────────────────
    diagnostics_json        TEXT,    -- JSON: computed funnel + per-case + judge averages
    fired_rule_ids          TEXT,    -- JSON array of rule_ids that fired for this run
    ai_insights_md          TEXT,    -- Cached LLM-generated narrative (markdown)
    ai_insights_model       TEXT,    -- Model that generated ai_insights_md
    ai_insights_generated_at TEXT    -- ISO timestamp of last narrative generation
);

-- ── Evaluation results ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS eval_result (
    run_id               TEXT NOT NULL REFERENCES eval_run(run_id) ON DELETE CASCADE,
    tc_id                TEXT NOT NULL REFERENCES test_case(tc_id) ON DELETE CASCADE,
    rag_response         TEXT,
    retrieved_doc_ids    TEXT DEFAULT '[]',
    chunk_signals        TEXT DEFAULT '[]',
    scores               TEXT DEFAULT '{}',
    failure_category     TEXT,
    judge_rationale      TEXT,
    latency_llm_ms       INTEGER,
    latency_retrieval_ms INTEGER,
    search_request_id    TEXT,
    search_payload       TEXT DEFAULT '{}',
    attempt_count        INTEGER DEFAULT 1,
    case_id              INTEGER,                -- 1..4 derived from test_case columns present
    expected_doc_rank    INTEGER,                -- 1-based rank of expected doc in retrieved (null if none/not found)
    recall_at_k          TEXT DEFAULT '{}',      -- JSON: {"1":0/1, "3":0/1, "5":0/1, "10":0/1}
    answer_similarity    REAL,                   -- rapidfuzz token-set ratio 0..1 (Cases 2, 4)
    verdict              TEXT,                   -- 'pass' | 'fail' | null (Case 1 no-LLM)
    verdict_source       TEXT,                   -- human-readable label of HOW verdict was derived
    PRIMARY KEY (run_id, tc_id)
);
