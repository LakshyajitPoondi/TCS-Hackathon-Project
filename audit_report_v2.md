# Audit report v2 — Production Intelligence & RCA

Audit date: 2026-10-07. Read-only audit. The only project file created is this report.

**How it was tested.** The project folder is checked out on `main`, which is the old baseline. The built app lives only on `feature/llm-rag-rbac`. I did not check out or change anything in the project folder. Instead, I exported `feature/llm-rag-rbac` (commit `5c6826e`) with `git archive` into a temporary scratch folder and ran it from there:

- Backend on port 8011, using the project `.venv`. The project `.env` was loaded into memory only.
- Frontend on port 5180, after `npm ci` in the scratch copy.
- Because `.env` has no auth values, I added throwaway in-memory values: `JWT_SECRET`, a seed admin, and demo users.
- The Chrome extension was not connected, so I used headless Chrome through `playwright-core`, installed in scratch only.

The scratch folder was deleted when I finished.

---

## 1. Summary

- **All the built work is on `feature/llm-rag-rbac`, not on `main`. The project folder is currently on `main`, the pre-build baseline.** If you run the app from the folder today, you get the old version.
- There are no stashes. The "interrupted stage 11" changes were committed as `5c6826e` ("Project without Vector DB, Memory agents, Docker").
- **The built app works well.** pytest passed 41/41. All deterministic eval suites pass, with ranking top-1 16/16 and top-3 16/16. The live check of 35 routes × 5 roles had 0 wrong cells. Server-side approval for memory works end to end, and approved cases really are recalled for similar incidents.
- **Gemini is not working today, for two reasons.**
  1. The key is stored in `GROQ_API_KEY`, but with `LLM_PROVIDER=openai_compatible` the app only reads `LLM_API_KEY`, which is empty. So the app silently uses template wording.
  2. When I passed the key correctly (in memory only), Google accepted it, but the free-tier quota (20 requests/day for `gemini-3.8-flash`) was already used up.
- **With the current `.env`, nobody can log in.** `JWT_SECRET`, `SEED_ADMIN_*` and `DEMO_PASSWORD` are empty.
- **Missing features:** cause-and-effect graph, saving/versioning/exporting the RCA draft, categories loaded from a config file, the animated robot (only a placeholder box exists), a sign-up toggle, an LLM memory agent, case edit/retire/de-duplication, and Postgres/pgvector.
- **Workflow gaps:** uploaded incidents never appear in the incident list. There is no incident status (new/analysed/proposed/approved) anywhere. Draft edits are lost on page reload.

**Counts (items 1–26):** Built 15 · Partial 5 · Mock 0 · Missing 4 · Unverified 2.

---

## 2. Git state (Step 1)

| Check | Result |
|---|---|
| Current branch | `main` (working tree clean) |
| `git status` | `nothing to commit, working tree clean` |
| `git stash list` | **empty, no stashes** |
| Branches | `main`, `feature/llm-rag-rbac`, `remotes/origin/main` (`origin` = github.com/LakshyajitPoondi/TCS-Hackathon-Project) |
| `origin/main` | `a103be9` (same as local `main`). The feature branch has **not** been pushed. |
| Does feature differ from main? | **Yes.** 97 files changed, +3,563 / −630. `main` = baseline `6c6aa2d` plus one commit `a103be9` ("tsconfig", which adds `frontend/tsconfig.tsbuildinfo`). |

**Last 15 commits (all branches):**

```
* a103be9 (main, origin/main) tsconfig                       2026-10-06 20:19
| * 5c6826e (feature/llm-rag-rbac) Project without Vector DB, Memory agents, Docker   16:27
| * 65042c6 stage 10: add isolated stored evaluation suites and deterministic fixtures
| * de0f000 stage 9: build authenticated machine document case and RCA interfaces
| * 651fb91 stage 8: bind claims and verification actions to evidence and chunks
| * b648413 stage 7: add scoped investigation traces and approved case memory
| * 839b769 stage 6: enforce scoped hybrid retrieval and chunk provenance
| * 5031a33 stage 5: add validated HTTP providers cache and call telemetry
| * a85aa3f stage 4: seed machine registry and scoped document ingestion
| * 203d596 stage 3: authentication and server-enforced permissions
| * 1039b7d stage 2: transactional SQLite schema and seed cases
| * 0f57ac1 stage 1: validate inputs and fix audit crashes
| * 22a6dbd stage 0: baseline setup and pinned dependencies
|/
* 6c6aa2d baseline before stage 1
```

The reflog shows two `reset: moving to HEAD` entries after stage 10, then commit `5c6826e`, then a checkout to `main`. So the stage 11 work was committed, not stashed. `5c6826e` changes `.env.example`, `README.md`, `engine/llm.py` (Gemini alias plus 429 backoff), `engine/memory.py`, and adds `evals/live_llm_check.py`, `evals/embedding_check.py`, `evals/test_final.py` and `evals/test_llm.py`.

**Other state found:**

- Processes left behind by the previous agent are still running from the project folder. They were not stopped because they are not mine:
  - uvicorn on 127.0.0.1:8001 (PID 29748)
  - Vite on :5173 (PID 22956)
  - Vite on :5174 (PID 16152)
