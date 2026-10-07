# Build report — v2 (branch `feature/v2`)

Date: 2026-10-07. Built from `main` (c58eed5) in stages 0–9; every stage ended with tests, a progress.md update
and its own commit. Not merged into `main` and not pushed (as instructed). Full detail, every decision and the
live-LLM log are in `progress.md`.

---

## 1. What was built (plain English)

| Stage | What you get now |
|---|---|
| 0 Housekeeping | The LLM key is read from `LLM_API_KEY` for every provider; `GROQ_API_KEY` only for Groq when `LLM_API_KEY` is blank, and a start-up warning tells you when the key sits in the wrong variable (B1). Evaluation fixtures are generated in a temp folder, so running evals no longer changes the repository (B17). The unknown-machine test now fails for the right reason (B16). The committed `tsconfig.tsbuildinfo` is gone. |
| 1 Postgres + pgvector | Postgres 18 + pgvector runs in Docker on port 5433 (your native PostgreSQL on 5432 is untouched). Alembic migrations create the schema; timestamps are timezone-aware (B14), JSON is JSONB, chunk embeddings are `vector(384)` with an HNSW index. Retrieval filters by machine **in SQL first**, then runs full-text and vector search in SQL and merges them (B13). Commands copy your old SQLite data (safe to repeat) and (re)build embeddings locally with fastembed. |
| 2 Gemini, reliably | Quota errors (429 / RESOURCE_EXHAUSTED / long Retry-After) are never retried and block further calls until the provider's retry time; 503 is retried at most twice (B2). The agent is deterministic by default (no LLM calls) or makes one planning call (B3). One wording call per analysis, a daily budget (default 18) counted in the database, at most 2 requests per analysis, and a cache so repeated or re-opened analyses cost nothing. The top bar shows "LLM calls today: x / 18" and each analysis shows its text source and fallback reason. |
| 3 Workflow | Uploaded incidents are listed next to the samples with an "Uploaded" label, machines, date, top hypothesis and a server-derived status: New → Analysed → Draft saved → Case proposed → Case approved / rejected (B5). RCA drafts are saved as versions with history, view and restore, and export to Markdown and PDF with the validation notice always included (B8). Incidents link to their cases and cases to their incident and documents; names replace IDs. New dashboard home page with KPI cards and role-specific to-dos; sidebar badges for pending documents/cases/users. Fixed B4, B6, B11 (plant-wide documents: admin only), B12 (machine page lists only incidents that affected that machine), B18, B19. |
| 4 Memory agent | "Propose case" is two steps: the memory agent drafts symptoms, suggested cause, evidence summary, documents used, lessons and a summary (LLM if available and in budget, template otherwise; invented numbers are rejected), then the engineer edits every field. Duplicate warning for the same incident or a very similar approved case; you can still submit with a reason (B7). Case summaries are embedded and similarity is one weighted recall factor; the old +4 echo of the current top hypothesis is now a visible +1 (B15). QA/admin can edit approved cases (old version kept) or retire them (never recalled again). Every change is audited. |
| 5 Config + graph | Cause categories, subcauses, display names, rule weights and thresholds live in `config/cause_categories.yaml`, validated at start-up; ranking output is byte-identical. The incident page has a cause-and-effect graph (React Flow): evidence → hypotheses → verification actions → cited documents, with rule weights on the edges; clicking a node highlights its whole chain and shows its evidence. The abstain case shows evidence, categories below the minimum, missing checks and references. |
| 6 Login + robot | Login page per the design: sign-in / sign-up toggle (sign-up = inactive viewer until an admin activates it), four demo profile buttons that fill email and password (only in demo mode, development only), eye-icon password toggle, glass capability chips, "Engine online" and footer status badges. The animated robot follows the cursor with lagged springs, blinks, looks around when idle, covers its eyes for the password, peeks when it is shown, thinks on submit, celebrates on success, shakes its head on error, waves for demo profiles, has easter eggs, works on touch, honours reduced motion, and loads in its own chunk behind a same-size placeholder. |
| 7 Hygiene | Every page is its own code chunk: main bundle 760 kB → 276 kB (B20). Admin audit-log viewer with user / action / date filters. README rewritten (Docker, Alembic, SQLite copy, roles, LLM budget, tests, env table). |
| 8 Evals | Retrieval measured on pgvector with real embeddings; new Workflow-and-drafts and Memory-agent suites; RBAC matrix covers 57 endpoint/method pairs; LLM quota/budget fallback suite. The optional agent-plan call now gives up on 503 at once so the wording call keeps the budget. |
| 9 Final verification | Fresh Docker volume → migrate → seed → copy SQLite data → embed; all tests, evals and browser checks below re-run on it. |

