# Build progress

## v2 build (branch feature/v2, from main c58eed5)
Prompt: v2 stages 0–9 (see audit_report_v2.md for bug IDs B1–B20). Each stage ends with checks, this file, and a commit "v2 stage N: …".
**Next unfinished stage: 7.**

### Live LLM call counter (budget 10 for the whole build)
Used: 2 of 10.
1–2. Stage 2 `python -m evals.live_llm_check --max-calls 2` (gemini-3.8-flash, key passed in memory from GROQ_API_KEY because .env has LLM_API_KEY empty): both requests were the agent-plan call, both HTTP 503 "overloaded" (5.1 s, 1.0 s). Per-analysis budget then stopped further calls; template wording used; grounding passed. Live LLM wording/plan: **Unverified (provider 503)**. Quota was not hit (no 429).

### v2 decisions (made by the agent)
- D0.1 `.env` does not match the brief: LLM_PROVIDER=openai_compatible, LLM_API_KEY empty (the key sits in GROQ_API_KEY), JWT_SECRET / SEED_ADMIN_* / DEMO_PASSWORD empty. `.env` is never written by the agent. After B1 the key in GROQ_API_KEY is only read for provider=groq, so the owner must move it to LLM_API_KEY and set LLM_PROVIDER=gemini. A warning is logged at start-up when this mismatch is detected (no key printed).
- D0.2 Generated eval fixtures (data/eval_docs/*, evals/docs_answer_key.json) were removed from git and are now produced in a temp folder per run; the key is passed in memory. Their content is deterministic, so nothing is lost.
- D0.3 Uploaded documents path is configurable (DOCUMENTS_DIR, default data/documents). Tests and the eval worker point it at temp folders.
- D1.1 Lexical search: Postgres full-text search (generated `tsv` column, GIN index, `ts_rank`, OR-query of the same tokens BM25 used); SQLite keeps BM25 over in-scope chunks (tests/dev only). Vector search: `embedding <=> query` ORDER BY … LIMIT in SQL with `hnsw.iterative_scan = strict_order` so the machine filter never starves the HNSW result. Fusion: reciprocal rank fusion (k=60) of the two candidate lists; ties broken by scope priority machine > model > line > plant.
- D1.2 Scope filter in SQL uses `document_machine_links` (kept in sync by `put_links`) joined to active documents. `create_machine` now rebuilds links too (it did not before, so a re-created machine lost plant SOPs).
- D1.3 Search is read-only: chunks are embedded on upload (active docs), on confirm/activation, or by `python -m backend.embed_chunks [--all]`.
- D1.4 Verification steps: numbered steps from all hits are preferred; a raw "Review reference" is used only if no hit has numbered steps; drafts cite such references by doc/chunk ID instead of quoting their prose (the quoted SOP text "motor current rose" made the INC-009 template draft fail grounding under the FTS ranking). Also fixes B4 (step = first sentence only) and B19 (abstain draft "Suggested checks" now lists the retrieved steps).
- D1.5 Schema bootstrap: Postgres → `alembic upgrade head` (a v1 DB without alembic_version is stamped 0001 first); SQLite → `create_all`. `DB_BOOTSTRAP=create_all|migrate` overrides. On SQLite migration 0002 only normalises ISO timestamp text (a batch rebuild would CAST it to a number).
- D1.6 Tests: `pytest --db sqlite|postgres` (or TEST_DB). Postgres tests use database rca_test (auto-created, never the app DB) with a throwaway schema per test; eval workers follow EVAL_DB.
- D2.1 Every provider HTTP request (including 503 retries and failures) is one row in llm_usage and counts toward LLM_DAILY_BUDGET (UTC day) and the per-operation budget. Fake-provider requests are counted too, so budgets are testable.
- D2.2 Any HTTP 429 is never retried. Quota-type 429 (RESOURCE_EXHAUSTED / "quota" / Retry-After > 60 s) stores blocked_until = now + provider retry delay (1 h if unknown); later calls skip the provider until then. 4xx errors (bad key/model) are never retried.
- D2.3 LLM output cache moved from data/llm_cache files to table llm_cache, keyed by kind + incident + input hash (which includes provider, model, prompt version and the full analysis payload). Agent plans are cached the same way (kind agent_plan).
- D2.4 AGENT_MODE=llm_plan sends hypotheses (rank/category/subcause/confidence/target only), allowed machines, retrieved chunk ids and the recommended deterministic plan; the returned plan is executed with the same authorization checks. AnalysisResponse gained an additive `llm_usage` field {requests, cache_hits, fallback_reason, per_analysis_budget}; investigation gained `plan_source`.
- D2.5 The test-only fake provider runs through the same HTTP status handling; LLM_FAKE_SCENARIO = ok | quota | rate_limit | 503 | 503_once | invalid_json.
- D3.1 Incident registry table `incidents` (sample + uploaded) holds file metadata; status is derived on every request: case_approved > case_proposed > case_rejected > draft_saved > analysed > new. Top hypothesis is stored in analysis_runs.config at analyse time.
- D3.2 B12 "affected machines" = machines that deviated (co-movement), whose defects rose, or that a hypothesis targets; computed once and stored; falls back to all machines in the file when nothing deviated.
- D3.3 New permission `draft` (admin, engineer, qa_lead) saves/restores drafts; every role can read and export. New permission `plant_documents` (admin) implements B11 for archive/re-map/confirm of plant-scope documents (existing or target scope).
- D3.4 Users gained `name` (display name; falls back to a title-cased email local part). Seeded names: Administrator, Plant Engineer, QA Lead, Viewer.
- D3.5 PDF export uses fpdf2 core fonts (Latin-1); symbols such as → ≥ ± are transliterated. The validation notice is added by the server at the top and bottom of every export.
- D3.6 UPLOADS_DIR is configurable (tests/eval workers use temp folders). The headless walk uses its own database `rca_walk` and in-memory auth values so the owner's `rca` database never gets throwaway demo passwords.
- D4.1 Memory agent: the LLM words only symptoms, evidence summary, lessons and the summary paragraph (one request, budget scope 1, cached as kind memory_summary). The suggested cause is the deterministic top hypothesis and documents_used is prefilled from documents_accessed; fix_applied always starts empty. Any LLM field containing a number not present in the evidence or draft is replaced by the template field (reason shown in the modal).
- D4.2 Duplicates (B7): blocking 409 with the list unless the engineer gives a reason (stored as duplicate_override). Same-incident check covers proposed + approved cases; similarity check covers approved cases with the same machine + category + subcause and cosine ≥ 0.90 between case texts (summary + evidence + symptoms + fix + lessons); without embeddings, ≥ 80 % shared signal tags.
- D4.3 Recall: semantic factor = +3 × cosine (only when ≥ 0.5), reason "summary similarity 0.xx". B15: analysis no longer passes the top hypothesis as `confirmed_category` (+4/+2); it is a separate +1 reason "matches current top hypothesis (+1, context only)". Hypothesis ranking is untouched. The memory eval still passes a reference case's own confirmed cause (that is a property of the case, not the engine).
- D4.4 Lifecycle: edit/retire only for approved cases, by admin or qa_lead, with a reason; the previous data is stored in case_versions; data.version increments; all actions audited; GET /api/cases/{id}/history. Retired cases are listed (status filter) but never recalled; the incident status ignores retired cases.
- D5.1 config/cause_categories.yaml holds categories + display names, the 7 candidates (category, subcause, label, display name, verification sentence, missing checks), the 7 rule weight bands and the score thresholds. Rule conditions stay in code; the loader (engine/cause_config.py, pydantic, extra keys forbidden) rejects missing/duplicate categories or candidates, wrong signs, unordered thresholds and subcauses outside machine. CAUSE_CONFIG_PATH can point elsewhere.
- D5.2 Hypothesis evidence now carries its rule `weight` (additive Evidence field; category_evidence unchanged). The sum of weights equals the hypothesis score (tested). Full scoring output for all 18 incidents was byte-identical before/after the move.
- D5.3 Graph built server-side from the stored analysis (GET /api/analyses/{run_id}/graph), rendered with @xyflow/react 12 in a lazy chunk. Clicking a node highlights its full upstream and downstream chain and shows its evidence, links and cited chunk. Abstain mode: evidence → categories (below minimum) → "Insufficient evidence" verdict → missing checks from the config and suggested references.
- D6.1 Demo mode seeds an extra demo-admin@demo.local (admin, DEMO_PASSWORD) for the admin demo button, so the real SEED_ADMIN password is never exposed. GET /api/public/config returns demo passwords only when DEMO_USERS_ENABLED=true and APP_ENV=development; nothing is baked into the bundle.
- D6.2 Sign-up: POST /api/auth/signup creates an inactive viewer (name, email, password 10–72 bytes). Login with the right password on an inactive account returns 403 "Account pending activation"; a wrong password stays 401. Admins see pending sign-ups on the dashboard, a users_pending nav count and an "Inactive" label on the Users page.
- D6.3 Robot animation: framer-motion springs (eyes 300/25, head 120/18, body 60/14, arms 170/20) driven from one framer frame loop (useAnimationFrame) that reads the pointer ref; float/pulse/dots are CSS keyframes; only transform/opacity animate (plus the static eye-glow filter). Expressions (line, dots, happy, sad, giggle) cross-fade by opacity. The privacy pose lifts the arms 44 px so the hands cover the eyes. Reduced motion: no float/hop/shake/head movement, eyes ±4 px, no springs.
- D6.4 Layout stability: the demo-profile area has a reserved height and a fixed 2 × 2 grid, so neither the config request nor the web-font swap moves the card (measured CLS ≈ 0.001).
- D1.7 Code defaults changed to DATABASE_URL=postgresql+psycopg://rca:rca@localhost:5433/rca and EMBEDDINGS_PROVIDER=fastembed. The owner's .env still says sqlite + none, so the owner must change those two lines to use Postgres/pgvector.

### v2 stage log
#### Stage 6 complete
- Login page per §7.1: glass left panel (logo, "Engine online" badge, 3-line headline, robot, 3 glass capability chips, footer "RCA engine v0.1.0" / "Data source connected"), right panel with Sign in / Sign up segmented toggle, email + password with icons, eye-icon toggle, 4 demo profile buttons (admin, plant engineer, QA lead, viewer) that fill email and password, errors under the inputs with input shake.
- RcaRobot per §8 in features/auth/robot/ (RcaRobot, RobotSvg, useCursorTarget, useRobotState, poses, RobotContext, robot.css + RobotFallback): layered SVG, cursor tracking with lagged springs, blink (incl. double), idle look-around after 4 s, float + shadow, chest pulse, state machine (watchingEmail with caret tracking and nods, privacy, peeking, thinking dots + sway, success hop/wave/happy eyes/mint flash then navigate after 900 ms, error head-shake + red sad eyes 1.5 s), demo-profile wave, toggle glance + hop, easter eggs (head giggle, chest glow, 1.5 s debounce), touch + already-permitted device orientation, reduced motion, lazy chunk (RcaRobot 146 kB) with a same-size static fallback.
- Verified headless (evals/browser/robot_check.mjs): **31/31 checks, 3 consecutive runs** — separate chunk, CLS ≈ 0.001 and no robot shift, lag hierarchy eyes 0.88 > head 0.73 > body 0.63 of range after 120 ms, ~60+ fps loop, blink, idle look-around, caret tracking, no long tasks while typing, privacy/peeking/thinking/error/success states, head + input shake, giggle, demo fill + wave, status badges, reduced motion, touch at 375 px, layout at 375/768/1280/1536 with no horizontal scroll, no console errors.
- Tests: SQLite 82 passed + 1 skipped; Postgres 83 passed (new test_signup_public.py). Workflow walk 9/9 through the new login page.

#### Stage 5 complete
- Categories/subcauses/display names/rule weights/thresholds/texts moved to config/cause_categories.yaml, validated at start-up; GET /api/config/causes. Ranking regression identical (16/16, 16/16, 2/2; full snapshot byte-identical).
- Cause-and-effect graph on the incident page (React Flow): signals/events → hypotheses → verification actions (+ missing checks) → cited documents; edge labels = rule weights (+3/+2/+1, −2/−3 dashed red for contradicting); click highlights connections and opens the evidence; works for the abstain case.
- Tests: SQLite 79 passed + 1 skipped; Postgres 80 passed (new test_cause_config.py incl. 7 invalid-config cases, test_cause_graph.py ranked + abstain; RBAC matrix + graph/config endpoints).
- Headless check (evals/browser/graph_check.mjs): INC-001 12 nodes / 12 edges / 6 weight labels, hypothesis click lights the whole chain; INC-008 abstain 23 nodes, verdict column, no console errors. Graph chunk 172 kB separate from the main bundle.

#### Stage 4 complete
- POST /api/cases/draft (memory agent), POST /api/cases (edited fields, duplicate check), PATCH /api/cases/{id} (versioned edit), POST /api/cases/{id}/retire, GET /api/cases/{id}/history; case embeddings (cases.embedding vector(384) + model, migration 0005), embedded on propose/approve/edit and by init_db / `python -m backend.embed_chunks`.
- UI: two-step "Propose case" modal (generate → edit every field: cause, summary, symptoms, evidence, fix, lessons, documents checklist, notes; duplicate warning with required reason); case detail with history, edit and retire for admin/QA. Case forms use explicit id/htmlFor labels (the walk found wrapped labels gave fields confusing accessible names).
- Tests: SQLite 67 passed + 1 skipped; Postgres 68 passed. New evals/test_memory_agent.py: template draft fields, fake-LLM draft = 1 request then cached, invented-number guard, edits stored, duplicate same incident (409 → reason → 201), similar approved case (signal overlap and embedding paths), edit versioning + history + permissions, retire never recalled, end-to-end recall with semantic reason and B15. RBAC matrix extended (draft, history, edit, retire).
- Evals (Postgres + fastembed): memory leave-one-out agreement 0.833 (≥ 0.7), all suites pass; ranking 16/16, 16/16, 2/2.
- Headless walk now 9/9 (added: QA edits approved case → version 2 kept, retires it, INC-009 re-analysis no longer recalls it). No live LLM calls in this stage (counter still 2/10).

#### Stage 3 complete
- B5: GET /api/incidents lists sample + uploaded incidents with source label, line/machines, date, top hypothesis and status (uploads still never enter evals). Status badge on dashboard, incident list, incident page, machine page; cases show case status.
- B8: table rca_drafts, versioned saves, history with view + restore (restore = new version), Markdown/PDF export with an irremovable validation notice, viewers read-only. Saved draft is loaded on page open.
- Links both ways (incident header → its cases; case → incident and documents), case detail page /cases/:id, names instead of IDs (proposer, approver, uploader, draft author).
- Dashboard (home): KPI cards (open incidents, cases pending, documents pending mapping, LLM calls today), incidents-by-status, recent incidents, role-specific pending items. Sidebar badges for pending documents (doc editors) and pending cases (approvers), refreshed on navigation and after actions.
- Fixed B6 (summary on review records reviewer + date), B11, B12, B18 (machine edit sends '' for required text), B4/B19 (stage 1). create_machine link rebuild (stage 1).
- Tests: SQLite 61 passed + 1 skipped; Postgres 62 passed (new evals/test_workflow.py: B5 listing, status transitions incl. rejected, draft versions/restore/validation, viewer read-only, MD/PDF exports keep notice, B11, B12, dashboard + nav counts; RBAC matrix extended with all new endpoints).
- Headless walk (evals/browser/workflow_walk.mjs, Chrome headless via playwright-core in scratch, backend 8001 on Postgres rca_walk, Vite 5173): **8/8 steps pass** with no reloads or URL workarounds; first run found a stale sidebar badge (fixed with a counts-changed event). Draft survived reload with 2 versions; Markdown + PDF downloads contained the notice; QA approval showed names; INC-009 recalled the approved case; evaluations 32 metrics pass; viewer read-only.

#### Stage 2 complete
- B2 fixed (no retry on 429/quota, ≤2 retries on 503 with 1 s/2 s backoff, immediate template fallback recording quota_exhausted). B3 fixed (AGENT_MODE deterministic default with zero LLM calls; llm_plan = one call). One wording call per analysis covers narratives, steps and draft. Daily budget table + GET /api/llm/status. UI: top-bar chip "LLM calls today: x / 18" (warns on quota/budget/no key), analysis shows text source, LLM requests used/budget, cache hits and fallback reason, agent mode.
- Tests: SQLite 54 passed + 1 skipped; Postgres 55 passed. New fake/mocked tests: quota not retried + blocks next call, long Retry-After, short 429, 503 ×2 then fail, 503 once then success, 4xx not retried, invalid JSON, daily budget, per-analysis budget, cache hit makes no request, analysis = exactly 2 requests then 0 on re-run, stored analysis re-open makes 0. Eval suite "LLM layer" adds quota_and_budget_fallback_rate (1.0); agent suite adds llm_plan_single_call_within_budget (1.0).
- Live: see counter above (Unverified, provider 503). Frontend tsc passes.

#### Stage 1 complete
- docker-compose.yml: pgvector/pgvector:pg18 (Postgres 18.6, pgvector 0.8.7), host port 5433, named volume rca_pgdata, pg_isready healthcheck, init SQL `CREATE EXTENSION IF NOT EXISTS vector`. Docker Desktop had to be started; the native PG18 on 5432 was not touched.
- Added pinned psycopg[binary] 3.3.6, alembic 1.20.0, pgvector 0.5.0 (+ fpdf2 2.8.9, PyYAML 6.0.3 for later stages).
- Alembic: 0001 = v1 schema exactly; 0002 = timestamptz (B14), JSONB, vector(384) + HNSW cosine index, tsvector + GIN.
- Retrieval rewritten (B13): SQL scope filter first, then SQL FTS + SQL vector search, RRF. Only candidate chunks are loaded.
- `python -m backend.migrate_sqlite` (idempotent, ON CONFLICT DO NOTHING, sequences reset) and `python -m backend.embed_chunks`.
- Verified: `alembic upgrade head` on an empty Postgres DB; data copy from the real data/app.db copy (9 machines, 8 docs, 32 chunks, 12 cases, 3 eval runs, 27 eval results) — second and third runs inserted 0; fastembed embedded 32 chunks (384 dims) in ~3 s.
- Tests: SQLite 44 passed + 1 skipped (Postgres-only copy test); Postgres 45 passed. New tests: upgrade on empty DB + no drift vs models, v1 adoption with timestamp conversion, SQLite→Postgres copy idempotency.
- Evals on Postgres with real fastembed: all suites pass. Retrieval: hybrid (pgvector) recall@4 1.0, wrong-machine leaks 0; lexical-only (Postgres FTS) recall@4 0.852, MRR 1.0, leaks 0. Ranking 16/16, 16/16, 2/2, ambiguous 3/3.

#### Stage 0 complete
- main already contains stage 0–11 work (merge c58eed5). No processes were listening on 8001/5173/5174 (nothing to stop). Created feature/v2.
- B1: `resolve_llm_key` — LLM_API_KEY for every provider; GROQ_API_KEY only when provider=groq and LLM_API_KEY empty/blank. Logs the source variable name only.
- B17: fixtures + key written to a TemporaryDirectory; eval worker uses a temp DOCUMENTS_DIR. `git status` stays clean after pytest/evals.
- B16: unknown-machine test now renames one machine (IMM-01→IMM-09) and asserts the exact "Unknown physical machine: LINE-A/IMM-09" message.
- Removed committed frontend/tsconfig.tsbuildinfo.
- Tests: pytest 42 passed (SQLite). Ranking regression 16/16 top-1, 16/16 top-3, 2/2 abstentions (test_rank_regression).
- Docker engine is not running at the start of the build (Stage 1 will try to start Docker Desktop).

---

## v1 history (feature/llm-rag-rbac)

Branch: feature/llm-rag-rbac; baseline on main: 6c6aa2d.
Stages 0–11 run in sequence; each completed stage has tests and its own commit.
Current stage: 11, final verification and report. Next unfinished stage: 11.

## Decisions
- New request supersedes old plan exclusions (database/auth); deterministic ranking and High/Medium/Low hypotheses remain authoritative.
- Robot is deliberately a labelled placeholder.
- Machine identity is line + short name; nine physical machines from CSVs.
- No .env writes or live API keys. Tests use ephemeral process values.
- Venv initially uses existing system packages; exact direct dependency pins support clean installs.
- Port 8000 occupied; verification uses 8001 without stopping it.
- Key isolation scans executable source, not prose or write-only generators; tests live in evals.

## Verified baseline
Top1/top3 16/16; abstentions 2/2; ambiguous 3/3. Frontend typecheck and bundle passed. Historical findings in audit_report.md.

## Stage log
### Stage 10 complete
All eight deterministic suites pass; ninth optional live judge is explicitly Unverified. Ranking 16/16, abstentions 2/2, ambiguity alternatives 3/3. Mapping precision/recall/status/conflict/ambiguity 1.0; retrieval recall@4 0.85185, MRR 1.0, wrong-machine leaks 0; final grounded sections/cited steps/adversarial probes 1.0; fake/mocked HTTP provider cases 1.0; agent validity/cap/trace/shape 1.0 and scope attempts 0; memory LOO category agreement 10/12, current exclusion and approval role checks 1.0; full HTTP role matrix 1.0. Combined pytest initially found two new failures (grounding false positive + scan regex false match), fixed; focused 5 tests passed, earlier 30 passed. Final full pytest follows in stage 11.
Decisions: isolated evaluation subprocess DBs prevent fixture/config interference with application users; nested eval computation is stubbed only in RBAC matrix to prevent recursion. Synthetic chiller references reuse known machine UIDs instead of inventing machine IDs. Evaluation fixtures are generated under data/eval_docs; labels stay in evals. Numeric scoring policy is supplied explicitly; direction checks operate on clauses so a defect increase does not assert rising temperature. Next unfinished stage: 11.
### Stage 9 complete
Frontend TypeScript and production build passed. Real login/session guard, role controls, machine registry/detail/spec editing, scoped document upload/detection/confirmation/library/chunk viewer, analysis provenance/source/grounding/trace, persisted analysis for viewers, case proposal/review and admin users pages implemented. Evaluations UI expects final stored suite shape. Light tokens and labelled robot placeholder retained. Browser end-to-end verification is scheduled in stage 11; bundle warning is informational (charts dominate). Next unfinished stage: 10.
### Stage 8 complete
29 pytest tests passed. Numeric pools exclude identifier digits; signal assertions bind direction/machine/value; actions require a retrieved doc+chunk and quoted text. Both audit probes flagged. Replaced sections and flags are reported; final replacement is rechecked. Abstention drafts are checked too. Decision: conservative exact normalized action quotes rather than permissive paraphrase matching. Next unfinished stage: 9.
### Stage 7 complete
27 tests passed. Read-only capped HTTP/fake/deterministic tool loop; authorized search and chunk reads; persisted traces/history APIs; weighted physical-machine/category/signal/event recall; transactional proposed/approved/rejected case workflow. Tests verify malicious cross-machine tool denial, stable scores, cap, trace shape, approval and current-incident exclusion. Seed fixes are explicitly synthetic, not repairs. Decision: memory summaries use deterministic structured templates so engineer-provided confirmed facts remain authoritative. Next unfinished stage: 8.

## Verification limits
Live model/judge: Unverified (no key). Fastembed inference must be attempted; default lexical-only retrieval.

### Stage 0 complete
Copied planning documents, created main baseline/feature branch, installed all requested packages, pinned exact versions and added README. Dependency import checks passed. Next unfinished stage: 1.


### Stage 1 complete
10 pytest cases passed; frontend tsc passed; all original ranking/abstention/ambiguity results retained. Upload rejects audited bad inputs; request IDs/JSON errors and stale-response protection added. Decision: rolling three-step defect onset suppresses isolated count noise; event context expanded to 20 minutes but strictly earlier than window start. Next unfinished stage: 2.


### Stage 2 complete
12 tables (including JWT revocation) created; SQLAlchemy transactional case retention replaces mutable JSON. Schema/seed command succeeded; idempotent seed test passed; stage 1 regression tests still passed. Next unfinished stage: 3.


### Stage 3 complete
14 pytest tests passed. Login/me/logout, bcrypt, JWT expiry/revocation, admin user creation/role/deactivation and server permissions implemented. All business routes protected; health/docs public. Mutation audits include actor. Decision: absent JWT_SECRET uses process-random secret only in development; persistent/production sessions require configured secret. Next unfinished stage: 4.

### Stage 4 complete
18 pytest tests passed. Nine physical machines seeded with measured baseline ranges; eight SOPs migrated with their existing IDs. PDF/DOCX/Markdown/TXT extraction, overlapping chunks, scope links, detection suggestions, conflict/ambiguity quarantine and confirmation endpoints implemented. Synthetic manufacturer/model metadata is labelled; no physical model or serial is invented. Next unfinished stage: 5.

### Stage 5 complete
Provider tests: 5 passed; prior 18 regression cases passed in the combined run (one new test used a wrong incident ID, corrected and retested). Plain HTTP Groq/OpenAI-compatible/Anthropic, fake provider, schema/retry/fallback, versioned cache and persisted per-call telemetry added. All responses expose llm/template; a cache hit is llm. Live calls Unverified. Decision: separate test temp directories when runs overlap; SQLite fixtures must finish before reuse. Next unfinished stage: 6.

### Stage 6 complete
25 pytest cases passed. Active SQLite chunk BM25, hard machine/model/line/plant filter, scope tie priority, top-k/min-score, embedding vectors in SQLite and cosine/RRF added. Analysis returns accessed and excluded document provenance and chunk citations. Mocked embedding inference passed, provider failure falls back to lexical. Actual fastembed model inference remains Unverified until attempted in final verification. Next unfinished stage: 7.