- `build_report.md` does not exist. The README refers to it.
- `progress.md` on the feature branch says "Current stage: 11 … Next unfinished stage: 11".

---

## 3. Feature status table (items 1–26)

| # | Item | Status | Evidence | Note |
|---|---|---|---|---|
| 1 | CSV upload & validation | **Built** | `backend/services/data_loader.py` `validate_dataframe`, `save_upload`. Live: missing column → 422 "Missing required columns: vibration"; text in a numeric column → 422 "Column 'temperature' has mostly non-numeric values"; bad timestamp → 422; unknown machine → 422 "Unknown physical machine: LINE-A/IMM-09"; `.txt` → 422; valid file → 200 `UPL-…` | Works. However, uploaded incidents are left out of `GET /api/incidents` (`list_incidents`, line 70–77), so they disappear from the UI. |
| 2 | Timeline & key indicators | **Built** | `engine/signals.py` `analyze_signals`. INC-001 → window 06:38–07:12 with `detected_by` list; KPIs (defect_rate 1.111, 60 defects, 5 min downtime, 4 alarms). UI `SignalChart` renders. | |
| 3 | Cause categories from a config file | **Missing** | Hardcoded in `engine/scoring.py:23` (`CATEGORIES`), `backend/models/schemas.py` (`Literal`) and `frontend/src/types/api.ts:9` | No config file exists. Rules and weights are also hardcoded. |
| 4 | Up to 3 hypotheses, evidence, H/M/L, missing checks, abstain | **Built** | `engine/scoring.py` `score_hypotheses` (MAX 3, MIN_SCORE 5). INC-001 → machine/cooling, high, 6 evidence items, 2 missing checks. INC-008 → `insufficient_evidence`, 0 hypotheses. | |
| 5 | Editable RCA draft, validation notice, save, versions, export | **Partial** | `frontend/src/components/analysis/RcaDraft.tsx` has a textarea, Revert, **Copy** and the warning. No draft endpoint exists in any route. UI test: edit, then reload → edit lost. | No save, no versions, no export or download. The edited draft is stored only inside a case proposal. |
| 6 | Cause-and-effect graph view | **Missing** | No component or route (searched for graph, reactflow, mermaid, fishbone) | |
| 7 | Regression, 18 incidents (`evals.sanity_check`) | **Built** | top-1 **16/16**, top-3 **16/16**, correct abstentions **2/2**, wrong abstentions 0/16, ambiguous also-plausible **3/3** | Synthetic, planted data. |
| 8 | Database | **Built** | SQLite through SQLAlchemy 2.1 (`backend/db.py`). `DATABASE_URL=sqlite:///./data/app.db` (relative to the folder you start from). 12 tables: users, machines, documents, document_machine_links, document_chunks, cases, analysis_runs, agent_traces, audit_log, eval_runs, eval_results, revoked_tokens. **No Alembic** (`Base.metadata.create_all`). Seed: `python -m backend.init_db` (idempotent) | |
| 9 | Embeddings storage & similarity | **Built** (off by default) | `document_chunks.embedding` = **JSON column in SQLite**, `embedding_model` string. Similarity = numpy cosine in Python (`engine/retrieval.py` `cosine`) plus RRF fusion with BM25. Model `BAAI/bge-small-en-v1.5` through fastembed, **384 dimensions** (measured). Re-run in this audit: recall@4 **1.0**, wrong-machine leaks **0**, 73 chunks embedded, 42 s. | `.env` has `EMBEDDINGS_PROVIDER=none`, so the live app uses BM25 only. |
| 10 | Postgres + pgvector readiness | **Partial** | ORM is mostly portable. SQLite-specific code: `db.py:118-123` (`check_same_thread`, PRAGMAs, which are conditional). Timestamps are ISO strings in `String` columns (`db.py:9-10`). `JSON` columns work but are not JSONB. Embeddings are in JSON, not `vector`. Retrieval loads every document and chunk into Python on every search (`retrieval.py:39-50`). No raw SQL. No psycopg driver in `requirements.txt`. Tests hardcode SQLite (`evals/conftest.py:21`, `run_evals.py:34`). | **Docker:** CLI 29.7.2 installed, but the engine is **not running**. **PostgreSQL:** 18 installed, and the service `postgresql-x64-18` is **Running**. `psql` is not on PATH. **pgvector extension files are not present.** |
| 11 | LLM provider code & env vars | **Built** | `engine/llm.py` `request_json`: `groq`, `openai_compatible`, `gemini` (alias), `anthropic`, `fake`. Env **set**: APP_ENV, DATABASE_URL, JWT_EXPIRE_MINUTES, CORS_ORIGINS, DEMO_USERS_ENABLED(=false), UPLOAD_MAX_MB, DOC_UPLOAD_MAX_MB, LLM_ENABLED, LLM_PROVIDER(=openai_compatible), LLM_MODEL(=gemini-3.8-flash), **GROQ_API_KEY**, LLM_BASE_URL(=Google OpenAI endpoint), LLM_TIMEOUT_SECONDS, LLM_MAX_RETRIES, AGENT_ENABLED, AGENT_MAX_STEPS, EMBEDDINGS_PROVIDER(=none), EMBEDDINGS_MODEL, RAG_TOP_K, RAG_MIN_SCORE, JUDGE_ENABLED, JUDGE_MODEL. **Empty**: **LLM_API_KEY**, JWT_SECRET, SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD, DEMO_PASSWORD, EMBEDDINGS_API_KEY, EMBEDDINGS_BASE_URL | The key is in the wrong variable (see item 12). |
| 12 | One real Gemini call | **Unverified** (live call failed) | As configured: `python -m evals.live_llm_check` → "Live checks skipped: no live LLM_API_KEY". With the key passed as `LLM_API_KEY` in memory: provider `openai_compatible`, model `gemini-3.8-flash`, URL `…/v1beta/openai/chat/completions`. Google **accepted the key** (no 401/403). Attempt 1: **HTTP 503** "This model is currently experiencing high demand". Then **HTTP 429 RESOURCE_EXHAUSTED**: "Quota exceeded for metric: generate_content_free_tier_requests, limit: 20, model: gemini-3.8-flash. Please retry in 22h36m". | Fell back to template after ≈21 s (7.9 s + 13.2 s). That one probe made **5 HTTP requests** because of the retries. text_source = template; no LLM grounding result. Not retried, per the "one call" rule. `data/llm_cache/` (main working tree) holds 7 validated cached outputs from Oct 6 15:11–15:42, which suggests earlier live calls succeeded. Not reproduced. |
| 13 | Tool calling with Gemini | **Unverified** | `engine/agent.py` `investigate`. It does not use native function calling. Each step sends a JSON-mode prompt "pick one tool + args", validated by `ToolCall`, and the server checks permissions. After the first failed LLM call it switches to `deterministic` (line 39-40). Live trace (deterministic, no key): 1 `get_incident_summary` → 2 `get_hypotheses_and_evidence` → 3 `get_machine LINE-A/IMM-02` → 4 `search_machine_documents` → 5 `read_document_chunk SOP-007:v1:1` → 6 `recall_similar_cases`; mode=deterministic, 6/10 steps, 0 denied. | Could not run with Gemini (quota). The agent's result only fills the trace. It never changes the hypotheses. One LLM call per step (up to 10) plus 1 wording call per analysis. |
| 14 | Machine registry & document upload | **Built** | 9 machines LINE-A/B/C × IMM-01/02/03 (`backend/services/machines.py` `seed_machines`). Uploaded live: MD/TXT/DOCX/PDF → 201 active (PDF chunk "Page 1", DOCX chunk "Maintenance"); `.exe` → 422. Scopes machine/model/line/plant. Detection: a doc scoped to LINE-A/IMM-02 whose text names LINE-C/IMM-01 → `pending_mapping`, conflict=true, warning "Explicit mapping disagrees…". A text naming only "IMM-02" → pending, ambiguous=true. Confirm with a bad target → 422; with a valid target → active. All of this also done in the UI. | Engineers can also upload, edit, confirm and archive any document, including plant SOPs. |
| 15 | Retrieval & hard machine filter | **Built** | `engine/retrieval.py` `search`: filters by scope **before** indexing, then BM25Plus, then optional cosine + RRF. **Proof:** uploaded a very cooling-heavy manual scoped to **LINE-B/IMM-02** and analysed INC-001 (LINE-A, target IMM-02). It was **not** in `documents_accessed` and **was** in `documents_filtered_out` with reason "Scope does not include relevant physical machines". The LINE-A/IMM-02 manual was accessed. Eval: wrong_machine_leak_rate 0. | |
| 16 | documents_accessed / filtered_out in output & UI | **Built** | Present in `AnalysisResponse`. UI `InvestigationPanels.tsx` shows "Documents accessed" with chunks and deep links, plus "Filtered out (8)". Verified headless. | |
| 17 | Case storage, weighted recall, exclusion, "why matched" | **Built** | `engine/memory.py` `recall`: tag overlap plus weights (machine_uid 5, category 4, line 2, subcause 2, model 1, shared events). `match_reasons` shown in the UI. Analysing INC-001 did **not** recall the case created from INC-001 (exclusion works). | No embeddings for cases. |
| 18 | Memory agent (structured summary) | **Partial** | `backend/api/routes/cases.py` `propose`: server builds `symptoms` (from evidence), `signals`, `events`, `machine_uid`. User-supplied: category/subcause, fix, lessons, notes, `documents_used`, draft. `summary` is a fixed template "Proposed {cat} case from {id}; awaiting QA approval." `text_source:'template'`. **No LLM.** | The summary is not shown or editable before submitting. The UI modal (`SaveCaseModal.tsx`) has **no documents_used field**. progress.md stage 7 says templates were chosen on purpose. |
| 19 | Approval workflow | **Built** | API: propose → 201 `proposed`. Viewer or engineer approve → 403. QA approve → 200 `approved`. Approve again → 409. Reject works. **End to end:** after approval, the case was recalled #1 for a CSV copy of INC-001 ("machine_uid agrees…") and for INC-009 and INC-017. It was not recalled before approval. The same happened in the UI (proposed in the UI, approved by QA in the UI, recalled on INC-009). | Enforced on the server (`require('approve')`). |
| 20 | Other memory features | **Missing** | No endpoint to edit, retire or delete a case. No de-duplication (two proposals for the same incident both accepted). No case embeddings. The summary still says "awaiting QA approval" after approval (`cases.py:31,50`). | |
| 21 | Login, JWT, roles, demo users, audit log | **Built** | `backend/auth.py`: bcrypt, HS256 JWT with jti/ver, revocation (logout → reusing the token gives 401), deactivation bumps `token_version`. 4 roles. Demo users exist only if `DEMO_USERS_ENABLED=true` + `DEMO_PASSWORD`. `audit_log` table filled for every change (15 action types, 0 rows without a user). | No endpoint or UI to view the audit log. The current `.env` creates **no** users (see bugs). |
| 22 | Endpoint × role matrix | **Built** | Live matrix (section 4): 35 routes × anonymous + 4 roles → **0 wrong cells**. Built-in `RBAC` eval suite also 1.0. | Design questions are in section 7. |
| 23 | Login page vs design §7.1 | **Partial** | `frontend/src/pages/LoginPage.tsx`. Present: two-panel card, 3-line gradient headline, "Plant access" / "Welcome back", 3 capability lines (plain text, not glass chips), demo buttons **Plant engineer / QA lead / Viewer**, "Show password" checkbox, "Open dashboard →", aura blur. Works at 375 px with no horizontal scroll. | **Missing:** Sign in/Sign up toggle, admin demo button, eye icon (a checkbox is used), "Engine online" badge, footer status. Demo buttons fill **only the email**, not the password. |
| 24 | Animated robot (§8) | **Missing** | Only a dashed box "Robot placeholder · Reserved for a future auth illustration" (`LoginPage.tsx:12`). No `RcaRobot` component, no `features/auth/robot/`, no framer-motion. | None of the §8 behaviours exist: cursor tracking, blink, idle look-around, password cover/peek, thinking, success, error, touch, reduced motion, lazy load. |
| 25 | pytest & eval suites | **Built** | `pytest`: **41 passed**, 1 deprecation warning, 103 s. `POST /api/evals/run` (≈32 s): every metric passes (table in section 4b). LLM judge = Unverified (no key). | |
| 26 | Secrets, .gitignore, pins, README | **Partial** | No secrets in git history (scanned all commits). `.env`, `*.db`, `data/llm_cache/`, `data/documents/`, `node_modules/`, `.cache/` are ignored. `requirements.txt` pins 16 direct packages exactly. README fresh-setup steps are correct for the feature branch. | Problems: README and code are not on `main`. The README points to a missing `build_report.md`. The README tells you to use `LLM_API_KEY`, but the owner's `.env` uses `GROQ_API_KEY`. `frontend/tsconfig.tsbuildinfo` is committed on `main` although `*.tsbuildinfo` is ignored on the feature branch. `.venv` was made with `--system-site-packages`, and its packages live in the user's global site-packages. Each eval run rewrites `evals/docs_answer_key.json` and `data/eval_docs/*`. |

