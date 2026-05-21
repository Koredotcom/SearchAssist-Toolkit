# RAG Evaluator

An end-to-end evaluation framework for RAG systems built on **Kore.ai SearchAI**. Supports multiple apps, automated test case generation via a 3-agent pipeline, LLM-as-judge evaluation, and a React UI for full configuration control.

---

## Architecture

```
Agent For testCases Evaluation/
├── backend/          # FastAPI Python API (port 8001)
│   ├── main.py       # FastAPI app, CORS, router registration
│   ├── models.py     # Pydantic request/response models
│   ├── db/
│   │   ├── schema.sql    # SQLite schema (10 tables)
│   │   └── database.py   # All DB helper functions
│   ├── agents/
│   │   ├── prompts.py    # Default system prompts for all agents
│   │   ├── summarizer.py # Agent 1 — doc summarization
│   │   ├── generator.py  # Agent 2 — test case generation
│   │   └── ranker.py     # Agent 3 — quality scoring & filtering
│   ├── judge/
│   │   └── judge.py      # GPT-4.1 LLM-as-judge for eval results
│   ├── koreai/
│   │   ├── client.py     # HTTP client factory (per-app JWT)
│   │   ├── connectors.py # Connector/source listing API
│   │   ├── content.py    # Content-by-Condition API (doc fetch)
│   │   └── search.py     # Advance Search V2 (RAG queries)
│   ├── pipeline/
│   │   ├── generate.py   # Full generation pipeline orchestration
│   │   └── evaluate.py   # Full evaluation pipeline with resumption
│   └── routers/          # One FastAPI router per resource
│       ├── apps.py, sources.py, llm_config.py, prompts.py
│       ├── generation.py, evaluation.py
│       ├── golden_sets.py, results.py
│       └── __init__.py
├── frontend/         # React + Vite + TypeScript (port 5174)
│   └── src/
│       ├── App.tsx           # All routes
│       ├── components/
│       │   └── Layout.tsx    # Collapsible sidebar with per-app nav
│       ├── lib/
│       │   ├── api.ts        # Axios API helpers + all TypeScript types
│       │   └── utils.ts      # cn() Tailwind class merge helper
│       └── pages/
│           ├── AppsPage.tsx       # Create/edit/delete app configs
│           ├── SourcesPage.tsx    # Browse Kore.ai connectors
│           ├── GeneratePage.tsx   # Select sources, run generation
│           ├── EvaluatePage.tsx   # Run evaluation against golden sets
│           ├── GoldenSetsPage.tsx # View/freeze versioned test case sets
│           ├── PromptsPage.tsx    # Edit/upload prompts per agent
│           ├── LLMConfigPage.tsx  # Model/temp/tokens per agent
│           ├── ResultsPage.tsx    # Eval run history and pass rates
│           └── RunDetailPage.tsx  # Per-test-case drill-down
└── data/
    └── eval.db       # SQLite database (auto-created on first run)
```

---

## Pipeline

### Generation (3-Agent Pipeline)

```
Kore.ai Content API
      ↓
  [Agent 1] Summarizer   — extracts key facts from each document (Claude Sonnet)
      ↓
  [Agent 2] Generator    — creates 7 question types with expected answers (Claude Sonnet)
      ↓
  [Agent 3] Ranker       — scores on 6 dimensions, keeps/drops each case (Claude Sonnet)
      ↓
  Golden Set (versioned, immutable once frozen)
```

**7 question types**: factual, multi_hop, comparative, negation_unanswerable, ambiguous, boundary, refusal_required

### Evaluation Pipeline

```
Golden Set (frozen)
      ↓
  Kore.ai Advance Search V2   — RAG query per test case
      ↓
  [Judge] GPT-4.1             — scores faithfulness, relevance, completeness, refusal
      ↓
  Eval Run Results (stored in eval_result table)
```

---

## Setup

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
```

Copy `.env.example` → `.env` and fill in real API keys:
```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

Start the server:
```bash
cd backend
python -m uvicorn main:app --port 8001 --reload
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5174` (proxies `/api` to `http://localhost:8001`).

### 3. First Run

1. Open `http://localhost:5174`
2. Click **New App** and enter your Kore.ai credentials:
   - **Host URL** — your Kore.ai instance base URL
   - **Bot ID** — `st-...` identifier
   - **Stream ID** — `fa-...` (optional)
   - **JWT Token** — bearer token for API auth
   - **RACL Entity IDs** — comma-separated access control entity IDs
3. Go to **Generate** → select sources → set doc count → start generation
4. After generation, freeze the golden set
5. Go to **Evaluate** → select the frozen set → run evaluation
6. View results in **Results** → drill into individual test cases

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Evaluation granularity | Doc-level (`docId`) | Simpler than chunk-level; v1 pilot |
| RAG query API | Advance Search V2 (non-streaming) | Returns `answerSearch` + `searchResults` + `raclEntityIds` support |
| Generation agents | Claude Sonnet 4.6 | Cost-efficient, high quality |
| Judge model | GPT-4.1 | Cross-family to avoid self-preference bias |
| Credentials storage | SQLite (per-app) | Multi-app support; only LLM keys in env |
| Background jobs | FastAPI BackgroundTasks + `job` table | Progress polling, resumable evaluation |
| Prompt versioning | DB-versioned (save = new version) | Full history, rollback to any version |
| Golden set versioning | Semver + `frozen_at` timestamp | Immutable once frozen; safe for CI |

---

## API Reference

Backend runs at `http://localhost:8001/api`. Interactive docs: `http://localhost:8001/docs`

| Method | Path | Description |
|---|---|---|
| GET/POST | `/apps` | List / create apps |
| GET/PUT/DELETE | `/apps/{app_id}` | Get / update / delete app |
| GET | `/apps/{app_id}/sources` | List Kore.ai connectors |
| GET/PUT | `/apps/{app_id}/llm-config` | Get / update LLM config per agent |
| GET/PUT/POST | `/apps/{app_id}/prompts` | Manage prompts (list/update/upload/reset) |
| POST | `/apps/{app_id}/generation/start` | Start generation job |
| POST | `/apps/{app_id}/generation/freeze/{version}` | Freeze a golden set |
| GET | `/apps/{app_id}/generation/jobs` | List generation jobs |
| POST | `/apps/{app_id}/evaluation/start` | Start evaluation job |
| GET | `/apps/{app_id}/evaluation/jobs` | List evaluation jobs |
| GET | `/apps/{app_id}/golden-sets` | List golden sets |
| GET | `/apps/{app_id}/golden-sets/{version}/test-cases` | List test cases |
| GET | `/apps/{app_id}/results` | List eval runs |
| GET | `/apps/{app_id}/results/{run_id}` | Get results for a run |

---

## Notes

- **Port conflict**: If port 8000 is occupied by a previous session, run backend on 8001 (`--port 8001`) and the Vite proxy in `frontend/vite.config.ts` is already configured for 8001.
- **Database**: SQLite file lives at `data/eval.db` (created automatically). Safe to delete to reset all state.
- **Resumption**: Evaluation jobs resume automatically from where they left off if restarted — already-completed test cases are skipped.
- **Budget**: Estimated under $50/month for a 10-doc / ~80 test-case pilot with Sonnet + GPT-4.1.
