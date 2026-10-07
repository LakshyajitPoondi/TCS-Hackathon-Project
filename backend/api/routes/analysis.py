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
    top={'category':result.hypotheses[0].category,'subcause':result.hypotheses[0].subcause,'confidence':result.hypotheses[0].confidence} if result.hypotheses else {'category':None,'status':result.analysis_status}
    from backend.services import workflow
    with db.Session.begin() as session:
        workflow.get_incident(session,incident_id)
        session.add(db.AnalysisRun(run_id=result.run_id,incident_id=incident_id,user_id=user.id,response=result.model_dump(mode='json'),config={'text_source':result.text_source,'top_hypothesis':top,'agent_mode':result.investigation.get('mode')},llm_calls=meta['llm_calls']))
        session.flush()
        session.add_all(db.AgentTrace(run_id=result.run_id,**item) for item in meta['trace'])
        db.audit(session,user.id,"analyze",{"incident_id":incident_id,'run_id':result.run_id})
    return result