---

## 4. Endpoint table

Roles come from `backend/auth.py` `PERMISSIONS`. "Tested" = live result per role, in the order anonymous / admin / engineer / qa_lead / viewer.

| Method | Path | Purpose | Roles allowed | Tested |
|---|---|---|---|---|
| GET | `/health` | Liveness | public | 200 |
| GET | `/docs`, `/openapi.json` | API docs | public | 200 |
| POST | `/api/auth/login` | Login → JWT | public | 200 (good password) / 401 (wrong password) |
| GET | `/` | API info | all roles | 401/200/200/200/200 |
| GET | `/api/auth/me` | Current user | all roles | 401/200/200/200/200 |
| POST | `/api/auth/logout` | Revoke token | all roles | 401/200/200/200/200; reusing the token → 401 |
| GET | `/api/users` | List users | admin | 401/200/403/403/403 |
| POST | `/api/users` | Create user | admin | 401/201/403/403/403 |
| PATCH | `/api/users/{id}` | Role / active | admin | 401/200/403/403/403 |
| GET | `/api/incidents` | List curated incidents (uploads excluded) | all roles | 401/200/200/200/200 |
| POST | `/api/incidents/upload` | Upload CSV | admin, engineer | 401/200/200/403/403 |
| GET | `/api/incidents/{id}` | Summary | all roles | 401/200/200/200/200; INC-999 → 404 |
| GET | `/api/incidents/{id}/signals` | Raw rows | all roles | 401/200/200/200/200 |
| POST | `/api/incidents/{id}/analyze` | Run and store analysis | admin, engineer, qa_lead | 401/200/200/200/403 (0.28 s, template) |
| GET | `/api/analyses` | Analysis history | all roles | 401/200/200/200/200 |
| GET | `/api/analyses/{run_id}` | Stored analysis | all roles | 401/200/200/200/200 |
| GET | `/api/analyses/{run_id}/trace` | Agent trace | all roles | 401/200/200/200/200 |
| GET | `/api/cases` | List cases (`?status=`) | all roles | 401/200/200/200/200 |
| POST | `/api/cases` and `/api/cases/propose` | Propose case (duplicate routes) | admin, engineer | 401/201/201/403/403; unknown doc → 422 |
| POST | `/api/cases/{id}/approve` | Approve | admin, qa_lead | 401/200/403/200/403; already decided → 409 |
| POST | `/api/cases/{id}/reject` | Reject | admin, qa_lead | 401/200/403/200/403 |
| GET | `/api/evals` | Latest stored eval run | all roles | 401/200/200/200/200 |
| POST | `/api/evals/run` | Run all suites (≈32 s) | admin, qa_lead | 401/200/403/200/403 |
| GET | `/api/sops/{id}` | Legacy SOP text | all roles | 401/200/200/200/200 |
| GET | `/api/machines` | Registry plus doc counts | all roles | 401/200/200/200/200 |
| POST | `/api/machines` | Create machine (only the 9 fixed IDs allowed) | admin | 401/409 (exists, permission passed)/403/403/403 |
| GET | `/api/machines/{uid}` | Machine detail | all roles | 401/200/200/200/200 |
| PATCH | `/api/machines/{uid}` | Edit spec / ranges | admin | 401/200/403/403/403 |
| GET | `/api/machines/{uid}/documents` | Linked documents | all roles | 401/200/200/200/200 |
| GET | `/api/machines/{uid}/incidents` | Incidents on the line (0.8 s) | all roles | 401/200/200/200/200 |
| GET | `/api/documents` | Library (filters) | all roles | 401/200/200/200/200 |
| POST | `/api/documents/upload` | Upload PDF/DOCX/MD/TXT | admin, engineer | 401/201/201/403/403 |
| GET | `/api/documents/{id}` | Document plus chunks | all roles | 401/200/200/200/200 |
| PATCH | `/api/documents/{id}` | Edit / archive / back to pending | admin, engineer | 401/200/200/403/403 |
| POST | `/api/documents/{id}/confirm` | Confirm mapping → active | admin, engineer | 401/200/200/403/403 |

