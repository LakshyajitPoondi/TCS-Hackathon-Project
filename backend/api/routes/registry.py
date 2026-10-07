import json
from sqlalchemy import select,func
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Form
from pydantic import BaseModel,Field
from backend import db
from backend.auth import require
from backend.services import documents,machines
from backend.services.data_loader import list_incidents,load_incident

router=APIRouter(prefix='/api',tags=['machines and documents'])
class MachineBody(BaseModel):
    machine_uid:str
    short_name:str
    line:str
    model:str=Field(min_length=1,max_length=100)
    display_name:str=''
    type:str=''
    manufacturer:str=''
    serial_number:str|None=None
    install_date:str|None=None
    status:str='running'
    normal_ranges:dict=Field(default_factory=dict)

def validate_machine(body):
    if body.line not in ('LINE-A','LINE-B','LINE-C') or body.short_name not in ('IMM-01','IMM-02','IMM-03') or body.machine_uid!=body.line+'/'+body.short_name:raise HTTPException(422,'Use existing line and short machine names')
    if body.status not in ('running','idle','fault','maintenance'):raise HTTPException(422,'Invalid machine status')
    if body.install_date:
        from datetime import date
        try:date.fromisoformat(body.install_date)
        except ValueError:raise HTTPException(422,'Invalid install date')
    from backend.core.config import PHYSICAL_RANGES
    for signal,r in body.normal_ranges.items():
        if signal not in PHYSICAL_RANGES or not all(isinstance(r.get(k),(int,float)) for k in ('min','max','normal')) or not PHYSICAL_RANGES[signal][0]<=r['min']<=r['normal']<=r['max']<=PHYSICAL_RANGES[signal][1]:raise HTTPException(422,'Invalid normal ranges')

@router.get('/machines')
def list_machines(user=Depends(require('view'))):
    with db.Session() as s:
        return [{**machines.serialize(m),'doc_count':s.scalar(select(func.count()).select_from(db.DocumentMachineLink).where(db.DocumentMachineLink.machine_uid==m.machine_uid))} for m in s.scalars(select(db.Machine).order_by(db.Machine.machine_uid))]

@router.post('/machines',status_code=201)
def create_machine(body:MachineBody,user=Depends(require('machines'))):
    validate_machine(body)
    with db.Session.begin() as s:
        if s.get(db.Machine,body.machine_uid):raise HTTPException(409,'Machine already exists')
        m=db.Machine(machine_uid=body.machine_uid,short_name=body.short_name,line=body.line,model=body.model,data=body.model_dump(exclude={'machine_uid','short_name','line','model'}));s.add(m)
        db.audit(s,user.id,'create_machine',body.model_dump());return machines.serialize(m)

@router.get('/machines/{machine_uid:path}/documents')
def linked(machine_uid:str,user=Depends(require('view'))):
    with db.Session() as s:
        if not s.get(db.Machine,machine_uid):raise HTTPException(404,'Machine not found')
        return [documents.serialize(d) for d in s.scalars(select(db.Document).join(db.DocumentMachineLink).where(db.DocumentMachineLink.machine_uid==machine_uid))]

@router.get('/machines/{machine_uid:path}/incidents')
def related(machine_uid:str,user=Depends(require('view'))):
    with db.Session() as s:
        m=s.get(db.Machine,machine_uid)
        if not m:raise HTTPException(404,'Machine not found')
        return [r for r in list_incidents() if (lambda f:m.line in f.line.values and m.short_name in f.machine.values)(load_incident(r['id']))]

@router.get('/machines/{machine_uid:path}')
def get_machine(machine_uid:str,user=Depends(require('view'))):
    with db.Session() as s:
        m=s.get(db.Machine,machine_uid)
        if not m:raise HTTPException(404,'Machine not found')
        return machines.serialize(m)

@router.patch('/machines/{machine_uid:path}')
def edit_machine(machine_uid:str,body:MachineBody,user=Depends(require('machines'))):
    validate_machine(body)
    if body.machine_uid!=machine_uid:raise HTTPException(422,'Machine identity cannot change')
    with db.Session.begin() as s:
        m=s.get(db.Machine,machine_uid)
        if not m:raise HTTPException(404,'Machine not found')
        m.model=body.model;m.data=body.model_dump(exclude={'machine_uid','short_name','line','model'})
        for doc in s.scalars(select(db.Document)):documents.put_links(s,doc,list(s.scalars(select(db.Machine))))
        db.audit(s,user.id,'edit_machine',body.model_dump());return machines.serialize(m)

