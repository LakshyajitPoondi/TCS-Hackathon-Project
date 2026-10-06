from fastapi import APIRouter, Depends
from backend.auth import require

from backend.models.schemas import AnalysisResponse
from backend.services.analysis_service import analyze_incident
from backend.services.data_loader import load_incident

router = APIRouter(prefix="/api/incidents", tags=["analysis"])


@router.post("/{incident_id}/analyze", response_model=AnalysisResponse)
def analyze(incident_id: str, user=Depends(require("analyze"))):
    df = load_incident(incident_id)
    result=analyze_incident(incident_id, df)
    from backend import db
    with db.Session.begin() as session: db.audit(session,user.id,"analyze",{"incident_id":incident_id})
    return result