**4b. Eval suites (`POST /api/evals/run`, run by qa_lead):**

| Suite | Metrics (value / threshold) | Pass? |
|---|---|---|
| RCA ranking | top1 1.0/1 · top3 1.0/1 · abstentions 1.0/1 · ambiguous alternatives 1.0/1 | Pass |
| Document mapping | mapping 1.0 · precision 1.0 · recall 1.0 · ambiguity flag 1.0 · conflict detection 1.0 | Pass |
| Retrieval | lexical recall@4 0.852/0.8 · MRR 1.0/0.8 · wrong-machine leaks 0 · filtered-out correctness 1.0 · mocked fusion leaks 0 · live embedding recall = Unverified in suite (verified separately in this audit: 1.0) | Pass |
| Grounding | final sections supported 1.0 · steps cite retrieved chunks 1.0 · adversarial flag rate 1.0 | Pass (fixture docs only; see bug B4) |
| LLM layer (fake / mocked HTTP) | schema_and_fallback_rate 1.0 | Pass (no live call) |
| Investigation agent | tool validity 1.0 · cap 1.0 · trace 1.0 · cross-machine attempts 0 · fake shape/stable rank 1.0 | Pass (fake/deterministic only) |
| Experience memory | leave-one-out category agreement 0.833/0.7 · exclusion 1.0 · approval roles 1.0 · machine agreement 0.0 (context only) | Pass |
| RBAC | endpoint role matrix 1.0 | Pass |
| LLM judge | helpfulness / faithfulness | **Unverified** (no live key) |

