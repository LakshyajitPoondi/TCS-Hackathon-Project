# Production Intelligence & RCA — Read-only audit

Audit date: 6 October 2026 (Asia/Calcutta). Project root: `C:\Users\laksh\Documents\TCS Tech Day`.

## 1. Summary

The core synthetic-data RCA demo works: the API analyzes all 18 incidents and the React frontend renders investigations and evidence.
The existing sanity check reproduced 16/16 top-1 and top-3 matches, 2/2 correct abstentions, and 3/3 ambiguous alternatives on planted data.
SOP retrieval uses real BM25 over eight fictional Markdown documents; memory recalls local JSON cases without changing rankings.
Groq client code and template fallback exist, but live LLM behavior remains Unverified; document upload and authentication/RBAC are absent.
The evaluation endpoint still returns 501, and the full evaluation metrics, automated test suite, README and delivery documents are unfinished.
Accepted sparse or infinite numeric inputs can cause 500 errors, and the grounding checker can accept unsupported claims and actions.
Only this report was created; successful upload/save tests intercepted disk writes in memory, so durable persistence remains Unverified.

### Scope and verification method

- Read `progress.md` fully. Root `plan.md` and `frontend_design.md` are missing; read the complete copies at `C:\Users\laksh\Downloads\plan.md` and `C:\Users\laksh\Downloads\frontend_design.md`, as referenced by `progress.md`. These external copies may not be version-aligned with the checkout.
- Inspected application source, configuration, dependency manifests/lockfile, all SOPs and JSON data. Parsed all 18 CSVs and compared every row with in-memory generator output: all match. Skipped dependencies, Git internals, caches and generated distribution code as authoritative source.
- Default Python 3.14 and bundled Python lack FastAPI. Existing Python 3.13 has the backend dependencies; no installation was performed. Port 8000 was already occupied, so started the imported FastAPI app through Uvicorn on `127.0.0.1:8001`, without reload, with `-B`, an empty Groq key and `LLM_ENABLED=false`.
- To honor read-only constraints, intercepted upload `Path.write_bytes`, case `Path.write_text`, and upload directory creation in memory. Case reads reflected those in-memory saves. Analysis and retrieval implementations were unchanged. Upload-to-disk/restart durability was intentionally not exercised.
- Real HTTP requests tested every declared application route and the automatic documentation routes. Edge-case downstream 500 tests used FastAPI TestClient with only the incident loader substituted to return the same validated in-memory CSV. Those are identified separately from network tests below.
- Started existing frontend dependencies through Vite's API with dependency discovery disabled, no configuration bundling, and a process-only `VITE_API_BASE_URL=http://localhost:8001`. Ran TypeScript `--noEmit` and Vite production build with `write:false`: both passed. The ordinary `npm run build` was not run because it writes `dist`.
- Browser verified `/`, `/incidents/INC-001` with analysis and SOP modal, `/upload`, `/evaluations`, `/incidents/INC-999`, and `/incidents/INC-008` with abstention. One current viewport was visually inspected; the full responsive/accessibility checklist was not run. No screenshots or temporary test scripts were saved.
- `py -3.13 -B -m evals.sanity_check` succeeded. `py -3.13 -B -m pytest -p no:cacheprovider` could not run because pytest is not installed; no pytest files or frontend test script exist.

Status meanings: **Built** = exercised relevant behavior; **Partial** = verified pieces plus missing/limited/unverified parts; **Mock** = simulated feature implementation; **Missing** = absent; **Unverified** = implementation present but its defining behavior was not exercised. Synthetic fixtures do not by themselves make an implementation Mock. Each of the 31 requested items has one status; qualifications remain in the note.

## 2. Feature status table