**Not done / Unverified**

- **Live LLM wording, live agent plan and the live memory-agent summary: Unverified (provider 503 / timeout).** All 6 live requests got HTTP 503 "overloaded" or a 60 s timeout from `gemini-3.8-flash`. The fallback was correct every time (template wording, grounding passed, quota never touched). See section 3.
- Optional LLM judge suite: Unverified (disabled; it would spend live calls).
- Device-orientation tracking for the robot is implemented but only listens when the browser already allows it (never prompts); not verifiable headless.
- The browser checks were run in headless Chrome, not on a physical phone or a second browser.

## 2. Test and evaluation results (fresh Postgres volume, stage 9)

**pytest:** SQLite **84 passed, 1 skipped** (the skip is the Postgres-only copy test). Postgres **85 passed**.

**Ranking regression** (`python -m evals.sanity_check`): top-1 **16/16**, top-3 **16/16**, abstentions **2/2**, wrong abstentions 0/16, ambiguous alternatives 3/3 — unchanged after every stage.

**Evaluation run** (`EVAL_DB=postgres python -m evals.run_evals`, fastembed, stored as run 4a27c773…):

| Suite | Metric | Value | Threshold | Result |
|---|---|---|---|---|
| RCA ranking | top-1 / top-3 / abstentions / ambiguous | 1.0 / 1.0 / 1.0 / 1.0 | 1 | Pass |
| Document mapping | mapping, precision, recall, ambiguity flag, conflict detection | 1.0 each | 1 | Pass |
| Retrieval (lexical, Postgres FTS) | recall@k / MRR / wrong-machine leaks / filtered-out | 0.852 / 1.0 / 0 / 1.0 | 0.8 / 0.8 / 0 / 1 | Pass |
| Retrieval (hybrid, **postgres+pgvector**, real embeddings) | recall@4 / MRR / leaks / filtered-out | **1.0 / 1.0 / 0 / 1.0** | 0.85 / 0.8 / 0 / 1 | Pass |
| Retrieval | mocked fusion leaks | 0 | 0 | Pass |
| Grounding | final sections supported / steps cite retrieved chunks / adversarial flags | 1.0 / 1.0 / 1.0 | 1 | Pass |
| LLM layer (fake + mocked HTTP) | schema & fallback / quota & budget fallback | 1.0 / 1.0 | 1 | Pass |
| Investigation agent | tool validity, step cap, trace, stable rank, single plan call in budget | 1.0 each; cross-machine attempts 0 | 1 / 0 | Pass |
| Experience memory | leave-one-out agreement / exclusion / approval roles | 0.833 / 1.0 / 1.0 | 0.7 / 1 / 1 | Pass |
| RBAC | endpoint × role matrix (57 endpoint/method pairs, anonymous + 4 roles) | 1.0 | 1 | Pass |
| Workflow and drafts | status transitions / versioning + exports | 1.0 / 1.0 | 1 | Pass |
| Memory agent | summary fields, duplicates, retired never recalled, semantic recall, edit versioning | 1.0 each | 1 | Pass |
| LLM judge | helpfulness / faithfulness | — | — | Unverified (needs live key, spends calls) |

**Browser (headless Chrome, backend on Postgres, Vite dev server):**
workflow walk **9/9** steps as admin, engineer, QA lead and viewer with no reloads or URL workarounds
(`evals/browser/workflow_walk.mjs`); login + robot **31/31** checks (`robot_check.mjs`, also passed 3 runs in a
row in stage 6); cause graph ranked + abstain (`graph_check.mjs`); audit-log filter.
Robot highlights: lag hierarchy eyes 0.88 > head 0.73 > body 0.63 of range 120 ms after a move, ~60+ fps,
CLS ≈ 0.001, robot chunk (146 kB) not in the main bundle, no long tasks while typing, layout holds at 375 / 768 /
1280 / 1536 px.

