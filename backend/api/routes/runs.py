from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from backend import db
from backend.auth import require
router=APIRouter(prefix='/api/analyses',tags=['analysis history'],dependencies=[Depends(require('view'))])
@router.get('')
def list_runs(incident_id:str | None=None):
    with db.Session() as s:
        query=select(db.AnalysisRun).order_by(db.AnalysisRun.created_at.desc()).limit(100)
        if incident_id:query=query.where(db.AnalysisRun.incident_id==incident_id)
        return [{'run_id':r.run_id,'incident_id':r.incident_id,'created_at':r.created_at,'text_source':r.response['text_source']} for r in s.scalars(query)]
@router.get('/{run_id}/trace')
def trace(run_id:str):
    with db.Session() as s:
        if not s.get(db.AnalysisRun,run_id):raise HTTPException(404,'Analysis not found')
        return [{k:getattr(t,k) for k in ('step','tool','args','result_summary','latency_ms','tokens')} for t in s.scalars(select(db.AgentTrace).where(db.AgentTrace.run_id==run_id).order_by(db.AgentTrace.step))]
@router.get('/{run_id}')
def result(run_id:str):
    with db.Session() as s:
        r=s.get(db.AnalysisRun,run_id)
        if not r:raise HTTPException(404,'Analysis not found')
        return r.response