| Item | Status | Evidence | Note |
|---|---|---|---|
| A1 Sensor/time-series data | Built | `data/incidents/incident_001.csv` through `incident_018.csv`; `backend/core/config.py:EXPECTED_COLUMNS`; GET summary/signals → 200; generator comparison | CSV files contain 120 rows each: 40 two-minute timesteps × IMM-01/02/03, one LINE-A/B/C per incident, March 1–18 2026. Columns: timestamp, line, machine, event_code, temperature, speed, vibration, motor_current, defect_count, downtime_min, batch, operator_note. Dynamic CSV analysis, synthetic fixtures and fixed domain rules; no real plant feed. |
| A2 Generator and answer key | Built | `generate_data.py:build_incident`, `build_memory_seed`, `main`; `data/answer_key.json`; in-memory regeneration matched all 18 CSVs and the memory seed | Incident seed is 42+n; memory seed 7. Seven cause families, two weak/conflicting abstention incidents and three overlaps. Generator writes were not run. See planted patterns below. |
| A3 CSV upload | Partial | `backend/services/data_loader.py:_read_csv`, `validate_dataframe`, `save_upload`; `backend/api/routes/incidents.py:upload_incident`; HTTP 200/422 tests | Schema, timestamps, mostly nonnumeric values, UTF-8 and empty files checked. Infinity, negative counts and sparse signals accepted; downstream crashes reproduced. Actual disk persistence Unverified. |
| A4 Machine documents | Partial | `data/sops/SOP-*.md`; `engine/rag.py:_load`, `SOP_INDEX`; all eight GET SOP routes → 200 | Eight fictional SOPs stored as Markdown and readable through API. No upload, document-management model, PDF extraction, manuals or maintenance-guide ingestion workflow. |
| A5 Sensor/document separation | Built | `backend/core/config.py:INCIDENTS_DIR`, `UPLOADS_DIR`, `SOPS_DIR`; `data_loader.py`, `engine/rag.py`; HTTP incident and SOP responses | Sensors in `data/incidents` and `data/uploads`; documents in `data/sops`; separate parsers and routes. Pydantic sensor models exist; SOP route returns a plain dict and has no typed document persistence model. |
| A6 Database | Missing | `data_loader.py:save_upload`; `engine/memory.py:_read`, `retain`; `requirements.txt` | CSV/Markdown/JSON files and in-process indexes only. Database explicitly out of scope in external plan §1. |
| B7 Anomaly detection | Built | `engine/signals.py:analyze_signals`; 18 HTTP analysis responses → 200 | First 25% baseline; 3.5σ point deviations, 3σ defect thresholds, sustained-run window, mean-shift/flatline/spike/jitter flags, batch concentration, co-movement and event proximity. No learned anomaly model. |
| B8 Root-cause ranking and evidence | Built | `engine/scoring.py:_rules`, `score_hypotheses`, `_confidence`; HTTP INC-001/011/017/018 | Fixed weighted rules: +3/+2/+1 support, −3/−2 contradictions, score ≥5 eligible, ≥6 medium, ≥8 high, at most three. Evidence, contradictions and missing checks returned. Scores are raw sums, not probabilities or normalized scores. |
| B9 Placeholders/mock parts | Partial | `backend/api/routes/evals.py:run_evals` → 501; `scoring.py:SOP_STEPS`; `IncidentPage.tsx:LOADING_LABELS`; `progress.md:Known limitations` | No literal `[MOCK]` marker in application files. Evaluation route is a stub; Hindsight deferred; legacy fixed SOP steps are overwritten by service retrieval. Cycling UI progress labels are timers, not actual stage telemetry. |
| B10 Incident memory | Partial | `engine/memory.py:build_signature`, `recall`, `retain`; `analysis_service.py:run_analysis`, `_llm_input`; POST cases → 200 INC-H13 with intercepted write | Twelve synthetic seed cases plus saved JSON. Jaccard similarity, ≥2 shared tags, top three; current source incident excluded. In-memory saved INC-H13 recalled for INC-002 and excluded for INC-001. Rankings never change; LLM input receives context, template narrative/draft do not use it. Durable writes/concurrency Unverified. |
| B11 Answer-key isolation | Built | `rg --hidden answer_key` results; `generate_data.py:main`; `evals/sanity_check.py:run`; all 18 full `run_analysis` calls with answer-key opens forbidden succeeded | Before this report, literal references occur only in generator (writes, docstring, print) and sanity-check script (read, docstring). No backend/engine reference or analysis read. This report adds explanatory references. |
| C12 LLM integration | Unverified | `engine/llm.py:SYSTEM_PROMPT`, `_call_groq`, `_parse`, `generate`; `backend/core/config.py:GROQ_*` | HTTP Groq OpenAI-compatible JSON-mode client, configurable model/key, timeout and invalid-output retry present. No live key call or real model output tested. Prompt references evidence, SOP steps and past cases; no OpenAI/Anthropic/Gemini/local provider client. |
| C13 Provider abstraction/config | Partial | `.env.example`; `backend/core/config.py`; `engine/llm.py:generate`, `_call_groq` | Environment-based key/model/enabled flags and one wording entry point exist. Provider URL is fixed to Groq; no selectable provider adapter. `MEMORY_BACKEND` is declared but does not select an implemented adapter. |
| C14 RAG/retrieval | Partial | `engine/rag.py:_tokens`, `_load`, `build_query`, `retrieve_for_hypothesis`; `analysis_service.py:_retrieve`; no-key INC-001 retrieves SOP-007/SOP-002 | Working lexical retrieval over whole SOP documents plus parsed numbered steps; testable without an LLM. No general chunking, embeddings, vector store, document upload or retrieval-evaluation suite. Vector stores deliberately excluded by plan. |
| C15 Agents/tool calling | Missing | `engine/llm.py:_call_groq`; `analysis_service.py:run_analysis` | Fixed Python pipeline and one completion request; no tools schema, agent loop or model-directed multi-step reasoning. Not required by external plan. |
| C16 No-key fallback | Built | `engine/llm.py:generate` → `(None, 'template')`; `analysis_service.py:run_analysis` meta `text_source=template`; all 18 HTTP analyses | Empty key/disabled model still yields complete template output or abstention. Live-provider failure behavior not exercised. Existing cache is checked before enabled/key flags. |
| D17 Evaluation | Partial | `evals/sanity_check.py:run`; GET `/api/evals` → 501; missing `evals/run_evals.py` | Sanity script measures category/subcause combined-label top1/top3, correct/wrong abstentions, ambiguous alternatives. Does not evaluate whole pipeline grounding, SOP hits or seed-only leave-one-out memory. |
| D18 Observability | Partial | `analysis_service.py:run_analysis` log.info; `engine/llm.py` warning logging; Uvicorn startup and request behavior | Basic status/source/grounding logs and server logging. No configured application log level, request IDs, structured traces, correlation or per-stage timing. INFO analysis events may be filtered by default logging configuration. |
| D19 Automated tests | Partial | `evals/sanity_check.py`; sanity run successful; pytest attempt reports `No module named pytest`; `frontend/package.json:scripts` | Executable regression diagnostic exists but no assertions/nonzero failure policy. No pytest/unit/API/browser test suite found. Type check and in-memory frontend production build passed. |
| E20 Authentication | Missing | `backend/main.py`, all route modules and schemas; `frontend/src/main.tsx` | No signup/login endpoints, users, password hashes, sessions/JWT or auth middleware. Auth excluded by plan but requested by design/audit. |
| E21 Roles/RBAC | Missing | `backend/api/routes/*.py`; OpenAPI paths; unauthenticated request successes | Every application endpoint and documentation route is unprotected; no roles or permission checks, including upload and save-as-validated-case. |
| E22 Demo/seed users | Missing | `data/memory_seed.json`; `generate_data.py:build_memory_seed`; frontend route inventory | Seed contains historical cases, not user accounts. No demo login profiles or user seed. |
| F23 API surface | Partial | `backend/main.py`, route decorators, GET OpenAPI → 200; endpoint table below | All declared endpoints exercised; most real, evals 501. Successful mutation persistence deliberately not tested. |
| F24 Error handling | Partial | `backend/main.py:_not_found`, `_invalid`; Pydantic request checks; `frontend/src/api/client.ts:readableDetail`, `request`; edge-case TestClient 500s | Expected 404/422/501 are clean; validation detail uses string or list. Unexpected 500 is plain text, not consistent JSON. Client handles both and substitutes generic 5xx text. |
| F25 CORS | Built | `backend/core/config.py:CORS_ORIGINS`; `backend/main.py:CORSMiddleware`; HTTP GET/preflight | `http://localhost:5173` allowed, methods/headers wildcard, credentials not enabled. GET includes allow-origin; preflight 200. `http://127.0.0.1:5173` preflight 400. |
| G26 Frontend pages/components | Built | `frontend/src/main.tsx`, `pages/*`, component folders; browser observations | List, detail, upload, evaluation empty state and missing-incident page render. Cooling RCA and abstention render; SOP modal loads actual text. Charts, KPIs, health, hypothesis/evidence cards, draft and save modal exist. Disk-backed upload/save UI flow Unverified. |
| G27 Design compliance | Partial | External design §§2–7/11; `globals.css`, `index.html`, `SignalChart.tsx`, `Sidebar.tsx`, page source; browser screenshot | Light tokens/fonts/pill controls and core evidence UI present. Missing dashboard/auth/cases, list filters/columns, baseline line, raw/events tabs, full motion and several layout details. Confidence labels follow plan rather than conflicting design percentages. Full breakpoint/accessibility checks Unverified. |
| G28 Animated auth robot | Missing | External design §8; `frontend/src/main.tsx`; full source inventory; `progress.md:What was cut` | No RcaRobot/robot files or auth route; cursor tracking, blink, privacy/peek and form reactions absent. Explicitly deferred. |
| H29 Security/hygiene | Partial | `.env.example`, both `.gitignore` files; `data_loader.py:resolve_incident_path`; `sops.py:get_sop`; `incidents.py:upload_incident`; secret-pattern scan; Git state | No actual key/secret found in inspected source; no commits exist. Safe incident ID/path containment and SOP dictionary lookup. No upload size/row limit, finite/range guards, auth or validated-case authority. No dependency-vulnerability audit performed. |
| H30 Reproducibility/dependencies | Partial | `requirements.txt`, `frontend/package.json`, `package-lock.json`, `.env.example`, `frontend/.env.example`, `progress.md:How to run`; runtime attempts | Existing Python 3.13 and Node 24 work. Requirements use unpinned lower bounds; numpy is imported directly but supplied transitively by pandas. README, clean-install verification, Python/Node version guidance and backend install/setup commands are missing. No installs permitted. |
| H31 Git/ignore state | Partial | `git status --short`, `git ls-files`, `git log -1`; root/frontend `.gitignore` | No commits, no tracked files; entire project initially untracked. Frontend dependencies/dist, `.env`, bytecode, uploads/cache ignored; `.gitkeep` exception works. Mutable `data/memory_cases.json` is not ignored. Final report is one additional untracked file. |

