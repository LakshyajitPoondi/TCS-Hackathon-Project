# Production Intelligence & RCA

Evidence-backed manufacturing hypotheses, machine documents and reviewed experience memory. Shipped fixtures are synthetic. Engineering validation is required before corrective action.

Tested: Python 3.13, Node 24. Vite needs Node 20.19+ or 22.12+. PowerShell setup:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm ci
cd ..
```

Set environment variables in your shell or an independently created .env. This build never writes secrets. See .env.example. JWT_SECRET, SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD are required to initialize authentication; DEMO_USERS_ENABLED=true and DEMO_PASSWORD enable demo accounts. Model keys are optional.

```powershell
.\.venv\Scripts\python.exe -m backend.init_db
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
# Another terminal:
cd frontend
npm run dev
```

Use http://localhost:5173 (127.0.0.1:5173 is also allowed). Set VITE_API_BASE_URL if the backend port changes.

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m evals.run_evals
.\.venv\Scripts\python.exe -m evals.live_llm_check
cd frontend
npm run build
```

Implementation, decisions and resumable status are in progress.md. The final build_report.md separates verified no-key/fake paths from live checks. audit_report.md is historical.