---

## 5. End-to-end workflow walkthrough (section G)

Tested headless in the running app (frontend 5180 → backend 8011), plus matching API calls.

| Step | Result | What happened / broke |
|---|---|---|
| **1. Admin:** sign in, check machines, upload a manual, scope it to one machine, resolve a conflict | **Pass** | Login → incident list. Machines page shows 9 cards; the detail page has an Edit button, ranges and linked docs. Upload form (Documents → "Upload machine documentation") with a scope picker: manual scoped to LINE-A/IMM-03 → "Uploaded … · active", and the list refreshed without a reload. A conflicting doc → warning "Explicit mapping disagrees…" plus a "Review and confirm mapping" link → set scope/target → "Confirm mapping and activate" → status active. Rough edges: the multi-select needs Ctrl-click. Pending documents are not flagged anywhere else (no badge or count). |
| **2. Engineer:** upload CSV (or open INC-001), review timeline/KPIs, run analysis | **Pass, with a break** | `/upload` → lands on `/incidents/UPL-…` with the chart and summary cards, then Run RCA Analysis. **Break:** the uploaded incident never appears on the incident list (still 18 rows), so you can only reach it again through the URL. The list shows only ID and file name: no machine, date, severity or status. |
| **3. Engineer:** hypotheses, documents, trace, graph; edit, save and export the draft | **Partial** | Shown: ranked hypothesis cards, "Template wording", "Agent: deterministic · 7/10 steps", grounding, Documents accessed, "Filtered out (8)", Agent trace (7 rows), grounding by section, Similar Past Cases. **Missing:** graph. No Save draft. No Export (Copy only). **Draft edits are lost on reload:** the page reloads the stored analysis with the original draft. Earlier in the API run, grounding showed "Review flags" for INC-001 once an uploaded manual was used (bug B4). |
| **4. Engineer:** propose case to memory | **Pass, with gaps** | Modal: category, subcause, notes, fix (required), lessons → "Case proposed · CASE-…". **Gaps:** no "documents used" picker, no preview of the generated summary or symptoms, and the incident page shows no "proposed" state afterwards. |
| **5. QA lead:** review and approve | **Pass, with gaps** | Cases → filter "proposed" → card → Approve → the card leaves the proposed list and appears under approved. **Gaps:** the proposer is shown as a raw user ID. The card does not show the draft, symptoms or a link to the incident. After approval the summary still reads "…awaiting QA approval." |
| **6. Engineer:** analyse a similar incident → recall | **Pass** | INC-009 → Similar Past Cases includes the case approved in the UI (and the API-approved INC-001 case ranks #1). |
| **7. QA lead:** run evaluations and view results | **Pass** | Evaluations → Run evaluations → 28 metric cards "Pass", 0 "Fail", 6 marked Unverified/skipped. Per-case details are in collapsible tables. Takes about 30–60 s with only a button spinner. |
| **8. Viewer:** view only | **Pass** | Sidebar shows Analysis, Machines, Documents, Cases and Evaluations (no Upload or Users). No Run or Propose buttons, but the stored analysis is visible. `/upload` and `/users` → "Your role cannot open this page". No doc upload form, no Approve, no Run evaluations, no Edit machine. Small issue: the viewer can still type in the draft textarea, but cannot save. |

**Navigation and connections:**

- There is no dashboard. "Analysis" (the incident list) is the home page.
- There is **no incident status model** (new / analysed / draft / proposed / approved), on the server or in the UI.
- Incident ↔ case links are missing in both directions.
- Case cards don't link to documents.
- Machine → "Related incidents" lists every incident on that line, because each CSV contains all 3 machines.
- Unknown routes show "Page not found".
- Error messages are readable: upload errors show the backend's 422 text, and a wrong login shows a "Sign in failed" alert.
- Session expiry clears the token and redirects to login.

**Manual workarounds needed:**

1. With the owner's `.env` as it is, `init_db` creates **no users** and nobody can sign in. You have to set `JWT_SECRET`, `SEED_ADMIN_EMAIL`/`SEED_ADMIN_PASSWORD`, `DEMO_USERS_ENABLED=true` and `DEMO_PASSWORD`.
2. Demo buttons fill only the email, so the user has to know `DEMO_PASSWORD`.
3. To reopen an uploaded incident, you need its URL.

---

## 6. Gaps grouped

### Critical (breaks the workflow)

1. **The built code is not on `main` and not pushed.** The project folder runs the baseline. Leftover servers from the previous agent are still running on 8001/5173/5174.
2. **`.env` cannot start an authenticated app.** `JWT_SECRET`, `SEED_ADMIN_*` and `DEMO_PASSWORD` are empty and `DEMO_USERS_ENABLED=false`, so no users are created. Without `JWT_SECRET`, sessions also break on every restart.
3. **Gemini key in the wrong variable** (`GROQ_API_KEY`, with provider `openai_compatible`). The app silently uses templates.
4. **Uploaded incidents vanish** from the incident list.
5. **Draft edits are not saved.** No save, versions or export.
6. **No incident status** across analyse → propose → approve.

### Important

- **Gemini:**
  - Free-tier quota of 20 requests/day is exhausted.
  - One analysis with the agent on costs up to about 11 LLM requests.
  - Each failed request is retried up to 5 times, including 429 "quota exhausted" responses that will not recover for hours.
  - Tool calling is a JSON-mode loop, not native function calling.
  - No successful live LLM run was observed in this audit.
- **Memory agent:** no LLM summary, no summary preview or editing, no documents_used field in the UI, no case edit/retire/de-duplication, no case embeddings, and a stale summary after approval.
- **pgvector / Postgres:** SQLite only, no Alembic, embeddings stored in JSON, retrieval loads everything into Python. Docker engine not running. PG18 is running but has no pgvector. No psycopg driver.
- **Robot:** placeholder only, with none of the §8 behaviours. The login page lacks the sign-up toggle and the admin demo button.
- **Grounding:** template verification steps can pull in non-step text from uploaded docs, so the template itself fails grounding (B4).
- **Missing graph view** (TCS bonus outcome) and **missing config file for categories**.

### Nice to have

- An audit-log viewer.
- Proposer/approver names instead of IDs.
- Pending-document badge.
- Dashboard.
- Incident list columns (machine, date, top cause, status).
- Code-splitting (713 kB bundle).
- Archived/pending filters on the machine docs page.
- Merging the duplicate `/api/cases` and `/api/cases/propose` routes.
- `build_report.md`.

---

## 7. Bugs and risks (file + line refer to `feature/llm-rag-rbac`)

| ID | File:line | Problem | Effect |
|---|---|---|---|
| B1 | `backend/core/config.py:56` | `LLM_API_KEY` falls back to `GROQ_API_KEY` only when provider is `groq` **and** `LLM_API_KEY` is missing. `.env` has `LLM_API_KEY=` (empty), so even the groq fallback fails. | Gemini or Groq never used; silent template fallback. |
| B2 | `engine/llm.py:57-67, 76` | A 429 is retried 3× (capped at 20 s) even for daily-quota exhaustion (Retry-After about 22 h). On top of that, `LLM_MAX_RETRIES` adds one more retry. | Observed: 5 requests and about 21 s for one failed call. Wastes the 20/day quota. |
| B3 | `engine/agent.py:31-40` | One LLM call per agent step (up to `AGENT_MAX_STEPS`=10) plus a wording call, for a trace that never changes the results. | About 1–2 analyses per day on the Gemini free tier. Analysis gets slower. |
| B4 | `engine/retrieval.py:90` + `backend/services/analysis_service.py:85` | The step regex `\d+\.\s+(.+?)(?=\s\d+\.\s\|$)` captures trailing non-step text from uploaded docs into a "verification action". The template draft then fails its own grounding. | INC-001 with an uploaded manual: `grounding.passed=false`, flag "Unsupported speed direction… 'Temperature rise speed drop…'". The template has no further fallback. |
| B5 | `backend/services/data_loader.py:70-77` | `list_incidents` excludes uploads on purpose ("keep the eval set clean"). `machines/{uid}/incidents` also uses it. | Uploaded incidents can't be found in the UI. |
| B6 | `backend/api/routes/cases.py:31, 50` | `summary` is set to "…awaiting QA approval." and never updated in `decide`. | Approved cases show stale text. |
| B7 | `backend/api/routes/cases.py:20-39`; `frontend/src/components/analysis/SaveCaseModal.tsx:58-65` | No duplicate check per incident. The UI never sends `documents_used`. | Duplicate cases inflate recall. Documents used are always empty from the UI. |
| B8 | `frontend/src/pages/IncidentPage.tsx:85-87`; `RcaDraft.tsx` | Draft lives only in React state. A reload loads the stored `rca_draft`. | Engineer edits lost. |
| B9 | `backend/auth.py:17, 25-27, 65-72` | No `JWT_SECRET` → a random secret per process in development. No seed values → no users. | Current `.env` gives an app nobody can log into, and tokens die on restart. |
| B10 | `frontend/src/pages/LoginPage.tsx:13` | Demo buttons set only the email. No admin profile. No sign-up toggle. | Demo login still needs the password typed in. |
| B11 | `backend/api/routes/registry.py:124-138` (`edit_doc`), `auth.py:15` | The `documents` permission lets **engineers** archive or re-pend **any** document, including the plant SOPs used for every analysis. | One engineer can remove SOP grounding for everyone. Needs a policy decision. |
| B12 | `backend/api/routes/registry.py:54-59` | "Related incidents" loads and validates all 18 CSVs on every request, and matches by line (every CSV has all 3 machines). | 0.8 s per call; not specific to the machine. |
| B13 | `engine/retrieval.py:39-50` | Every search loads all documents and chunks and builds BM25 in memory. Embeddings are in JSON. | Fine for 50 chunks; won't scale. Must be rewritten for pgvector. |
| B14 | `backend/db.py:9-10` and all `created_at` columns | Timestamps are ISO strings in `String` columns. | Ordering relies on string sort. Needs `DateTime(timezone=True)` for Postgres. |
| B15 | `engine/memory.py:75-76` | Recall adds +4 when a case's category equals the **current top hypothesis**. | Memory echoes the engine's own guess (confirmation bias). Ranking is not affected. |
| B16 | `evals/test_final.py:27-28` | The "unknown machine" upload test sets all machines to `UNKNOWN`, which fails on "Duplicate machine timestamps" instead. | The test passes for the wrong reason. The real check works (verified manually). |
| B17 | `evals/generate_docs.py:46`, `:10` | Every eval run (including `POST /api/evals/run`) rewrites `evals/docs_answer_key.json` and `data/eval_docs/*`. | The working tree gets dirty from normal app use. |
| B18 | `frontend/src/pages/MachinesPage.tsx:15` | Clearing a text field sends `null` for required `str` fields. | 422 when saving a machine. |
| B19 | `backend/services/analysis_service.py:91` | `sops = []` in `_abstain_draft`, so the "Suggested checks" block is always empty before retrieval steps are appended. | Cosmetic. |
| B20 | `frontend` build | Single 713 kB JS chunk (Vite warning). | Slower first load. |
| R1 | environment | Leftover processes PIDs 29748 (uvicorn :8001), 22956 (Vite :5173) and 16152 (Vite :5174) run from the project folder, which is now on `main`. | Confusing results if someone opens those ports. |
| R2 | `.venv` | Created with `--system-site-packages`. All packages are in the user's global Python site-packages. | Works on this PC. A fresh `pip install -r requirements.txt` is still correct. |

---

## 8. Recommended build order (plan only)

| Phase | Goal | Depends on | How to verify |
|---|---|---|---|
| **0. Make the real app the working copy** | Decide on and merge (or check out) `feature/llm-rag-rbac`, push it, and stop the leftover servers. Fix `.env`: `LLM_PROVIDER=gemini`, move the key to `LLM_API_KEY`, set `JWT_SECRET` (32+ chars), seed admin, `DEMO_USERS_ENABLED=true`, `DEMO_PASSWORD`. | Owner's decision on the branch | `git log main` shows stage commits. `init_db`, then all 4 roles log in. Sessions survive a restart. |
| **1. Close workflow breaks** | List uploaded incidents with a source label. Add an incident status derived from `analysis_runs` and `cases` (new → analysed → proposed → approved) on the list and the incident page. Add an `rca_drafts` table with versions plus save, history and export (Markdown/PDF). Add incident ↔ case links. Fix B4 (step extraction), B6 (summary on approval), B7 (documents_used picker, duplicate warning). | Phase 0 | Re-run this audit's section G: no reloads or URL workarounds. A draft survives reload and has versions. Export downloads. Grounding passes with uploaded manuals. |
| **2. Gemini, reliably** | Treat a 429 RESOURCE_EXHAUSTED or long Retry-After as "do not retry". Cut agent calls: one planning call, or native Gemini function calling, or deterministic agent + LLM wording only. Add a per-day budget counter and show it in the UI. Then run `evals.live_llm_check` once the quota resets or on a paid key. | Phase 0 | `live_llm_check` passes: text_source=llm, grounding passed, agent mode=llm, 0 denied. Calls per analysis ≤ budget. |
| **3. Memory agent** | On "Propose", generate a structured draft (symptoms, confirmed cause, fix, documents used, lessons), with the LLM when available and the template otherwise. Show it **editable** before submit. Add case edit/retire (admin or QA) with audit. Detect duplicates per incident and by similarity. Optionally embed cases for recall. | Phases 1–2 | New tests: summary preview edited → stored. Retired case not recalled. Duplicate proposal warned. Memory eval suite still ≥ 0.7. |
| **4. Postgres + pgvector** | Choose Docker (`pgvector/pgvector:pg18`, after starting Docker Desktop) or a native pgvector build for the installed PG18. Add `psycopg`, Alembic, `DateTime` columns, a `vector(384)` column, and SQL similarity with the machine-scope filter **before** ranking. Keep BM25 (or Postgres full-text search) + RRF. Make tests able to target Postgres. | Phase 0 (ideally after 1) | Alembic upgrade on an empty DB. All pytest and eval suites green on both SQLite and Postgres. Wrong-machine leak = 0. Recall@4 ≥ 0.85. |
| **5. Missing TCS items** | Cause-and-effect graph (signal → hypothesis → verification/doc) from existing analysis fields. Move categories, candidates and weights into a config file (YAML/JSON) loaded at startup, with validation. | Phase 1 | Graph renders for INC-001 and the abstain case. Ranking regression still 16/16 after the move to config. |
| **6. Login page & robot** | Finish §7.1: sign in/up toggle (decide whether sign-up is real or a "request access" form), admin demo button, eye icon, status badges. Build `RcaRobot` per §8 (lazy-loaded SVG layers, rAF loop, state machine, reduced motion, touch). | Independent | Manual checklist from design §11. Lighthouse/perf at 60 fps. Robot chunk not in the main bundle. |
| **7. Hygiene** | Write `build_report.md` and update the README. Fix B16 and B17 (write eval fixtures to a temp folder). Remove the committed `tsbuildinfo`. Add an audit-log viewer and user names. Code-split. | Any time | Clean `git status` after running evals. README fresh-setup run on a clean clone. |

---

## 9. Open questions

1. Should `feature/llm-rag-rbac` be merged into `main` and pushed, or is `main` meant to stay as the baseline?
2. Gemini: will you stay on the free tier (20 requests/day for `gemini-3.8-flash`) or use a paid key or a cheaper model? That decides whether the LLM agent loop is worth keeping or should become deterministic.
3. May I stop the leftover processes on ports 8001, 5173 and 5174 (PIDs 29748, 22956, 16152)?
4. pgvector: Docker Desktop (engine currently stopped) or native install into the running PostgreSQL 18?
5. Sign-up: real self-registration (which role?) or admin-created accounts only, as the backend does now?
6. Should engineers be allowed to archive or re-map plant-wide SOPs, or only admins (B11)?
7. Should uploaded incidents be listed with curated ones, and should they ever join the evaluation set?
8. Draft export format: Markdown, PDF, DOCX? Does each save need to be a version?
9. Memory agent: must the case summary stay template-only (stage 7 decision: "engineer-provided facts remain authoritative"), or may an LLM draft it for the engineer to edit?
10. Were the 7 cached LLM outputs in `data/llm_cache/` (Oct 6, 15:11–15:42) produced by real Gemini calls? If yes, that is probably what used up the free-tier quota.
