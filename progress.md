# Build progress

## v2 build (branch feature/v2, from main c58eed5)
Prompt: v2 stages 0–9 (see audit_report_v2.md for bug IDs B1–B20). Each stage ends with checks, this file, and a commit "v2 stage N: …".
**Next unfinished stage: 1.**

### Live LLM call counter (budget 10 for the whole build)
Used: 0.

### v2 decisions (made by the agent)
- D0.1 `.env` does not match the brief: LLM_PROVIDER=openai_compatible, LLM_API_KEY empty (the key sits in GROQ_API_KEY), JWT_SECRET / SEED_ADMIN_* / DEMO_PASSWORD empty. `.env` is never written by the agent. After B1 the key in GROQ_API_KEY is only read for provider=groq, so the owner must move it to LLM_API_KEY and set LLM_PROVIDER=gemini. A warning is logged at start-up when this mismatch is detected (no key printed).
- D0.2 Generated eval fixtures (data/eval_docs/*, evals/docs_answer_key.json) were removed from git and are now produced in a temp folder per run; the key is passed in memory. Their content is deterministic, so nothing is lost.
- D0.3 Uploaded documents path is configurable (DOCUMENTS_DIR, default data/documents). Tests and the eval worker point it at temp folders.

### v2 stage log
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

