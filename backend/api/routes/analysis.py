from fastapi import APIRouter

from backend.models.schemas import AnalysisResponse
from backend.services.analysis_service import analyze_incident
from backend.services.data_loader import load_incident

router = APIRouter(prefix="/api/incidents", tags=["analysis"])


@router.post("/{incident_id}/analyze", response_model=AnalysisResponse)
def analyze(incident_id: str):
    df = load_incident(incident_id)
    return analyze_incident(incident_id, df)