**Counts (31 items): Built 9; Partial 15; Mock 0; Missing 6; Unverified 1.**

### Planted dataset patterns

`generate_data.py:SCENARIOS`, `ANSWER`, `ALSO_PLAUSIBLE`, `build_incident` and `data/answer_key.json`:

| Incidents | Planted cause/pattern |
|---|---|
| 001, 009, 017 | Cooling: target temperature +15.5–18.5°C ramp, speed −8–12%, defects, temperature alarms, downtime and heat/cooling notes. 017 also has vibration +22%. |
| 002, 010, 018 | Mechanical: vibration +55–70%, current +10–15%, speed jitter, defects, vibration alarms and grinding notes. 018 also has temperature +7°C. |
| 003, 011 | Material: shared suspect lot across three machines, defects, normal sensors, QC hold and supplier/resin notes. 011 includes preceding changeover. |
| 004, 012 | Method: preceding CHG, target speed setpoint +8%, defects, setup notes. |
| 005, 013 | People: shift change, defects with normal sensors, skipped calibration/incomplete handover notes. |
| 006, 014 | Measurement: isolated temperature spikes or flatline; other sensors and defects remain near baseline; panel/probe notes. |
| 007, 015 | Environment: +6–8°C drift across machines, mild defects, ambient/AC notes. |
| 008, 016 | Insufficient: weak temperature/defect changes, or conflicting weak changes across machines. |

