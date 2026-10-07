# Production Intelligence & RCA

Evidence-backed root-cause **hypotheses** for injection-moulding incidents (TCS-SASTRA hackathon, use case #11).
Upload a production CSV, get ranked hypotheses with High / Medium / Low confidence, the evidence for and against
each one, verification actions grounded in machine-scoped documents, a cause-and-effect graph, a versioned RCA
draft, and an experience memory of QA-approved cases.

- **Ranking is deterministic.** Scores and confidence come only from the rule engine (`engine/scoring.py` +
  `config/cause_categories.yaml`). The LLM and the agent only explain, draft, summarise and plan read-only tools.
- **Works without an LLM.** With no key, an exhausted quota or the daily budget used up, every response falls back
  to template wording with the same shape, and reports `text_source`.
- Shipped incidents, machines and documents are synthetic. Engineering validation is required before corrective action.

Tested with Python 3.13, Node 24, Docker Desktop 29, Postgres 18.6 + pgvector 0.8.7 (Windows 11, PowerShell).

---

## 1. First-time setup

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm ci
cd ..
```

Create your own `.env` (copy `.env.example`; the app never writes it). At minimum set `JWT_SECRET`,
`SEED_ADMIN_EMAIL` and `SEED_ADMIN_PASSWORD` — without them nobody can sign in.

## 2. Database: Postgres + pgvector in Docker

Port 5433 is used on the host because 5432 is taken by a native PostgreSQL install.

```powershell
docker compose up -d                       # pgvector/pgvector:pg18, volume rca_pgdata, healthcheck
docker compose ps                          # wait for "healthy"
.\.venv\Scripts\python.exe -m alembic upgrade head      # schema (migrations 0001–0005)
.\.venv\Scripts\python.exe -m backend.init_db           # seed machines, SOPs, sample incidents, seed cases, users (idempotent)
.\.venv\Scripts\python.exe -m backend.embed_chunks      # embed document chunks + case summaries (fastembed, local)
```

`backend.init_db` also runs `alembic upgrade head` on Postgres, so the explicit Alembic step is optional.
`DATABASE_URL` must be `postgresql+psycopg://rca:rca@localhost:5433/rca` (the docker-compose credentials are for
local development only).

### Moving data from the old SQLite database

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m backend.migrate_sqlite --source sqlite:///./data/app.db
.\.venv\Scripts\python.exe -m backend.init_db
.\.venv\Scripts\python.exe -m backend.embed_chunks
```

The copy is idempotent (rows that already exist are skipped), converts ISO-text timestamps to `timestamptz`
and JSON to JSONB, and resets ID sequences. Old JSON embeddings are dropped and rebuilt by `embed_chunks`.

SQLite still works (`DATABASE_URL=sqlite:///./data/app.db`) for quick experiments and the test suite, but full-text
and vector search are Postgres features; on SQLite retrieval uses BM25 and in-memory cosine.

## 3. Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000
# second terminal
cd frontend
npm run dev                                 # http://localhost:5173
```

If the API runs on another port, start Vite with `VITE_API_BASE_URL=http://localhost:<port>`.

## 4. Roles

| Role | Can |
|---|---|
| admin | everything, incl. users, audit log, machine specs, plant-wide documents |
| engineer | upload CSVs and documents (machine/model/line scope), analyse, save drafts, propose cases |
| qa_lead | analyse, save drafts, approve/reject/edit/retire cases, run evaluations |
| viewer | read everything, export drafts |

Sign-up creates an **inactive viewer**; an admin activates it on the Users page (pending sign-ups appear on the
dashboard and as a badge). With `DEMO_USERS_ENABLED=true` and `APP_ENV=development` the login page shows four demo
buttons (`demo-admin@demo.local`, `engineer@demo.local`, `qa@demo.local`, `viewer@demo.local`, password
`DEMO_PASSWORD`). Never enable demo mode on a shared server.

## 5. LLM (Gemini) — optional, budgeted

```dotenv
LLM_ENABLED=true
LLM_PROVIDER=gemini                 # OpenAI-compatible endpoint, base URL filled in automatically
LLM_MODEL=gemini-3.8-flash
LLM_API_KEY=<your key from https://aistudio.google.com/apikey>
LLM_DAILY_BUDGET=18                 # Gemini free tier is about 20 requests/day
LLM_MAX_CALLS_PER_ANALYSIS=2        # one agent plan + one wording call
AGENT_MODE=deterministic            # or llm_plan (one call returns the whole read-only tool plan)
```

- The key is read from `LLM_API_KEY` for every provider. `GROQ_API_KEY` is used only when `LLM_PROVIDER=groq`
  and `LLM_API_KEY` is empty.
- Every provider request is counted per UTC day in the database. The top bar shows **"LLM calls today: x / 18"**.
- HTTP 429 / `RESOURCE_EXHAUSTED` / Retry-After > 60 s is **never retried**: the app uses templates at once and
  blocks live calls until the provider's retry time. HTTP 503 is retried at most twice.
- Outputs are cached by incident + analysis input + provider + model + prompt version: re-running an identical
  analysis or re-opening a stored one makes no new call.
- Check a key with at most two requests: `python -m evals.live_llm_check` (results are cached afterwards).

Embeddings stay local: fastembed `BAAI/bge-small-en-v1.5`, 384 dimensions, stored as `vector(384)`. The model is
downloaded once into `data/embedding_cache/`.

## 6. Tests and evaluations

```powershell
.\.venv\Scripts\python.exe -m pytest --db sqlite        # default
.\.venv\Scripts\python.exe -m pytest --db postgres      # needs the docker database; uses rca_test, never rca
.\.venv\Scripts\python.exe -m evals.sanity_check        # ranking regression table (16/16, 16/16, 2/2)
$env:EVAL_DB="postgres"; .\.venv\Scripts\python.exe -m evals.run_evals   # all suites, stored as an eval run
.\.venv\Scripts\python.exe -m evals.live_llm_check      # live provider (spends up to 2 requests)
cd frontend; npm run build
```

