from fastapi import APIRouter, Depends
from backend import db
from backend.auth import require
from backend.services import workflow

router = APIRouter(prefix='/api', tags=['dashboard'])


@router.get('/dashboard')
def dashboard(user=Depends(require('view'))):
    """KPI cards, recent incidents and pending items for the signed-in role."""
    with db.Session.begin() as session:
        return workflow.dashboard(session, user)


@router.get('/nav/counts')
def nav_counts(user=Depends(require('view'))):
    with db.Session() as session:
        return workflow.nav_counts(session)