Answer key includes category, subcause, expected SOP, planted window, target machine, alternatives and abstention flag. Historical cases are synthetic tags generated from the same cause taxonomy, not real engineer-validated production records, despite their display wording (`generate_data.py:build_memory_seed`). Perfect synthetic scores are not evidence of real-data generalization.

## 3. Endpoint table

All requests below used no credentials. Network tests targeted the audit server on port 8001. Real = actual implementation, not a guarantee of complete production readiness. Automatic docs routes are included for completeness.

| Method | Path | Purpose | Implementation/status | Auth required | Actual tested result |
|---|---|---|---|---|---|
| GET | `/` | API identity/version | Real | No | 200, name/status/version 0.1.0. |
| GET | `/health` | Liveness | Real | No | 200 `{"status":"healthy"}`; does not probe model/provider, data or memory health. |
| GET | `/api/incidents` | Curated list | Real | No | 200, 18 IDs/filenames; uploads intentionally excluded. |
| POST | `/api/incidents/upload` | Validate/store CSV | Real; storage intercepted | No | 200 UPL-df9f1675 for INC-001 bytes; no-file, empty, missing-columns, invalid UTF-8, bad dates and mostly bad numbers → 422. Infinity, sparse temperature, negative counts and valid CSV named `.txt` → 200. Durable writes Unverified. |
| GET | `/api/incidents/{incident_id}` | Summary | Real | No | INC-001 → 200, 120 rows, three machines, 75 defects, five downtime minutes; INC-999 → 404. Validated infinity input through TestClient loader substitution → 500. |
| GET | `/api/incidents/{incident_id}/signals` | Chart records | Real | No | INC-001 → 200, 120 records; INC-999 → 404. |
| POST | `/api/incidents/{incident_id}/analyze` | Full RCA pipeline | Real | No | All INC-001..018 → 200; 008/016 abstain, others complete. Grounding field passed for all template responses. INC-999 → 404. Sparse/infinite inputs through TestClient loader substitution → 500. |
| POST | `/api/cases` | Retain validated case | Real; storage intercepted | No | Valid machine/cooling case → 200 `saved`, INC-H13. Missing machine subcause/empty body → 422; unknown incident → 404. Later INC-002 analysis recalls in-memory INC-H13. |
| GET | `/api/evals` | Evaluation dashboard data | Stub/501 | No | 501 `{"detail":"Implemented in Phase 5"}`. |
| GET | `/api/sops/{sop_id}` | SOP text | Real | No | Every stored SOP → 200 id/title/content; SOP-999 → 404. |
| GET | `/openapi.json` | OpenAPI contract | Generated | No | 200 schema with all ten application path keys. |
| GET | `/docs` | Swagger UI | Generated | No | 200 HTML. Remote Swagger asset loading not browser-verified. |
| GET | `/docs/oauth2-redirect` | Swagger helper | Generated | No | 200 HTML; presence does not mean OAuth is implemented. |
| GET | `/redoc` | ReDoc UI | Generated | No | 200 HTML. Remote ReDoc asset loading not browser-verified. |
| OPTIONS | `/api/incidents/INC-001/analyze` | CORS preflight | Middleware | No | 200 `OK` for localhost:5173; alternate-origin health preflight → 400. |

