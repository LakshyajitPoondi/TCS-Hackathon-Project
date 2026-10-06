from fastapi import APIRouter, Depends
from backend.auth import require

from backend.models.schemas import AnalysisResponse
from backend.services.analysis_service import run_analysis
from backend.services.data_loader import load_incident

router = APIRouter(prefix="/api/incidents", tags=["analysis"])


@router.post("/{incident_id}/analyze", response_model=AnalysisResponse)
def analyze(incident_id: str, user=Depends(require("analyze"))):
    df = load_incident(incident_id)
    result, meta=run_analysis(incident_id, df)
    from backend import db
    import uuid
    result.run_id=uuid.uuid4().hex
    with db.Session.begin() as session:
        session.add(db.AnalysisRun(run_id=result.run_id,incident_id=incident_id,user_id=user.id,response=result.model_dump(mode='json'),config={'text_source':result.text_source},llm_calls=meta['llm_calls']))
        db.audit(session,user.id,"analyze",{"incident_id":incident_id,'run_id':result.run_id})
    return result