## 3. Live LLM calls

**6 of the allowed 10 used.** Key passed in memory only (your `.env` has the Gemini key in `GROQ_API_KEY` and
`LLM_API_KEY` empty, so the app itself would not use it). Nothing was written to `.env` and no key was printed.

| # | When | Purpose | Result |
|---|---|---|---|
| 1–2 | stage 2 | agent plan (`llm_plan` mode) | HTTP 503, 503 → template, grounding passed |
| 3–4 | stage 8 | agent plan (`llm_plan` mode) | HTTP 503, 503 → template, grounding passed (led to the plan-fails-fast change) |
| 5–6 | stage 9 | wording only (deterministic agent) | HTTP 503, then ReadTimeout at 60 s → template, grounding passed |

No 429 / quota error was seen, so the quota was not the problem this time; the model was overloaded.
**Status: Unverified.** To verify later (spends at most 2 requests, cached afterwards):
`python -m evals.live_llm_check --agent-mode deterministic`.

## 4. Environment variables

Changes you must make in your `.env` are marked **ADD** or **CHANGE**.

| Name | Required? | Example | What it does | Your .env |
|---|---|---|---|---|
| `DATABASE_URL` | yes | `postgresql+psycopg://rca:rca@localhost:5433/rca` | Database | **CHANGE** (currently SQLite) |
| `JWT_SECRET` | yes | 48 random characters | Signs sessions | **ADD** (empty) |
| `SEED_ADMIN_EMAIL` | yes (first run) | `admin@plant.local` | First admin | **ADD** (empty) |
| `SEED_ADMIN_PASSWORD` | yes (first run) | 10–72 chars | First admin's password | **ADD** (empty) |
| `LLM_PROVIDER` | for LLM | `gemini` | Provider | **CHANGE** (`openai_compatible` also works with the base URL, but `gemini` is simpler) |
| `LLM_API_KEY` | for LLM | your Gemini key | Provider key | **CHANGE**: move the key here from `GROQ_API_KEY` |
| `GROQ_API_KEY` | no | empty | Legacy Groq-only fallback | clear it after moving the key |
| `LLM_BASE_URL` | no for gemini | empty | API root | may stay as is or be emptied |
| `EMBEDDINGS_PROVIDER` | no | `fastembed` | Local embeddings for vector search | **CHANGE** (currently `none`) |
| `LLM_DAILY_BUDGET` | no | `18` | Requests per UTC day | optional ADD |
| `LLM_MAX_CALLS_PER_ANALYSIS` | no | `2` | Requests per analysis | optional ADD |
| `AGENT_MODE` | no | `deterministic` | `llm_plan` = one planning call | optional ADD |
| `DEMO_USERS_ENABLED` / `DEMO_PASSWORD` | no | `true` / 10–72 chars | Demo accounts + login demo buttons (development only) | optional (set both for a demo) |
| `APP_ENV` | no | `development` | Dev conveniences | keep |
| `LLM_MODEL` | no | `gemini-3.8-flash` | Model | keep (check availability in AI Studio if 503s continue) |
| `JWT_EXPIRE_MINUTES`, `CORS_ORIGINS`, `UPLOAD_MAX_MB`, `DOC_UPLOAD_MAX_MB`, `LLM_ENABLED`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `AGENT_ENABLED`, `AGENT_MAX_STEPS`, `EMBEDDINGS_MODEL`, `RAG_TOP_K`, `RAG_MIN_SCORE`, `JUDGE_ENABLED`, `JUDGE_MODEL` | no | see README | unchanged meaning | keep |
| `DOCUMENTS_DIR`, `UPLOADS_DIR`, `DB_BOOTSTRAP`, `CAUSE_CONFIG_PATH`, `EMBEDDINGS_API_KEY`, `EMBEDDINGS_BASE_URL` | no | empty | advanced overrides | not needed |
| `TEST_DB`, `TEST_POSTGRES_URL`, `EVAL_DB` | tests only | `postgres` | test/eval database | not needed in `.env` |
| `VITE_API_BASE_URL` | frontend | `http://localhost:8000` | API address for the browser | only if the API port changes |