There are no document-upload, login/signup, user/role, case-list or agent endpoints (`backend/main.py` and route inventory). Encoded incident traversal request `/api/incidents/..%2F..%2Fsecret` returned 404; `resolve_incident_path` additionally enforces an alphanumeric ID suffix and parent containment. SOP lookup never derives a file path from request input.

## 4. Planned vs built

Phase comparison uses the external Downloads plan; its phase table has stale “next”/blank markers, while project `progress.md` claims Phase 4/5 complete.

### Phase 0 — data

Fixture and seed generation verified in memory. No missing Phase 0 deliverable found. Real production data and broad incident families beyond this synthetic taxonomy were never part of the implemented generator (`generate_data.py`).

### Phase 1 — foundation

API, schemas, CSV loader and routes verified. Planned root documentation files are absent from the checkout. Upload validation does not cover finite values, physical ranges, sparse per-machine baselines or upload limits (`validate_dataframe`, `upload_incident`). The design/plan claim that columns are defined once is also imperfect: generator and upload UI repeat the header list.

### Phase 2 — deterministic analysis

Core signal/scoring/abstention behavior verified. Plan §6 promises a health contribution from trend slope; implementation uses baseline/window z-scores and a jitter floor only (`signals.py:analyze_signals`, lines 403–412). Plan §7 calls the score normalized; implementation is a raw weighted sum (`scoring.py:score_hypotheses`). Physical range checks mentioned in plan §2 remain absent. Event “precedence” also accepts events after the detected start (see bugs).

### Phase 3 — knowledge, memory and wording

BM25, SOP sources, local memory recall and templates verified. Live Groq output, provider failures, disk persistence and cache lifecycle are Unverified (`llm.py`, `memory.py`). Hindsight is explicitly deferred by progress, not implemented. Plan §10 lists model-generated missing checks; actual LLM schema has only narratives, verification steps and draft, with deterministic `MISSING_CHECKS` retained (`LLMOutput`, `_llm_input`, `scoring.py`). Grounding does not enforce all prompt promises.

### Phase 4 — frontend/design

Core RCA page and evaluation placeholder render. The external frontend design is much larger than the delivered UI:

