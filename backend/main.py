from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import analysis, cases, evals, incidents, sops
from backend.core.config import API_NAME, API_VERSION, CORS_ORIGINS
from backend.services.data_loader import IncidentNotFoundError, IncidentValidationError

app = FastAPI(title=API_NAME, version=API_VERSION)

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


@app.get("/")
def root():
    return {"name": API_NAME, "status": "ok", "version": API_VERSION}


@app.get("/health")
def health():
    return {"status": "healthy"}


for module in (incidents, analysis, cases, evals, sops):
    app.include_router(module.router)