@router.get('/documents')
def list_docs(machine_uid:str|None=None,doc_type:str|None=None,status:str|None=None,user=Depends(require('view'))):
    with db.Session() as s:
        query=select(db.Document)
        if machine_uid:query=query.join(db.DocumentMachineLink).where(db.DocumentMachineLink.machine_uid==machine_uid)
        if doc_type:query=query.where(db.Document.doc_type==doc_type)
        if status:query=query.where(db.Document.status==status)
        return [documents.serialize(d) for d in s.scalars(query)]

@router.post('/documents/upload',status_code=201)
async def upload_doc(file:UploadFile=File(...),title:str=Form(...),doc_type:str=Form(...),scope:str=Form(...),targets:str=Form('[]'),version:str=Form('1'),user=Depends(require('documents'))):
    from backend.core.config import DOC_UPLOAD_MAX_MB
    try:
        target_list=json.loads(targets)
        if not isinstance(target_list,list) or not all(isinstance(t,str) for t in target_list):raise ValueError()
    except (ValueError,TypeError):raise HTTPException(422,'targets must be a JSON string list')
    content=await file.read(int(DOC_UPLOAD_MAX_MB*1024*1024)+1)
    with db.Session.begin() as s:
        doc=documents.ingest(s,file.filename or '',content,title,doc_type,version,scope,target_list,user.id)
        db.audit(s,user.id,'upload_document',{'doc_id':doc.doc_id});return documents.serialize(doc)

@router.get('/documents/{doc_id}')
def get_doc(doc_id:str,user=Depends(require('view'))):
    with db.Session() as s:
        d=s.get(db.Document,doc_id)
        if not d:raise HTTPException(404,'Document not found')
        return {**documents.serialize(d),'chunks':[{'chunk_id':c.chunk_id,'page_or_section':c.page_or_section,'text':c.text,'version':c.version} for c in s.scalars(select(db.DocumentChunk).where(db.DocumentChunk.doc_id==doc_id))]}

class Mapping(BaseModel):
    title:str|None=Field(default=None,min_length=1,max_length=300)
    doc_type:str|None=None
    scope:str
    targets:list[str]=Field(default_factory=list)
    status:str|None=None

@router.post('/documents/{doc_id}/confirm')
def confirm_doc(doc_id:str,body:Mapping,user=Depends(require('documents'))):
    with db.Session.begin() as s:
        d=s.get(db.Document,doc_id)
        if not d:raise HTTPException(404,'Document not found')
        ms=list(s.scalars(select(db.Machine)));documents.validate_mapping(body.scope,body.targets,ms)
        d.scope=body.scope;d.targets=body.targets;d.status='active'
        d.detection={**d.detection,'confirmed_by':user.id}
        documents.put_links(s,d,ms);db.audit(s,user.id,'confirm_document',{'doc_id':doc_id,'scope':body.scope,'targets':body.targets});return documents.serialize(d)

@router.patch('/documents/{doc_id}')
def edit_doc(doc_id:str,body:Mapping,user=Depends(require('documents'))):
    if body.status not in (None,'archived','pending_mapping'):raise HTTPException(422,'Use confirmation endpoint to activate')
    with db.Session.begin() as s:
        d=s.get(db.Document,doc_id)
        if not d:raise HTTPException(404,'Document not found')
        ms=list(s.scalars(select(db.Machine)));documents.validate_mapping(body.scope,body.targets,ms)
        d.scope=body.scope;d.targets=body.targets;d.status=body.status or 'pending_mapping'
        if body.title is not None:
            if not body.title.strip():raise HTTPException(422,'Title must not be blank')
            d.title=body.title.strip()
        if body.doc_type is not None:
            if body.doc_type not in documents.DOC_TYPES:raise HTTPException(422,'Invalid doc_type')
            d.doc_type=body.doc_type
        documents.put_links(s,d,ms);db.audit(s,user.id,'edit_document',{'doc_id':doc_id});return documents.serialize(d)