- §7.1 and §8: auth screen, sign-up/sign-in toggle, demo profiles and every robot state/animation absent.
- §§7.2–7.3/7.7: dashboard, cases grid/list and related navigation absent; no case-list backend route.
- §7.4: incident list lacks search, machine/severity/date filters and machine/time/duration/severity/top-hypothesis/status columns. Actual list is ID/file/action (`IncidentsPage.tsx`).
- §§6.8/7.5: chart has incident band, machine lines and selected event markers, but no baseline horizontal line; no Summary/Raw readings/Events tabs or raw-table virtualization. STOP/QC_HOLD are not chart markers. Layout is stacked rather than the specified 8/4 split (`SignalChart.tsx`, `IncidentPage.tsx`).
- §§6.1/6.9: rectangular 64px top bar rather than floating pill navbar; 256px sidebar rather than 264px; no 80px collapse mode (`TopBar.tsx`, `Sidebar.tsx`).
- §§5/6: no framer-motion, aura drift/binary texture, viewport-triggered reveals, count-up stats, initial chart drawing, toast system, glass/feature-card family or danger button variant. Existing CSS fade/hover and inline alerts are intentional cuts (`package.json`, `globals.css`, `Button.tsx`, `progress.md:What was cut`).
- §7.7 and plan §11: evaluations has no run button or real metrics/pass-fail data; generic tables await a future payload (`EvaluationsPage.tsx`).
- §7.8: optional landing hero/features/stats/process/CTA/footer absent, explicitly cut.
- §11: complete 375/768/1280/1536px, contrast, keyboard and reduced-motion checks remain Unverified. Cyan contrast is a documented limitation in `progress.md`.

Design §6.3 requests confidence percentages and several headlines claim root-cause certainty; external plan §§5/17 prohibits those. Existing `ConfidenceBadge` correctly uses High/Medium/Low, and hypotheses terminology should be preserved when resolving that conflict.

### Phase 5 — evaluations and delivery

Missing `evals/run_evals.py`, real `/api/evals`, separate subcause metrics, grounding/SOP hit-rate metrics and seed-only leave-one-out memory evaluation. Sanity script is only the deterministic engine diagnostic. Missing root README, `docs/manual.md`, `docs/prompts_log.md`, saved demo screenshots, presentation and scripted/rehearsed demo evidence (`progress.md:Next`, external plan §§12/14/16; inventory). Architecture diagram exists only in external plan §3, not as a repo deliverable. The optional cause-and-effect graph remains absent.

## 5. Gaps by priority

### Critical — blocks reliable completion of the core demo

1. Accepted numeric/sparse CSVs can crash later; fix the contract before claiming arbitrary-upload support (`validate_dataframe`, `_shift_ev`, `build_summary`, `analyze_signals`). Curated fixtures still work.
2. Grounding cannot substantiate the evidence-backed/action-bounded claim for live model output (`grounding.py:check_detailed`; reproduced probe below).
3. Demo's final evaluation step cannot show actual metrics in the UI because `/api/evals` is 501 (`evals.py:run_evals`, `EvaluationsPage`).
4. Entire project is untracked with no commits; README/setup instructions and portable planning/delivery documents missing (`git ls-files`, `progress.md`, external plan §14).

### Important — expected capabilities/evaluator evidence

1. Exercise live Groq and error/timeout/schema/grounding fallbacks. Integration already exists; verification and robust provider abstraction are the gap (`llm.py`).
2. Add document ingestion and lifecycle for actual machine manuals/SOPs, maintaining the existing sensor/document separation. General chunking/embeddings are absent; current small-corpus BM25 already provides retrieval without an LLM (`rag.py`).
3. Complete whole-pipeline metrics and asserted regression tests, including retrieval, grounded actions and saved-case exclusion (`evals/sanity_check.py`, plan §12).
4. Define scope for authentication, role checks and validated-case authority. Plan excludes auth, design expects it, audit asks for it; implementation currently has none (`main.py`, route modules).
5. Verify durable save/upload lifecycle and handle concurrent writes, corruption and errors (`memory.py:retain`, `data_loader.py:save_upload`).
6. Request IDs, configured logging and step timing; surface actual text source for honest model-vs-template demos (`analysis_service.py:run_analysis`, response schemas).

### Nice to have

Robot/auth animation, optional landing, dashboard/cases navigation, list filters, chart baseline/raw-events views, sidebar collapse, motion/toasts, code splitting and bonus graph (`frontend_design.md` external §§5–8, `progress.md:What was cut`, plan §2). Robot is lower priority than auth correctness and backend gaps.

## 6. Risks and bugs found

