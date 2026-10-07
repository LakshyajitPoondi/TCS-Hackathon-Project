from fastapi import APIRouter,Depends
from sqlalchemy import select
from backend import db
from backend.auth import require
from evals.run_evals import compute,persist
router=APIRouter(prefix='/api/evals',tags=['evals'])
@router.get('')
def latest(user=Depends(require('view'))):
    with db.Session() as s:
        r=s.scalar(select(db.EvalRun).order_by(db.EvalRun.created_at.desc()))
        return {'run_id':r.run_id,'created_at':r.created_at,**r.result} if r else {'run_id':None,'suites':[]}
@router.post('/run')
def run(user=Depends(require('evals'))):return persist(compute(),user.id)
