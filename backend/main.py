from fastapi import FastAPI, Request, Depends
from backend.auth import require
from backend.api.routes import auth
from backend.api.routes import registry
from backend.api.routes import runs
from backend.api.routes import llm_status
from backend.api.routes import dashboard
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import uuid
import time

from backend.api.routes import analysis, cases, evals, incidents, sops
from backend.core.config import API_NAME, API_VERSION, CORS_ORIGINS
from backend.services.data_loader import IncidentNotFoundError, IncidentValidationError

app = FastAPI(title=API_NAME, version=API_VERSION)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("rca.requests")

@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = uuid.uuid4().hex
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("request_id=%s unexpected request failure", request.state.request_id)
        response = JSONResponse(status_code=500, content={"detail": "Internal server error", "request_id": request.state.request_id})
    response.headers["X-Request-ID"] = request.state.request_id
    log.info("request_id=%s method=%s path=%s status=%s latency_ms=%.1f", request.state.request_id, request.method, request.url.path, response.status_code, (time.perf_counter()-started)*1000)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(IncidentNotFoundError)
async def _not_found(_: Request, exc: IncidentNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(IncidentValidationError)
async def _invalid(_: Request, exc: IncidentValidationError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/", dependencies=[Depends(require("view"))])
def root():
    return {"name": API_NAME, "status": "ok", "version": API_VERSION}


@app.get("/health")
def health():
    return {"status": "healthy"}


for module in (incidents, analysis, cases, evals, sops):
    app.include_router(module.router, dependencies=[Depends(require("view"))])
app.include_router(auth.router)
app.include_router(registry.router)
app.include_router(runs.router)
app.include_router(llm_status.router)
app.include_router(dashboard.router)
