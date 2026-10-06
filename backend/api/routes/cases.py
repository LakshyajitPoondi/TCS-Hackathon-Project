import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from backend import db
from backend.auth import require
from backend.models.schemas import SaveCaseRequest, SaveCaseResponse
from backend.services.data_loader import load_incident
from engine.memory import build_signature
from engine.signals import analyze_signals

router=APIRouter(prefix='/api/cases',tags=['cases'])
def serialize(c):return {'case_id':c.case_id,'status':c.status,'source_incident_id':c.source_incident_id,'proposer_id':c.proposer_id,'approver_id':c.approver_id,'created_at':c.created_at,**c.data}
@router.get('')
def list_cases(status: str | None=None,user=Depends(require('view'))):
    if status and status not in ('proposed','approved','rejected'):raise HTTPException(422,'Invalid case status')
    with db.Session() as session:
        query=select(db.Case).order_by(db.Case.created_at.desc())
        if status:query=query.where(db.Case.status==status)
        return [serialize(c) for c in session.scalars(query)]
@router.post('',response_model=SaveCaseResponse,status_code=201)
@router.post('/propose',response_model=SaveCaseResponse,status_code=201)
def propose(request:SaveCaseRequest,user=Depends(require('propose'))):
    df=load_incident(request.incident_id);ev=analyze_signals(df)
    from engine.scoring import score_hypotheses
    hs=score_hypotheses(ev)['hypotheses'];target=hs[0].get('target') if hs else None
    line=str(df['line'].iloc[0]);machines=sorted(df['machine'].unique())
    data={'label':'engineer proposal','line':line,'model':'IMM','machine_uid':line+'/'+target if target in machines else None,
          'signals':build_signature(ev),'events':sorted(df['event_code'].dropna().unique()),
          'symptoms':[e['description'] for h in hs for e in h['supporting_evidence']][:8],
          'confirmed_category':request.confirmed_category,'confirmed_subcause':request.confirmed_subcause,
          'summary':f'Proposed {request.confirmed_category} case from {request.incident_id}; awaiting QA approval.',
          'fix_applied':request.fix_applied,'documents_used':request.documents_used,'lessons':request.lessons,
          'notes':request.notes,'draft':request.rca_draft,'text_source':'template'}
    case_id='CASE-'+uuid.uuid4().hex
    with db.Session.begin() as s:
        if any(s.get(db.Document,did) is None for did in request.documents_used):raise HTTPException(422,'Unknown document')
        s.add(db.Case(case_id=case_id,source_incident_id=request.incident_id,status='proposed',proposer_id=user.id,data=data))
        db.audit(s,user.id,'propose_case',{'case_id':case_id})
    return SaveCaseResponse(status='proposed',case_id=case_id)
@router.post('/{case_id}/approve')
def approve(case_id:str,user=Depends(require('approve'))):return decide(case_id,'approved',user)
@router.post('/{case_id}/reject')
def reject(case_id:str,user=Depends(require('approve'))):return decide(case_id,'rejected',user)
def decide(case_id,status,user):
    with db.Session.begin() as s:
        c=s.get(db.Case,case_id)
        if not c:raise HTTPException(404,'Case not found')
        if c.status!='proposed':raise HTTPException(409,'Only proposed cases can be reviewed')
        c.status=status;c.approver_id=user.id
        c.data={**c.data,'label':'QA-approved' if status=='approved' else 'rejected proposal'}
        db.audit(s,user.id,status+'_case',{'case_id':case_id})
        return serialize(c)
