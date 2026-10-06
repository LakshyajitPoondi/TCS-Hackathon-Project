# Project Progress

## Current Phase
**Phase 4/5 complete:** React frontend over the frozen Phase 1–3 backend. `plan.md` is at `~/Downloads/plan.md`; the design doc is at `~/Downloads/frontend_design.md` (read §1–6, 9, 10).

**Backend pipeline (frozen):** signals → scoring (MIN_SCORE=5) → BM25 SOPs → memory recall → wording (cache → Groq → template) → grounding → `AnalysisResponse`.
**Regression (`python -m evals.sanity_check`):** top1 16/16 · top3 16/16 · abstentions 2/2 · wrong abstentions 0/16 · ambiguous 3/3.

## How to run
- Backend: `uvicorn backend.main:app --reload` (port 8000). `.env` holds `GROQ_API_KEY` (plus GROQ_MODEL, LLM_ENABLED, MEMORY_BACKEND).
- Frontend: `cd frontend && npm install && npm run dev` (port 5173, which matches the CORS origin). `frontend/.env` holds `VITE_API_BASE_URL` (falls back to `http://localhost:8000`); see `frontend/.env.example`.

## Frontend stack and routes
- **Stack:** React 19, Vite 8, TypeScript 7, Tailwind v4 (`@tailwindcss/vite`, tokens in `@theme` in `src/styles/globals.css`), react-router-dom 7, Recharts 3, lucide-react. CSS transitions only (no framer-motion).
- **Routes:**
  - `/` incidents
  - `/incidents/:id`
  - `/upload`
  - `/evaluations`
  - `*` not found
- **Endpoints consumed** (`src/api/endpoints.ts`):
  - `GET /health`
  - `GET /api/incidents`, `GET /api/incidents/{id}`, `GET /api/incidents/{id}/signals`
  - `POST /api/incidents/upload`, `POST /api/incidents/{id}/analyze`
  - `POST /api/cases`
  - `GET /api/sops/{id}`
  - `GET /api/evals`
- **Errors:** `api/client.ts` turns `{"detail"}` (string or a 422 list) into one readable line. Status 0 means the network is down; 5xx shows a generic message. Raw JSON is never shown.

## New backend endpoint (the only backend change)
- `GET /api/sops/{sop_id}` returns `{id, title, content}`. It lives in `backend/api/routes/sops.py` and is registered in `main.py`.
- It looks the id up in `engine.rag.SOP_INDEX` only; the input never becomes a file path, so path traversal is impossible. Unknown ids return 404.

## Major components (`frontend/src/components`)
- `layout/AppShell`: top bar, sticky banner, sidebar (a drawer below 1024px), skip link.
- `layout/TopBar`: real `/health` badge ("Engine online" or "Backend unavailable"), polled every 30 s.
- `layout/ValidationBanner`: sticky warning on every page. Holds the API `warning` once an analysis returns; until then, an identical constant.
- `ui/*`: Button (pill + trailing arrow), Card/SectionTitle, Badge/Chip/ConfidenceBadge (bars + text, no %)/HealthBadge (dot + text), Alert, EmptyState (small aura), Modal (focus trap, Esc, restores focus), Spinner/Skeleton.
- `analysis/SummaryCards`: SummaryCards, KpiCards (window KPIs), HealthCards (score / 100, bar, status label, helper text).
- `analysis/HypothesisCard`: accordion; #1 is expanded with a 2px indigo border. Shows narrative, ✓/✗ evidence lists, missing-checks checklist, verification actions and SopChip.
- `analysis/SopModal`: fetches the SOP and renders its markdown (headings, numbered steps, bold).
- `analysis/StatusPanels`: AnalysisComplete (window + detected_by), InsufficientEvidence (replaces the hypothesis area), GroundingNote (expandable flagged list).
- `analysis/CategoryEvidenceGrid`: always 6 tiles in API order. Tiles with no support are greyed out. Expandable evidence.
- `analysis/SimilarCases`: rows with a permanent helper and an empty state.
- `analysis/RcaDraft`: editable textarea. Edits reset only on a new analysis. Copy, Revert edits, warning below.
- `analysis/SaveCaseModal`: required category (no preselect); subcause only for machine (null otherwise); notes; success shows the case_id; 422 detail shown.
- `charts/SignalChart`: signal selector (temperature, speed, vibration, motor current, defects); one line per machine; dashed horizontal grid. After analysis it adds the incident-window band and dashed markers at CHG/SHIFT_CHG/ALM_* (code in the tooltip).