1. **Confirmed: infinity passes upload and causes 500.** `backend/services/data_loader.py:validate_dataframe`, lines 107–114, checks parseability without finiteness. Uploading the existing CSV with `defect_count=inf` returned 200. Identical validated input in TestClient returned summary/analysis 500; direct engine raised `OverflowError: cannot convert float infinity to integer`. Conversion sites include `backend/services/incidents.py:31`, `engine/signals.py:320`.
2. **Confirmed: sparse temperature passes upload and crashes scoring.** Leave only the first temperature value and blank all later values in INC-001: upload 200, summary 200, analysis 500 with `TypeError: '>' not supported between instances of 'NoneType' and 'int'`. Global nonempty signal guard in `engine/signals.py:151` does not ensure baseline/window statistics per machine. `engine/scoring.py:_shift_ev`, line 103, compares missing `delta_abs`; `_rules` evaluates this evidence even when its supporting condition is false (around line 162).
3. **Confirmed: invalid physical/count values accepted.** CSV with all defect counts −2 and downtime −4 returned upload 200 and downstream 200; no nonnegative, integral-count or plausible-range validation (`validate_dataframe`). Valid CSV content named `.txt` is accepted by the backend; client-only `.csv` filter does not enforce server policy (`UploadPage.tsx:choose`, route `upload_incident`).
4. **Confirmed: grounding false pass.** Called `engine/grounding.py:check` with input evidence “Temperature rose.” and incident ID INC-007; output said “Temperature fell to 7.” and prescribed “Replace the entire machine immediately.” citing allowed SOP-007. Result was `passed=True`, no flags. Number pool includes identifier digits (`check_detailed:58`), signal test checks existence rather than direction/machine/value context (lines 79–85), and verification checks only allowed source ID/number/phrase rules (lines 87–94), not whether an action appears in that SOP. The probe supplies an allowlisted SOP ID, so this demonstrates checker behavior rather than a claim that a live model produced it.
5. **Code-confirmed: abstention grounding is asserted rather than checked.** `backend/services/analysis_service.py:134` constructs `Grounding(passed=True, flagged=[])` directly. Complete-template responses are checked, but abstention drafts are not. A reported 18/18 `grounding.passed` field is not a separately measured grounding pass rate.
6. **Code-confirmed: unvalidated cache can fail before graceful fallback.** `engine/llm.py:load_cache/generate`, lines 56–61/98–100, returns truthy decoded JSON without `LLMOutput` validation. `analysis_service.py:153–158` assumes valid ranks/shape. Cache checked before `LLM_ENABLED`; corrupt syntax falls back, but wrong valid-JSON structure may crash. Cache key does not incorporate model/prompt version (`input_hash`). Failure not dynamically exercised.
7. **Code-confirmed: memory writes lack transaction/locking.** `engine/memory.py:retain`, lines 110–112, reads existing state, derives ID, rewrites whole file. Concurrent calls can lose updates or share IDs; interruption can corrupt JSON. `_read` silently treats JSON corruption as empty. Concurrency/actual disk failure not run in this audit.
8. **Code-confirmed: upload size/row limits absent.** `backend/api/routes/incidents.py:17` reads entire file, then pandas parses it; no application-specific cap. `save_upload` stores original bytes with an eight-hex UUID suffix and no collision check (`data_loader.py:129–132`). Resource exhaustion/collision not stress-tested.
9. **Code-confirmed: event precedence includes later events.** `engine/signals.py:61`, `precedence` lines 375–381, accepts start−5 through start+2 steps and marks `before_incident=True`; `scoring.py` then describes the event as before the window. Post-start events can count as preceding evidence; not separately reproduced.
10. **Observed/code-confirmed: synthetic memory can produce irrelevant associations.** INC-001 recalls material case INC-H06 alongside cooling cases; INC-002 recalls an in-memory cooling INC-H13. Jaccard matching ignores machine/line/cause (`memory.py:recall`). UI says contextual evidence only, and rankings are unaffected, but “Engineer-validated” labels refer to synthetic seeds (`generate_data.py:build_memory_seed`).
11. **Code-confirmed: loader/list semantics can surprise users.** Uploads are excluded from list endpoint (`data_loader.py:list_incidents`), so reopened home page does not list an uploaded investigation. Intended for eval purity, but no separate upload history/case-list route exists. Frontend draft/chart/copy state is local; not durable session storage.
12. **Code-confirmed: frontend stale-response risk.** `frontend/src/pages/IncidentPage.tsx:run` lacks the `alive`/request-ID protection used for summary loading; `SopModal.tsx` fetch effect also lacks stale-response protection. Switching incidents/SOPs before a response resolves may display old results. Race not dynamically reproduced.
13. **Observed: CORS hostname dependence.** Localhost:5173 works; 127.0.0.1:5173 preflight returns 400 (`config.py:CORS_ORIGINS`). README should specify the allowed origin. Health is unconditional liveness, not dependency readiness (`main.py:health`).
14. **Observed: incomplete reproducibility and no committed secrets/history to inspect.** No commits/tracked files; no actual secret found in source scan. Root and frontend `.env.example` values are placeholders. Unpinned Python dependencies, absent pytest, and missing runtime/setup guidance prevent a verified clean-machine claim (`requirements.txt`, `package.json`, `progress.md`). Existing runtime emitted a FastAPI TestClient/httpx deprecation warning; dependency compatibility deserves a pinned/tested environment.