## 5. Commands (PowerShell, project folder)

```powershell
# Start the database (Docker Desktop must be running)
docker compose up -d
# Migrate, seed, move data from SQLite, build embeddings
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m backend.init_db
.\.venv\Scripts\python.exe -m backend.migrate_sqlite --source sqlite:///./data/app.db
.\.venv\Scripts\python.exe -m backend.embed_chunks
# Run backend and frontend
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000
cd frontend; npm run dev          # second terminal, http://localhost:5173
# Tests
.\.venv\Scripts\python.exe -m pytest --db sqlite
.\.venv\Scripts\python.exe -m pytest --db postgres
# Evaluations
.\.venv\Scripts\python.exe -m evals.sanity_check
$env:EVAL_DB="postgres"; .\.venv\Scripts\python.exe -m evals.run_evals
# Live LLM check (spends at most 2 requests)
.\.venv\Scripts\python.exe -m evals.live_llm_check --agent-mode deterministic
```

## 6. Decisions I made, and open questions

Decisions (full list with reasons in progress.md, D0.1–D8.2): key-variable warning instead of touching `.env`;
eval fixtures in temp folders; Postgres FTS + pgvector with RRF and iterative HNSW scans (SQLite keeps BM25 for
tests); search is read-only (embedding at upload/activation or via the command); verification steps prefer
numbered steps and drafts cite raw references by ID; separate `rca_test` database with a schema per test; every
provider request counts toward the budget and quota errors block until the retry time; LLM cache in the database;
incident registry table with derived status; new `draft` and `plant_documents` permissions; user display names;
fpdf2 Latin-1 PDF export; memory-agent LLM limited to wording with a number guard; duplicate checks on full case
text; B15 as a visible +1; a separate demo admin so the real admin password is never exposed; demo passwords only
in development; fixed 2×2 demo-button grid to avoid layout shift; route code-splitting; tests pin LLM settings;
the agent-plan call fails fast on 503.

Open questions for you:
1. Gemini returned 503/timeouts all day. Keep `gemini-3.8-flash`, or switch model/plan? Re-run the live check when it is less busy.
2. `data/uploads/` holds 46 older uploaded CSVs (from earlier sessions/audits). They now show up as "Uploaded" incidents. Keep them or clear the folder? (I did not delete anything.)
3. Merge `feature/v2` into `main` and push? (Not done, as instructed.)
4. The headless browser checks need `playwright-core` (installed only in a scratch folder). Add it as a dev dependency?
5. The PDF export uses built-in Latin-1 fonts (symbols like → become "->"). Is that acceptable, or should a Unicode font be bundled?

## 7. Branch and commits

Branch `feature/v2` (from `main` c58eed5):

```
v2 stage 0: key resolution fix, temp eval fixtures, test and repo hygiene                        403b796
v2 stage 1: Postgres + pgvector, Alembic, SQL-first hybrid retrieval, SQLite data copy          7e150de
v2 stage 2: quota-safe Gemini calls, daily/per-analysis budgets, single-call agent plan, DB cache 4fbeaaf
v2 stage 3: incident registry and status, versioned drafts with exports, dashboard, links and names abeee83
v2 stage 4: memory agent drafts, duplicate checks, case embeddings, case edit/retire lifecycle  897abc7
v2 stage 5: cause categories and rule weights in validated YAML config, cause-and-effect graph  79e9d99
v2 stage 6: login page with sign-up and demo profiles, animated RcaRobot                        4dbcc92
v2 stage 7: route code-splitting, audit-log viewer, README and env docs, build report draft     fd41f6f
v2 stage 8: pgvector retrieval benchmark, workflow and memory-agent eval suites, plan call fails fast on 503 d5f3089
v2 stage 9: final verification on a fresh Postgres volume, build report                         (this commit)
```