Postgres tests create the `rca_test` database if missing and give each test its own schema. Evaluation workers
use a scratch database too (`EVAL_DB=sqlite|postgres`), so evaluations never touch app data or the repository.

Browser checks (headless Chrome via `playwright-core`, app running on 5173 with demo users enabled):
`evals/browser/workflow_walk.mjs <password>` (9-step workflow), `evals/browser/robot_check.mjs` (login page and
robot, 31 checks), `evals/browser/graph_check.mjs <password>` (cause-and-effect graph). Install
`playwright-core` in a scratch folder; set `CHROME_PATH` if Chrome is not in the default location.

## 7. Environment variables

| Name | Required? | Example | What it does |
|---|---|---|---|
| `DATABASE_URL` | yes | `postgresql+psycopg://rca:rca@localhost:5433/rca` | Database. SQLite URLs work for tests/dev. |
| `JWT_SECRET` | yes | 48 random characters | Signs sessions (≥ 32 chars). Missing = random per process in development. |
| `SEED_ADMIN_EMAIL` | yes (first run) | `admin@plant.local` | First administrator, created by `init_db`. |
| `SEED_ADMIN_PASSWORD` | yes (first run) | 10–72 characters | Its password (never reset by later seeds). |
| `APP_ENV` | no | `development` | `development` allows a random JWT secret and demo passwords on the login page. |
| `JWT_EXPIRE_MINUTES` | no | `60` | Session lifetime. |
| `CORS_ORIGINS` | no | `http://localhost:5173,http://127.0.0.1:5173` | Browser origins allowed to call the API. |
| `DEMO_USERS_ENABLED` | no | `false` | Seeds the four demo accounts and shows demo buttons (development only). |
| `DEMO_PASSWORD` | if demo on | 10–72 characters | Password for all demo accounts. |
| `UPLOAD_MAX_MB` / `DOC_UPLOAD_MAX_MB` | no | `10` / `20` | Upload limits for CSVs / documents. |
| `UPLOADS_DIR` / `DOCUMENTS_DIR` | no | empty | Storage folders (default `data/uploads`, `data/documents`). |
| `LLM_ENABLED` | no | `true` | Master switch for LLM wording/planning/summaries. |
| `LLM_PROVIDER` | no | `gemini` | `gemini`, `groq`, `openai_compatible`, `anthropic` (`fake` is test-only). |
| `LLM_MODEL` | no | `gemini-3.8-flash` | Model name for the provider. |
| `LLM_API_KEY` | for LLM | your key | Provider key, read for every provider. |
| `GROQ_API_KEY` | no | empty | Legacy; read only when `LLM_PROVIDER=groq` and `LLM_API_KEY` is empty. |
| `LLM_BASE_URL` | for `openai_compatible` | `https://…/v1` | API root; defaults exist for gemini/groq/anthropic. |
| `LLM_TIMEOUT_SECONDS` | no | `15` | Per-request timeout. |
| `LLM_MAX_RETRIES` | no | `1` | Retries for invalid output/timeouts (never for 4xx or quota). |
| `LLM_DAILY_BUDGET` | no | `18` | Provider requests per UTC day. |
| `LLM_MAX_CALLS_PER_ANALYSIS` | no | `2` | Provider requests per analysis. |
| `AGENT_ENABLED` / `AGENT_MODE` | no | `true` / `deterministic` | Investigation agent; `llm_plan` = one planning call. |
| `AGENT_MAX_STEPS` | no | `10` | Tool-call cap per investigation. |
| `EMBEDDINGS_PROVIDER` | no | `fastembed` | `fastembed` (local), `none`, `openai_compatible`. |
| `EMBEDDINGS_MODEL` | no | `BAAI/bge-small-en-v1.5` | Must produce 384 dimensions. |
| `EMBEDDINGS_API_KEY` / `EMBEDDINGS_BASE_URL` | for `openai_compatible` | | Remote embeddings (not used by default). |
| `RAG_TOP_K` / `RAG_MIN_SCORE` | no | `4` / `0` | Chunks per hypothesis / minimum relevance. |
| `JUDGE_ENABLED` / `JUDGE_MODEL` | no | `false` | Optional live LLM judge in evaluations (spends calls). |
| `CAUSE_CONFIG_PATH` | no | empty | Alternative cause-category config file. |
| `DB_BOOTSTRAP` | no | empty | `migrate` or `create_all`; default migrate on Postgres, create_all on SQLite. |
| `TEST_DB` / `TEST_POSTGRES_URL` / `EVAL_DB` | tests only | `postgres` | Test and evaluation database selection. |
| `VITE_API_BASE_URL` | frontend | `http://localhost:8000` | API address used by the browser app. |

## 8. Project layout

```
backend/        FastAPI app, models (db.py), Alembic migrations, services (workflow, memory agent, graph), CLIs
engine/         signals, deterministic scoring, retrieval (FTS + pgvector + RRF), grounding, LLM, agent, memory
config/         cause_categories.yaml (categories, subcauses, display names, rule weights, thresholds)
evals/          pytest suites, evaluation runner, answer-key consumers, browser checks
frontend/       React + Vite + TypeScript + Tailwind (light theme only); robot in src/features/auth/robot
data/           synthetic incidents, SOPs, seed cases, answer key (read only by evals/)
docker-compose.yml, alembic.ini
```

Status, decisions and verification history: `progress.md`. Final report: `build_report.md`. Audits:
`audit_report_v2.md` (bug IDs B1–B20) and `audit_report.md` (historical).
