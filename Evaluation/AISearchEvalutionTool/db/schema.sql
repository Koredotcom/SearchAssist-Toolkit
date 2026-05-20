PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS source_document (
    doc_id          TEXT PRIMARY KEY,
    title           TEXT,
    content_hash    TEXT,
    content         TEXT,
    metadata        TEXT,               -- JSON blob of full _source
    sys_content_type TEXT,
    source_url      TEXT,
    ingested_at     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS golden_set (
    version         TEXT PRIMARY KEY,   -- semver: 1.0.0
    created_at      TEXT DEFAULT (datetime('now')),
    frozen_at       TEXT,               -- NULL = still editable
    parent_version  TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS test_case (
    tc_id               TEXT PRIMARY KEY,
    golden_set_version  TEXT REFERENCES golden_set(version),
    question            TEXT NOT NULL,
    expected_answer     TEXT NOT NULL,
    expected_behavior   TEXT CHECK(expected_behavior IN ('ANSWER','REFUSE','CLARIFY')),
    question_type       TEXT,
    difficulty          INTEGER CHECK(difficulty IN (1,2,3)),
    answer_type         TEXT,
    reference_doc_ids   TEXT,           -- JSON array of doc_ids
    generation_metadata TEXT,           -- JSON: agent versions, model ids, run_id
    human_validated     INTEGER DEFAULT 0,
    status              TEXT DEFAULT 'active' CHECK(status IN ('active','retired','invalidated')),
    rationale           TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_scores (
    tc_id                   TEXT PRIMARY KEY REFERENCES test_case(tc_id),
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

CREATE TABLE IF NOT EXISTS eval_run (
    run_id              TEXT PRIMARY KEY,
    started_at          TEXT DEFAULT (datetime('now')),
    finished_at         TEXT,
    rag_version         TEXT,
    judge_model         TEXT,
    golden_set_version  TEXT REFERENCES golden_set(version),
    trigger             TEXT CHECK(trigger IN ('ci','manual','cron')),
    status              TEXT DEFAULT 'running' CHECK(status IN ('running','complete','failed','partial')),
    cost_usd            REAL,
    total_cases         INTEGER,
    passed_cases        INTEGER
);

CREATE TABLE IF NOT EXISTS eval_result (
    run_id              TEXT REFERENCES eval_run(run_id),
    tc_id               TEXT REFERENCES test_case(tc_id),
    rag_response        TEXT,
    retrieved_doc_ids   TEXT,           -- JSON array
    chunk_signals       TEXT,           -- JSON: chunkQualified, sentToLLM, usedInAnswer per chunk
    scores              TEXT,           -- JSON: {faithfulness, relevance, completeness, refusal_correct}
    failure_category    TEXT,
    judge_rationale     TEXT,
    latency_llm_ms      INTEGER,
    latency_retrieval_ms INTEGER,
    search_request_id   TEXT,
    attempt_count       INTEGER DEFAULT 1,
    PRIMARY KEY (run_id, tc_id)
);
