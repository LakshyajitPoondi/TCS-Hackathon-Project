from fastapi import APIRouter, File, UploadFile

from backend.models.schemas import IncidentRef, IncidentSummary, SignalsResponse
from backend.services import data_loader
from backend.services.incidents import build_signals, build_summary

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentRef])
def list_incidents():
    return data_loader.list_incidents()


@router.post("/upload", response_model=IncidentRef)
async def upload_incident(file: UploadFile = File(...)):
    from backend.core.config import UPLOAD_MAX_MB
    return data_loader.save_upload(await file.read(int(UPLOAD_MAX_MB * 1024 * 1024) + 1), file.filename or "")


@router.get("/{incident_id}", response_model=IncidentSummary)
def get_incident(incident_id: str):
    return build_summary(incident_id, data_loader.load_incident(incident_id))


@router.get("/{incident_id}/signals", response_model=SignalsResponse)
def get_signals(incident_id: str):
    return build_signals(incident_id, data_loader.load_incident(incident_id))
