# CLAUDE.md — RAG Evaluator Project

Instructions for Claude Code sessions on this project.

## Project Structure

- `backend/` — FastAPI Python API. Always run uvicorn from inside this directory.
- `frontend/` — React + Vite + TypeScript. `npm run dev` from inside this directory.
- `data/eval.db` — SQLite database, auto-created on first backend startup.

## Running the App

```bash
# Backend (from backend/ directory)
cd backend
python -m uvicorn main:app --port 8001 --reload

# Frontend (from frontend/ directory)
cd frontend
npm run dev
```

The frontend proxies `/api` → `http://localhost:8001` (configured in `vite.config.ts`).

**Port note**: Port 8000 may be occupied by a previous or external session. Use 8001 for the backend. Vite will auto-increment if 5173 is taken (will use 5174).

To kill stale backend processes before starting: `pkill -f uvicorn` (in Bash tool).

## Critical TypeScript Rule

`tsconfig.app.json` has `"verbatimModuleSyntax": true`. This means **all type-only imports must use `import type`**:

```typescript
// CORRECT
import { appsApi } from "@/lib/api";
import type { AppConfig } from "@/lib/api";

// ALSO CORRECT (inline form)
import { appsApi, type AppConfig } from "@/lib/api";

// WRONG — will cause runtime error in browser
import { appsApi, AppConfig } from "@/lib/api";
```

TypeScript interfaces, types, and type aliases have no runtime representation. Without `import type`, the browser throws: "The requested module does not provide an export named 'X'".

## Backend Import Rule

The backend is run from the `backend/` directory. All internal imports must use relative package names, NOT the `backend.` prefix:

```python
# CORRECT (running from backend/)
from agents.prompts import DEFAULT_PROMPTS
from db.database import get_app

# WRONG
from backend.agents.prompts import DEFAULT_PROMPTS
```

## Key Files

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI app entry point, CORS, router registration |
| `backend/db/database.py` | All SQLite helpers — create/read/update for every table |
| `backend/db/schema.sql` | SQLite schema (10 tables) |
| `backend/agents/prompts.py` | `DEFAULT_PROMPTS` dict — seeded into DB on app creation |
| `backend/.env` | `ANTHROPIC_API_KEY` + `OPENAI_API_KEY` (Kore.ai creds are in DB) |
| `frontend/src/lib/api.ts` | All TypeScript types + axios API helper objects |
| `frontend/src/components/Layout.tsx` | Sidebar nav (imports AppConfig — use `import type`) |
| `frontend/vite.config.ts` | Proxy `/api` → `http://localhost:8001` |

## Database Tables

`app_config`, `llm_config`, `prompt_config`, `source_document`, `golden_set`, `test_case`, `agent_scores`, `job`, `eval_run`, `eval_result`

- `app_config` stores Kore.ai credentials (host_url, bot_id, stream_id, jwt_token, racl_entity_ids) per app
- `golden_set` uses semver versioning; `frozen_at` is set to lock a set for evaluation
- `job` table tracks background generation/evaluation progress (0–100)
- `eval_result` primary key is `(run_id, tc_id)` — supports resumption

## Locked Decisions (Do Not Change Without Discussion)

- **Evaluation granularity**: doc-level (`docId`), NOT chunk-level — v1 design
- **RAG query API**: Advance Search V2 non-streaming (`/api/public/bot/{bot_id}/search/v2/advanced-search`)
- **docId field**: camelCase `docId` from Kore.ai API — do NOT rename to `doc_id`
- **Generation agents**: Claude Sonnet 4.6
- **Judge model**: GPT-4.1 (cross-family intentional)
- **Credentials**: Only `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` in `.env` — all Kore.ai config is per-app in DB
- **Frontend stack**: React + Vite + TypeScript + Tailwind v4 + lucide-react (no shadcn/ui — no @radix-ui/react-badge)

## Common Gotchas

1. **`lucide-react` version**: Project uses v1.16+ — icon import names may differ from older docs
2. **Tailwind v4**: Uses `@import "tailwindcss"` in CSS (not `@tailwind base/components/utilities`)
3. **`@tailwindcss/vite` plugin**: Tailwind is loaded as a Vite plugin, not PostCSS
4. **`index.css` global styles**: Do NOT add layout styles to `#root` — the Layout component controls full-screen height
5. **SQLite WAL mode**: Schema enables WAL and foreign keys via PRAGMA — both must be set on every connection
6. **Background jobs**: Use FastAPI `BackgroundTasks`, not threads or asyncio — keeps it simple
7. **Prompt versioning**: Saving a new prompt deactivates all old ones and increments version — there is always exactly one `is_active=1` prompt per (app_id, agent_name)
