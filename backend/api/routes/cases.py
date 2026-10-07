"""Experience memory cases: memory-agent draft, proposal with duplicate check, review, versioned edit, retirement.

Lifecycle: proposed -> approved | rejected; approved -> retired. Only approved cases are recalled.
Admin or qa_lead may edit an approved case (the previous version is kept) or retire it with a reason.
Every change is written to audit_log.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from backend import db
from backend.auth import require
from backend.models.schemas import SaveCaseRequest, SaveCaseResponse, Category, Subcause
from backend.services.data_loader import load_incident
from backend.services import memory_agent
from engine.memory import build_signature, embed_case, case_text
from engine.signals import analyze_signals

router = APIRouter(prefix='/api/cases', tags=['cases'])
STATUSES = ('proposed', 'approved', 'rejected', 'retired')
EDITABLE = ('summary', 'symptoms', 'evidence_summary', 'fix_applied', 'lessons', 'documents_used', 'confirmed_category', 'confirmed_subcause')


def serialize(c, names=None, docs=None):
    names = names or {}; docs = docs or {}
    out = {'case_id': c.case_id, 'status': c.status, 'source_incident_id': c.source_incident_id, 'proposer_id': c.proposer_id,
           'approver_id': c.approver_id, 'created_at': c.created_at, 'version': 1, **c.data}
    out.update(proposer_name=names.get(c.proposer_id), approver_name=names.get(c.approver_id),
               documents=[{'doc_id': d, 'title': docs.get(d, d)} for d in c.data.get('documents_used', [])],
               has_embedding=c.embedding is not None)
    return out


def serialize_many(session, cases):
    from backend.services.workflow import user_names
    cases = list(cases)
    names = user_names(session, [c.proposer_id for c in cases] + [c.approver_id for c in cases])
    ids = {d for c in cases for d in c.data.get('documents_used', [])}
    docs = {d.doc_id: d.title for d in session.scalars(select(db.Document).where(db.Document.doc_id.in_(ids)))} if ids else {}
    return [serialize(c, names, docs) for c in cases]


@router.get('')
def list_cases(status: str | None = None, machine_uid: str | None = None, category: str | None = None, user=Depends(require('view'))):
    if status and status not in STATUSES: raise HTTPException(422, 'Invalid case status')
    with db.Session() as session:
        query = select(db.Case).order_by(db.Case.created_at.desc())
        if status: query = query.where(db.Case.status == status)
        rows = [c for c in session.scalars(query) if (not machine_uid or c.data.get('machine_uid') == machine_uid)
                and (not category or c.data.get('confirmed_category') == category)]
        return serialize_many(session, rows)


class DraftRequest(BaseModel):
    incident_id: str
    run_id: str | None = None
    rca_draft: str = Field(default='', max_length=50000)


@router.post('/draft')
def draft(body: DraftRequest, user=Depends(require('propose'))):
    """Step 1 of "Propose case": a structured, editable draft (LLM within budget, template otherwise)."""
    with db.Session() as session:
        return memory_agent.draft_case(session, body.incident_id, body.rca_draft, body.run_id)


@router.post('', response_model=SaveCaseResponse, status_code=201)
@router.post('/propose', response_model=SaveCaseResponse, status_code=201, include_in_schema=False)
def propose(request: SaveCaseRequest, user=Depends(require('propose'))):
    df = load_incident(request.incident_id); ev = analyze_signals(df)
    from engine.scoring import score_hypotheses
    hs = score_hypotheses(ev)['hypotheses']; target = hs[0].get('target') if hs else None
    line = str(df['line'].iloc[0]); machines = sorted(df['machine'].unique())
    machine_uid = line + '/' + target if target in machines else None
    signals = build_signature(ev)
    summary = (request.summary or '').strip() or f'Proposed {request.confirmed_category} case from {request.incident_id}; pending QA review.'
    data = {'label': 'engineer proposal', 'line': line, 'model': 'IMM', 'machine_uid': machine_uid,
            'signals': signals, 'events': sorted(df['event_code'].dropna().unique()),
            'symptoms': request.symptoms if request.symptoms is not None else [e['description'] for h in hs for e in h['supporting_evidence']][:8],
            'evidence_summary': request.evidence_summary or '',
            'confirmed_category': request.confirmed_category, 'confirmed_subcause': request.confirmed_subcause,
            'summary': summary, 'fix_applied': request.fix_applied, 'documents_used': request.documents_used,
            'lessons': request.lessons, 'notes': request.notes, 'draft': request.rca_draft,
            'text_source': request.text_source, 'engineer_edited': True, 'version': 1}
    case_id = 'CASE-' + uuid.uuid4().hex
    with db.Session.begin() as s:
        if any(s.get(db.Document, did) is None for did in request.documents_used): raise HTTPException(422, 'Unknown document')
        duplicates = memory_agent.find_duplicates(s, request.incident_id, machine_uid, request.confirmed_category,
                                                  request.confirmed_subcause, case_text(data), signals)
        if duplicates and len((request.duplicate_reason or '').strip()) < 5:
            raise HTTPException(409, {'message': 'Possible duplicate case. Give a reason to submit anyway.', 'duplicates': duplicates})
        if duplicates:
            data['duplicate_override'] = {'reason': request.duplicate_reason.strip(), 'duplicates': duplicates}
        case = db.Case(case_id=case_id, source_incident_id=request.incident_id, status='proposed', proposer_id=user.id, data=data)
        embed_case(case)
        s.add(case)
        db.audit(s, user.id, 'propose_case', {'case_id': case_id, 'incident_id': request.incident_id, 'text_source': request.text_source,
                                              'duplicate_override': bool(duplicates)})
    return SaveCaseResponse(status='proposed', case_id=case_id)


@router.post('/{case_id}/approve')
def approve(case_id: str, user=Depends(require('approve'))): return decide(case_id, 'approved', user)


@router.post('/{case_id}/reject')
def reject(case_id: str, user=Depends(require('approve'))): return decide(case_id, 'rejected', user)


def decide(case_id, status, user):
    with db.Session.begin() as s:
        c = s.get(db.Case, case_id)
        if not c: raise HTTPException(404, 'Case not found')
        if c.status != 'proposed': raise HTTPException(409, 'Only proposed cases can be reviewed')
        from backend.services.workflow import display_name
        c.status = status; c.approver_id = user.id
        when = datetime.now(timezone.utc)
        name = display_name(user); cause = c.data.get('confirmed_category', '') + ('/' + c.data['confirmed_subcause'] if c.data.get('confirmed_subcause') else '')
        # B6: the summary records the decision, reviewer and date (no stale "awaiting approval").
        verb = 'Approved' if status == 'approved' else 'Rejected'
        summary = c.data.get('summary', '').replace('; pending QA review.', '.').replace('; awaiting QA approval.', '.')
        c.data = {**c.data, 'label': 'QA-approved' if status == 'approved' else 'rejected proposal', 'reviewed_by': user.id,
                  'reviewed_by_name': name, 'reviewed_at': when.isoformat(),
                  'summary': f'{summary} {verb} by {name} on {when:%Y-%m-%d} ({cause}).'.strip()}
        embed_case(c)
        db.audit(s, user.id, status + '_case', {'case_id': case_id})
        return serialize_many(s, [c])[0]


class CaseEdit(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)
    summary: str | None = Field(default=None, max_length=4000)
    symptoms: list[str] | None = Field(default=None, max_length=20)
    evidence_summary: str | None = Field(default=None, max_length=4000)
    fix_applied: str | None = Field(default=None, min_length=3, max_length=4000)
    lessons: str | None = Field(default=None, max_length=4000)
    documents_used: list[str] | None = None
    confirmed_category: Category | None = None
    confirmed_subcause: Subcause = None


def _snapshot(s, c, change, reason, user):
    version = c.data.get('version', 1)
    s.add(db.CaseVersion(case_id=c.case_id, version=version, status=c.status, data=c.data, change=change, reason=reason, editor_id=user.id))
    return version


@router.patch('/{case_id}')
def edit(case_id: str, body: CaseEdit, user=Depends(require('approve'))):
    """Edit an approved case; the previous version is kept in case_versions."""
    with db.Session.begin() as s:
        c = s.get(db.Case, case_id)
        if not c: raise HTTPException(404, 'Case not found')
        if c.status != 'approved': raise HTTPException(409, 'Only approved cases can be edited')
        changes = body.model_dump(exclude_unset=True, exclude={'reason'})
        if not changes: raise HTTPException(422, 'Nothing to change')
        category = changes.get('confirmed_category', c.data.get('confirmed_category'))
        subcause = changes['confirmed_subcause'] if 'confirmed_subcause' in changes else c.data.get('confirmed_subcause')
        if (category == 'machine') != (subcause in ('cooling', 'mechanical')) or (category != 'machine' and subcause is not None):
            raise HTTPException(422, "confirmed_subcause must be 'cooling' or 'mechanical' only for machine cases")
        if any(s.get(db.Document, d) is None for d in changes.get('documents_used', [])): raise HTTPException(422, 'Unknown document')
        version = _snapshot(s, c, 'edit', body.reason.strip(), user)
        from backend.services.workflow import display_name
        c.data = {**c.data, **changes, 'version': version + 1, 'last_edited_by_name': display_name(user),
                  'last_edited_at': datetime.now(timezone.utc).isoformat()}
        embed_case(c)
        db.audit(s, user.id, 'edit_case', {'case_id': case_id, 'version': version + 1, 'fields': sorted(changes), 'reason': body.reason.strip()})
        return serialize_many(s, [c])[0]


class Retire(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


@router.post('/{case_id}/retire')
def retire(case_id: str, body: Retire, user=Depends(require('approve'))):
    """Retired cases are kept for audit but never recalled."""
    with db.Session.begin() as s:
        c = s.get(db.Case, case_id)
        if not c: raise HTTPException(404, 'Case not found')
        if c.status != 'approved': raise HTTPException(409, 'Only approved cases can be retired')
        version = _snapshot(s, c, 'retire', body.reason.strip(), user)
        from backend.services.workflow import display_name
        c.status = 'retired'
        c.data = {**c.data, 'version': version + 1, 'label': 'retired', 'retired_reason': body.reason.strip(),
                  'retired_by_name': display_name(user), 'retired_at': datetime.now(timezone.utc).isoformat()}
        db.audit(s, user.id, 'retire_case', {'case_id': case_id, 'reason': body.reason.strip()})
        return serialize_many(s, [c])[0]


@router.get('/{case_id}/history')
def history(case_id: str, user=Depends(require('view'))):
    """Previous versions plus every audited action on this case, oldest first."""
    from backend.services.workflow import user_names
    with db.Session() as s:
        if not s.get(db.Case, case_id): raise HTTPException(404, 'Case not found')
        versions = list(s.scalars(select(db.CaseVersion).where(db.CaseVersion.case_id == case_id).order_by(db.CaseVersion.id)))
        events = [a for a in s.scalars(select(db.AuditLog).where(db.AuditLog.action.like('%case')).order_by(db.AuditLog.id))
                  if (a.data or {}).get('case_id') == case_id]
        names = user_names(s, [v.editor_id for v in versions] + [a.user_id for a in events])
        return {'versions': [{'version': v.version, 'status': v.status, 'change': v.change, 'reason': v.reason, 'data': v.data,
                              'editor_name': names.get(v.editor_id), 'created_at': v.created_at} for v in versions],
                'events': [{'action': a.action, 'user_name': names.get(a.user_id), 'created_at': a.created_at, 'data': a.data} for a in events]}


@router.get('/{case_id}')
def get_case(case_id: str, user=Depends(require('view'))):
    with db.Session() as s:
        c = s.get(db.Case, case_id)
        if not c: raise HTTPException(404, 'Case not found')
        return serialize_many(s, [c])[0]
