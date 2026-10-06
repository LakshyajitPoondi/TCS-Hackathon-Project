# Build progress

Branch: feature/llm-rag-rbac; baseline on main: 6c6aa2d.
Stages 0–11 run in sequence; each completed stage has tests and its own commit.
Current stage: 5, provider layer. Next unfinished stage: 5.

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