## Design notes
- **Theme:** light only (`color-scheme: light` meta + CSS; no `dark:`). Tokens are from frontend_design.md, plus darker `*-ink` text shades for success, warning and danger to reach 4.5:1. No raw hex in components.
- **Fonts:** Plus Jakarta Sans for the UI, JetBrains Mono for IDs, codes, timestamps and numbers.
- **Terminology:** "Hypothesis #N", "Leading hypothesis", "Verification required/actions". `hypothesis.score` is never rendered; confidence is a High/Medium/Low badge.
- **Chart colours:** the doc's series colours (indigo/cyan/violet) fail the dataviz lightness band check, and cyan has 1.68:1 contrast. Kept as the doc mandates, with relief from the machine legend and tooltip values.

## Build: **PASS** (`npm run build`: tsc + vite, 0 TS errors; only a >500 kB chunk-size warning)

## Verified via API (script, backend + CORS from localhost:5173)
- CORS GET + preflight OK.
- `/api/sops/SOP-007` → 200; `/api/sops/..%2Fx` → 404; `SOP-999` → 404.
- INC-001 → machine/cooling (high), SOP-007 + SOP-002.
- INC-002 (mechanical) → SOP-004.
- INC-006 (measurement) → SOP-015.
- INC-008 → `insufficient_evidence`, `hypotheses: []`.
- Valid upload → `UPL-664ae6e9`, and it analyzes (machine/mechanical). Invalid upload → 422 "Missing required columns: …".
- Save Case → `INC-H13`; bad subcause → 422 (the client strips the "Value error," prefix).
- `/api/evals` → 501, which shows the empty state.
- Cleanup done: `memory_cases.json` = `[]`; test upload deleted.
- Grep of `frontend/src`: no "root cause" outside the exact warning, no "diagnos", no "AI detected", no hypothesis `.score`, no % next to confidence. The only `.score` hits are machine-health scores, which the brief requires.

## Manual demo checklist (API-verified ✅. I did not click through the UI in a browser, so please confirm each step)
1. ✅ Open INC-001 → Run RCA Analysis → window chips, KPIs, IMM-02 "Degraded" health, chart with the window band and ALM_TEMP_HI markers.
2. ✅ Hypothesis #1 Machine · Cooling (expanded) → supporting evidence, missing checks, 4 verification actions.
3. ✅ Click `SOP-007 · Cooling System Troubleshooting` → the modal opens with the steps; Esc closes it.
4. ✅ Similar Past Cases → INC-H02 / INC-H01 / INC-H06 with shared-signal chips.
5. ✅ Edit the draft → Save as Validated Case → pick Machine + Cooling → "Case saved … · INC-H13". **Reset `data/memory_cases.json` to `[]` after rehearsal.**
6. ✅ Open INC-008 → Run → "Insufficient evidence" panel; no hypothesis cards; the other sections still render.
7. ✅ Evaluations → "Evaluation dashboard coming in Phase 5" (filled in Phase 5).

## What was cut
- Landing page, auth page and robot mascot. **Interactive auth robot and landing page deferred as non-core visual enhancements.**
- Dashboard, cases list, framer-motion, scroll reveals.
- Collapsed 80px sidebar, toasts (inline alerts used instead), code-splitting.

## Known limitations
- Groq has not been exercised with a real key (Phase 3); live runs use template wording. To enable it, add the key and analyze INC-001..007 once to warm the cache.
- Hindsight memory adapter deferred (`MEMORY_BACKEND=local`). Evals pending (501).
- Grounding is regex-based. Memory tags are a hand mapping. `downtime_up` fires on any window downtime.
- Sticky sidebar offset assumes a ~100px header (`--header-h` in AppShell). The banner wraps on narrow screens, which is fine because the sidebar is a drawer there.
- The UI was build-checked and API-checked only; there was no automated browser test.

## Next: Phase 5
1. `evals/run_evals.py` (extend `sanity_check.py`). Plan §12 metrics:
   - top-3 category
   - sub-cause top-1 and top-3
   - grounding pass rate
   - SOP hit rate
   - memory recall (leave-one-out, seed only)
   - abstention
2. Implement the real `GET /api/evals`. `EvaluationsPage` already renders `{metrics, cases}` generically (metrics may be a list or a dict). Add a run button if needed.
3. `docs/manual.md` (1 page) and `docs/prompts_log.md`.
4. Screenshots: INC-001, INC-008, an ambiguous case.
5. README run instructions.
6. Rehearse the demo.