## 7. Recommended build order

1. **Make the project reproducible and preserve a baseline.** Depends on current files. Add portable plan/design/README, supported Python/Node versions, environment/setup steps and a reviewed Git baseline. Verify a clean clone runs backend/frontend without local Downloads references; keep secrets/generated artifacts excluded.
2. **Harden the CSV/analysis contract.** Depends on schemas/loader. Define finite/nonnegative/integer/range rules, upload caps and per-machine usable baselines; make sparse inputs reject cleanly or abstain. Add assertions for the reproduced crashes. Verify accepted files never produce unexpected 500, rejected inputs give readable 422, and the 18 fixture regressions remain correct.
3. **Enforce grounding and verify wording providers.** Depends on stable evidence contract. Bind claims to signal, direction, machine and numeric provenance; validate actions against retrieved SOP steps; check abstention drafts and cache schema/version. Add a provider interface and exercise Groq plus no-key, timeout, invalid JSON, cache and fallback branches. Verify the false-pass probe is rejected and ranking remains deterministic.
4. **Complete evaluations.** Depends on reliable analysis/retrieval/grounding. Implement plan §12 metrics, seed-only leave-one-out memory tests, asserted results and real `/api/evals`; connect run/results UI. Verify per-case and per-metric outputs, explicit abstention denominators, SOP hits, subcause scores and grounding results against answer keys read only in eval code.
5. **Add machine-document ingestion.** Depends on document policy and retrieval interface. Separate document storage/models/endpoints from sensor CSVs, extract/chunk allowed formats, attach provenance/version metadata, and choose BM25 or embeddings only as corpus needs justify. Verify uploaded manual passages can be retrieved without an LLM and actions cite the uploaded source.
6. **Establish validated-case authority and durable memory.** Depends on an agreed auth/RBAC scope. Add users/roles and server-side permissions if required, then atomic/concurrency-safe case retention and a cases list/history. Verify anonymous/restricted users cannot validate cases, concurrent saves preserve unique records, restart retains cases, and source-incident exclusion works.
7. **Finish observability, UI and demo delivery.** Depends on stable APIs/evals. Add request IDs/timing, text-source visibility, missing core chart/list/error features, breakpoint/keyboard checks, manual/prompts log/screenshots/presentation. Verify the complete five-minute plan §16 demo and clean setup; build landing/dashboard/robot polish last.

## 8. Open questions

- Are the Downloads plan/design copies authoritative, and should authentication remain out of scope or become a requirement? They conflict on this point and confidence/claim wording.
- What real machine types, units, sampling rates, timestamp/timezone conventions, schema mappings and physical bounds must uploaded data support beyond these IMM synthetic fixtures?
- Which document formats, retention/versioning policies and upload limits are expected? Is current lexical SOP retrieval sufficient, or is embedding retrieval specifically required?
- Which live Groq model/key and evaluation environment will be available at the venue? Is there an approved alternative provider, and how should sensor notes/cases sent to a provider be governed?
- Should past cases merely provide context as implemented, or influence ranking? Who is allowed to label a case validated, and what evidence must be recorded?
- What should happen to uploaded investigations after refresh/restart, and is JSON storage intended only for a single-process demo?
- Who owns the already-running service on port 8000? It was not stopped or modified; audit requests with possible side effects used only the isolated 8001 server.
- How should evaluation generalization be tested beyond the generator's known taxonomy? No held-out real data or broader manufacturing benchmark exists in the repo.
- Disk persistence, real model behavior, concurrent requests, provider failures, full responsive/accessibility coverage and a fresh-machine install remain Unverified where this audit could not exercise them without changing files/installing dependencies.

Audit cleanup: no temporary scripts created; no installs or application-source edits. Disk `data/memory_cases.json` remained `[]`; `data/uploads` contained only `.gitkeep`. Audit-owned backend/frontend servers were stopped; the pre-existing port-8000 service was left running.
