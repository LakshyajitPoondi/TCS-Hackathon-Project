from fastapi import APIRouter, Depends
from backend.auth import require
from engine import llm

router = APIRouter(prefix='/api/llm', tags=['llm'])


@router.get('/status')
def status(user=Depends(require('view'))):
    """Provider, model, agent mode, calls today / daily budget and any quota block. Never returns the key."""
    return llm.status()
