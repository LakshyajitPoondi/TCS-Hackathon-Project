# Build report — v2 (branch feature/v2)

Status: **draft written in stage 7; completed in stage 9 (final verification).** See progress.md for the
per-stage log, every decision and the live-LLM counter.

## Stages done so far
- 0 Housekeeping: B1 key resolution, B16 test, B17 temp eval fixtures, tsbuildinfo removed.
- 1 Postgres 18 + pgvector 0.8.7 (Docker, port 5433), Alembic, SQL-first hybrid retrieval (FTS + vector + RRF), SQLite data copy.
- 2 Quota-safe Gemini (no 429 retries, ≤ 2 × 503), daily + per-analysis budgets, single-call agent plan, DB cache, UI usage chip.
- 3 Incident registry + derived status, versioned drafts with Markdown/PDF export, dashboard, links, names, B5/B6/B11/B12/B18.
- 4 Memory agent (LLM/template draft, engineer edits), duplicate checks (B7), case embeddings in recall, B15, edit/retire lifecycle.
- 5 Cause categories + rule weights in validated YAML; cause-and-effect graph (React Flow).
- 6 Login page (sign-in/up, demo profiles, eye toggle, status badges) and the animated RcaRobot (31/31 headless checks).
- 7 Route code-splitting (main bundle 760 kB → 276 kB), admin audit-log viewer, README, .env.example.
