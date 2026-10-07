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


@router.get('/config/causes')
def causes(user=Depends(require('view'))):
    """Display names, candidates, weights and thresholds from config/cause_categories.yaml."""
    from engine.cause_config import CONFIG
    return {'categories': CONFIG.category_names(),
            'candidates': [c.model_dump(include={'key', 'category', 'subcause', 'display_name'}) for c in CONFIG.candidates],
            'weights': CONFIG.weights.model_dump(), 'thresholds': CONFIG.thresholds.model_dump()}
